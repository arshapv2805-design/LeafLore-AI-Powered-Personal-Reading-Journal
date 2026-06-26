// garden_canvas.js — Living Greenhouse Garden for LeafLore
// Panoramic canvas scene reacting to reading streak, pages, and activity.
// Six seed themes unlocked by achievements; selection persists in localStorage.

(function () {
  'use strict';

  // ─── Canvas roundRect polyfill ─────────────────────────────────────────────
  if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
      r = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
      this.beginPath();
      this.moveTo(x + r, y);
      this.lineTo(x + w - r, y);
      this.arcTo(x + w, y, x + w, y + r, r);
      this.lineTo(x + w, y + h - r);
      this.arcTo(x + w, y + h, x + w - r, y + h, r);
      this.lineTo(x + r, y + h);
      this.arcTo(x, y + h, x, y + h - r, r);
      this.lineTo(x, y + r);
      this.arcTo(x, y, x + r, y, r);
      this.closePath();
    };
  }

  // ─── Theme Definitions ─────────────────────────────────────────────────────
  const THEMES = {
    forest: {
      label: '🌿 Forest',
      light: {
        sky: ['#c8dff0', '#d4edcc'],
        hills: ['#3a7028', '#487830'],
        hillsB: ['#2d5a20', '#3a6e28'],
        ground: '#2d5a1b',
        trunk: '#5c3d1e', leaf: '#206f19', accent: '#4ec344',
        particle: 'rgba(32,111,25,0.65)',
      },
      dark: {
        sky: ['#0b160c', '#0d1a0d'],
        hills: ['#173010', '#1f3e14'],
        hillsB: ['#102508', '#162e0c'],
        ground: '#0f2008',
        trunk: '#3d2a10', leaf: '#2a8c20', accent: '#38b82e',
        particle: 'rgba(42,140,32,0.7)',
      },
    },
    meadow: {
      label: '🌸 Meadow',
      light: {
        sky: ['#a8d8ea', '#fff4f8'],
        hills: ['#5a9030', '#70b040'],
        hillsB: ['#4a7828', '#5a9030'],
        ground: '#4a8a20',
        trunk: '#4a7820', leaf: '#70bc38', accent: '#ff9ec4',
        particle: 'rgba(255,140,190,0.75)',
      },
      dark: {
        sky: ['#0a1520', '#180d18'],
        hills: ['#1c3210', '#243c14'],
        hillsB: ['#142808', '#1c3010'],
        ground: '#122808',
        trunk: '#283810', leaf: '#385e20', accent: '#c07090',
        particle: 'rgba(192,112,144,0.7)',
      },
    },
    autumn: {
      label: '🍂 Autumn',
      light: {
        sky: ['#f5b060', '#ffd966'],
        hills: ['#a06030', '#b8721e'],
        hillsB: ['#884a20', '#a05e28'],
        ground: '#6b4010',
        trunk: '#5c2d0a', leaf: '#e07020', accent: '#d4401a',
        particle: 'rgba(220,100,28,0.72)',
      },
      dark: {
        sky: ['#180800', '#281200'],
        hills: ['#38150a', '#481c0e'],
        hillsB: ['#280d05', '#381208'],
        ground: '#200800',
        trunk: '#3c1a08', leaf: '#b84e10', accent: '#9c2e10',
        particle: 'rgba(180,70,16,0.7)',
      },
    },
    library: {
      label: '📚 Library',
      light: {
        sky: ['#8faa8f', '#a5bfa0'],
        hills: ['#4a6a3a', '#5a7a4a'],
        hillsB: ['#3a5830', '#4a6838'],
        ground: '#2a4a20',
        trunk: '#4a6030', leaf: '#3a6a28', accent: '#5a8a40',
        particle: 'rgba(90,138,64,0.62)',
      },
      dark: {
        sky: ['#0c140c', '#101810'],
        hills: ['#14200f', '#1a2812'],
        hillsB: ['#0f1a0a', '#14200e'],
        ground: '#0c180a',
        trunk: '#1a2510', leaf: '#1e3418', accent: '#284820',
        particle: 'rgba(40,72,32,0.7)',
      },
    },
    zen: {
      label: '🎋 Zen',
      light: {
        sky: ['#e8e4d4', '#f5f0e0'],
        hills: ['#c8b888', '#d4c898'],
        hillsB: ['#b8a878', '#c4b888'],
        ground: '#a89868',
        trunk: '#587840', leaf: '#4a6a30', accent: '#7a9a50',
        particle: 'rgba(120,154,80,0.55)',
      },
      dark: {
        sky: ['#181410', '#201c14'],
        hills: ['#4a4030', '#565040'],
        hillsB: ['#3a3028', '#484038'],
        ground: '#30281a',
        trunk: '#2a3818', leaf: '#243018', accent: '#384820',
        particle: 'rgba(56,72,32,0.6)',
      },
    },
    royal: {
      label: '🏆 Royal',
      light: {
        sky: ['#c084fc', '#818cf8'],
        hills: ['#5a3a7a', '#6a4a8a'],
        hillsB: ['#4a2a6a', '#5a3a7a'],
        ground: '#3a1a5a',
        trunk: '#7a3a9a', leaf: '#6a2a8a', accent: '#b060d0',
        particle: 'rgba(176,96,208,0.72)',
      },
      dark: {
        sky: ['#0e0318', '#090a1a'],
        hills: ['#1e0a2c', '#280e3a'],
        hillsB: ['#160620', '#200a2e'],
        ground: '#0e0220',
        trunk: '#381060', leaf: '#280a48', accent: '#6c3ca0',
        particle: 'rgba(108,60,160,0.7)',
      },
    },
  };

  // Achievement ID required to unlock each seed (null = always available)
  const SEED_ACHIEVEMENT = {
    forest: null,
    meadow: 'novice',
    autumn: 'streak',
    library: 'bookworm',
    zen: 'focus',
    royal: 'goal',
  };

  // ─── State ─────────────────────────────────────────────────────────────────
  let canvas, ctx;
  let animFrame = null;
  let t = 0;
  let currentTheme = localStorage.getItem('leaflore-garden-seed') || 'forest';
  let plants = [];
  let particles = [];
  const stats = { activeDays: 0, avgPages: 0, maxPages: 0, streakDays: 0 };

  // ─── Utilities ─────────────────────────────────────────────────────────────
  function seededR(n) {
    // Deterministic pseudo-random in [0, 1) from integer seed
    var x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  }

  function isDarkMode() {
    return document.documentElement.getAttribute('data-theme') === 'dark';
  }

  function isCalmMode() {
    return document.documentElement.classList.contains('calm-mode') ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // ─── Initialisation ────────────────────────────────────────────────────────
  function init() {
    canvas = document.getElementById('greenhouse-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('leaflore-theme-change', function () {
      setTimeout(function () { generatePlants(); }, 60);
    });
    buildSeedPicker();
    spawnParticles();
    startLoop();
  }

  function resize() {
    if (!canvas) return;
    var parent = canvas.parentElement;
    canvas.width = parent ? parent.clientWidth : window.innerWidth;
    canvas.height = 175;
    generatePlants();
  }

  // ─── Stats ─────────────────────────────────────────────────────────────────
  function computeStats(data) {
    var vals = Object.values(data || {});
    stats.activeDays = vals.filter(function (v) { return v > 0; }).length;
    var total = vals.reduce(function (a, b) { return a + b; }, 0);
    stats.avgPages = stats.activeDays > 0 ? total / stats.activeDays : 0;
    stats.maxPages = vals.length > 0 ? Math.max.apply(null, vals) : 0;
    stats.streakDays = window.LEAFLORE_STREAK_DAYS || 0;
  }

  // ─── Plant Generation ──────────────────────────────────────────────────────
  function generatePlants() {
    plants = [];
    if (!canvas) return;
    var W = canvas.width;
    var groundY = canvas.height - 24;
    var count = Math.max(3, Math.min(14, Math.floor(stats.activeDays / 3.5) + 3));
    var seed = (stats.activeDays * 137 + Math.floor(stats.maxPages) * 41) | 0;

    for (var i = 0; i < count; i++) {
      var r1 = seededR(seed + i * 13);
      var r2 = seededR(seed + i * 19 + 7);
      var r3 = seededR(seed + i * 29 + 11);

      var xFrac = (i + 0.5) / count + (r1 - 0.5) * 0.12;
      var x = Math.max(16, Math.min(W - 16, xFrac * W));

      var pageFactor = Math.min(1, stats.avgPages / 45);
      var sizeCategory = i % 3;
      var baseHeights = [28 + pageFactor * 32, 46 + pageFactor * 46, 68 + pageFactor * 68];
      var h = baseHeights[sizeCategory] * (0.72 + r2 * 0.56);

      plants.push({
        x: x, groundY: groundY, h: h,
        size: sizeCategory,
        swayPhase: r3 * Math.PI * 2,
        swaySpeed: 0.017 + r1 * 0.014,
        variant: Math.floor(r2 * 3),
        idx: i,
      });
    }
  }

  // ─── Particles ─────────────────────────────────────────────────────────────
  function spawnParticles() {
    particles = [];
    if (!canvas) return;
    var count = stats.streakDays >= 5 ? 12 : 5;
    for (var i = 0; i < count; i++) {
      particles.push(mkParticle(true));
    }
  }

  function mkParticle(spread) {
    var W = canvas ? canvas.width : 800;
    var H = canvas ? canvas.height : 175;
    return {
      x: Math.random() * W,
      y: spread ? Math.random() * H : H + 6,
      vx: (Math.random() - 0.5) * 0.55,
      vy: -(0.28 + Math.random() * 0.55),
      size: 2.5 + Math.random() * 4,
      opacity: 0.35 + Math.random() * 0.5,
      rotation: Math.random() * 360,
      rotSpeed: (Math.random() - 0.5) * 2.2,
      life: 1.0,
    };
  }

  // ─── Main Draw ─────────────────────────────────────────────────────────────
  function draw() {
    if (!canvas || !ctx) return;
    var W = canvas.width, H = canvas.height;
    var dark = isDarkMode();
    var theme = THEMES[currentTheme] || THEMES.forest;
    var pal = dark ? theme.dark : theme.light;

    ctx.clearRect(0, 0, W, H);

    // Sky gradient
    var skyGrad = ctx.createLinearGradient(0, 0, 0, H * 0.78);
    skyGrad.addColorStop(0, pal.sky[0]);
    skyGrad.addColorStop(1, pal.sky[1]);
    ctx.fillStyle = skyGrad;
    ctx.fillRect(0, 0, W, H);

    // Streak warm glow
    if (stats.streakDays >= 5) {
      var intensity = Math.min((stats.streakDays - 5) / 14, 1);
      var glowA = (dark ? 0.10 : 0.08) + intensity * 0.09;
      var g2 = ctx.createRadialGradient(W * 0.5, H, 0, W * 0.5, H, W * 0.72);
      g2.addColorStop(0, 'rgba(255,170,0,' + glowA + ')');
      g2.addColorStop(0.55, 'rgba(255,100,0,' + (glowA * 0.35) + ')');
      g2.addColorStop(1, 'rgba(255,100,0,0)');
      ctx.fillStyle = g2;
      ctx.fillRect(0, 0, W, H);
    }

    // Hills (back → front)
    drawHill(W, H, pal.hills[0], 0.50, 0.30, 0.78, 0.38, 0.68, 0.52);
    drawHill(W, H, pal.hills[1], 0.55, 0.42, 0.80, 0.50, 0.73, 0.60);
    drawHill(W, H, pal.hillsB[1], 0.68, 0.55, 0.85, 0.62, 0.80, 0.70);

    // Ground strip
    var groundY = H - 24;
    ctx.fillStyle = pal.ground;
    ctx.beginPath();
    ctx.moveTo(0, groundY + 2);
    ctx.bezierCurveTo(W * 0.35, groundY - 5, W * 0.65, groundY + 3, W, groundY - 1);
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fill();

    // Plants
    var calm = isCalmMode();
    for (var pi = 0; pi < plants.length; pi++) {
      var p = plants[pi];
      var sway = calm ? 0 : Math.sin(t * p.swaySpeed + p.swayPhase) * 3.2;
      drawPlant(p, pal, sway);
    }

    // Floating particles
    if (!calm) {
      updateParticles(W, H, pal);
    }

    // Edge vignette
    var vig = ctx.createRadialGradient(W / 2, H / 2, H * 0.1, W / 2, H / 2, W * 0.72);
    vig.addColorStop(0, 'rgba(0,0,0,0)');
    vig.addColorStop(1, dark ? 'rgba(0,0,0,0.38)' : 'rgba(0,0,0,0.07)');
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, W, H);
  }

  function drawHill(W, H, color, cy1, y1, cy2, y2, endY, baseY) {
    ctx.beginPath();
    ctx.moveTo(0, H * baseY);
    ctx.bezierCurveTo(W * 0.25, H * cy1, W * 0.55, H * y1, W * 0.78, H * cy2);
    ctx.bezierCurveTo(W * 0.9, H * y2, W, H * endY, W, H * baseY);
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  // ─── Plant Dispatch ─────────────────────────────────────────────────────────
  function drawPlant(p, pal, sway) {
    switch (currentTheme) {
      case 'meadow':  drawFlower(p, pal, sway); break;
      case 'autumn':  drawMaple(p, pal, sway); break;
      case 'library': drawFern(p, pal, sway); break;
      case 'zen':     drawZen(p, pal, sway); break;
      case 'royal':   drawOrchid(p, pal, sway); break;
      default:        drawTree(p, pal, sway); break;
    }
  }

  // ─── Forest Tree ────────────────────────────────────────────────────────────
  function drawTree(p, pal, sway) {
    var x = p.x, gy = p.groundY, h = p.h, size = p.size;
    ctx.save();
    ctx.translate(x, gy);
    var tw = 4 + size * 3, th = h * 0.38;
    ctx.fillStyle = pal.trunk;
    ctx.roundRect(-tw / 2 + sway * 0.08, -th, tw, th, tw * 0.4);
    ctx.fill();
    var cr = h * 0.36;
    ctx.globalAlpha = 0.88;
    ctx.fillStyle = pal.leaf;
    ctx.beginPath(); ctx.arc(sway * 0.5, -th - cr * 0.55, cr * 0.86, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(sway * 0.65 - cr * 0.52, -th - cr * 0.3, cr * 0.74, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(sway * 0.65 + cr * 0.52, -th - cr * 0.3, cr * 0.74, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = pal.accent;
    ctx.globalAlpha = 0.32;
    ctx.beginPath(); ctx.arc(sway * 0.4 - cr * 0.22, -th - cr * 0.72, cr * 0.44, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1.0;
    ctx.restore();
  }

  // ─── Meadow Flower ─────────────────────────────────────────────────────────
  var PETAL_COLORS = ['#ff9ec4', '#ffa0ff', '#ffcc80', '#a0d8ef', '#c8a0e0'];

  function drawFlower(p, pal, sway) {
    var x = p.x, gy = p.groundY, h = p.h, v = p.variant;
    ctx.save();
    ctx.translate(x, gy);
    ctx.strokeStyle = pal.trunk;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(sway * 0.7, -h * 0.5, sway * 1.1, -h);
    ctx.stroke();
    var r = h * 0.23;
    ctx.save();
    ctx.translate(sway * 1.1, -h);
    ctx.fillStyle = PETAL_COLORS[v % PETAL_COLORS.length];
    ctx.globalAlpha = 0.85;
    for (var i = 0; i < 6; i++) {
      ctx.save();
      ctx.rotate((i / 6) * Math.PI * 2);
      ctx.beginPath();
      ctx.ellipse(0, -r, r * 0.44, r, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    ctx.fillStyle = '#ffee44';
    ctx.globalAlpha = 1.0;
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.38, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    ctx.globalAlpha = 1.0;
    ctx.restore();
  }

  // ─── Autumn Maple ──────────────────────────────────────────────────────────
  function drawMaple(p, pal, sway) {
    var x = p.x, gy = p.groundY, h = p.h, size = p.size;
    ctx.save();
    ctx.translate(x, gy);
    var tw = 3.5 + size * 2.5, th = h * 0.36;
    ctx.fillStyle = pal.trunk;
    ctx.roundRect(-tw / 2 + sway * 0.07, -th, tw, th, tw * 0.38);
    ctx.fill();
    var cr = h * 0.39, sw = sway * 0.52;
    var topY = -th - cr * 1.08;
    ctx.fillStyle = pal.leaf;
    ctx.globalAlpha = 0.88;
    ctx.beginPath();
    ctx.moveTo(sw, topY);
    ctx.lineTo(sw + cr * 0.85, -th + cr * 0.08);
    ctx.lineTo(sw - cr * 0.85, -th + cr * 0.08);
    ctx.closePath(); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(sw - cr * 0.28, topY + cr * 0.38);
    ctx.lineTo(sw + cr * 1.02, -th + cr * 0.28);
    ctx.lineTo(sw - cr * 1.02, -th + cr * 0.28);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle = pal.accent;
    ctx.globalAlpha = 0.72;
    for (var li = 0; li < 5; li++) {
      var lx = sw + (seededR(li * 13 + p.idx) - 0.5) * cr * 2.6;
      var ly = -th + seededR(li * 17 + p.idx) * cr;
      ctx.beginPath();
      ctx.arc(lx, ly, 2.5 + seededR(li * 7 + p.idx) * 4.5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;
    ctx.restore();
  }

  // ─── Library Fern ──────────────────────────────────────────────────────────
  function drawFern(p, pal, sway) {
    var x = p.x, gy = p.groundY, h = p.h, v = p.variant;
    ctx.save();
    ctx.translate(x, gy);
    var fronds = 5 + v;
    ctx.strokeStyle = pal.leaf;
    ctx.lineWidth = 1.6;
    for (var f = 0; f < fronds; f++) {
      var angle = (-Math.PI / 2) + ((f / (fronds - 1)) - 0.5) * Math.PI * 0.88;
      var len = h * (0.6 + (f === Math.floor(fronds / 2) ? 0.4 : 0));
      ctx.save();
      ctx.rotate(angle + sway * 0.018);
      ctx.globalAlpha = 0.82;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(len * 0.28, -len * 0.48, 0, -len);
      ctx.stroke();
      ctx.fillStyle = pal.accent;
      ctx.globalAlpha = 0.6;
      for (var li = 1; li < 5; li++) {
        var frac = li / 5;
        var lx2 = len * 0.28 * frac;
        var ly2 = -len * 0.48 * frac - len * frac * 0.52;
        ctx.beginPath();
        ctx.ellipse(lx2, ly2, 5.5 - frac * 2, 3 - frac, angle * 0.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
    ctx.globalAlpha = 1.0;
    ctx.restore();
  }

  // ─── Zen (Bamboo + Bonsai) ─────────────────────────────────────────────────
  function drawZen(p, pal, sway) {
    var x = p.x, gy = p.groundY, h = p.h, v = p.variant;
    ctx.save();
    ctx.translate(x, gy);
    if (v !== 2) {
      // Bamboo stalks
      for (var s = 0; s < 2; s++) {
        var ox = (s - 0.5) * 13;
        var sw2 = sway * (0.55 + s * 0.3);
        var sh = h * (0.88 + s * 0.14);
        ctx.strokeStyle = pal.trunk;
        ctx.lineWidth = 5 - s;
        ctx.beginPath(); ctx.moveTo(ox, 0); ctx.lineTo(ox + sw2, -sh); ctx.stroke();
        ctx.fillStyle = pal.leaf;
        for (var j = 1; j < 4; j++) {
          var jy = -(sh * j / 4);
          ctx.beginPath();
          ctx.roundRect(ox - 3.5, jy - 3.5, 7, 7, 2.5);
          ctx.fill();
          ctx.save();
          ctx.translate(ox + sw2 * j / 4, jy);
          ctx.rotate(-Math.PI / 4 + sway * 0.04);
          ctx.fillStyle = pal.accent;
          ctx.globalAlpha = 0.78;
          ctx.beginPath(); ctx.ellipse(9, 0, 11, 4, 0, 0, Math.PI * 2); ctx.fill();
          ctx.restore();
        }
      }
    } else {
      // Bonsai
      var thb = h * 0.5;
      ctx.lineWidth = 5.5;
      ctx.strokeStyle = pal.trunk;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.bezierCurveTo(sway * 0.4, -thb * 0.38, sway * 0.28 - 11, -thb * 0.72, sway * 0.5, -thb);
      ctx.stroke();
      ctx.fillStyle = pal.leaf;
      ctx.globalAlpha = 0.82;
      [[0, -thb, h * 0.19], [-h * 0.13, -thb * 0.84, h * 0.13], [h * 0.1, -thb * 0.74, h * 0.11]].forEach(function (c) {
        ctx.beginPath(); ctx.arc(c[0] + sway * 0.38, c[1], c[2], 0, Math.PI * 2); ctx.fill();
      });
      ctx.fillStyle = pal.accent;
      ctx.globalAlpha = 0.42;
      ctx.beginPath(); ctx.arc(-h * 0.06 + sway * 0.38, -thb - h * 0.02, h * 0.1, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1.0;
    ctx.restore();
  }

  // ─── Royal Orchid ──────────────────────────────────────────────────────────
  var ORCHID_COLORS = ['#d070e0', '#e080c0', '#a050e8', '#8060d0', '#c060f0'];

  function drawOrchid(p, pal, sway) {
    var x = p.x, gy = p.groundY, h = p.h, v = p.variant;
    ctx.save();
    ctx.translate(x, gy);
    ctx.strokeStyle = pal.trunk;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.bezierCurveTo(sway * 0.55, -h * 0.38, sway * 0.75 - 9, -h * 0.68, sway, -h);
    ctx.stroke();
    var numBlooms = 2 + v;
    var bloomColor = ORCHID_COLORS[v % ORCHID_COLORS.length];
    for (var b = 0; b < numBlooms; b++) {
      var frac = (b + 1) / (numBlooms + 1);
      ctx.save();
      ctx.translate(sway * frac, -h * frac);
      ctx.fillStyle = bloomColor;
      ctx.globalAlpha = 0.82;
      for (var pe = 0; pe < 5; pe++) {
        ctx.save();
        ctx.rotate((pe / 5) * Math.PI * 2);
        ctx.beginPath();
        ctx.ellipse(0, -h * 0.077, h * 0.038, h * 0.077, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      ctx.fillStyle = '#ffee88';
      ctx.globalAlpha = 1.0;
      ctx.beginPath(); ctx.arc(0, 0, h * 0.028, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    ctx.globalAlpha = 1.0;
    ctx.restore();
  }

  // ─── Particle System ────────────────────────────────────────────────────────
  function updateParticles(W, H, pal) {
    if (Math.random() < 0.032 && particles.length < (stats.streakDays >= 5 ? 16 : 6)) {
      particles.push(mkParticle(false));
    }
    particles = particles.filter(function (p) { return p.life > 0.02; });
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.x += p.vx; p.y += p.vy;
      p.rotation += p.rotSpeed;
      p.life -= 0.0025;
      ctx.save();
      ctx.globalAlpha = p.opacity * p.life;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation * Math.PI / 180);
      ctx.fillStyle = pal.particle;
      if (currentTheme === 'zen') {
        ctx.fillRect(-p.size / 2, -p.size / 5, p.size, p.size / 2.5);
      } else {
        ctx.beginPath();
        ctx.moveTo(0, -p.size / 2);
        ctx.quadraticCurveTo(p.size / 2, 0, 0, p.size / 2);
        ctx.quadraticCurveTo(-p.size / 2, 0, 0, -p.size / 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  // ─── Animation Loop ─────────────────────────────────────────────────────────
  function startLoop() {
    function loop() {
      t += 0.016;
      draw();
      animFrame = requestAnimationFrame(loop);
    }
    if (animFrame) cancelAnimationFrame(animFrame);
    loop();
  }

  // ─── Seed Picker UI ─────────────────────────────────────────────────────────
  function buildSeedPicker() {
    var picker = document.getElementById('garden-seed-picker');
    if (!picker) return;
    picker.innerHTML = '';
    var unlocked = window.LEAFLORE_UNLOCKED_SEEDS || [];

    Object.keys(THEMES).forEach(function (key) {
      var theme = THEMES[key];
      var reqAch = SEED_ACHIEVEMENT[key];
      var isUnlocked = !reqAch || unlocked.indexOf(reqAch) !== -1;
      var isActive = key === currentTheme;

      var btn = document.createElement('button');
      btn.className = 'seed-pill' + (isActive ? ' active' : '') + (isUnlocked ? '' : ' locked');
      btn.title = isUnlocked ? ('Switch to ' + theme.label) : ('Locked — unlock by earning the achievement');
      btn.setAttribute('data-seed', key);
      btn.innerHTML = theme.label + (isUnlocked ? '' : ' 🔒');
      btn.disabled = !isUnlocked;

      if (isUnlocked) {
        btn.addEventListener('click', function () {
          window.LeafGarden.setTheme(key);
          picker.querySelectorAll('.seed-pill').forEach(function (b) { b.classList.remove('active'); });
          btn.classList.add('active');
        });
      }
      picker.appendChild(btn);
    });
  }

  // ─── Public API ────────────────────────────────────────────────────────────
  window.LeafGarden = {
    setTheme: function (seedType) {
      if (!THEMES[seedType]) return;
      currentTheme = seedType;
      localStorage.setItem('leaflore-garden-seed', seedType);
      generatePlants();
    },
    refresh: function (data) {
      computeStats(data);
      generatePlants();
      spawnParticles();
      buildSeedPicker();
    },
    getThemes: function () { return THEMES; },
    getSeedAchievement: function () { return SEED_ACHIEVEMENT; },
    triggerCelebration: function () {
      if (isCalmMode()) return;
      var W = canvas ? canvas.width : 800;
      var H = canvas ? canvas.height : 175;
      for (var i = 0; i < 45; i++) {
        particles.push({
          x: Math.random() * W,
          y: Math.random() * (H * 0.4),
          vx: (Math.random() - 0.5) * 1.5,
          vy: 0.5 + Math.random() * 1.2,
          size: 3.5 + Math.random() * 5,
          opacity: 0.6 + Math.random() * 0.4,
          rotation: Math.random() * 360,
          rotSpeed: (Math.random() - 0.5) * 4.5,
          life: 1.0,
        });
      }
    }
  };

  document.addEventListener('DOMContentLoaded', init);
})();
