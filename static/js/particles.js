(function () {
  const canvas = document.createElement("canvas");
  canvas.id = "leaf-canvas";
  canvas.style.position = "fixed";
  canvas.style.top = "0";
  canvas.style.left = "0";
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  canvas.style.zIndex = "-1";
  canvas.style.pointerEvents = "none";
  canvas.style.transition = "opacity 0.4s ease";
  document.body.appendChild(canvas);

  const ctx = canvas.getContext("2d");
  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  const particles = [];
  const particleCount = 65;
  const mouse = { x: null, y: null, radius: 120 };

  // Customization settings
  let activeTheme = localStorage.getItem("leaflore-canvas-theme") || "leaves"; // 'leaves', 'sakura', 'nebula'
  let speedMultiplier = parseFloat(localStorage.getItem("leaflore-canvas-speed")) || 1.0;

  // Click & Drag Wind gust physics
  let isDragging = false;
  let lastDragX = null;
  let lastDragY = null;
  const dragWind = { x: 0, y: 0 };

  window.addEventListener("resize", function () {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  window.addEventListener("mousemove", function (e) {
    mouse.x = e.clientX;
    mouse.y = e.clientY;

    if (isDragging && lastDragX !== null && lastDragY !== null) {
      const dx = e.clientX - lastDragX;
      const dy = e.clientY - lastDragY;
      // Accelerate the wind gust based on drag velocity
      dragWind.x += dx * 0.12;
      dragWind.y += dy * 0.12;

      // Clamp max drag force
      const currentForce = Math.sqrt(dragWind.x * dragWind.x + dragWind.y * dragWind.y);
      if (currentForce > 18) {
        dragWind.x = (dragWind.x / currentForce) * 18;
        dragWind.y = (dragWind.y / currentForce) * 18;
      }
      lastDragX = e.clientX;
      lastDragY = e.clientY;
    }
  });

  window.addEventListener("mousedown", function (e) {
    isDragging = true;
    lastDragX = e.clientX;
    lastDragY = e.clientY;
  });

  window.addEventListener("mouseup", function () {
    isDragging = false;
    lastDragX = null;
    lastDragY = null;
  });

  window.addEventListener("mouseout", function () {
    mouse.x = null;
    mouse.y = null;
    isDragging = false;
  });

  function getThemeColors() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    if (activeTheme === "sakura") {
      return [
        "rgba(255, 183, 197, 0.45)",  // Soft vibrant pink
        "rgba(255, 145, 175, 0.38)",  // Cherry blossom pink
        "rgba(240, 110, 150, 0.35)"   // Deep blossom pink
      ];
    } else if (activeTheme === "nebula") {
      if (isDark) {
        return [
          "rgba(123, 97, 255, 0.40)",  // Purple nebula glow
          "rgba(224, 86, 253, 0.35)",  // Pink cosmic mist
          "rgba(72, 219, 251, 0.40)"   // Cyan star ember
        ];
      } else {
        return [
          "rgba(100, 149, 237, 0.30)", // Cornflower blue
          "rgba(186, 85, 211, 0.28)",  // Lavender star
          "rgba(72, 209, 204, 0.32)"   // Soft turquoise
        ];
      }
    } else {
      // Default: 'leaves'
      if (isDark) {
        return [
          "rgba(230, 145, 69, 0.45)",  // Glowing amber
          "rgba(252, 171, 93, 0.40)",  // Soft gold
          "rgba(178, 84, 47, 0.42)"    // Deep copper
        ];
      } else {
        return [
          "rgba(32, 111, 25, 0.35)",    // Forest green
          "rgba(41, 141, 32, 0.32)",    // Light forest green
          "rgba(78, 195, 68, 0.30)"     // Warm light forest green
        ];
      }
    }
  }

  class Particle {
    constructor() {
      this.reset();
      this.y = Math.random() * height;
    }

    reset() {
      this.x = Math.random() * width;
      this.y = -20;
      this.size = Math.random() * 15 + 8;
      this.speedX = Math.random() * 0.8 - 0.4;
      this.speedY = Math.random() * 0.7 + 0.4;
      this.rotation = Math.random() * 360;
      this.rotationSpeed = Math.random() * 0.5 - 0.25;
      const colors = getThemeColors();
      this.color = colors[Math.floor(Math.random() * colors.length)];
      this.swaySpeed = Math.random() * 0.01 + 0.005;
      this.swayOffset = Math.random() * 100;
    }

    update() {
      // Move using standard drift + speed multiplier + current wind gust
      this.x += (this.speedX + Math.sin(this.swayOffset) * 0.2) * speedMultiplier + dragWind.x;
      this.y += this.speedY * speedMultiplier + dragWind.y;
      this.rotation += this.rotationSpeed;
      this.swayOffset += this.swaySpeed;

      // Mouse repel logic
      if (mouse.x !== null && mouse.y !== null && !isDragging) {
        const dx = this.x - mouse.x;
        const dy = this.y - mouse.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance < mouse.radius) {
          const force = (mouse.radius - distance) / mouse.radius;
          const forceX = (dx / distance) * force * 3;
          const forceY = (dy / distance) * force * 3;
          this.x += forceX;
          this.y += forceY;
        }
      }

      if (this.y > height + 20 || this.x < -20 || this.x > width + 20) {
        this.reset();
      }
    }

    draw() {
      ctx.save();
      ctx.translate(this.x, this.y);
      ctx.rotate((this.rotation * Math.PI) / 180);
      ctx.fillStyle = this.color;

      if (activeTheme === "sakura") {
        // Draw a cherry blossom petal
        ctx.beginPath();
        ctx.moveTo(0, -this.size / 2);
        ctx.quadraticCurveTo(this.size * 0.4, -this.size * 0.3, this.size * 0.25, this.size * 0.2);
        ctx.quadraticCurveTo(0, this.size * 0.5, -this.size * 0.25, this.size * 0.2);
        ctx.quadraticCurveTo(-this.size * 0.4, -this.size * 0.3, 0, -this.size / 2);
        ctx.fill();
      } else if (activeTheme === "nebula") {
        // Draw soft glowing orb
        ctx.beginPath();
        const baseColor = this.color.substring(0, this.color.lastIndexOf(",")) + ", 0.55)";
        const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, this.size / 2);
        grad.addColorStop(0, baseColor);
        grad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = grad;
        ctx.arc(0, 0, this.size / 2, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // Default: 'leaves' organic shape
        ctx.beginPath();
        ctx.moveTo(0, -this.size / 2);
        ctx.quadraticCurveTo(this.size / 2, 0, 0, this.size / 2);
        ctx.quadraticCurveTo(-this.size / 2, 0, 0, -this.size / 2);
        ctx.fill();
      }

      ctx.restore();
    }
  }

  function init() {
    for (let i = 0; i < particleCount; i++) {
      particles.push(new Particle());
    }
  }

  function animate() {
    const isCalmMode = document.documentElement.classList.contains("calm-mode") || document.body.classList.contains("calm-mode") || localStorage.getItem("leaflore-calm-mode") === "enabled";
    const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isMobile = window.innerWidth < 768;

    if (isCalmMode || isReducedMotion || isMobile) {
      ctx.clearRect(0, 0, width, height);
      requestAnimationFrame(animate);
      return;
    }

    ctx.clearRect(0, 0, width, height);

    // Fade/decay drag wind gradually
    dragWind.x *= 0.92;
    dragWind.y *= 0.92;

    const colors = getThemeColors();

    for (let i = 0; i < particles.length; i++) {
      // Periodically refresh colors if theme switches
      if (Math.random() < 0.05) {
        particles[i].color = colors[Math.floor(Math.random() * colors.length)];
      }
      particles[i].update();
      particles[i].draw();
    }
    requestAnimationFrame(animate);
  }


  init();
  animate();

  // Expose global canvas controller APIs
  window.LeafCanvas = {
    setTheme: function (themeName) {
      if (["leaves", "sakura", "nebula"].includes(themeName)) {
        activeTheme = themeName;
        localStorage.setItem("leaflore-canvas-theme", themeName);
        // Instantly force-refresh colors
        const colors = getThemeColors();
        particles.forEach(p => {
          p.color = colors[Math.floor(Math.random() * colors.length)];
        });
      }
    },
    setSpeed: function (multiplier) {
      const parsed = parseFloat(multiplier);
      if (!isNaN(parsed) && parsed >= 0.1 && parsed <= 5.0) {
        speedMultiplier = parsed;
        localStorage.setItem("leaflore-canvas-speed", parsed);
      }
    },
    triggerGust: function (strengthX, strengthY) {
      dragWind.x += strengthX;
      dragWind.y += strengthY;
    }
  };
})();
