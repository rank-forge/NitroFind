# Phase 8: Browser Search UI - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 5
**Analogs found:** 2 / 5 (templates/index.html, static/css/style.css, static/js/app.js have no codebase analog — they are the first HTML/CSS/JS files in the project)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `nitrofind/server.py` | server / route handler | request-response | `nitrofind/server.py` itself (modify) | exact — existing file |
| `templates/index.html` | view / HTML skeleton | request-response | none in codebase | no analog |
| `static/css/style.css` | stylesheet / design tokens | — | none in codebase | no analog |
| `static/js/app.js` | client-side SPA controller | event-driven | none in codebase | no analog |
| `tests/test_server.py` | unit test | request-response | `tests/test_server.py` itself (modify) | exact — existing file |

---

## Pattern Assignments

### `nitrofind/server.py` (modify: Flask constructor + render_template)

**Analog:** `nitrofind/server.py` — read in full above.

**Current Flask instantiation** (line 47):
```python
app = Flask(__name__)
```

**Pattern to replace it with** (from RESEARCH.md Code Examples, cross-verified against Flask 3.x docs):
```python
import os

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_pkg_dir, "..", "templates"),
    static_folder=os.path.join(_pkg_dir, "..", "static"),
)
```
Rationale: `Flask(__name__)` inside `nitrofind/server.py` resolves `root_path` to `nitrofind/`, not the project root. Explicit `template_folder` and `static_folder` paths are required to serve from `templates/` and `static/` at the project root (D-08, RESEARCH.md Pitfall 1).

**Current import line** (line 34):
```python
from flask import Flask, jsonify, request
```

**Pattern to replace it with** (add `render_template`):
```python
from flask import Flask, jsonify, render_template, request
```

**Current GET / route** (lines 67-70):
```python
@app.route("/")
def index():
    """GET / — NitroFind placeholder HTML (D-13)."""
    return "<h1>NitroFind</h1><p>Search UI coming in Phase 8.</p>"
```

**Pattern to replace the return with**:
```python
@app.route("/")
def index():
    """GET / — NitroFind search UI (Phase 8)."""
    return render_template("index.html")
```

**Module docstring update** — line 10 (`index` export description) and line 21 (`API-04` coverage note) should be updated to reflect the template route. Follow the existing docstring style: short phrase, no trailing period on the one-liner.

---

### `templates/index.html` (create: HTML skeleton, three-state SPA)

**No codebase analog.** This is the first HTML file in the project. Use patterns from RESEARCH.md Code Examples directly.

**HTML shell pattern** (from RESEARCH.md "HTML data-state attribute for CSS-driven state machine"):
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NitroFind</title>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body data-state="home">

  <!-- Home view: centered logo + search box -->
  <div class="home-view">
    <h1 class="logo">NitroFind</h1>
    <div class="search-wrap">
      <input id="search-input" type="search" placeholder="Search cars…" autocomplete="off" disabled>
      <p id="status-line">Starting up…</p>
    </div>
  </div>

  <!-- Results view: top bar + filters + results list -->
  <div class="results-view">
    <header class="top-bar">
      <span class="logo-small">NitroFind</span>
      <input id="search-input-results" type="search" placeholder="Search cars…" autocomplete="off">
    </header>
    <div class="filter-row">
      <select id="filter-manufacturer"><option value="">All manufacturers</option></select>
      <select id="filter-era">
        <option value="">All eras</option>
        <option value="1950s">1950s</option>
        <option value="1960s">1960s</option>
        <option value="1970s">1970s</option>
        <option value="1980s">1980s</option>
        <option value="1990s">1990s</option>
        <option value="2000s">2000s</option>
        <option value="2010s">2010s</option>
        <option value="2020s">2020s</option>
      </select>
      <select id="filter-body">
        <option value="">All body styles</option>
        <option value="coupe">Coupe</option>
        <option value="sedan">Sedan</option>
        <option value="hatchback">Hatchback</option>
        <option value="convertible">Convertible</option>
        <option value="SUV">SUV</option>
        <option value="truck">Truck</option>
      </select>
    </div>
    <p id="stats-line"></p>
    <div id="results-list"></div>
  </div>

  <!-- Article view: full-page article with back button -->
  <div class="article-view">
    <button id="back-btn" type="button">&#8592; Back</button>
    <h2 id="article-title"></h2>
    <p id="article-source"></p>
    <div id="article-body"></div>
  </div>

  <script src="/static/js/app.js"></script>
</body>
</html>
```

Key decisions baked in:
- `data-state="home"` on `<body>` at parse time — prevents flash of unstyled state (RESEARCH.md Pitfall 6).
- Search input starts `disabled` — JS enables it after warmup poll resolves (D-07).
- Static `era_bucket` and `body_style` options per RESEARCH.md Open Question 1 recommendation.
- `manufacturer` is an empty `<select>` with only "All" — no static list; leave free or populate dynamically.
- No CDN links anywhere — offline-safe (D-08, project constraint).

**Result row HTML** (generated by JS into `#results-list`; template for JS reference):
```html
<div class="result-item" data-index="0">
  <div class="result-title">Ford Mustang</div>
  <div class="result-meta">
    <span class="result-domain">en.wikipedia.org</span>
  </div>
  <div class="result-excerpt"><!-- innerHTML: ES <b> highlight tags only --></div>
</div>
```

---

### `static/css/style.css` (create: CSS custom properties + three-state layout)

**No codebase analog.** This is the first CSS file in the project.

**Color token pattern** (from RESEARCH.md Pattern 6; satisfies D-09, UIPL-01, taste-skill §4.2 and §8):
```css
:root {
  /* Off-black — taste-skill §8.B: never pure #000 */
  --bg-primary:    #0f1117;
  --bg-surface:    #161b22;
  --bg-input:      #1c2128;

  /* Text — WCAG AA on --bg-primary (D-09) */
  --text-primary:  #e6edf3;
  --text-secondary:#8b949e;

  /* One accent, locked — dark teal (D-09) */
  --accent:        #2dd4bf;
  --accent-hover:  #5eead4;

  /* Structure */
  --border:        #30363d;
  --radius:        6px;           /* one radius scale — taste-skill §4.4 */
  --transition:    200ms ease;
}
```

**State machine CSS** (from RESEARCH.md Code Examples "HTML data-state attribute"):
```css
/* Default: only home-view visible */
.results-view,
.article-view { display: none; }

body[data-state="results"] .home-view   { display: none; }
body[data-state="results"] .results-view { display: block; }

body[data-state="article"] .home-view   { display: none; }
body[data-state="article"] .results-view { display: none; }
body[data-state="article"] .article-view { display: block; }
```

**Typography** — system-font stack (offline-safe per D-08 / project offline constraint; taste-skill §4.1 "Geist or system-font stack as fallback"):
```css
body {
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
               "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  margin: 0;
}
```

**Warmup disabled state** (D-07):
```css
#search-input:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

#status-line {
  font-size: 0.8rem;
  color: var(--text-secondary);
  transition: opacity var(--transition);
}
```

**Selected result highlight** (D-11 keyboard nav):
```css
.result-item.selected {
  background-color: var(--bg-surface);
  border-left: 2px solid var(--accent);
}
```

**Result excerpt bold** — ES `<b>` tags rendered bold (SRCH-02):
```css
.result-excerpt b {
  color: var(--text-primary);
  font-weight: 600;
}
```

---

### `static/js/app.js` (create: SPA state machine, debounce, fetch, keyboard nav)

**No codebase analog.** This is the first JavaScript file in the project.

All patterns come from RESEARCH.md Patterns 1–7. Extract per-pattern below for planner reference.

**Module-level state** (RESEARCH.md Pattern 1):
```javascript
// Module-level state — no framework, no closures needed
let uiState = "home";       // "home" | "results" | "article"
let selectedIndex = -1;     // keyboard nav cursor
let currentQuery = "";
let currentFilters = { manufacturer: "", era_bucket: "", body_style: "" };
let currentResults = [];
let debounceTimer = null;
let abortController = null;
```

**Cached DOM references** — cache all at load (RESEARCH.md anti-pattern: never query DOM on every render):
```javascript
const searchInput     = document.getElementById("search-input");
const statusLine      = document.getElementById("status-line");
const resultsList     = document.getElementById("results-list");
const statsLine       = document.getElementById("stats-line");
const filterMfr       = document.getElementById("filter-manufacturer");
const filterEra       = document.getElementById("filter-era");
const filterBody      = document.getElementById("filter-body");
const backBtn         = document.getElementById("back-btn");
const articleTitle    = document.getElementById("article-title");
const articleSource   = document.getElementById("article-source");
const articleBody     = document.getElementById("article-body");
```

**State transition** (RESEARCH.md Pattern 1):
```javascript
function transitionTo(newState) {
  document.body.dataset.state = newState;
  uiState = newState;
}
```

**Debounced search** (RESEARCH.md Pattern 2; 300ms matches existing PyQt UI timing, SRCH-01):
```javascript
const DEBOUNCE_MS = 300;

searchInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const q = searchInput.value.trim();
  if (!q) { transitionTo("home"); return; }
  debounceTimer = setTimeout(() => runSearch(q), DEBOUNCE_MS);
});
```

**Fetch with AbortController** (RESEARCH.md Pattern 3; prevents stale result races, Pitfall 4):
```javascript
async function runSearch(q) {
  currentQuery = q;
  if (abortController) abortController.abort();
  abortController = new AbortController();

  const params = new URLSearchParams({ q, ...currentFilters });
  // Remove empty filter values — prevents sending manufacturer= (Pitfall 5)
  for (const [k, v] of [...params.entries()]) {
    if (!v) params.delete(k);
  }

  try {
    const resp = await fetch(`/api/search?${params}`, {
      signal: abortController.signal,
    });
    const results = await resp.json();
    currentResults = results;
    selectedIndex = -1;   // reset keyboard cursor on new results
    renderResults(results);
    transitionTo("results");
  } catch (err) {
    if (err.name !== "AbortError") console.error("Search failed:", err);
  }
}
```

**Result rendering** (RESEARCH.md Pattern 7 + Code Examples):
```javascript
function renderResults(results) {
  // Stats line (UIPL-02)
  if (results.length === 0) {
    statsLine.textContent = "No results";
  } else {
    const took = results[0].took_ms;
    statsLine.textContent = `${results.length} results (${(took / 1000).toFixed(2)}s)`;
  }

  resultsList.innerHTML = "";
  results.forEach((r, i) => {
    const item = document.createElement("div");
    item.className = "result-item";
    item.dataset.index = i;

    const title = document.createElement("div");
    title.className = "result-title";
    title.textContent = r.title;           // textContent — untrusted field

    const meta = document.createElement("div");
    meta.className = "result-meta";
    const domain = document.createElement("span");
    domain.className = "result-domain";
    domain.textContent = r.source_domain;  // textContent — untrusted field
    meta.appendChild(domain);

    const excerpt = document.createElement("div");
    excerpt.className = "result-excerpt";
    excerpt.innerHTML = r.excerpt || "";   // innerHTML ONLY — ES highlight <b> tags (D-10)

    item.appendChild(title);
    item.appendChild(meta);
    item.appendChild(excerpt);
    item.addEventListener("click", () => openArticle(r));
    resultsList.appendChild(item);
  });
}
```

**Article view** (SRCH-03, D-05):
```javascript
function openArticle(result) {
  articleTitle.textContent  = result.title;         // textContent — not innerHTML
  articleSource.textContent = result.source_domain; // textContent
  articleBody.textContent   = result.body || "No content available."; // textContent — Pitfall 3
  transitionTo("article");
}

backBtn.addEventListener("click", () => {
  transitionTo("results");
  // Query and filter state are preserved in module-level variables (D-05)
});
```

**Keyboard navigation** (RESEARCH.md Pattern 5; D-11, UIPL-03):
```javascript
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
  if (e.key === "Escape") {
    searchInput.value = "";
    transitionTo("home");
    selectedIndex = -1;
  }
});

function updateSelection() {
  document.querySelectorAll(".result-item").forEach((el, i) => {
    el.classList.toggle("selected", i === selectedIndex);
  });
}
```

**Filter change handler** (D-06, SRCH-04):
```javascript
function onFilterChange() {
  currentFilters.manufacturer = filterMfr.value;
  currentFilters.era_bucket   = filterEra.value;
  currentFilters.body_style   = filterBody.value;
  if (currentQuery) runSearch(currentQuery);
}

filterMfr.addEventListener("change", onFilterChange);
filterEra.addEventListener("change", onFilterChange);
filterBody.addEventListener("change", onFilterChange);
```

**ES warmup polling** (RESEARCH.md Pattern 4; D-07):
```javascript
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
    } catch (_) { /* ES not yet up — continue polling */ }
  }, 2000);
}

// Kick off immediately on page load
startWarmupPolling();
```

---

### `tests/test_server.py` (modify: update test_root_returns_html assertion)

**Analog:** `tests/test_server.py` itself — read in full above.

**Current assertion that must change** (lines 115-119):
```python
def test_root_returns_html(client_not_ready):
    """GET / returns HTTP 200 with HTML body containing 'NitroFind'."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert b"NitroFind" in resp.data
```

**Updated assertion pattern** — check for structural HTML marker instead of raw string. The `b"NitroFind"` assertion still holds (the `<title>` tag contains it), but add a more specific check to validate template rendering worked. Match the existing fixture and assert style in the file:
```python
def test_root_returns_html(client_not_ready):
    """GET / returns HTTP 200 with rendered index.html template."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert b"NitroFind" in resp.data          # title present
    assert b"<!DOCTYPE html>" in resp.data    # template rendered (not raw string)
```

**Fixture pattern** — both existing fixtures (`client_not_ready`, `client_ready`) work unchanged for this test. `test_root_returns_html` uses `client_not_ready` — correct, because `GET /` does not check `state["ready"]` (it always serves the HTML shell regardless of ES status).

**Important:** For the test client to resolve `render_template("index.html")`, the Flask app's `template_folder` must resolve correctly at test time. The `os.path.dirname(os.path.abspath(__file__))` approach in `server.py` uses the file's actual location on disk — this works correctly in pytest because the path is absolute and does not depend on `cwd`. No fixture change is needed.

---

## Shared Patterns

### Flask import pattern
**Source:** `nitrofind/server.py` line 34
**Apply to:** `nitrofind/server.py` (modify)
```python
from flask import Flask, jsonify, render_template, request
```
Add `render_template` to the existing import. No other import changes needed.

### Response data shape consumed by JS
**Source:** `nitrofind/server.py` `_result_to_api_dict` (lines 90-114) and `api_search` (lines 117-163)

The JS `app.js` must consume this exact shape from `/api/search`:
```python
{
    "title": result.title,
    "url": result.url,
    "source_domain": result.source_domain,
    "excerpt": excerpt,          # may contain <b> ES highlight tags
    "score": result.score,
    "took_ms": took_ms,
    # NOTE: "body" field is returned via _source — confirmed in query_builder.py
}
```
And from `/api/status`:
```python
{"status": "ok", "es_health": "...", "doc_count": N, "index_size_bytes": N}  # 200
{"status": "starting"}  # 503
```

### Test fixture pattern
**Source:** `tests/test_server.py` lines 26-43
**Apply to:** `tests/test_server.py` (no change needed — existing fixtures reused)
```python
@pytest.fixture
def client_not_ready(monkeypatch):
    from nitrofind import server
    monkeypatch.setitem(server.state, "ready", False)
    return server.app.test_client()
```
New tests for `GET /` reuse `client_not_ready`. No new fixtures required.

### innerHTML vs textContent safety rule
**Source:** CONTEXT.md D-10, RESEARCH.md Pitfall 3
**Apply to:** `static/js/app.js` — every DOM assignment
- `innerHTML`: **only** for `result.excerpt` (ES highlight `<b>` tags — local ES source)
- `textContent`: all other fields (`title`, `source_domain`, `body`, `url`)

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `templates/index.html` | view / HTML skeleton | request-response | No HTML templates exist in the project; first ever |
| `static/css/style.css` | stylesheet | — | No CSS files exist in the project; first ever |
| `static/js/app.js` | client-side SPA | event-driven | No JS files exist in the project; first ever |

For these three files, patterns come entirely from RESEARCH.md (which is high confidence — all patterns are from verified native browser APIs and Flask docs, not invented conventions).

---

## Metadata

**Analog search scope:** `nitrofind/`, `tests/`, project root
**Files scanned:** `nitrofind/server.py` (full), `tests/test_server.py` (full), `.agents/skills/design-taste-frontend/SKILL.md` (sections 0–4, 8)
**Project HTML/CSS/JS baseline:** none (all three are net-new)
**Pattern extraction date:** 2026-06-03
