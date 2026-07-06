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
let currentResults = [];
let debounceTimer = null;
let abortController = null;

const DEBOUNCE_MS = 300;
const TRANSITION_MIN_MS = 750;
const TRANSITION_MAX_MS = 1250;

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
const articleTitle    = document.getElementById("article-title");
const articleSource   = document.getElementById("article-source");
const articleBody     = document.getElementById("article-body");
const transitionOverlay = document.getElementById("transition-overlay");
const speedometerVideo  = document.getElementById("speedometer-video");
const articlePhoto      = document.getElementById("article-photo");
const articlePhotoPlaceholder = document.getElementById("article-photo-placeholder");
const articleEra        = document.getElementById("article-era");
const articleSummary    = document.getElementById("article-summary");
const articleSpecs      = document.getElementById("article-specs");

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

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function playSpeedometerTransition() {
  transitionOverlay.classList.add("active");
  speedometerVideo.currentTime = 0;

  const startedAt = performance.now();
  try {
    await speedometerVideo.play();
  } catch (_) {
    return delay(TRANSITION_MIN_MS);
  }

  await delay(TRANSITION_MAX_MS);
  speedometerVideo.pause();
  const elapsed = performance.now() - startedAt;
  if (elapsed < TRANSITION_MIN_MS) {
    await delay(TRANSITION_MIN_MS - elapsed);
  }
}

function endSpeedometerTransition() {
  transitionOverlay.classList.remove("active");
  speedometerVideo.pause();
}

async function openArticle(result) {
  if (!result.article_id) return;

  const transitionPromise = playSpeedometerTransition();
  let detail = null;

  try {
    const resp = await fetch(`/api/articles/${encodeURIComponent(result.article_id)}`);
    if (!resp.ok) throw new Error(`Article detail failed: ${resp.status}`);
    detail = await resp.json();
  } catch (err) {
    console.error("Article detail failed:", err);
    endSpeedometerTransition();
    return;
  }

  await transitionPromise;
  renderArticle(detail);
  transitionTo("article");
  requestAnimationFrame(endSpeedometerTransition);
}

function appendSpec(label, value) {
  if (value === null || value === undefined || value === "") return;

  const term = document.createElement("dt");
  term.textContent = label;
  const definition = document.createElement("dd");
  definition.textContent = String(value);

  articleSpecs.appendChild(term);
  articleSpecs.appendChild(definition);
}

function productionRange(detail) {
  if (detail.production_start && detail.production_end) {
    return `${detail.production_start}-${detail.production_end}`;
  }
  if (detail.production_start) return String(detail.production_start);
  if (detail.production_end) return String(detail.production_end);
  return "";
}

function renderArticle(detail) {
  articleTitle.textContent = detail.title || "";
  articleSource.textContent = detail.source_domain || "";
  articleEra.textContent = detail.era_bucket || "";
  articleSummary.textContent = detail.excerpt || "";

  articleSpecs.innerHTML = "";
  appendSpec("Maker", detail.manufacturer);
  appendSpec("Production", productionRange(detail));
  appendSpec("Body", detail.body_style);
  appendSpec("Origin", detail.country_of_origin);
  appendSpec("Words", detail.word_count);

  renderArticleImage(detail);

  if (detail.body_html) {
    // innerHTML is intentional — renders <table>, <h2>, etc. (Phase 9, BUG-01).
    // Matches existing excerpt.innerHTML precedent (D-10). Scraper strips
    // <script>, <style>, and on* event handler attributes before storing.
    // Local single-user offline app — XSS attack surface is near-zero.
    articleBody.innerHTML = detail.body_html;
  } else {
    articleBody.textContent = detail.body || "No content available.";
  }
}

function renderArticleImage(detail) {
  articlePhoto.classList.remove("loaded");
  articlePhoto.removeAttribute("src");
  articlePhoto.alt = detail.title ? `${detail.title} photo` : "Car photo";

  if (!detail.hero_image_url) {
    articlePhotoPlaceholder.dataset.state = "missing";
    return;
  }

  articlePhotoPlaceholder.dataset.state = "loading";
  articlePhoto.onload = () => {
    articlePhotoPlaceholder.dataset.state = "loaded";
    articlePhoto.classList.add("loaded");
  };
  articlePhoto.onerror = () => {
    articlePhotoPlaceholder.dataset.state = "missing";
    articlePhoto.classList.remove("loaded");
  };
  articlePhoto.src = detail.hero_image_url;
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
    transitionTo("home");
    selectedIndex = -1;
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
