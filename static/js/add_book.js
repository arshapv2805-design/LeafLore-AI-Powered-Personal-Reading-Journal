document.addEventListener("DOMContentLoaded", function () {
  const input = document.getElementById("book-search");
  const resultsBox = document.getElementById("search-results");
  if (!input || !resultsBox) return;

  let debounceTimer;

  input.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    const query = input.value.trim();
    if (query.length < 2) {
      resultsBox.innerHTML = "";
      return;
    }
    // Show searching placeholder
    resultsBox.innerHTML = '<div class="list-group-item text-secondary small d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm text-success" role="status"></div>Searching...</div>';
    
    debounceTimer = setTimeout(function () {
      fetch("/books/api/search?q=" + encodeURIComponent(query))
        .then(function (res) {
          return res.json();
        })
        .then(renderResults)
        .catch(function () {
          resultsBox.innerHTML = "";
        });
    }, 400);
  });


  document.addEventListener("click", function (e) {
    if (!resultsBox.contains(e.target) && e.target !== input) {
      resultsBox.innerHTML = "";
    }
  });

  function renderResults(items) {
    if (items && items.error) {
      if (items.error === "quota_exceeded") {
        resultsBox.innerHTML = '<div class="list-group-item text-danger small"><i class="bi bi-exclamation-triangle-fill text-danger me-1"></i> Google Books quota limit exceeded (429). Search requires a free API key in your <code>.env</code> file. You can still type details manually below.</div>';
      } else {
        resultsBox.innerHTML = '<div class="list-group-item text-danger small"><i class="bi bi-exclamation-circle-fill text-danger me-1"></i> Failed to query Google Books API. Please type details manually.</div>';
      }
      return;
    }
    if (!items || !items.length) {
      resultsBox.innerHTML = '<div class="list-group-item text-secondary small">No matches found</div>';
      return;
    }
    resultsBox.innerHTML = items
      .map(function (item, i) {
        const cover = item.cover_url
          ? '<img src="' + item.cover_url + '" alt="" style="width:32px;height:48px;object-fit:cover;border-radius:2px;">'
          : '<div style="width:32px;height:48px;background:#eef0ea;border-radius:2px;"></div>';
        return (
          '<button type="button" class="list-group-item list-group-item-action d-flex gap-2 align-items-center" data-idx="' +
          i +
          '">' +
          cover +
          "<span><strong>" +
          escapeHtml(item.title) +
          "</strong><br><small class=\"text-secondary\">" +
          escapeHtml(item.author) +
          "</small></span></button>"
        );
      })
      .join("");

    resultsBox.querySelectorAll("button[data-idx]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        fillForm(items[Number(btn.dataset.idx)]);
      });
    });
  }

  function fillForm(item) {
    document.getElementById("title").value = item.title || "";
    document.getElementById("author").value = item.author || "";
    if (item.total_pages) document.getElementById("total_pages").value = item.total_pages;
    if (item.genre) {
      const genreSelect = document.getElementById("genre");
      if (genreSelect) {
        genreSelect.value = item.genre;
      }
    }
    document.getElementById("cover_url").value = item.cover_url || "";
    document.getElementById("description").value = item.description || "";
    resultsBox.innerHTML = "";
    input.value = item.title;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }
});
