// offline_sync.js — LeafLore PWA offline support & install banner
// • Registers the service worker
// • Shows an offline indicator banner when navigator.onLine is false
// • Shows a custom "Install App" banner on beforeinstallprompt
// • Intercepts focus session and quick-log submits to queue offline
// • Triggers background sync when coming back online

(function () {
  'use strict';

  // ─── Service Worker Registration ────────────────────────────────────────────
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(function (reg) {
        // Background sync when back online
        window.addEventListener('online', function () {
          if ('sync' in reg) {
            reg.sync.register('leaflore-sync').catch(function () {
              // Fallback: replay manually if Background Sync API not available
              manualSync();
            });
          } else {
            manualSync();
          }
        });
      }).catch(function (err) {
        console.warn('[LeafLore SW] Registration failed:', err);
      });
    });
  }

  // ─── IndexedDB Queue ────────────────────────────────────────────────────────
  var DB_NAME = 'leaflore-offline-db';
  var STORE_NAME = 'offline-queue';
  var _db = null;

  function openDB() {
    return new Promise(function (resolve, reject) {
      if (_db) { resolve(_db); return; }
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        }
      };
      req.onsuccess = function (e) { _db = e.target.result; resolve(_db); };
      req.onerror = function (e) { reject(e.target.error); };
    });
  }

  function enqueue(payload) {
    return openDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE_NAME, 'readwrite');
        var store = tx.objectStore(STORE_NAME);
        var req = store.add(Object.assign({ timestamp: Date.now() }, payload));
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function countQueued() {
    return openDB().then(function (db) {
      return new Promise(function (resolve) {
        var tx = db.transaction(STORE_NAME, 'readonly');
        var store = tx.objectStore(STORE_NAME);
        var req = store.count();
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { resolve(0); };
      });
    });
  }

  // ─── Manual Sync Fallback ───────────────────────────────────────────────────
  function manualSync() {
    openDB().then(function (db) {
      var tx = db.transaction(STORE_NAME, 'readonly');
      var store = tx.objectStore(STORE_NAME);
      var req = store.getAll();
      req.onsuccess = function () {
        var items = req.result;
        if (!items || !items.length) return;
        fetch('/dashboard/api/offline-sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ items: items })
        }).then(function (resp) {
          return resp.json();
        }).then(function (result) {
          var processed = result.processed || [];
          if (!processed.length) return;
          var tx2 = db.transaction(STORE_NAME, 'readwrite');
          var store2 = tx2.objectStore(STORE_NAME);
          processed.forEach(function (id) { store2.delete(id); });
          showToast('✅ ' + processed.length + ' offline action(s) synced!', 'success');
          updateQueueBadge();
        }).catch(function (err) {
          console.warn('[LeafLore Sync] Manual sync failed:', err);
        });
      };
    });
  }

  // ─── Offline Banner ─────────────────────────────────────────────────────────
  function createOfflineBanner() {
    if (document.getElementById('ll-offline-banner')) return;
    var banner = document.createElement('div');
    banner.id = 'll-offline-banner';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    banner.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:9999',
      'background:linear-gradient(90deg,#b45309,#92400e)',
      'color:#fff', 'text-align:center',
      'padding:9px 16px', 'font-size:0.85rem', 'font-weight:600',
      'display:flex', 'align-items:center', 'justify-content:center', 'gap:8px',
      'transform:translateY(-100%)', 'transition:transform 0.35s cubic-bezier(.22,.68,0,1.2)',
      'font-family:Inter,sans-serif',
    ].join(';');
    banner.innerHTML = '<span>📡 You\'re offline — reading logs are being saved locally</span>' +
      '<span id="ll-queue-badge" style="background:rgba(255,255,255,0.2);padding:2px 8px;border-radius:12px;font-size:0.78rem;display:none"></span>';
    document.body.appendChild(banner);
    return banner;
  }

  function showOfflineBanner() {
    var b = document.getElementById('ll-offline-banner') || createOfflineBanner();
    setTimeout(function () { b.style.transform = 'translateY(0)'; }, 50);
    updateQueueBadge();
  }

  function hideOfflineBanner() {
    var b = document.getElementById('ll-offline-banner');
    if (b) b.style.transform = 'translateY(-100%)';
  }

  function updateQueueBadge() {
    countQueued().then(function (n) {
      var badge = document.getElementById('ll-queue-badge');
      if (!badge) return;
      if (n > 0) {
        badge.textContent = n + ' queued';
        badge.style.display = '';
      } else {
        badge.style.display = 'none';
      }
    });
  }

  window.addEventListener('online', function () {
    hideOfflineBanner();
    showToast('🌐 You\'re back online! Syncing queued data…', 'info');
  });

  window.addEventListener('offline', function () {
    showOfflineBanner();
  });

  if (!navigator.onLine) {
    document.addEventListener('DOMContentLoaded', showOfflineBanner);
  }

  // ─── Toast Helper ───────────────────────────────────────────────────────────
  function showToast(message, type) {
    // Prefer LeafLore's existing trophy toast if available, else create a simple one
    var toast = document.createElement('div');
    toast.style.cssText = [
      'position:fixed', 'bottom:24px', 'left:50%', 'transform:translateX(-50%)',
      'z-index:10000',
      type === 'success' ? 'background:linear-gradient(135deg,#206f19,#2d9d24)' : 'background:linear-gradient(135deg,#1a6080,#1a8050)',
      'color:#fff', 'padding:12px 20px', 'border-radius:12px',
      'font-size:0.88rem', 'font-weight:600', 'box-shadow:0 8px 24px rgba(0,0,0,0.35)',
      'font-family:Inter,sans-serif',
      'animation:slideUp 0.35s cubic-bezier(.22,.68,0,1.2)',
      'white-space:nowrap',
    ].join(';');
    toast.textContent = message;

    if (!document.getElementById('ll-toast-style')) {
      var style = document.createElement('style');
      style.id = 'll-toast-style';
      style.textContent = '@keyframes slideUp{from{opacity:0;transform:translateX(-50%) translateY(16px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}';
      document.head.appendChild(style);
    }

    document.body.appendChild(toast);
    setTimeout(function () {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.4s';
      setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 450);
    }, 3500);
  }

  // ─── Intercept Focus Session Submission ────────────────────────────────────
  // Wraps the global submitFocusLog to handle offline queuing
  document.addEventListener('DOMContentLoaded', function () {
    // Patch submitFocusLog if it exists in the page
    var _original = window.submitFocusLog;
    if (typeof _original === 'function') {
      window.submitFocusLog = function () {
        if (navigator.onLine) {
          _original.apply(this, arguments);
          return;
        }
        // Offline: read form values and queue
        var bookId = document.getElementById('focus-book-select') && document.getElementById('focus-book-select').value;
        var pages = document.getElementById('focus-pages-read') && document.getElementById('focus-pages-read').value;
        if (!bookId || !pages || parseInt(pages) <= 0) {
          alert('Please fill in book and page count before saving offline.');
          return;
        }
        enqueue({
          type: 'focus_log',
          book_id: parseInt(bookId),
          pages_read: parseInt(pages),
          duration_minutes: 0,
        }).then(function () {
          showToast('📴 Session saved offline — will sync when connected', 'info');
          updateQueueBadge();
        });
      };
    }

    // Intercept Quick Log modal form
    var quickLogForm = document.querySelector('#quickLogModal form');
    if (quickLogForm) {
      quickLogForm.addEventListener('submit', function (e) {
        if (navigator.onLine) return; // let it through normally
        e.preventDefault();
        var formData = new FormData(quickLogForm);
        var bookId = formData.get('book_id');
        var pages = formData.get('pages_read');
        var dateVal = formData.get('date');
        if (!bookId || !pages) {
          alert('Please select a book and enter pages read.');
          return;
        }
        enqueue({
          type: 'quick_log',
          book_id: parseInt(bookId),
          pages_read: parseInt(pages),
          date: dateVal,
        }).then(function () {
          var modal = document.getElementById('quickLogModal');
          if (modal) {
            var bsModal = bootstrap && bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
          }
          showToast('📴 Log saved offline — will sync when connected', 'info');
          updateQueueBadge();
        });
      });
    }
  });

  // ─── Install Banner ────────────────────────────────────────────────────────
  var _deferredInstallPrompt = null;

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    _deferredInstallPrompt = e;
    showInstallBanner();
  });

  function showInstallBanner() {
    if (document.getElementById('ll-install-banner')) return;
    var banner = document.createElement('div');
    banner.id = 'll-install-banner';
    banner.style.cssText = [
      'position:fixed', 'bottom:24px', 'right:24px', 'z-index:9998',
      'background:var(--bg-card,#131e13)',
      'border:1px solid rgba(32,111,25,0.35)',
      'border-radius:14px',
      'padding:14px 18px',
      'box-shadow:0 12px 40px rgba(0,0,0,0.45)',
      'display:flex', 'align-items:center', 'gap:12px',
      'font-family:Inter,sans-serif',
      'max-width:320px',
      'animation:slideInRight 0.4s cubic-bezier(.22,.68,0,1.2)',
    ].join(';');
    banner.innerHTML =
      '<span style="font-size:1.8rem">🍃</span>' +
      '<div style="flex:1">' +
        '<div style="font-weight:700;color:var(--text-primary,#d4e4cc);font-size:0.88rem;margin-bottom:3px">Install LeafLore</div>' +
        '<div style="font-size:0.75rem;color:var(--text-muted,#7a9a70)">Add to your home screen for the full app experience</div>' +
      '</div>' +
      '<div style="display:flex;flex-direction:column;gap:6px">' +
        '<button id="ll-install-btn" style="background:#206f19;color:#fff;border:none;border-radius:8px;padding:6px 12px;font-size:0.78rem;font-weight:600;cursor:pointer;font-family:Inter,sans-serif">Install</button>' +
        '<button id="ll-install-dismiss" style="background:transparent;color:var(--text-muted,#7a9a70);border:none;font-size:0.72rem;cursor:pointer;font-family:Inter,sans-serif">Not now</button>' +
      '</div>';

    if (!document.getElementById('ll-install-style')) {
      var style = document.createElement('style');
      style.id = 'll-install-style';
      style.textContent = '@keyframes slideInRight{from{opacity:0;transform:translateX(40px)}to{opacity:1;transform:translateX(0)}}';
      document.head.appendChild(style);
    }

    document.body.appendChild(banner);

    document.getElementById('ll-install-btn').addEventListener('click', function () {
      if (_deferredInstallPrompt) {
        _deferredInstallPrompt.prompt();
        _deferredInstallPrompt.userChoice.then(function (choice) {
          if (choice.outcome === 'accepted') {
            showToast('🎉 LeafLore installed! Find it on your home screen.', 'success');
          }
          _deferredInstallPrompt = null;
          removeBanner();
        });
      }
    });

    document.getElementById('ll-install-dismiss').addEventListener('click', removeBanner);

    function removeBanner() {
      if (banner.parentNode) banner.parentNode.removeChild(banner);
    }

    // Auto-dismiss after 12 seconds
    setTimeout(removeBanner, 12000);
  }

  // ─── Run initial sync check on load ────────────────────────────────────────
  window.addEventListener('load', function () {
    if (navigator.onLine) {
      countQueued().then(function (n) {
        if (n > 0) { manualSync(); }
      });
    }
    updateQueueBadge();
  });

})();
