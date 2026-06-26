document.addEventListener("DOMContentLoaded", function () {
  const box = document.getElementById("recommendations");
  if (!box) return;

  fetch("/dashboard/api/recommendations")
    .then(function (res) {
      return res.json();
    })
    .then(function (items) {
      if (!items.length) {
        box.innerHTML =
          '<p class="text-secondary small mb-0">Finish your first book to unlock personalized picks — ' +
          "recommendations learn from what you've already read.</p>";
        return;
      }
      box.innerHTML = items.map((item, idx) => renderCard(item, idx)).join("");
    })
    .catch(function (err) {
      console.error(err);
      box.innerHTML = '<p class="text-secondary small mb-0">Could not load recommendations right now.</p>';
    });

  function renderCard(item, idx) {
    const cover = item.cover_url
      ? '<img src="' + item.cover_url + '" alt="">'
      : '<div class="cover-placeholder"><i class="bi bi-book"></i></div>';

    const matchBadgeText =
      item.score !== null && item.score !== undefined
        ? Math.round(item.score * 100) + "% match"
        : "discover";

    const titleHtml =
      item.source === "shelf" && item.book_id
        ? '<a href="/books/' + item.book_id + '" class="text-decoration-none">' + escapeHtml(item.title) + "</a>"
        : escapeHtml(item.title);

    return (
      '<div class="recommendation-card" style="animation: fadeInUp 0.4s ease both; animation-delay: ' + (idx * 0.08) + 's;">' +
      '  <div class="rec-cover-wrapper">' +
      '    ' + cover +
      '    <div class="rec-hover-overlay">' +
      '      <div class="rec-overlay-content">' +
      '        <span class="badge match-percentage-badge">' + matchBadgeText + '</span>' +
      '        <p class="rec-reason-text mt-2">' + escapeHtml(item.reason || "") + '</p>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="rec-info mt-2">' +
      '    <h6 class="rec-title text-truncate" title="' + escapeHtml(item.title) + '">' + titleHtml + '</h6>' +
      '    <p class="rec-author text-muted small text-truncate mb-0">' + escapeHtml(item.author || "Unknown") + '</p>' +
      '  </div>' +
      '</div>'
    );
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }
});
