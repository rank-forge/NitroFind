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
let currentFilters = {
  manufacturer: "",
  era_bucket:   "",
  body_style:   "",
  year_from:    "",   // FILT-01
  year_to:      "",   // FILT-01
  country:      "",   // FILT-02
};
let currentSort = "relevance";   // "relevance" | "date" | "size"
let currentPage = 1;
let currentResults = [];
let debounceTimer = null;
let abortController = null;

const DEBOUNCE_MS = 300;
const TRANSITION_MIN_MS = 750;
const TRANSITION_MAX_MS = 1250;
const HISTORY_KEY = 'nitrofind-history';
const HISTORY_MAX = 10;

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
const filterYearFrom  = document.getElementById("filter-year-from");
const filterYearTo    = document.getElementById("filter-year-to");
const filterCountry   = document.getElementById("filter-country");
const backBtn         = document.getElementById("back-btn");
const prevBtn         = document.getElementById("prev-btn");
const nextBtn         = document.getElementById("next-btn");
const sortBtns        = document.querySelectorAll(".sort-btn");
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
const historyList     = document.getElementById("history-list");
const themeToggleBtn  = document.getElementById("theme-toggle");
const themeToggleBtnResults = document.getElementById("theme-toggle-results");

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
  debounceTimer = setTimeout(() => {
    currentPage = 1;
    runSearch(q);
  }, DEBOUNCE_MS);
}

searchInput.addEventListener("input", () => handleSearchInput(searchInput));
searchInputResults.addEventListener("input", () => handleSearchInput(searchInputResults));

// ---------------------------------------------------------------------------
// Search fetch with AbortController (SRCH-01, Pitfall 4 stale-result race)
// ---------------------------------------------------------------------------

async function runSearch(q) {
  currentQuery = q;
  addToHistory(q);   // HIST-01: write after empty-string guard resolves in handleSearchInput

  // Cancel any in-flight request before starting a new one (Pitfall 4)
  if (abortController) abortController.abort();
  abortController = new AbortController();

  const params = new URLSearchParams({ q, ...currentFilters, page: currentPage });
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
    const data = await resp.json();
    if (!data || !Array.isArray(data.results)) return;
    currentResults = data.results;
    selectedIndex = -1;   // reset keyboard cursor on new results
    renderResults(data.results);
    renderResultCount(data.total, data.took_ms);
    renderPagination(data.total, data.page);
    transitionTo("results");
  } catch (err) {
    if (err.name !== "AbortError") console.error("Search failed:", err);
  }
}

// ---------------------------------------------------------------------------
// Result rendering (SRCH-02, UIPL-02)
// ---------------------------------------------------------------------------

function renderResultCount(total, tookMs) {
  if (total === 0) {
    statsLine.textContent = "No results";
  } else {
    statsLine.textContent = `${total} results (${(tookMs / 1000).toFixed(2)}s)`;
  }
}

function renderResults(results) {
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
    item.addEventListener("click", () => openArticle(r, item));
    resultsList.appendChild(item);
  });
}

function renderPagination(total, page) {
  const pageSize = 10;  // must match PAGE_SIZE in server.py
  prevBtn.disabled = page <= 1;
  nextBtn.disabled = page * pageSize >= total;
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

// ---------------------------------------------------------------------------
// Item -> photo morph (FLIP): the clicked result card grows and crossfades
// into the dossier hero photo, so the transition reads as one continuous
// motion instead of a video overlay followed by a hard page swap.
// ---------------------------------------------------------------------------

const GHOST_MORPH_MS = 520;

function preloadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = resolve;
    img.onerror = reject;
    img.src = url;
  });
}

function createMorphGhost(itemEl) {
  const rect = itemEl.getBoundingClientRect();
  const ghost = document.createElement("div");
  ghost.className = "dossier-ghost";
  ghost.style.top = `${rect.top}px`;
  ghost.style.left = `${rect.left}px`;
  ghost.style.width = `${rect.width}px`;
  ghost.style.height = `${rect.height}px`;

  const label = document.createElement("div");
  label.className = "dossier-ghost-label";
  label.innerHTML = itemEl.innerHTML;   // clone the card's own already-sanitized markup

  const photoLayer = document.createElement("div");
  photoLayer.className = "dossier-ghost-photo";

  ghost.appendChild(label);
  ghost.appendChild(photoLayer);
  document.body.appendChild(ghost);

  return {
    async morphInto(targetImg, imageUrl) {
      const targetRect = targetImg.getBoundingClientRect();

      // Grow/move into position right away — never block the motion on the
      // network. The dossier itself is already fully rendered underneath,
      // so a slow image must not stall the transition (approved decision:
      // the page renders even if the photo hasn't finished loading).
      ghost.getBoundingClientRect(); // force layout before mutating the rect
      ghost.style.top = `${targetRect.top}px`;
      ghost.style.left = `${targetRect.left}px`;
      ghost.style.width = `${targetRect.width}px`;
      ghost.style.height = `${targetRect.height}px`;
      ghost.classList.add("morphed");

      // Crossfade the photo in only if it's ready before the morph itself
      // finishes; otherwise skip straight to destroy() and let the dossier's
      // own <img> onload handle the fade-in whenever it actually arrives.
      const imageReady = await Promise.race([
        preloadImage(imageUrl).then(() => true, () => false),
        delay(GHOST_MORPH_MS),
      ]);
      if (imageReady) {
        photoLayer.style.backgroundImage = `url("${imageUrl}")`;
        ghost.classList.add("photo-ready");
      }

      await delay(GHOST_MORPH_MS);
    },
    destroy() {
      ghost.remove();
    },
  };
}

async function openArticle(result, itemEl) {
  if (!result.article_id) return;

  const ghost = itemEl ? createMorphGhost(itemEl) : null;
  const transitionPromise = playSpeedometerTransition();
  let detail = null;

  try {
    const resp = await fetch(`/api/articles/${encodeURIComponent(result.article_id)}`);
    if (!resp.ok) throw new Error(`Article detail failed: ${resp.status}`);
    detail = await resp.json();
  } catch (err) {
    console.error("Article detail failed:", err);
    ghost?.destroy();
    endSpeedometerTransition();
    return;
  }

  await transitionPromise;
  renderArticle(detail);
  transitionTo("article");
  endSpeedometerTransition();

  if (ghost) {
    if (detail.hero_image_url) {
      await ghost.morphInto(articlePhoto, detail.hero_image_url);
    }
    ghost.destroy();
  }
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

// Wikipedia's rendered HTML carries its own inline `style="..."` attributes
// (grey infobox headers, fixed widths, etc.) that would otherwise win over
// our stylesheet. Stripping them lets .dossier-body's own CSS fully own the
// look — no !important overrides needed, and nothing here touches search.
function stripInlineStyles(container) {
  container.querySelectorAll("[style]").forEach((el) => el.removeAttribute("style"));
}

// Build a compact "on this page" jump list from the article's own top-level
// section headings so long entries stay easy to navigate.
function buildTableOfContents(container) {
  const headings = container.querySelectorAll("h2[id]");
  if (headings.length < 2) return;

  const toc = document.createElement("nav");
  toc.className = "dossier-toc";
  toc.setAttribute("aria-label", "On this page");

  const label = document.createElement("span");
  label.className = "dossier-toc-label";
  label.textContent = "On this page";
  toc.appendChild(label);

  headings.forEach((heading) => {
    const link = document.createElement("a");
    link.href = `#${heading.id}`;
    link.textContent = heading.textContent;
    toc.appendChild(link);
  });

  container.insertBefore(toc, container.firstChild);
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
    stripInlineStyles(articleBody);   // let our own CSS restyle the raw Wikipedia markup
    buildTableOfContents(articleBody);
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

prevBtn.addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage -= 1;
    runSearch(currentQuery);
  }
});

nextBtn.addEventListener("click", () => {
  currentPage += 1;
  runSearch(currentQuery);
});

// ---------------------------------------------------------------------------
// Filter handlers (SRCH-04, D-06)
// ---------------------------------------------------------------------------

function onFilterChange() {
  currentFilters.manufacturer = filterMfr.value;
  currentFilters.era_bucket   = filterEra.value;
  currentFilters.body_style   = filterBody.value;
  currentFilters.year_from    = filterYearFrom.value;   // FILT-01
  currentFilters.year_to      = filterYearTo.value;     // FILT-01
  currentFilters.country      = filterCountry.value;    // FILT-02
  currentPage = 1;
  if (currentQuery) runSearch(currentQuery);
}

filterMfr.addEventListener("change", onFilterChange);
filterEra.addEventListener("change", onFilterChange);
filterBody.addEventListener("change", onFilterChange);
filterYearFrom.addEventListener("change", onFilterChange);   // FILT-01: change not input (Pitfall 4)
filterYearTo.addEventListener("change", onFilterChange);     // FILT-01: change not input (Pitfall 4)
filterCountry.addEventListener("change", onFilterChange);    // FILT-02

function onSortChange(newSort) {
  currentSort = newSort;
  currentPage = 1;
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
      const itemEl = document.querySelectorAll(".result-item")[selectedIndex];
      openArticle(currentResults[selectedIndex], itemEl);
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
// Search history (HIST-01, HIST-02)
// ---------------------------------------------------------------------------

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch (_) {
    return [];
  }
}

function addToHistory(query) {
  let history;
  try {
    history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch (_) {
    history = [];
  }
  history = history.filter(q => q !== query);
  history.unshift(query);
  history = history.slice(0, HISTORY_MAX);
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch (_) { /* degrade silently — localStorage quota or private mode */ }
  renderHistory(history);
}

function renderHistory(history) {
  historyList.innerHTML = '';   // empties container structure — safe, no user data here
  history.forEach(query => {
    const li = document.createElement('li');
    li.className = 'history-item';
    li.textContent = query;     // textContent — NEVER innerHTML for user-supplied strings
    li.addEventListener('click', () => executeHistoryQuery(query));
    historyList.appendChild(li);
  });
  historyList.style.display = history.length ? 'block' : 'none';
}

function executeHistoryQuery(query) {
  searchInput.value = query;
  searchInputResults.value = query;
  currentPage = 1;
  runSearch(query);   // addToHistory() inside runSearch() moves item to front automatically
}

// ---------------------------------------------------------------------------
// Theme toggle (THME-01)
// ---------------------------------------------------------------------------

function applyThemeLabel() {
  const isDark = document.documentElement.dataset.theme === 'dark';
  const label = isDark ? 'Light' : 'Dark';
  if (themeToggleBtn) themeToggleBtn.textContent = label;
  if (themeToggleBtnResults) themeToggleBtnResults.textContent = label;
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme;
  const next = (current === 'dark') ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem('nitrofind-theme', next);
  } catch (_) { /* degrade silently */ }
  applyThemeLabel();
}

if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);
if (themeToggleBtnResults) themeToggleBtnResults.addEventListener('click', toggleTheme);

// ---------------------------------------------------------------------------
// ES warmup polling (D-07)
// ---------------------------------------------------------------------------

function startWarmupPolling() {
  searchInput.disabled = true;
  searchInputResults.disabled = true;   // disable results-view input during warmup
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
          searchInputResults.disabled = false;  // re-enable results-view input on ready
          statusLine.style.opacity = "0";  // CSS transition fades it out
          searchInput.focus();
        }
      }
    } catch (_) { /* ES not yet up — keep polling */ }
  }, 2000);
}

// Kick off immediately on page load
startWarmupPolling();

// History & theme init
renderHistory(loadHistory());
applyThemeLabel();
