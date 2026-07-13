(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem('sems-theme');
  if (saved) root.setAttribute('data-theme', saved);

  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', function () {
      const current = root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
      const next = current === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      localStorage.setItem('sems-theme', next);
    });
  }

  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('is-open');
    });
  }

  // ---------------------------------------------------------- Global search
  const searchWrap = document.getElementById('global-search');
  const searchInput = document.getElementById('global-search-input');
  const resultsPanel = document.getElementById('global-search-results');

  if (searchInput) {
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
    });
  }

  if (searchInput && resultsPanel) {
    let debounceTimer = null;
    let activeIndex = -1;
    let flatResults = [];

    function closeDropdown() {
      resultsPanel.classList.remove('is-open');
      resultsPanel.innerHTML = '';
      activeIndex = -1;
      flatResults = [];
    }

    function renderGroups(groups, query) {
      flatResults = [];
      if (!groups.length) {
        resultsPanel.innerHTML = `<div class="search-dropdown-empty">No matches for "${query}"</div>`;
        resultsPanel.classList.add('is-open');
        return;
      }
      let html = '';
      groups.forEach(function (group) {
        html += `<div class="search-group-label">${group.label}</div>`;
        group.results.forEach(function (r) {
          flatResults.push(r);
          html += `<div class="search-result-item" data-url="${r.url}">
            <div class="search-result-title">${r.title}</div>
            <div class="search-result-subtitle">${r.subtitle}</div>
          </div>`;
        });
      });
      html += `<div class="search-dropdown-footer" id="search-see-all">See all results for "${query}"</div>`;
      resultsPanel.innerHTML = html;
      resultsPanel.classList.add('is-open');

      resultsPanel.querySelectorAll('.search-result-item').forEach(function (el) {
        el.addEventListener('click', function () { window.location.href = el.dataset.url; });
      });
      const seeAll = document.getElementById('search-see-all');
      if (seeAll) {
        seeAll.addEventListener('click', function () {
          window.location.href = '/dashboard/search/?q=' + encodeURIComponent(query);
        });
      }
    }

    function updateActiveHighlight() {
      const items = resultsPanel.querySelectorAll('.search-result-item');
      items.forEach((el, i) => el.classList.toggle('is-active', i === activeIndex));
      if (activeIndex >= 0 && items[activeIndex]) {
        items[activeIndex].scrollIntoView({ block: 'nearest' });
      }
    }

    searchInput.addEventListener('input', function () {
      const query = searchInput.value.trim();
      clearTimeout(debounceTimer);
      if (query.length < 2) { closeDropdown(); return; }
      debounceTimer = setTimeout(function () {
        fetch('/dashboard/search/api/?q=' + encodeURIComponent(query))
          .then(r => r.json())
          .then(data => renderGroups(data.groups, data.query))
          .catch(() => closeDropdown());
      }, 200);
    });

    searchInput.addEventListener('keydown', function (e) {
      if (!resultsPanel.classList.contains('is-open')) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, flatResults.length - 1);
        updateActiveHighlight();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, -1);
        updateActiveHighlight();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (activeIndex >= 0 && flatResults[activeIndex]) {
          window.location.href = flatResults[activeIndex].url;
        } else {
          window.location.href = '/dashboard/search/?q=' + encodeURIComponent(searchInput.value.trim());
        }
      } else if (e.key === 'Escape') {
        closeDropdown();
        searchInput.blur();
      }
    });

    document.addEventListener('click', function (e) {
      if (searchWrap && !searchWrap.contains(e.target)) closeDropdown();
    });
  }
})();
