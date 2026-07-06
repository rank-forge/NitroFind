# Phase 13: History & Theme - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 4 (3 modified + 1 test additions)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `templates/index.html` | template | request-response | `templates/index.html` (existing) | exact — adding elements to known structure |
| `static/css/style.css` | config/style | transform | `static/css/style.css` (existing `:root` block) | exact — extending token architecture |
| `static/js/app.js` | controller | event-driven | `static/js/app.js` (existing `runSearch`, `renderResults`) | exact — same module, same patterns |
| `tests/test_server.py` | test | request-response | `tests/test_server.py` (existing `test_root_*` tests) | exact — same fixture, same assertion style |

---

## Pattern Assignments

### `templates/index.html` — add FOUC script, theme-toggle button, `#history-list`

**Analog:** `templates/index.html` lines 1–79

**Current `<head>` structure** (lines 3–8):
```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NitroFind</title>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
```

**Target — inline script BEFORE `<link>`** (insert before line 7):
```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NitroFind</title>
  <script>
    (function () {
      var t = localStorage.getItem('nitrofind-theme');
      document.documentElement.dataset.theme = (t === 'light') ? 'light' : 'dark';
    }());
  </script>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
```
The inline IIFE runs synchronously before the stylesheet parses — the only correct position for FOUC prevention. `data-theme` goes on `<html>` (not `<body>`) to avoid compound-selector conflicts with the existing `body[data-state="..."]` rules (lines 58–64 of style.css).

**Theme-toggle button placement — home view** (insert inside `.home-view` div, after line 13):
```html
<div class="home-view">
  <button id="theme-toggle" type="button" class="theme-toggle-btn">Light</button>
  <h1 class="logo">NitroFind</h1>
  ...
</div>
```

**Theme-toggle button placement — results view `.top-bar`** (insert inside `.top-bar`, after line 24):
```html
<header class="top-bar">
  <span class="logo-small">NitroFind</span>
  <input id="search-input-results" type="search" placeholder="Search cars…" autocomplete="off">
  <button id="theme-toggle-results" type="button" class="theme-toggle-btn">Light</button>
</header>
```
Note: The home-view button needs a distinct id (`theme-toggle`) from the results-view button (`theme-toggle-results`) because `document.getElementById` returns one element. Both buttons call `toggleTheme()` in their click handlers.

**History list** (insert inside `.home-view`, below `.search-wrap`):
```html
<ul id="history-list" style="display:none;"></ul>
```
The `style="display:none"` matches the pattern in `renderHistory()` — the list is shown/hidden programmatically (`historyList.style.display = history.length ? 'block' : 'none'`).

---

### `static/css/style.css` — light theme override + history/toggle styles

**Analog:** `static/css/style.css` lines 11–29 (`:root` token block)

**Existing dark token block** (lines 11–29):
```css
:root {
  --bg-primary:   #0f1117;
  --bg-surface:   #161b22;
  --bg-input:     #1c2128;
  --text-primary:   #e6edf3;
  --text-secondary: #8b949e;
  --accent:       #2dd4bf;
  --accent-hover: #5eead4;
  --border:     #30363d;
  --radius:     6px;
  --transition: 200ms ease;
}
```

**New light theme override block** (append immediately after `:root` block, before section 2 comment):
```css
/* Light theme token override — same names, different values.
   Scoped to html[data-theme="light"] so body[data-state] selectors are untouched. */
html[data-theme="light"] {
  --bg-primary:     #ffffff;
  --bg-surface:     #f6f8fa;
  --bg-input:       #ffffff;
  --text-primary:   #1c2128;
  --text-secondary: #57606a;
  --accent:         #0d9488;   /* teal-600 — 4.6:1 on #fff (WCAG AA) */
  --accent-hover:   #0f766e;   /* teal-700 */
  --border:         #d0d7de;
}
```

**Theme toggle button styles** (modeled on `.sort-btn` — lines ~200+ in style.css):
```css
/* Theme toggle button — shares sort-btn visual language */
.theme-toggle-btn {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition);
}
.theme-toggle-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

/* Home-view toggle — fixed position so visible without results bar */
.home-view .theme-toggle-btn {
  position: absolute;
  top: 0.75rem;
  right: 1.5rem;
}
```

**History list styles** (modeled on `#results-list` / `.result-item` DOM list pattern):
```css
/* History list — home-view recent searches */
#history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  width: 100%;
  max-width: 580px;  /* matches .search-wrap max-width */
}

.history-item {
  padding: 0.5rem 1rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
  cursor: pointer;
  border-radius: var(--radius);
  transition: color var(--transition), background-color var(--transition);
}

.history-item:hover {
  color: var(--accent);
  background-color: var(--bg-surface);
}
```

---

### `static/js/app.js` — add history + theme functions, wire handlers

**Analog:** `static/js/app.js` — module-level state section (lines 24–42), DOM cache section (lines 48–65), `runSearch()` (lines 100–133), `renderResults()` (lines 147–175)

**Module-level constants** (append to existing constants block after `DEBOUNCE_MS`):
```javascript
const HISTORY_KEY = 'nitrofind-history';
const HISTORY_MAX = 10;
```

**DOM cache additions** (append to existing DOM cache block, same pattern as lines 48–65):
```javascript
const historyList     = document.getElementById("history-list");
const themeToggleBtn  = document.getElementById("theme-toggle");
const themeToggleBtnResults = document.getElementById("theme-toggle-results");
```

**History functions** (modeled on `renderResults()` DOM-creation pattern, lines 147–175):
```javascript
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
```

**Theme functions** (modeled on `transitionTo()` pattern — simple state write + DOM update, line 71–74):
```javascript
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
```

**Wire up handlers** (append to event-listener section; follows same `addEventListener` pattern as line 93–94):
```javascript
if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);
if (themeToggleBtnResults) themeToggleBtnResults.addEventListener('click', toggleTheme);
```

**Initialization calls** (append to module init block at end of file, after warmup polling setup):
```javascript
// History & theme init
renderHistory(loadHistory());
applyThemeLabel();
```

**Insertion point in `runSearch()`** — after `currentQuery = q;` (line 101), before `abortController` setup:
```javascript
async function runSearch(q) {
  currentQuery = q;
  addToHistory(q);   // HIST-01: write after empty-string guard resolves in handleSearchInput
  // ... rest unchanged
```

---

### `tests/test_server.py` — Wave 0 DOM structure test stubs

**Analog:** `tests/test_server.py` lines 115–129 (`test_root_*` tests)

**Existing pattern to copy** (lines 115–129):
```python
def test_root_returns_html(client_not_ready):
    """GET / returns HTTP 200 with rendered index.html template."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert b"NitroFind" in resp.data
    assert b"<!DOCTYPE html>" in resp.data


def test_root_uses_template(client_not_ready):
    """GET / responds with text/html content-type and structural template marker."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")
    assert b'data-state="home"' in resp.data
```

**New tests** (append after line 129, same fixture, same assertion style):
```python
def test_template_has_theme_toggle(client_not_ready):
    """GET / rendered HTML contains id="theme-toggle" button (THME-01 DOM structure)."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert b'id="theme-toggle"' in resp.data


def test_template_has_history_list(client_not_ready):
    """GET / rendered HTML contains id="history-list" container (HIST-01/02 DOM structure)."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert b'id="history-list"' in resp.data


def test_template_has_fouc_prevention_script(client_not_ready):
    """GET / rendered HTML contains inline <script> in <head> for FOUC prevention (THME-01)."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert b'nitrofind-theme' in resp.data
    assert b'dataset.theme' in resp.data
```

---

## Shared Patterns

### CSS Token Architecture
**Source:** `static/css/style.css` lines 11–29
**Apply to:** All new color values in style.css additions
All color values must use `var(--token)` — no raw hex values outside the `:root` / `html[data-theme]` blocks. This is an existing project rule (line 3–5 comment in style.css).

### textContent Discipline
**Source:** `static/js/app.js` lines 155–156, 160, 188–189
**Apply to:** All history item label rendering
History queries are user-authored strings. Use `.textContent` — never `.innerHTML`. This matches the established project pattern: `title.textContent = r.title`, `domain.textContent = r.source_domain`.

### try/catch Around localStorage
**Source:** RESEARCH.md Pitfall 3, Pitfall 6
**Apply to:** All `localStorage.getItem` and `localStorage.setItem` calls in app.js
Pattern: wrap reads with `try/catch` that falls back to `[]`; wrap writes with silent `catch (_) {}`. No existing analog in codebase (first localStorage use) — follow RESEARCH.md Pattern 3 exactly.

### Guard-Based Null Check on DOM References
**Source:** `static/js/app.js` lines 48–65 (all DOM refs queried once at load)
**Apply to:** `themeToggleBtn`, `themeToggleBtnResults`, `historyList`
Use `if (element)` guards before calling `.addEventListener()` on elements that may not exist in all views. The existing code assumes elements exist; new elements have the same guarantee, but defensive checks are low cost.

### Flask test_client + `client_not_ready` Fixture
**Source:** `tests/test_server.py` lines 27–32
**Apply to:** All three new test functions
```python
@pytest.fixture
def client_not_ready(monkeypatch):
    from nitrofind import server
    monkeypatch.setitem(server.state, "ready", False)
    return server.app.test_client()
```
All three Wave 0 tests use `client_not_ready` — template DOM structure is independent of ES readiness state.

---

## No Analog Found

No files require patterns from outside the codebase. All four files being modified have direct self-analogs (they are existing files being extended).

---

## Metadata

**Analog search scope:** `templates/`, `static/css/`, `static/js/`, `tests/`
**Files scanned:** 4 primary files read in full or targeted sections
**Pattern extraction date:** 2026-07-06
