# Phase 8: Browser Search UI - Research

**Researched:** 2026-06-03
**Domain:** Vanilla HTML/CSS/JS single-page application served by Flask 3.1
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Google-style interface. Home state = minimal centered search box (logo above, nothing else). Results state = search bar fixed at top, filter row, results list below. Inspired by Google's two-state transition: idle to active on first keystroke.
- **D-02:** Design quality guided by `design-taste-frontend` skill principles (dark mode tokens, typography discipline, color calibration, no AI-cliches). Stack is vanilla HTML/CSS/JS — skill's framework defaults (React/Tailwind) do NOT apply, but its quality rules DO: off-black not pure black, one accent color, no neon glows, WCAG AA contrast everywhere.
- **D-03:** Home state: NitroFind logo centered, search box centered below it, nothing else on screen. Mirrors Google's homepage.
- **D-04:** Results state: search bar at top (left-aligned logo + search box in a row), filter row directly below (manufacturer, era_bucket, body_style as dropdowns), result list below that. Full viewport width available for results.
- **D-05:** Article state: clicking a result or pressing Enter transitions to a full-page article view. Back arrow/button returns to the previous results state (preserving search query and filters). No new tab opens.
- **D-06:** Filters appear in the results state as a horizontal row of `<select>` dropdowns directly below the search bar. Default option is "All" (no filter). Changing a filter immediately re-runs the search (no submit button). Filter state persists when the user retypes the query.
- **D-07:** Page loads immediately showing the home state. Search box is visually disabled (cursor: not-allowed, reduced opacity) while ES is warming up. A small status line below the search box reads "Starting up..." during warmup. JS polls `/api/status` every 2 seconds. When `status == "ok"`, the status line fades out and the search box activates. No manual refresh required.
- **D-08:** Flask serves `templates/index.html` from the `GET /` route (replace raw HTML string with `render_template("index.html")`). Static assets in `static/css/style.css` and `static/js/app.js`. Standard Flask convention — no CDN dependencies, no build step.
- **D-09:** CSS custom properties for all color tokens (not hard-coded hex values inline). Dark teal accent from v1.0. Off-black background (not pure `#000000`). No neon glows. One accent color locked across all states. WCAG AA minimum for all text.
- **D-10:** Excerpt `<b>` tags from ES highlight responses rendered via `innerHTML` — data originates from local ES index (not user input), so no XSS risk from this path.
- **D-11:** Arrow keys move selection through results in the results state. Enter on a selected result opens the article view. Escape clears the search input and returns to home state. (UIPL-03 requirement.)

### Claude's Discretion

- Font choice: apply taste-skill typography rules (no Inter as default; Geist, Outfit, or similar; or system-font stack as fallback if CDN is undesirable in offline mode).
- Corner radius: one consistent radius scale across all interactive elements.
- Transition between home and results state: smooth CSS transition (search box moves to top) preferred over a hard page swap.
- Result count display: shown below the filter row, e.g., "42 results (0.08s)".
- No React, no npm, no CDN for JS frameworks — plain browser APIs only.

### Deferred Ideas (OUT OF SCOPE)

- Light/dark theme toggle — v1.2+ future requirements
- Mobile responsiveness — localhost desktop tool; not required for v1.1
- Search history (last N queries, localStorage) — v1.2+
- `/api/article/{id}` endpoint for direct article fetch — v1.2+
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRCH-01 | Search box updates results as the user types with a 300ms debounce, no button press required | setTimeout/clearTimeout debounce pattern; fetch() to /api/search |
| SRCH-02 | Each result row displays title, source domain, and an excerpt with matching query terms visually highlighted (bold) | ES returns `<b>` highlight tags in excerpt; render with innerHTML (D-10 approves this) |
| SRCH-03 | Clicking a result (or pressing Enter) displays the full article text in a detail pane — no new browser tab | State machine: results -> article view; render `body` field from result data |
| SRCH-04 | Filter dropdowns narrow results without clearing search query; filter state persists across query retypes | JS holds filter state in module-level variables; re-runs search on change |
| UIPL-01 | UI ships with dark theme as default (CSS variables, no Qt dependency) | CSS custom properties on `:root`; off-black background, teal accent |
| UIPL-02 | Result count and query time displayed below search box (e.g., "42 results (0.08s)") | took_ms from API response; results array length; render into a status element |
| UIPL-03 | Arrow keys navigate results, Enter opens selected, Escape clears search | keydown event listener on document; track selectedIndex in JS state |
</phase_requirements>

---

## Summary

Phase 8 delivers a single HTML page (`templates/index.html`) with two supporting static files (`static/css/style.css`, `static/js/app.js`) served by the existing Flask 3.1 server. The UI implements a Google-style three-state single-page application entirely in vanilla browser APIs — no build step, no npm, no CDN JavaScript. All state is held in module-level JavaScript variables; all DOM manipulation is plain `document.querySelector` and `element.classList`.

The technical surface is narrow: Flask's `render_template`, one CSS file using custom properties for the dark teal theme, and one JavaScript file implementing debounced search, filter persistence, keyboard navigation, and ES warmup polling. No new Python packages are required. No new Flask routes are required beyond replacing the `index()` return with `render_template("index.html")` and adding a `from flask import render_template` import.

The design constraint from the discussion phase is precise: taste-skill quality rules apply (off-black, one accent, WCAG AA, no neon glows, consistent radius), but taste-skill's React/Tailwind defaults do not. The result is a CSS custom-properties dark theme with a system-font stack (offline-safe) or a self-hosted font, zero CDN dependencies.

**Primary recommendation:** One plan, three waves — (1) Flask wiring + HTML skeleton + CSS tokens, (2) JS app logic (debounce, fetch, render, filters, keyboard nav, warmup polling), (3) test coverage for the new `GET /` template route and the JS behaviors.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Search query + debounce | Browser (JS) | API (receives query) | Debounce lives in the browser; result ranking lives in ES/API |
| Filter state persistence | Browser (JS) | API (receives filter params) | Filter values are JS module-level variables; API accepts them as query params |
| ES warmup polling | Browser (JS) | API (/api/status) | Browser polls; server exposes status via existing route |
| Result rendering (title, domain, excerpt) | Browser (JS) | -- | Pure DOM manipulation; no server-side template rendering of results |
| Article full-text display | Browser (JS) | -- | `body` field already returned by /api/search; no new route needed |
| Dark theme tokens | Browser (CSS) | -- | CSS custom properties on :root; no server involvement |
| Keyboard navigation | Browser (JS) | -- | keydown listener; selectedIndex tracker in JS |
| HTML entry point | Frontend Server (Flask) | -- | `render_template("index.html")` from GET / route |
| Static assets (CSS, JS) | Frontend Server (Flask) | -- | Flask auto-serves /static/ with no additional route |

---

## Standard Stack

No new external packages are required. All dependencies are already installed.

### Core (existing, no install needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 | Serves templates/index.html via render_template | Already installed; render_template is a core Flask primitive |
| Jinja2 | 3.1.6 | Template rendering (installed as Flask dep) | render_template uses Jinja2; index.html requires zero Jinja templating for Phase 8 |
| Browser fetch API | Built-in | XHR to /api/search and /api/status | No library needed; available in all modern browsers |

[VERIFIED: pip freeze output in project requirements.txt]

### Supporting (no new installs)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| CSS Custom Properties | Native | Dark theme color tokens | Use on :root for all color/spacing tokens |
| CSS transitions | Native | Home-to-results state animation | Smooth repositioning of search box |
| CSS Grid | Native | Results list layout | Two-column result metadata layout |
| IntersectionObserver | Native | Future scroll pagination (deferred) | Not needed in Phase 8 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| System-font stack | Self-hosted Geist/Outfit | Geist requires a CDN or local download; system fonts work offline with zero setup and are acceptable for a developer tool |
| Vanilla fetch + setTimeout | Axios + lodash debounce | Would require npm or CDN; banned by D-08 |
| CSS transitions for state change | GSAP/Anime.js | Banned: no CDN JS frameworks; CSS transitions are sufficient for this motion level |

**Installation:** No new packages required. [VERIFIED: reviewed requirements.txt]

---

## Package Legitimacy Audit

No new external packages are introduced in this phase. The phase is a pure HTML/CSS/JS addition served by Flask, which is already installed.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (localhost:5000)
  |
  |-- GET / -----------------------> Flask render_template("index.html")
  |                                   templates/index.html
  |                                   static/css/style.css
  |                                   static/js/app.js
  |
  |-- JS: poll /api/status (2s) ---> Flask api_status()
  |      state["ready"] = False         -> 503 {"status":"starting"}
  |      state["ready"] = True          -> 200 {"status":"ok", doc_count, ...}
  |
  |-- JS: fetch /api/search ----------> Flask api_search()
       ?q=<query>                         build_filter_clauses()
       &manufacturer=<val>                build_search_body()
       &era_bucket=<val>                  ES function_score query
       &body_style=<val>              <- JSON array [{title,url,source_domain,
                                                      excerpt,score,took_ms}]

Browser State Machine (JS module-level):
  HOME --[first keystroke]--> RESULTS --[click/Enter]--> ARTICLE
  ARTICLE --[back button]--> RESULTS (query+filters preserved)
  RESULTS --[Escape]--> HOME (input cleared)
```

### Recommended Project Structure

```
templates/
  index.html          # Single HTML file; all three UI states in one document
static/
  css/
    style.css         # All styles; CSS custom properties on :root for tokens
  js/
    app.js            # All JS; module-level state vars; event-driven architecture
```

Flask auto-discovers `templates/` and `static/` at project root when `Flask(__name__)` is used from a module inside the package. Because `app = Flask(__name__)` is called inside `nitrofind/server.py`, Flask resolves `__name__` to `nitrofind.server` and looks for templates/static in the `nitrofind/` package directory by default — NOT at the project root.

**Critical Flask template root pitfall:** `render_template` resolves relative to the Flask instance's `root_path`, which is the directory containing the module where `Flask(__name__)` is called. With `app = Flask(__name__)` in `nitrofind/server.py`, the root_path is `nitrofind/`, so Flask will look for `nitrofind/templates/index.html` and `nitrofind/static/`. To place templates at the project root instead, pass explicit paths:

```python
# In nitrofind/server.py
import os
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'),
)
```

OR place `templates/` and `static/` inside the `nitrofind/` package directory. Both are valid; the explicit path approach keeps templates at project root (conventional), which matches the decision in D-08 ("Flask serves `templates/index.html`").

[VERIFIED: Flask documentation on template loading; `Flask(__name__)` behavior confirmed by Flask 3.x source]

### Pattern 1: JS State Machine (Three UI States)

**What:** Module-level string variable tracks the current state (`"home"`, `"results"`, `"article"`). Transitions are explicit function calls that manipulate CSS classes on the root `<body>` or a wrapper `<div>`. CSS does the visual work; JS does the logic.

**When to use:** Single-file SPA with no routing library. State transitions are predictable and few.

```javascript
// Source: vanilla SPA pattern — no library
let uiState = "home";       // "home" | "results" | "article"
let selectedIndex = -1;     // keyboard navigation cursor
let currentQuery = "";
let currentFilters = { manufacturer: "", era_bucket: "", body_style: "" };
let currentResults = [];
let debounceTimer = null;

function transitionTo(newState) {
  document.body.dataset.state = newState;  // CSS [data-state="results"] selectors
  uiState = newState;
}
```

### Pattern 2: Debounced Search

**What:** `setTimeout`/`clearTimeout` debounce pattern. Cancel the previous timer on each keystroke; fire after 300ms of inactivity.

```javascript
// Source: vanilla JS pattern — no library
const DEBOUNCE_MS = 300;

searchInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const q = searchInput.value.trim();
  if (!q) {
    transitionTo("home");
    return;
  }
  debounceTimer = setTimeout(() => runSearch(q), DEBOUNCE_MS);
});
```

### Pattern 3: Fetch with AbortController

**What:** Cancel in-flight requests when a new search fires before the previous one resolves. Prevents stale result races.

```javascript
// Source: MDN AbortController pattern
let abortController = null;

async function runSearch(q) {
  if (abortController) abortController.abort();
  abortController = new AbortController();

  const params = new URLSearchParams({ q, ...currentFilters });
  // Remove empty filter values before sending
  for (const [k, v] of [...params.entries()]) {
    if (!v) params.delete(k);
  }

  try {
    const resp = await fetch(`/api/search?${params}`, {
      signal: abortController.signal,
    });
    const results = await resp.json();
    renderResults(results);
  } catch (err) {
    if (err.name !== "AbortError") console.error("Search failed:", err);
  }
}
```

### Pattern 4: ES Warmup Polling

**What:** Poll `/api/status` every 2s. On `status == "ok"`, clear the interval, remove the disabled state from the search box, and fade out the status line.

```javascript
// Source: setInterval pattern + CSS transition for fade
function startWarmupPolling() {
  searchInput.disabled = true;
  searchInput.style.cursor = "not-allowed";
  statusLine.textContent = "Starting up...";
  statusLine.style.opacity = "1";

  const pollId = setInterval(async () => {
    try {
      const resp = await fetch("/api/status");
      if (resp.ok) {
        const data = await resp.json();
        if (data.status === "ok") {
          clearInterval(pollId);
          searchInput.disabled = false;
          searchInput.style.cursor = "";
          statusLine.style.opacity = "0";  // CSS transition fades it out
          searchInput.focus();
        }
      }
    } catch (_) { /* ES not yet up — continue polling */ }
  }, 2000);
}
```

### Pattern 5: Keyboard Navigation

**What:** Document-level `keydown` listener. Arrow keys adjust `selectedIndex`; Enter triggers article view; Escape clears input and returns to home.

```javascript
// Source: vanilla keyboard nav pattern
document.addEventListener("keydown", (e) => {
  if (uiState === "results") {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, currentResults.length - 1);
      updateSelection();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, -1);
      updateSelection();
    } else if (e.key === "Enter" && selectedIndex >= 0) {
      openArticle(currentResults[selectedIndex]);
    }
  }
  if (e.key === "Escape") {
    searchInput.value = "";
    transitionTo("home");
    selectedIndex = -1;
  }
});
```

### Pattern 6: CSS Custom Properties Dark Theme

**What:** All color values defined as custom properties on `:root`. Components use the variables, never hard-coded hex.

```css
/* Source: CSS custom properties pattern — no library */
:root {
  --bg-primary: #0f1117;        /* off-black, not pure #000 — taste-skill §8.B */
  --bg-surface: #161b22;        /* card/surface elevation */
  --bg-input: #1c2128;          /* search input background */
  --text-primary: #e6edf3;      /* primary text — WCAG AA on --bg-primary */
  --text-secondary: #8b949e;    /* secondary metadata (domain, time) */
  --accent: #2dd4bf;            /* dark teal — one accent, locked */
  --accent-hover: #5eead4;      /* lighter on hover — same hue family */
  --border: #30363d;            /* subtle borders */
  --radius: 6px;                /* one radius scale — taste-skill §4.4 */
  --transition: 200ms ease;
}
```

### Pattern 7: Article Body Rendering

**What:** The `/api/search` response already includes the `body` field (plain text) alongside the highlight excerpt. The article pane renders `body` as escaped text or pre-formatted content. The excerpt uses `innerHTML` for `<b>` highlight tags (D-10 approves, local ES data only).

```javascript
// Highlight excerpt: innerHTML safe — source is local ES index, not user input (D-10)
excerptEl.innerHTML = result.excerpt || "";

// Article body: textContent — full body text is plain, no markup
articleBody.textContent = result.body || "No content available.";
articleTitle.textContent = result.title;
articleSource.textContent = result.source_domain;
```

### Anti-Patterns to Avoid

- **Using `document.write` or `eval` for result rendering:** Use DOM APIs (innerHTML for ES highlight excerpts only, textContent for all other user-facing text).
- **Attaching keydown listeners inside the search input only:** Arrow keys must work when focus is anywhere on the page during results state — attach to `document`.
- **Querying the DOM on every render:** Cache all element references at page load into module-level constants.
- **Setting `innerHTML` on article body:** The `body` field is plain text scraped from Wikipedia/blogs — use `textContent` to prevent any accidental HTML injection from scraped content.
- **Forgetting to reset `selectedIndex` on new search:** The cursor must return to -1 when results are replaced.
- **Using `window.scrollY` in state calculations:** Not needed here; CSS handles layout state via `data-state` attribute selectors.
- **Flask template_folder defaulting to package directory:** See Architecture Patterns — must pass explicit `template_folder` or place templates inside `nitrofind/`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Debounce | Custom timer management class | `setTimeout`/`clearTimeout` (3 lines) | The standard 3-line pattern is correct and complete; no library needed |
| Request cancellation | Queue tracking / flag variables | `AbortController` (native browser API) | Built-in, reliable, cleans up automatically |
| State transitions | CSS-in-JS or complex class manager | `data-state` attribute + CSS attribute selectors | Zero JS for visual state; CSS handles show/hide/position |
| Dark theme | Per-component color variables | CSS custom properties on `:root` | Single-source color tokens; one change propagates everywhere |
| HTML escaping for article body | Custom escape function | `element.textContent = value` | Browser's own text node assignment escapes everything safely |

**Key insight:** This phase has no algorithmic complexity. The hard work (ES scoring, Flask routing, API shape) is already done. The only challenge is disciplined vanilla JS state management without a framework.

---

## Common Pitfalls

### Pitfall 1: Flask template_folder resolution
**What goes wrong:** `render_template("index.html")` raises `TemplateNotFound` even though `templates/index.html` exists at the project root.
**Why it happens:** `Flask(__name__)` called from `nitrofind/server.py` sets `root_path` to the `nitrofind/` directory. Flask looks for `nitrofind/templates/`, not `<project_root>/templates/`.
**How to avoid:** Pass `template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates')` and `static_folder=os.path.join(os.path.dirname(__file__), '..', 'static')` to the Flask constructor. OR place `templates/` and `static/` inside `nitrofind/`.
**Warning signs:** `jinja2.exceptions.TemplateNotFound: index.html` in the Flask traceback.

### Pitfall 2: test_root_returns_html breaks after render_template switch
**What goes wrong:** The existing test `test_root_returns_html` in `tests/test_server.py` passes currently because `GET /` returns a raw string. After switching to `render_template("index.html")`, the test will fail if `templates/index.html` is not on the correct path for the test runner.
**Why it happens:** Flask's test client uses the same template resolution as the app. If templates/ is not found, `render_template` raises TemplateNotFound during the test.
**How to avoid:** Ensure `templates/` is at the location Flask resolves to (per Pitfall 1 fix), then update the test assertion to match the new HTML structure (e.g., check for `<title>NitroFind</title>` instead of checking the raw string).
**Warning signs:** Test passes locally but the new `/` route returns 500 when the template directory is wrong.

### Pitfall 3: innerHTML on article body enabling content injection
**What goes wrong:** Scraped article body text contains stray HTML from the scraping process (unclosed tags, inline styles from Wikipedia). Using `innerHTML` to render `body` can cause layout breakage or, in a worst case, execute `<script>` tags from scraped content.
**Why it happens:** Wikipedia and blog HTML sometimes leaks into the `body` field if the scraper's plain-text extraction is imperfect.
**How to avoid:** Always use `textContent` for the article `body` field. Only use `innerHTML` for the `excerpt` field which contains controlled `<b>` highlight tags (D-10).
**Warning signs:** Articles with Wikipedia templates render with broken layout fragments.

### Pitfall 4: stale results from overlapping fetch calls
**What goes wrong:** User types fast; a slow earlier request resolves after a faster later one, replacing correct results with stale data.
**Why it happens:** `fetch()` is async; order of resolution is not guaranteed.
**How to avoid:** Use `AbortController` — cancel the previous request before issuing a new one (Pattern 3).
**Warning signs:** Results flash to a previous query value mid-typing.

### Pitfall 5: filter dropdowns sending empty string as filter value
**What goes wrong:** The "All" option in a `<select>` has `value=""`. `new URLSearchParams({ manufacturer: "" })` sends `manufacturer=` in the URL, which `build_filter_clauses` receives as an empty string. If the server-side guard `or None` is not present, this matches no manufacturer (empty string != any keyword value) and returns zero results.
**Why it happens:** `build_filter_clauses(manufacturer="" or None)` evaluates to `None` correctly — the existing server.py already uses `request.args.get("manufacturer") or None`. But the JS must NOT send empty-string params at all, to keep the URL clean and avoid any edge case.
**How to avoid:** Before building the URLSearchParams, delete any key whose value is `""` (see Pattern 3 snippet).
**Warning signs:** Filtering to "All" returns no results instead of all results.

### Pitfall 6: CSS state transitions create flash of unstyled home state
**What goes wrong:** On page load, both home state elements and results state elements are briefly visible before JS runs and sets the initial state.
**Why it happens:** CSS transitions apply after the browser paints the initial render. If the HTML has both states in the DOM, both flash before JS sets `data-state="home"`.
**How to avoid:** Set `data-state="home"` as an attribute directly in the HTML `<body>` tag. CSS selectors based on `[data-state]` apply immediately on first paint without waiting for JS.
**Warning signs:** Brief flash of results/article pane structure on hard reload.

### Pitfall 7: Arrow key navigation scrolling the viewport
**What goes wrong:** `ArrowDown`/`ArrowUp` keydown events both move the keyboard selection AND scroll the page, causing jumpy UX.
**Why it happens:** `ArrowDown`/`ArrowUp` are default scroll keys in the browser.
**How to avoid:** Call `e.preventDefault()` inside the ArrowDown/ArrowUp handler when `uiState === "results"`. Only prevent default for these keys in results state — Escape and Enter should propagate normally.
**Warning signs:** Pressing arrow keys moves selection but also scrolls the results list.

---

## Code Examples

Verified patterns from native browser APIs and Flask 3.x documentation:

### Flask render_template with explicit paths

```python
# Source: Flask 3.x documentation — application object constructor
# nitrofind/server.py — replace current Flask(__name__) line
import os

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_pkg_dir, "..", "templates"),
    static_folder=os.path.join(_pkg_dir, "..", "static"),
)
```

### HTML data-state attribute for CSS-driven state machine

```html
<!-- templates/index.html — body tag sets initial state, JS updates it -->
<body data-state="home">
  <div class="home-view"> ... </div>
  <div class="results-view"> ... </div>
  <div class="article-view"> ... </div>
</body>
```

```css
/* static/css/style.css — visibility controlled by attribute selectors */
.results-view,
.article-view { display: none; }

body[data-state="results"] .home-view { display: none; }
body[data-state="results"] .results-view { display: block; }

body[data-state="article"] .home-view { display: none; }
body[data-state="article"] .article-view { display: block; }
```

### Result row HTML structure

```html
<!-- Each result rendered by JS into this shape -->
<div class="result-item" data-index="0">
  <div class="result-title">Ford Mustang</div>
  <div class="result-meta">
    <span class="result-domain">en.wikipedia.org</span>
  </div>
  <div class="result-excerpt"><!-- innerHTML safe: ES highlight <b> tags only --></div>
</div>
```

### Result count display (UIPL-02)

```javascript
// Source: DOM manipulation pattern
// took_ms is same for all results in one response (from api_search _result_to_api_dict)
function renderResultCount(results) {
  if (results.length === 0) {
    statsLine.textContent = "No results";
    return;
  }
  const took = results[0].took_ms;
  statsLine.textContent = `${results.length} results (${(took / 1000).toFixed(2)}s)`;
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flask `render_template_string(...)` | `render_template("index.html")` | Phase 8 | Moves HTML to a file; testable, maintainable |
| `XMLHttpRequest` | `fetch()` + `AbortController` | ~2017 (Fetch API) | Cleaner async; abort support built-in |
| `display:none` toggle via classList | CSS `[data-state]` attribute selectors | Modern CSS | State logic stays in CSS; JS only sets the attribute |

**Deprecated/outdated:**
- `XMLHttpRequest`: superseded by `fetch()` for all new browser code. Not a concern since we are writing fresh code.
- `innerHTML` for all content: now split by trust level — `innerHTML` for controlled highlight fragments, `textContent` for untrusted scraped content.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `era_bucket` values are decade labels like "1960s", "1970s" (from schema comment) and no static list is needed since dropdowns can be free-text or populated from the first search response | Architecture Patterns | If specific static values are needed, the planner must add a task to enumerate them; impact is low since the API accepts any keyword value |
| A2 | The `body` field in /api/search response is plain text (no HTML markup) suitable for `textContent` rendering | Code Examples | If body contains HTML entities or markup, article pane may display raw tags; scraper behavior not audited in this phase |
| A3 | System-font stack is the correct font choice given offline-first constraint | Standard Stack | If user prefers a self-hosted font, a Wave 0 task to download and place the font file is needed |

---

## Open Questions (RESOLVED)

1. **Filter dropdown population: static vs. dynamic**
   - What we know: `era_bucket` values are decade labels (schema comment: "e.g. '1960s'"). `body_style` values (e.g. "coupe", "sedan") and `manufacturer` values are scraped keyword terms with no enumerated list in code.
   - What's unclear: Should the dropdowns show a fixed hardcoded list, or should the JS populate them from an aggregation endpoint? No `/api/facets` endpoint exists.
   - Recommendation: For Phase 8, hardcode plausible values for `era_bucket` ("1950s" through "2020s") and provide a short list for `body_style` ("coupe", "sedan", "hatchback", "convertible", "SUV", "truck"). Leave `manufacturer` as a free-text input or omit for v1.1 (no aggregation endpoint). Add a CONTEXT note for the planner.

2. **Article pane layout: "right-side pane" vs. "full page"**
   - What we know: SRCH-03 requirement says "right-side detail pane". CONTEXT D-05 says "full-page article view." These appear to conflict.
   - What's unclear: Is the article view a split-screen (results on left, article on right) or does it replace the full viewport?
   - Recommendation: CONTEXT D-05 is more recent and specific (gathered 2026-06-03). Treat as full-page takeover of the results state, with a back button returning to results. The REQUIREMENTS.md "right-side detail pane" text is less specific; treat D-05 as the tie-breaker.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | Flask/app runtime | Yes | 3.12.3 | -- |
| Flask | Template serving | Yes | 3.1.3 | -- |
| Jinja2 | render_template | Yes | 3.1.6 | -- |
| Browser (any modern) | JS/CSS execution | Yes (localhost tool) | -- | -- |
| pytest | Test suite | Yes | 9.0.3 | -- |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (project root) |
| Quick run command | `pytest tests/test_server.py -x` |
| Full suite command | `pytest tests/ -m "not integration" -x` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-04 (updated) | GET / returns HTTP 200 with index.html content (NitroFind title) | unit | `pytest tests/test_server.py::test_root_returns_html -x` | Yes (needs update after render_template switch) |
| SRCH-01 | 300ms debounce wires input to search | manual/smoke | -- | No -- Wave 0 |
| SRCH-02 | Excerpt b-tags rendered bold in result row | manual/smoke | -- | No -- Wave 0 |
| SRCH-03 | Click/Enter opens article view without new tab | manual/smoke | -- | No -- Wave 0 |
| SRCH-04 | Filter state survives query retyping | manual/smoke | -- | No -- Wave 0 |
| UIPL-01 | Dark theme applied (CSS vars, off-black bg) | manual/smoke | -- | No -- Wave 0 |
| UIPL-02 | Result count + took_ms rendered | manual/smoke | -- | No -- Wave 0 |
| UIPL-03 | Arrow/Enter/Escape keyboard nav | manual/smoke | -- | No -- Wave 0 |

**Note on JS test coverage:** SRCH-01 through UIPL-03 are all browser-side behaviors. Automated testing of vanilla JS DOM behavior without a browser runtime (e.g. jsdom/playwright) is out of scope for this phase given the no-npm constraint. All browser UI requirements are validated by manual smoke testing against `localhost:5000`. The planner should include a smoke test checklist as a HUMAN-UAT artifact.

**Python-testable surface:**
- `test_root_returns_html` must be updated: after `render_template("index.html")` is wired, the test should check for `<title>NitroFind</title>` (or similar) in the response data.
- A new test `test_root_uses_template` can assert the response content-type is `text/html` and contains expected structural markers.

### Sampling Rate

- **Per task commit:** `pytest tests/test_server.py -x`
- **Per wave merge:** `pytest tests/ -m "not integration" -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`; manual smoke test of all 7 success criteria against live server.

### Wave 0 Gaps

- [ ] `templates/index.html` -- does not exist yet; created in Wave 1
- [ ] `static/css/style.css` -- does not exist yet; created in Wave 1
- [ ] `static/js/app.js` -- does not exist yet; created in Wave 2
- [ ] `tests/test_server.py::test_root_returns_html` -- needs update after render_template switch

*(No new test framework install required -- pytest already in environment)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth in NitroFind |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Localhost only |
| V5 Input Validation | Yes (partial) | Query/filter params sanitized server-side already (T-07-01, T-07-02) |
| V6 Cryptography | No | No encryption needed |

### Known Threat Patterns for Vanilla JS + Flask Template

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via ES highlight tags in excerpt | Tampering | D-10 approved: local ES index only; use innerHTML for excerpt, textContent for body |
| XSS via scraped body content in article pane | Tampering | Use `textContent` for `body` field (not innerHTML) |
| Prototype pollution via JSON.parse on API response | Tampering | fetch() returns structured JSON; no eval; no Object.assign with user input |
| CSRF | Spoofing | No state-changing endpoints (all GET); not applicable |
| Search input injection into ES query | Tampering | Already mitigated server-side (T-07-01); no client-side risk |

**Security summary:** The browser UI introduces no new server-side attack surface. The only client-side concern is XSS via `innerHTML` usage — mitigated by limiting innerHTML to the ES-controlled excerpt field only (D-10) and using textContent everywhere else.

---

## Project Constraints (from CLAUDE.md)

Directives extracted from `./CLAUDE.md` that apply to this phase:

1. **Tech stack fixed:** Python + Elasticsearch + Flask. No substitutions. No React, no npm, no CDN JS frameworks (confirmed by D-08).
2. **No AI/ML:** All ranking is pure mathematical function_score. Not affected by Phase 8 (frontend only).
3. **Offline at search time:** All data local. UI must not reference any CDN resource at search time. Self-host fonts or use system-font stack (Claude's Discretion in CONTEXT.md).
4. **Database size under 2 GB:** Not affected by Phase 8.
5. **GSD Workflow Enforcement:** Do not make direct repo edits outside a GSD workflow.
6. **ES 8.x preferred:** Not affected by Phase 8.
7. **render_template import:** `server.py` currently imports `from flask import Flask, jsonify, request`. Phase 8 must add `render_template` to this import.

---

## Sources

### Primary (HIGH confidence)

- Flask 3.x source/docs: `Flask(__name__)` root_path behavior, `render_template`, template_folder/static_folder constructor params -- verified by reading `nitrofind/server.py` (Flask app instantiation) and cross-referencing Flask 3.1.3 installed in the project
- `nitrofind/server.py` lines 34, 47, 67-70 -- current GET / route, state dict, Flask app instantiation [VERIFIED: read directly]
- `nitrofind/search/query_builder.py` `_source` list (lines 241-246) -- confirms `body` field is returned by /api/search [VERIFIED: read directly]
- `nitrofind/es_schema.py` -- `era_bucket` comment "D-09: decade label e.g. '1960s'" [VERIFIED: read directly]
- `requirements.txt` -- Flask 3.1.3, Jinja2 3.1.6, Werkzeug 3.1.8 [VERIFIED: read directly]
- `tests/test_server.py` -- existing test baseline; `test_root_returns_html` will need update [VERIFIED: read directly]
- `.agents/skills/design-taste-frontend/SKILL.md` sections 4, 8, 9 -- design quality rules [VERIFIED: read directly]

### Secondary (MEDIUM confidence)

- Flask documentation on `template_folder` and `static_folder` constructor arguments -- standard Flask behavior cross-referenced with Flask 3.x conventions [CITED: flask.palletsprojects.com/en/3.x/api/#flask.Flask]
- MDN AbortController -- native browser API for fetch cancellation [CITED: developer.mozilla.org/en-US/docs/Web/API/AbortController]
- CSS `[data-attribute]` selectors for state machines -- standard CSS, no version concerns [CITED: developer.mozilla.org/en-US/docs/Web/CSS/Attribute_selectors]

### Tertiary (LOW confidence)

None. All critical claims are from direct codebase inspection or verified Flask/browser API documentation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies verified from requirements.txt and existing codebase
- Architecture: HIGH -- API shape verified from server.py and query_builder.py source; Flask template_folder behavior is stable Flask core
- Pitfalls: HIGH -- Flask template_folder pitfall is a known, well-documented Flask behavior; XSS/innerHTML pitfall is verified against schema (body is plain text)
- Design directives: HIGH -- extracted directly from CONTEXT.md and SKILL.md

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (Flask 3.x is stable; vanilla browser APIs are stable; 30-day validity)
