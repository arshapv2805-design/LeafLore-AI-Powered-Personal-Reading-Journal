document.addEventListener("DOMContentLoaded", function () {
  const data = window.LEAFLORE_CHART_DATA || {};
  const palette = ["#206f19", "#c8762b", "#5b85b8", "#8a5fb0", "#b2542f", "#3f9a8c", "#a3a13a", "#8a8a82"];

  let textMuted = getComputedStyle(document.documentElement).getPropertyValue("--text-muted").trim() || "#8A978E";
  let borderColor = getComputedStyle(document.documentElement).getPropertyValue("--border-color").trim() || "#28322C";

  let pagesChartInstance = null;
  let genreChartInstance = null;

  function createPagesChart() {
    const barCanvas = document.getElementById("pagesChart");
    if (!barCanvas || !data.monthLabels || !data.monthLabels.length) return;

    const ctx = barCanvas.getContext("2d");
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, "#206f19");
    gradient.addColorStop(1, "rgba(32, 111, 25, 0.15)");

    pagesChartInstance = new Chart(barCanvas, {
      type: "bar",
      data: {
        labels: data.monthLabels,
        datasets: [
          {
            label: "Pages read",
            data: data.monthValues,
            backgroundColor: gradient,
            borderColor: "#206f19",
            borderWidth: 1.5,
            borderRadius: 6,
            maxBarThickness: 36,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { 
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(14, 18, 16, 0.95)",
            titleFont: { family: "Fraunces", size: 14, weight: "bold" },
            bodyFont: { family: "Inter", size: 12 },
            borderColor: borderColor,
            borderWidth: 1,
            padding: 10
          }
        },
        scales: { 
          x: { 
            grid: { color: borderColor },
            ticks: { color: textMuted, font: { family: "Inter", size: 11 } }
          },
          y: { 
            beginAtZero: true, 
            grid: { color: borderColor },
            ticks: { precision: 0, color: textMuted, font: { family: "Inter", size: 11 } } 
          } 
        },
      },
    });
  }

  function createGenreChart() {
    const genreCanvas = document.getElementById("genreChart");
    if (!genreCanvas || !data.genreLabels || !data.genreLabels.length) return;

    genreChartInstance = new Chart(genreCanvas, {
      type: "doughnut",
      data: {
        labels: data.genreLabels,
        datasets: [
          {
            data: data.genreValues,
            backgroundColor: palette.slice(0, data.genreLabels.length),
            borderWidth: 2,
            borderColor: borderColor,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { 
          legend: { 
            position: "bottom", 
            labels: { 
              boxWidth: 12, 
              color: textMuted,
              font: { family: "Inter", size: 11 } 
            } 
          },
          tooltip: {
            backgroundColor: "rgba(14, 18, 16, 0.95)",
            titleFont: { family: "Fraunces", size: 14, weight: "bold" },
            bodyFont: { family: "Inter", size: 12 },
            borderColor: borderColor,
            borderWidth: 1,
            padding: 10
          }
        },
      },
    });
  }

  createPagesChart();
  createGenreChart();

  // Listen to custom theme-changed events
  window.addEventListener("leaflore-theme-change", function () {
    setTimeout(() => {
      const rootStyle = getComputedStyle(document.documentElement);
      textMuted = rootStyle.getPropertyValue("--text-muted").trim();
      borderColor = rootStyle.getPropertyValue("--border-color").trim();

      if (pagesChartInstance) {
        pagesChartInstance.options.scales.x.grid.color = borderColor;
        pagesChartInstance.options.scales.x.ticks.color = textMuted;
        pagesChartInstance.options.scales.y.grid.color = borderColor;
        pagesChartInstance.options.scales.y.ticks.color = textMuted;
        pagesChartInstance.options.plugins.tooltip.borderColor = borderColor;
        pagesChartInstance.update();
      }

      if (genreChartInstance) {
        genreChartInstance.options.plugins.legend.labels.color = textMuted;
        genreChartInstance.options.plugins.tooltip.borderColor = borderColor;
        genreChartInstance.data.datasets[0].borderColor = borderColor;
        genreChartInstance.update();
      }
    }, 50);
  });
});
