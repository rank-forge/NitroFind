/**
 * NitroFind — SPA controller (Phase 8, Plan 02)
 *
 * Vanilla browser APIs only — no npm, no CDN, no framework.
 *
 * UI states (driven by document.body.dataset.state):
 *   "home"    — centered logo + search box (ES warmup or idle)
 *   "results" — top bar, filter row, result list
 *   "article" — full-page article with back button
 *
 * Requirements covered:
 *   SRCH-01  debounced search (300ms, no button press)
 *   SRCH-02  highlighted result rows (ES <b> tags in excerpt, excerpt-only)
 *   SRCH-03  article view (textContent body, no new tab)
 *   SRCH-04  persistent filters (module-level state, re-run on change)
 *   UIPL-02  result count + query time display
 *   UIPL-03  keyboard navigation (ArrowUp/Down/Enter/Escape)
 *   D-07     ES warmup polling (2s interval, enables input on status==ok)
 */

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

let uiState = "home";        // "home" | "results" | "article"
let selectedIndex = -1;      // keyboard nav cursor
let currentQuery = "";
let currentFilters = { manufacturer: "", era_bucket: "", body_style: "" };
let currentSort = "relevance";   // "relevance" | "date" | "size"
let currentResults = [];
let debounceTimer = null;
let abortController = null;

const DEBOUNCE_MS = 300;

// ---------------------------------------------------------------------------
// Cached DOM references (queried once at load — never inside render loops)
// ---------------------------------------------------------------------------

const searchInput     = document.getElementById("search-input");
const statusLine      = document.getElementById("status-line");
const searchInputResults = document.getElementById("search-input-results");
const resultsList     = document.getElementById("results-list");
const statsLine       = document.getElementById("stats-line");
const filterMfr       = document.getElementById("filter-manufacturer");
const filterEra       = document.getElementById("filter-era");
const filterBody      = document.getElementById("filter-body");
const backBtn         = document.getElementById("back-btn");
const sortBtns        = document.querySelectorAll(".sort-btn");
const articleTitle    = document.getElementById("article-title");
const articleSource   = document.getElementById("article-source");
const articleBody     = document.getElementById("article-body");

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

function transitionTo(newState) {
  document.body.dataset.state = newState;
  uiState = newState;
}

// ---------------------------------------------------------------------------
// Debounced search input handler (SRCH-01)
// ---------------------------------------------------------------------------

function handleSearchInput(input) {
  clearTimeout(debounceTimer);
  const q = input.value.trim();
  if (!q) {
    transitionTo("home");
    return;
  }
  debounceTimer = setTimeout(() => runSearch(q), DEBOUNCE_MS);
}

searchInput.addEventListener("input", () => handleSearchInput(searchInput));
searchInputResults.addEventListener("input", () => handleSearchInput(searchInputResults));

// ---------------------------------------------------------------------------
// Search fetch with AbortController (SRCH-01, Pitfall 4 stale-result race)
// ---------------------------------------------------------------------------

async function runSearch(q) {
  currentQuery = q;

  // Cancel any in-flight request before starting a new one (Pitfall 4)
  if (abortController) abortController.abort();
  abortController = new AbortController();

  const params = new URLSearchParams({ q, ...currentFilters });
  // Strip empty filter values — prevents sending manufacturer= (Pitfall 5)
  for (const [k, v] of [...params.entries()]) {
    if (!v) params.delete(k);
  }
  // Append sort param only when non-default (omit for relevance = ES default _score desc)
  if (currentSort && currentSort !== "relevance") {
    params.set("sort", currentSort);
  }

  try {
    const resp = await fetch(`/api/search?${params}`, {
      signal: abortController.signal,
    });
    if (!resp.ok) return;
    const results = await resp.json();
    if (!Array.isArray(results)) return;
    currentResults = results;
    selectedIndex = -1;   // reset keyboard cursor on new results
    renderResults(results);
    transitionTo("results");
  } catch (err) {
    if (err.name !== "AbortError") console.error("Search failed:", err);
  }
}

// ---------------------------------------------------------------------------
// Result rendering (SRCH-02, UIPL-02)
// ---------------------------------------------------------------------------

function renderResultCount(results) {
  if (results.length === 0) {
    statsLine.textContent = "No results";
  } else {
    const took = results[0].took_ms;
    statsLine.textContent = `${results.length} results (${(took / 1000).toFixed(2)}s)`;
  }
}

function renderResults(results) {
  renderResultCount(results);

  resultsList.innerHTML = "";
  results.forEach((r, i) => {
    const item = document.createElement("div");
    item.className = "result-item";
    item.dataset.index = i;

    const title = document.createElement("div");
    title.className = "result-title";
    title.textContent = r.title;              // textContent — untrusted field

    const meta = document.createElement("div");
    meta.className = "result-meta";
    const domain = document.createElement("span");
    domain.className = "result-domain";
    domain.textContent = r.source_domain;     // textContent — untrusted field
    meta.appendChild(domain);

    const excerpt = document.createElement("div");
    excerpt.className = "result-excerpt";
    excerpt.innerHTML = r.excerpt || "";      // innerHTML ONLY — ES highlight <b> tags (D-10)

    item.appendChild(title);
    item.appendChild(meta);
    item.appendChild(excerpt);
    item.addEventListener("click", () => openArticle(r));
    resultsList.appendChild(item);
  });
}

// ---------------------------------------------------------------------------
// Article view (SRCH-03, D-05)
// ---------------------------------------------------------------------------

function openArticle(result) {
  articleTitle.textContent  = result.title;                          // textContent
  articleSource.textContent = result.source_domain;                  // textContent
  const htmlContent = result.body_html || "";
  if (htmlContent) {
    // innerHTML is intentional — renders <table>, <h2>, etc. (Phase 9, BUG-01).
    // Matches existing excerpt.innerHTML precedent (D-10). Scraper strips
    // <script>, <style>, and on* event handler attributes before storing.
    // Local single-user offline app — XSS attack surface is near-zero.
    articleBody.innerHTML = htmlContent;
  } else {
    // Fallback for articles without body_html (scraped before Phase 9)
    articleBody.textContent = result.body || "No content available.";
  }
  transitionTo("article");
}

backBtn.addEventListener("click", () => {
  transitionTo("results");
  // Query and filter state are preserved in module-level vars (D-05)
});

// ---------------------------------------------------------------------------
// Filter handlers (SRCH-04, D-06)
// ---------------------------------------------------------------------------

function onFilterChange() {
  currentFilters.manufacturer = filterMfr.value;
  currentFilters.era_bucket   = filterEra.value;
  currentFilters.body_style   = filterBody.value;
  if (currentQuery) runSearch(currentQuery);
}

filterMfr.addEventListener("change", onFilterChange);
filterEra.addEventListener("change", onFilterChange);
filterBody.addEventListener("change", onFilterChange);

function onSortChange(newSort) {
  currentSort = newSort;
  sortBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.sort === newSort));
  if (currentQuery) runSearch(currentQuery);
}

sortBtns.forEach(btn => btn.addEventListener("click", () => onSortChange(btn.dataset.sort)));

// ---------------------------------------------------------------------------
// Keyboard navigation (UIPL-03, D-11)
// ---------------------------------------------------------------------------

function updateSelection() {
  document.querySelectorAll(".result-item").forEach((el, i) => {
    el.classList.toggle("selected", i === selectedIndex);
  });
}

document.addEventListener("keydown", (e) => {
  if (uiState === "results") {
    if (e.key === "ArrowDown") {
      e.preventDefault();  // prevent page scroll (Pitfall 7)
      selectedIndex = Math.min(selectedIndex + 1, currentResults.length - 1);
      updateSelection();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();  // prevent page scroll (Pitfall 7)
      selectedIndex = Math.max(selectedIndex - 1, -1);
      updateSelection();
    } else if (e.key === "Enter" && selectedIndex >= 0) {
      openArticle(currentResults[selectedIndex]);
    }
  }
  // Escape works from any state
  if (e.key === "Escape") {
    searchInput.value = "";
    searchInputResults.value = "";
    currentQuery = "";        // prevent stale re-search on filter/sort change from home state
    currentResults = [];      // prevent stale keyboard nav after returning to home
    selectedIndex = -1;
    transitionTo("home");
  }
});

// ---------------------------------------------------------------------------
// ES warmup polling (D-07)
// ---------------------------------------------------------------------------

function startWarmupPolling() {
  searchInput.disabled = true;
  statusLine.textContent = "Starting up…";
  statusLine.style.opacity = "1";

  const pollId = setInterval(async () => {
    try {
      const resp = await fetch("/api/status");
      if (resp.ok) {
        const data = await resp.json();
        if (data.status === "ok") {
          clearInterval(pollId);
          searchInput.disabled = false;
          statusLine.style.opacity = "0";  // CSS transition fades it out
          searchInput.focus();
        }
      }
    } catch (_) { /* ES not yet up — keep polling */ }
  }, 2000);
}

// Kick off immediately on page load
startWarmupPolling();
