(function () {
  // Theme Manager
  const currentTheme = localStorage.getItem("leaflore-theme") || "light";
  document.documentElement.setAttribute("data-theme", currentTheme);

  // Calm Mode Manager
  const currentCalm = localStorage.getItem("leaflore-calm-mode") || "disabled";
  if (currentCalm === "enabled") {
    document.documentElement.classList.add("calm-mode");
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Add calm-mode class to body as well to ensure standard targets match
    if (currentCalm === "enabled") {
      document.body.classList.add("calm-mode");
    }

    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
      updateToggleIcon(currentTheme);

      themeToggle.addEventListener("click", function () {
        const activeTheme = document.documentElement.getAttribute("data-theme");
        const newTheme = activeTheme === "dark" ? "light" : "dark";

        document.documentElement.setAttribute("data-theme", newTheme);
        localStorage.setItem("leaflore-theme", newTheme);
        updateToggleIcon(newTheme);
        window.dispatchEvent(new CustomEvent("leaflore-theme-change", { detail: { theme: newTheme } }));
      });
    }

    const calmToggle = document.getElementById("calm-toggle");
    if (calmToggle) {
      updateCalmIcon(localStorage.getItem("leaflore-calm-mode") || "disabled");

      calmToggle.addEventListener("click", function () {
        const isCalm = document.documentElement.classList.contains("calm-mode") || document.body.classList.contains("calm-mode");
        const newCalm = isCalm ? "disabled" : "enabled";

        if (newCalm === "enabled") {
          document.documentElement.classList.add("calm-mode");
          document.body.classList.add("calm-mode");
        } else {
          document.documentElement.classList.remove("calm-mode");
          document.body.classList.remove("calm-mode");
        }
        localStorage.setItem("leaflore-calm-mode", newCalm);
        updateCalmIcon(newCalm);
      });
    }

    function updateToggleIcon(theme) {
      const icon = themeToggle ? themeToggle.querySelector("i") : null;
      if (!icon) return;
      if (theme === "dark") {
        icon.className = "bi bi-sun-fill";
      } else {
        icon.className = "bi bi-moon-stars-fill";
      }
    }

    function updateCalmIcon(state) {
      const icon = calmToggle ? calmToggle.querySelector("i") : null;
      if (!icon) return;
      if (state === "enabled") {
        icon.className = "bi bi-wind text-success";
        calmToggle.title = "Disable Calm Mode";
      } else {
        icon.className = "bi bi-wind text-secondary";
        calmToggle.title = "Enable Calm Mode";
      }
    }


    // Success Confetti Trigger
    const hasSuccessFlash = document.querySelector(".alert-success");
    if (hasSuccessFlash && typeof confetti === "function") {
      // Fire a nice celebratory confetti burst
      const duration = 1.5 * 1000;
      const animationEnd = Date.now() + duration;
      const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 10000 };

      function randomInRange(min, max) {
        return Math.random() * (max - min) + min;
      }

      const interval = setInterval(function() {
        const timeLeft = animationEnd - Date.now();

        if (timeLeft <= 0) {
          return clearInterval(interval);
        }

        const particleCount = 50 * (timeLeft / duration);
        confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 } }));
        confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 } }));
      }, 250);
    }
  });
})();
