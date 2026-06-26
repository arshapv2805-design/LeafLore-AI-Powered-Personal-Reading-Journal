// sw.js — LeafLore Service Worker
// Handles caching, offline fallback, and background sync for queued reading logs.

const CACHE_NAME = 'leaflore-cache-v2';
const OFFLINE_URL = '/offline.html';

const PRECACHE_ASSETS = [
  '/offline.html',
  '/static/css/style.css',
  '/static/css/garden.css',
  '/static/css/bootstrap-icons.min.css',
  '/static/css/fonts/bootstrap-icons.woff2',
  '/static/css/fonts/bootstrap-icons.woff',
  '/static/js/theme.js',
  '/static/js/particles.js',
  '/static/js/calendar.js',
  '/static/js/charts.js',
  '/static/js/garden_canvas.js',
  '/static/js/offline_sync.js',
  '/static/js/recommendations.js',
  '/static/manifest.json',
];

// ─── Install: pre-cache static shell ──────────────────────────────────────────
self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

// ─── Activate: clean old caches ────────────────────────────────────────────────
self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; })
          .map(function (k) { return caches.delete(k); })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

// ─── Fetch: cache-first for static, network-first for HTML/API ────────────────
self.addEventListener('fetch', function (event) {
  var req = event.request;

  // Only handle GET + same-origin requests in fetch handler
  if (req.method !== 'GET') return;
  if (!req.url.startsWith(self.location.origin)) return;

  var url = new URL(req.url);

  // Static assets: cache-first, update in background
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then(function (cached) {
        var fetchPromise = fetch(req).then(function (resp) {
          if (resp && resp.status === 200) {
            var clone = resp.clone();
            caches.open(CACHE_NAME).then(function (c) { c.put(req, clone); });
          }
          return resp;
        });
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Navigation requests: network-first, offline fallback
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(function () {
        return caches.match(OFFLINE_URL);
      })
    );
    return;
  }
});

// ─── Background Sync: replay offline queue ─────────────────────────────────────
self.addEventListener('sync', function (event) {
  if (event.tag === 'leaflore-sync') {
    event.waitUntil(replayOfflineQueue());
  }
});

function openDB() {
  return new Promise(function (resolve, reject) {
    var req = indexedDB.open('leaflore-offline-db', 1);
    req.onupgradeneeded = function (e) {
      var db = e.target.result;
      if (!db.objectStoreNames.contains('offline-queue')) {
        db.createObjectStore('offline-queue', { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = function (e) { resolve(e.target.result); };
    req.onerror = function (e) { reject(e.target.error); };
  });
}

function getAllQueued(db) {
  return new Promise(function (resolve, reject) {
    var tx = db.transaction('offline-queue', 'readonly');
    var store = tx.objectStore('offline-queue');
    var req = store.getAll();
    req.onsuccess = function () { resolve(req.result); };
    req.onerror = function (e) { reject(e.target.error); };
  });
}

function deleteQueued(db, id) {
  return new Promise(function (resolve, reject) {
    var tx = db.transaction('offline-queue', 'readwrite');
    var store = tx.objectStore('offline-queue');
    var req = store.delete(id);
    req.onsuccess = function () { resolve(); };
    req.onerror = function (e) { reject(e.target.error); };
  });
}

function replayOfflineQueue() {
  return openDB().then(function (db) {
    return getAllQueued(db).then(function (items) {
      if (!items.length) return;

      // Batch all items to the offline-sync endpoint
      return fetch('/dashboard/api/offline-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ items: items })
      }).then(function (resp) {
        if (!resp.ok) throw new Error('Sync failed: ' + resp.status);
        return resp.json();
      }).then(function (result) {
        // Delete successfully processed items
        var processed = result.processed || [];
        return Promise.all(
          processed.map(function (id) { return deleteQueued(db, id); })
        );
      });
    });
  });
}

// ─── Push Notifications (future) ───────────────────────────────────────────────
self.addEventListener('push', function (event) {
  // Placeholder for future push notification support
});
