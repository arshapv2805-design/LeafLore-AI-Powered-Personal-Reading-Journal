document.addEventListener("DOMContentLoaded", function () {
  const grid = document.getElementById("garden-grid");
  if (!grid) return;

  // 1. Intensity stages based on page logs
  function intensityClass(pages) {
    if (!pages) return "heat-0";
    if (pages <= 10) return "heat-1";
    if (pages <= 30) return "heat-2";
    if (pages <= 50) return "heat-3";
    return "heat-4";
  }

  // 2. Click particle bursts of green leaves
  function createCellParticles(el) {
    // Ensure relative parent
    el.style.position = "relative";
    for (let i = 0; i < 8; i++) {
      const p = document.createElement("div");
      p.className = "cell-leaf-particle";
      
      const angle = Math.random() * Math.PI * 2;
      const distance = 12 + Math.random() * 25;
      const randX = Math.cos(angle) * distance;
      const randY = Math.sin(angle) * distance;
      
      const rotStart = Math.random() * 360;
      const rotEnd = rotStart + 90 + Math.random() * 180;
      
      p.style.setProperty("--rand-x", `${randX}px`);
      p.style.setProperty("--rand-y", `${randY}px`);
      p.style.setProperty("--rand-rot-start", `${rotStart}deg`);
      p.style.setProperty("--rand-rot-end", `${rotEnd}deg`);
      
      p.style.left = "50%";
      p.style.top = "50%";
      
      const colors = ["#206f19", "#298d20", "#154e11", "#4ec344"];
      p.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
      
      el.appendChild(p);
      setTimeout(() => p.remove(), 600);
    }
  }

  // 3. Construct the 53-week garden timeline grid
  const today = new Date();
  const currentSunday = new Date(today);
  currentSunday.setDate(today.getDate() - today.getDay());
  
  const startDate = new Date(currentSunday);
  startDate.setDate(currentSunday.getDate() - (52 * 7)); // 52 weeks before current Sunday

  grid.innerHTML = "";
  
  // Create or retrieve floating tooltip
  let tooltip = document.getElementById("garden-tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.id = "garden-tooltip";
    tooltip.className = "garden-tooltip";
    document.body.appendChild(tooltip);
  }

  for (let w = 0; w < 53; w++) {
    const weekCol = document.createElement("div");
    weekCol.className = "garden-week-col";
    
    for (let d = 0; d < 7; d++) {
      const dayDate = new Date(startDate);
      dayDate.setDate(startDate.getDate() + (w * 7) + d);
      
      const iso = dayDate.toLocaleDateString("en-CA"); // YYYY-MM-DD local format
      
      const cell = document.createElement("div");
      cell.className = "garden-cell";
      cell.dataset.date = iso;
      
      // Mark today's cell
      if (iso === today.toLocaleDateString("en-CA")) {
        cell.classList.add("is-today");
      }
      
      // Lock future days
      if (dayDate > today) {
        cell.style.opacity = "0.15";
        cell.style.pointerEvents = "none";
      }
      
      weekCol.appendChild(cell);
    }
    grid.appendChild(weekCol);
  }

  // 4. Load Heatmap Data & Bind Event Listeners
  fetch("/dashboard/api/heatmap-data")
    .then(function (res) {
      return res.json();
    })
    .then(function (pagesByDate) {
      // ── Wire up the Living Garden Canvas ──────────────────────────────────
      window.LEAFLORE_GARDEN_DATA = pagesByDate;
      if (window.LeafGarden && typeof window.LeafGarden.refresh === 'function') {
        window.LeafGarden.refresh(pagesByDate);
      }
      // ──────────────────────────────────────────────────────────────────────

      const detailEl = document.getElementById("day-detail");
      const cells = document.querySelectorAll(".garden-cell");

      cells.forEach(function (cell) {
        const iso = cell.dataset.date;
        if (!iso) return;

        const pages = pagesByDate[iso] || 0;
        const cls = intensityClass(pages);
        cell.classList.add(cls);

        // Nurture plant emoji inside the soil cell
        let plantHtml = "";
        let plantClass = "";
        if (pages > 0) {
          if (pages <= 10) {
            plantHtml = "🌱";
            plantClass = "plant-sway";
          } else if (pages <= 30) {
            plantHtml = "🌿";
            plantClass = "plant-sway";
          } else if (pages <= 50) {
            plantHtml = "🌸";
            plantClass = "plant-pulse";
          } else {
            plantHtml = "👑";
            plantClass = "plant-pulse";
          }
          cell.innerHTML = `<span class="garden-plant ${plantClass}">${plantHtml}</span>`;
        }

        // Mouse Hover Tooltip Bindings
        cell.addEventListener("mouseenter", function (e) {
          showTooltip(e, iso, pages);
        });
        cell.addEventListener("mousemove", function (e) {
          positionTooltip(e);
        });
        cell.addEventListener("mouseleave", function () {
          hideTooltip();
        });

        // Click Selection Bindings
        cell.addEventListener("click", function () {
          createCellParticles(cell);
          updateDetailBadge(iso, pages);
        });
      });

      function showTooltip(e, dateStr, pages) {
        let plantName = "Empty Soil";
        if (pages > 0) {
          if (pages <= 10) plantName = "Young Sprout 🌱";
          else if (pages <= 30) plantName = "Growing Stem 🌿";
          else if (pages <= 50) plantName = "Blooming Flower 🌸";
          else plantName = "Golden Crown 👑";
        }

        const dateObj = new Date(dateStr + "T00:00:00");
        const formattedDate = dateObj.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        });

        tooltip.innerHTML = `
          <div style="font-weight:600; margin-bottom: 2px;">${formattedDate}</div>
          <div style="color: #7fc59f; font-weight: 500;">${pages} pages read</div>
          <div style="font-size: 0.65rem; opacity: 0.8; margin-top: 2px;">Garden: ${plantName}</div>
        `;
        tooltip.classList.add("visible");
        positionTooltip(e);
      }

      function positionTooltip(e) {
        tooltip.style.left = e.pageX + "px";
        tooltip.style.top = e.pageY + "px";
      }

      function hideTooltip() {
        tooltip.classList.remove("visible");
      }

      function updateDetailBadge(dateStr, pages) {
        if (!detailEl) return;

        const dateObj = new Date(dateStr + "T00:00:00");
        const formattedDate = dateObj.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        });

        detailEl.textContent = pages
          ? `${formattedDate} — ${pages} pages read`
          : `${formattedDate} — no reading logged`;

        // Spark pulse animation
        detailEl.style.animation = "none";
        void detailEl.offsetWidth; // Reflow reset
        detailEl.style.animation = "pulseGrow 0.35s ease-out";
      }
    })
    .catch(function (err) {
      console.error(err);
      grid.innerHTML = '<p class="text-secondary small mb-0 p-3">Could not load reading garden right now.</p>';
    });
});
