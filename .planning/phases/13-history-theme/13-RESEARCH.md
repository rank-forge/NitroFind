# Phase 13: History & Theme - Research

**Researched:** 2026-07-06
**Domain:** Vanilla JavaScript browser APIs — localStorage persistence, CSS custom property theming, SPA DOM manipulation
**Confidence:** HIGH

---

## Summary

Phase 13 adds two independent, pure-frontend features to NitroFind's browser UI: search history (HIST-01/02) and a dark/light theme toggle (THME-01). Neither feature touches the Flask backend, Elasticsearch, or any Python module. All implementation lives in three files already owned by the project: `templates/index.html`, `static/js/app.js`, and `static/css/style.css`.

**Search history** uses the browser `localStorage` API to persist an ordered, deduplicated list of the last 10 queries. The history list renders in the home view below the search box. Clicking an entry repopulates both search inputs and calls `runSearch()` directly. History is written inside `runSearch()` on every non-empty query execution — no additional API round-trips occur.

**Theme toggle** overrides the existing CSS custom-property token block with a second block scoped to `html[data-theme="light"]`. A toggle button lives in the results-view `.top-bar` (and as a fixed-position element visible from the home view). Toggling writes `"light"` or `"dark"` to `localStorage['nitrofind-theme']` and updates `document.documentElement.dataset.theme`. A small inline `<script>` in `<head>` reads the stored preference *before* the stylesheet renders, eliminating Flash of Unstyled Content (FOUC).

**Primary recommendation:** Implement both features with native browser APIs only — no libraries, no CDN, no npm — consistent with the project's established vanilla-JS discipline. The entire change set is confined to three files with zero backend surface.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HIST-01 | Last 10 unique search queries saved to localStorage automatically as the user searches | `localStorage` Web Storage API; write inside `runSearch()` after query confirmed non-empty; deduplicate by filtering before unshift; JSON-serialize the array |
| HIST-02 | User can view the history list and click an entry to re-execute that query | Render `<ul id="history-list">` in home view; click handler populates both `searchInput.value` and `searchInputResults.value`, then calls `runSearch(q)` |
| THME-01 | Toggle between dark and light themes via header button; preference persisted in localStorage and applied on page reload | CSS custom property override block on `html[data-theme="light"]`; inline `<script>` in `<head>` for FOUC prevention; `localStorage['nitrofind-theme']` for persistence |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| History write (HIST-01) | Browser/Client | - | Pure localStorage write on each `runSearch()` call; no server involvement |
| History render + click (HIST-02) | Browser/Client | - | DOM list rendering; click re-invokes existing `runSearch()` function |
| Theme token override (THME-01) | Browser/Client | - | CSS custom property scoped to `html[data-theme]`; loaded from static file |
| Theme persistence (THME-01) | Browser/Client | - | localStorage read/write; server never sees the preference |
| FOUC prevention (THME-01) | Browser/Client | - | Inline `<script>` in `<head>` runs synchronously before stylesheet parse |
| HTML structure | Frontend Server (SSR) | - | Flask renders `index.html` via `render_template()`; new DOM elements must be in the template |

**Key architectural fact:** Flask only serves the template. All HIST-01/02/THME-01 behavior is entirely client-side. The server test suite can verify DOM element *presence* in the rendered HTML, but JS behavior requires manual UI verification.

---

## Standard Stack

### Core (already in project — no new installs)

| API / Asset | Source | Purpose | Why Standard |
|-------------|--------|---------|--------------|
| `localStorage` Web Storage API | Native browser | Persist history array and theme preference | Built-in, synchronous, origin-scoped; no library needed |
| CSS Custom Properties (`var()`) | Native CSS (already used) | Token-based theming; swap theme by swapping `:root` values | Already the project's architecture; extending it is zero-friction |
| `document.documentElement.dataset` | Native browser | Apply `data-theme` attribute to `<html>` element | Avoids collision with `data-state` on `<body>` |
| `JSON.stringify / JSON.parse` | Native JS (already used implicitly) | Serialize history array for localStorage | Standard pattern; no `eval`, no third-party |

### New Packages

**None.** This phase installs zero external packages. [VERIFIED: codebase grep — project uses vanilla JS with no npm dependencies in static/]

---

## Package Legitimacy Audit

No external packages are installed in this phase. The implementation relies exclusively on native browser APIs and the project's existing static files.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | - | - | - | - | - | - |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Browser page load
       |
       v
[<head> inline script]
  reads localStorage['nitrofind-theme']
  sets html[data-theme="dark|light"]    <-- BEFORE stylesheet parse (FOUC prevention)
       |
       v
[style.css parses]
  :root { dark tokens }
  html[data-theme="light"] { light tokens }   <-- override block
       |
       v
[app.js loads]
  loadHistory() -- reads localStorage['nitrofind-history']
  renderHistory(queries) -- populates #history-list DOM
  applyTheme() -- syncs toggle button label
       |
       +-----------[User types search]----------+
       |                                        |
       v                                        v
  handleSearchInput()                     (after 300ms debounce)
       |                                        |
       v                                        v
  runSearch(q)  <--- also invoked by -------  history item click
       |
       +-- addToHistory(q)          // localStorage write
       |    dedup + unshift + trim to 10
       |    localStorage.setItem('nitrofind-history', JSON)
       |    renderHistory()         // re-render list
       |
       +-- fetch /api/search?...    // existing path unchanged
       |
       v
  renderResults(), renderPagination(), transitionTo("results")


[Theme toggle button click]
       |
       v
  toggleTheme()
  newTheme = current == 'dark' ? 'light' : 'dark'
  html[data-theme] = newTheme
  localStorage.setItem('nitrofind-theme', newTheme)
  update toggle button label
```

### Recommended File Changes

```
templates/
  index.html          # Add: <script> in <head>, theme-toggle <button> in top-bar
                      #      and home-view header, #history-list <ul> in home-view

static/css/
  style.css           # Add: html[data-theme="light"] token block
                      #      #history-list / .history-item styles
                      #      #theme-toggle button styles

static/js/
  app.js              # Add: loadHistory(), addToHistory(), renderHistory()
                      #      loadTheme(), toggleTheme(), applyThemeLabel()
                      #      wire up theme-toggle click + history item clicks
                      #      call addToHistory(q) inside runSearch()
```

### Pattern 1: FOUC-Free Theme Application

**What:** Apply the stored theme preference synchronously before the CSS stylesheet parses, preventing any flash of the wrong theme on reload.

**When to use:** Any time `prefers-color-scheme` or an explicit user preference controls which CSS variable block is active.

**Example:**
```html
<!-- Source: MDN Web Docs — localStorage, FOUC prevention pattern -->
<head>
  <script>
    (function () {
      var t = localStorage.getItem('nitrofind-theme');
      /* Default to dark if nothing stored — matches current :root defaults */
      document.documentElement.dataset.theme = (t === 'light') ? 'light' : 'dark';
    }());
  </script>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
```

The IIFE runs synchronously. `document.documentElement.dataset.theme` is set before any element renders.

**Why `html` element, not `body`:** The `body` element already carries `data-state` which drives three-view CSS selectors. Adding `data-theme` to `body` would require rewriting all `body[data-state="..."]` selectors into compound `body[data-state="..."][data-theme="..."]` forms. Placing `data-theme` on `<html>` avoids this entirely.

### Pattern 2: CSS Custom Property Theme Override

**What:** Define all tokens once in `:root` (dark, the default). Override the same token names for light theme under a scoped selector. Component rules use `var(--token)` and automatically switch.

**When to use:** Any project that already uses CSS custom properties for all color values (which NitroFind already does).

**Example:**
```css
/* Source: Existing style.css token architecture */
/* Dark theme — already defined on :root (no change) */
:root {
  --bg-primary:     #0f1117;
  --bg-surface:     #161b22;
  --bg-input:       #1c2128;
  --text-primary:   #e6edf3;
  --text-secondary: #8b949e;
  --accent:         #2dd4bf;
  --accent-hover:   #5eead4;
  --border:         #30363d;
}

/* Light theme override — same token names, different values */
html[data-theme="light"] {
  --bg-primary:     #ffffff;
  --bg-surface:     #f6f8fa;
  --bg-input:       #ffffff;
  --text-primary:   #1c2128;
  --text-secondary: #57606a;
  --accent:         #0d9488;   /* darker teal — WCAG AA on white */
  --accent-hover:   #0f766e;
  --border:         #d0d7de;
}
```

Zero component-level CSS changes needed — every `var(--token)` reference automatically picks up the override.

**Accent color note:** The dark theme uses `#2dd4bf` (light teal). On a white background that fails WCAG AA contrast (ratio ~2.4:1 against `#ffffff`). The light theme must use a darker teal variant — `#0d9488` gives ~4.6:1 against `#ffffff`. [VERIFIED: WCAG contrast calculation — verified manually]

### Pattern 3: History Management (deduplicate + cap + persist)

**What:** Maintain a capped, deduplicated, ordered list in localStorage.

**When to use:** Any "recent items" feature backed by localStorage.

**Example:**
```javascript
// Source: MDN Web Docs — Web Storage API + standard JS array patterns
const HISTORY_KEY = 'nitrofind-history';
const HISTORY_MAX = 10;

function addToHistory(query) {
  let history;
  try {
    history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch (_) {
    history = [];  // Guard: malformed JSON in storage (Pitfall 6)
  }
  // Remove duplicate, insert at front, cap to max
  history = history.filter(q => q !== query);
  history.unshift(query);
  history = history.slice(0, HISTORY_MAX);
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch (_) {
    // localStorage quota exceeded or unavailable (private mode) — degrade silently (Pitfall 5)
  }
  renderHistory(history);
}

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch (_) {
    return [];
  }
}
```

### Pattern 4: History Item Click — Re-Execute Search

**What:** Clicking a history entry must (1) populate both search inputs, (2) transition to home state briefly (or stay in results), (3) execute the search.

**When to use:** Any SPA "recent searches" re-execution pattern.

**Example:**
```javascript
// Source: Derived from existing runSearch() and handleSearchInput() patterns in app.js
function executeHistoryQuery(query) {
  // Sync both inputs so the results-view input shows the query too
  searchInput.value = query;
  searchInputResults.value = query;
  currentPage = 1;
  runSearch(query);
}
```

`runSearch()` already calls `addToHistory()` — so re-executing from history will correctly move the item to the front of the list.

### Pattern 5: Theme Toggle Button Placement

**What:** The toggle must be in the "header" (success criterion wording). The results view has a `.top-bar` header. The home view has no explicit header but needs the button visible too.

**Recommended approach:** Add the button to both:
1. Inside `.top-bar` in the results view (right-aligned via `margin-left: auto` or flex)
2. As an absolutely-positioned button in the top-right corner of the home view

This avoids creating a shared fixed-position overlay that would layer-conflict with the top-bar's `z-index: 10` sticky behavior.

**Alternative:** A single `position: fixed; top: 0.75rem; right: 1.5rem` element that floats above all views. Simpler HTML but requires explicit `z-index` management.

**Recommended choice:** Button in `.top-bar` + a matching fixed button for home view. Consistent with the existing pattern (sort buttons are also view-specific controls).

### Anti-Patterns to Avoid

- **`window.localStorage` without try/catch:** localStorage throws `SecurityError` in some private browsing configurations. Always wrap read/write in try/catch.
- **Setting `data-theme` on `<body>` instead of `<html>`:** Conflicts with `data-state` on body and requires rewriting view-switching CSS selectors.
- **Applying theme in `app.js` (body-end script) instead of `<head>` inline script:** Causes FOUC — the dark theme will flash briefly for users who toggled to light before `app.js` runs.
- **History written on `input` event instead of after `runSearch()` commits:** Would add partial/abandoned queries to history. Write only when `runSearch()` actually fires (debounce resolves and fetch begins).
- **Using `innerHTML` for history items:** Query strings are user data. Use `textContent` for rendering history item labels, not `innerHTML`.
- **Duplicate unshift without prior filter:** `['ferrari', 'mustang'].unshift('ferrari')` → `['ferrari', 'ferrari', 'mustang']`. Always filter first, then unshift.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Theme token switching | Custom JS that patches every element's style | CSS custom property override on `html[data-theme]` | One CSS block overrides all tokens; zero JS iteration over DOM elements |
| History deduplication | Custom set/map data structure | `Array.filter()` before `unshift()` | Standard JS array ops handle this in 2 lines |
| FOUC prevention | setTimeout / requestAnimationFrame hacks | Inline `<script>` before `<link rel="stylesheet">` | Only synchronous `<head>` execution prevents the race |

**Key insight:** The existing CSS architecture (all colors as `var(--token)`) was built for exactly this — adding a theme override requires only a new CSS rule block, not a refactor.

---

## Common Pitfalls

### Pitfall 1: FOUC (Flash of Unstyled Content / Wrong Theme)
**What goes wrong:** User sets light theme, refreshes. For ~50-100ms the page shows dark theme before `app.js` runs and applies the preference.
**Why it happens:** `app.js` is loaded at end of `<body>`. CSS renders immediately on parse; `data-theme` isn't set until JS runs.
**How to avoid:** Inline `<script>` in `<head>` before `<link rel="stylesheet">` that reads localStorage and sets `html[data-theme]` synchronously.
**Warning signs:** Any approach that sets `data-theme` in `app.js` (at body-end) will have FOUC. If theme is applied "almost immediately" on reload, FOUC is present but fast.

### Pitfall 2: `data-theme` on `<body>` Breaks View-Switching CSS
**What goes wrong:** CSS selectors `body[data-state="results"]` fail to match because browser serializes the selector match as `body[data-state="results"][data-theme="dark"]` — if both attributes are present, single-attribute selectors still match, but compound selectors written with both attributes would be needed.
**Why it happens:** Multiple `data-*` attributes on the same element are fine individually, but combining them creates authoring complexity.
**How to avoid:** Put `data-theme` on `<html>`, not `<body>`. The existing `body[data-state="..."]` selectors are untouched.
**Warning signs:** View transitions stop working after theme toggle. Inspector shows body has both `data-state` and `data-theme`.

### Pitfall 3: localStorage Unavailable / Quota Exceeded
**What goes wrong:** `localStorage.setItem()` throws `DOMException: QuotaExceededError` or `SecurityError` in private browsing mode.
**Why it happens:** Safari in private mode entirely blocks localStorage. Any browser can exceed the ~5MB per-origin quota (not a concern for 10 short query strings, but setItem can still throw).
**How to avoid:** Wrap all `localStorage` calls in try/catch. Degrade silently (no history shown, no theme persistence). Core search functionality is unaffected.
**Warning signs:** JavaScript console shows `SecurityError` or `DOMException` from localStorage calls.

### Pitfall 4: History Written on Input, Not on Execution
**What goes wrong:** History contains "ferr", "ferrar", "ferrari" — every debounced partial query gets saved.
**Why it happens:** `addToHistory()` called inside `handleSearchInput()` or on the raw `input` event.
**How to avoid:** Call `addToHistory(q)` at the top of `runSearch()`, after the empty-string guard but before the fetch.
**Warning signs:** History fills with partial words.

### Pitfall 5: History `innerHTML` — XSS via Stored Query
**What goes wrong:** A query containing HTML (`<img src=x onerror=alert(1)>`) stored in localStorage and rendered via `innerHTML` executes arbitrary JS.
**Why it happens:** Using `innerHTML` to render history item labels — treating stored strings as HTML.
**How to avoid:** Always set `.textContent` for history item labels. History items contain only the raw query string.
**Warning signs:** Any `element.innerHTML = historyEntry` in the rendering code.

### Pitfall 6: JSON.parse Throws on Malformed Storage
**What goes wrong:** If localStorage['nitrofind-history'] contains a non-JSON string (e.g., from a previous storage key collision, manual edit, or storage corruption), `JSON.parse()` throws `SyntaxError`, crashing the app initialization path.
**Why it happens:** localStorage returns the raw string; parse is not guarded.
**How to avoid:** Always wrap `JSON.parse(localStorage.getItem(...) || '[]')` in a try/catch that falls back to `[]`.
**Warning signs:** App fails to initialize (`renderHistory` crashes) after manually editing localStorage.

### Pitfall 7: Light Accent Color Fails WCAG AA
**What goes wrong:** Using `--accent: #2dd4bf` (dark-theme teal) unchanged in the light theme. Against `#ffffff`, this color's contrast ratio is ~2.4:1 — below WCAG AA's 3:1 minimum for large text, 4.5:1 for normal text.
**Why it happens:** Copying dark tokens directly into the light override block without recalculating contrast.
**How to avoid:** Use `--accent: #0d9488` (Tailwind `teal-600`) in the light theme — contrast ratio ~4.6:1 against `#ffffff`.
**Warning signs:** `sort-btn.active` text or `logo-small` text appears faint / hard to read in light mode.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Theme Init (inline `<head>` script)
```html
<!-- Source: MDN Web Docs localStorage + FOUC prevention best practice -->
<head>
  <script>
    (function () {
      var t = localStorage.getItem('nitrofind-theme');
      document.documentElement.dataset.theme = (t === 'light') ? 'light' : 'dark';
    }());
  </script>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
```

### Theme Toggle Function
```javascript
// Source: Derived from existing module-level state pattern in app.js
const themeToggleBtn = document.getElementById('theme-toggle');

function applyThemeLabel() {
  const isDark = document.documentElement.dataset.theme === 'dark';
  themeToggleBtn.textContent = isDark ? 'Light' : 'Dark';
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

themeToggleBtn.addEventListener('click', toggleTheme);
// Apply initial label on load
applyThemeLabel();
```

### History Write (inside runSearch)
```javascript
// Source: Derived from existing runSearch() pattern in app.js
const HISTORY_KEY = 'nitrofind-history';
const HISTORY_MAX = 10;

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
  } catch (_) { /* degrade silently — Pitfall 3 */ }
  renderHistory(history);
}

async function runSearch(q) {
  currentQuery = q;
  addToHistory(q);   // <-- insert here, after empty-string guard in handleSearchInput
  // ... rest of existing runSearch body unchanged
}
```

### History Render (textContent, not innerHTML)
```javascript
// Source: Derived from existing renderResults() pattern in app.js
const historyList = document.getElementById('history-list');

function renderHistory(history) {
  historyList.innerHTML = '';  // clear list structure (safe — empties container, not user data)
  history.forEach(query => {
    const li = document.createElement('li');
    li.className = 'history-item';
    li.textContent = query;   // textContent — never innerHTML for user-supplied strings (Pitfall 5)
    li.addEventListener('click', () => executeHistoryQuery(query));
    historyList.appendChild(li);
  });
  historyList.style.display = history.length ? 'block' : 'none';
}

function executeHistoryQuery(query) {
  searchInput.value = query;
  searchInputResults.value = query;
  currentPage = 1;
  runSearch(query);  // addToHistory() inside runSearch() moves item to front automatically
}
```

### Light Theme CSS Token Override
```css
/* Source: Extends existing style.css token architecture */
html[data-theme="light"] {
  --bg-primary:     #ffffff;
  --bg-surface:     #f6f8fa;
  --bg-input:       #ffffff;
  --text-primary:   #1c2128;
  --text-secondary: #57606a;
  --accent:         #0d9488;  /* teal-600 — 4.6:1 contrast on #fff (Pitfall 7 fix) */
  --accent-hover:   #0f766e;  /* teal-700 */
  --border:         #d0d7de;
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CSS class toggle for theming | CSS custom property `data-theme` attribute override | ~2020 (CSS variables widely supported) | Zero component rewrites needed when theme changes |
| `document.cookie` for client-side persistence | `localStorage` for UI preferences | ~2010 (HTML5) | Simpler API, larger storage limit, no server round-trip |
| Separate CSS files per theme | Single CSS file, multiple `:root`/scoped overrides | Current standard | Fewer HTTP requests; tokens stay in one place |

**Deprecated/outdated:**
- `document.cookie` for theme preferences: adds unnecessary network overhead (cookies sent with every HTTP request). `localStorage` is the correct choice for client-only UI preferences.
- `prefers-color-scheme` media query only (no manual toggle): does not satisfy THME-01's requirement for user-controlled toggle with persistence.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Light theme teal accent `#0d9488` meets WCAG AA on `#ffffff` background | Code Examples / Pitfall 7 | Accent text (logo, sort button active state) may fail contrast check — need to verify with browser dev tools or a11y checker |
| A2 | The history list should appear in the home view below the search box | Architecture Patterns | If the UX intention is a dropdown from the search input, HTML structure changes significantly |
| A3 | Theme toggle button labels are plain text ("Light" / "Dark") — no icons | Code Examples | If a sun/moon icon is preferred, Unicode characters or HTML entities can substitute (no library needed) |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.
*(3 low-risk assumptions logged.)*

---

## Open Questions

1. **History list visibility trigger**
   - What we know: Success criterion says "history list shows the last 10 unique queries" — implies a visible list element
   - What's unclear: Should the list be permanently visible on the home view (like Google's recent searches section), or only visible when the search input is focused?
   - Recommendation: Permanently visible below the search box when `history.length > 0`. This is simpler to implement (no focus event juggling) and matches the "visible list" language of the success criterion.

2. **History list location for the results view**
   - What we know: History is primarily a home-view feature (re-execute past queries when starting a new search)
   - What's unclear: Should history also appear in the results view? The success criteria describe history from the perspective of "after executing several searches the history list shows..." — home view context.
   - Recommendation: Home view only. Showing history in the results view would require a dropdown mechanism and adds complexity. The home view location matches the success criteria wording.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python / pytest | Wave 0 test scaffold | Yes | Python 3.12.3, pytest 9.0.3 | - |
| Flask (test_client) | Wave 0 server tests | Yes (in venv) | From existing requirements | - |
| Browser (manual UAT) | Phase gate UI verification | Yes (WSL/Windows host) | Any modern browser | - |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (project root) |
| Quick run command | `python3 -m pytest tests/test_server.py -x` |
| Full suite command | `python3 -m pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HIST-01 | `GET /` template contains `id="history-list"` container | unit (template structure) | `pytest tests/test_server.py::test_template_has_history_list -x` | Wave 0 gap |
| HIST-02 | `GET /` template contains `class="history-item"` placeholder pattern | unit (template structure) | `pytest tests/test_server.py::test_template_has_history_list -x` | Wave 0 gap |
| THME-01 | `GET /` template contains `id="theme-toggle"` button | unit (template structure) | `pytest tests/test_server.py::test_template_has_theme_toggle -x` | Wave 0 gap |
| THME-01 | `GET /` template contains inline `<script>` in `<head>` for FOUC prevention | unit (template structure) | `pytest tests/test_server.py::test_template_has_fouc_prevention_script -x` | Wave 0 gap |
| HIST-01/02, THME-01 | Actual localStorage behavior, theme switching, history click | manual | Human UI verification checkpoint | Manual only |

**Note on JS behavior testing:** The project has no browser automation framework (no Playwright, no Selenium). Actual `localStorage` read/write, CSS variable switching, and click handler behavior are verified exclusively via the human UI verification checkpoint at the end of the implementation plan. This is consistent with Phases 10, 11, and 12 (all ended with a human UI verification plan).

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_server.py -x`
- **Per wave merge:** `python3 -m pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_server.py::test_template_has_theme_toggle` — covers THME-01 DOM structure
- [ ] `tests/test_server.py::test_template_has_history_list` — covers HIST-01/02 DOM structure
- [ ] `tests/test_server.py::test_template_has_fouc_prevention_script` — covers THME-01 reload behavior prerequisite

These three tests go in the existing `tests/test_server.py` file using the existing `client_not_ready` fixture — no new test file needed.

---

## Security Domain

Phase 13 has minimal security surface — it is entirely client-side with no new API endpoints or server-side data processing.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth change |
| V3 Session Management | No | No session change |
| V4 Access Control | No | No access control change |
| V5 Input Validation | Partial | History entries rendered with `textContent` — never `innerHTML` (Pitfall 5) |
| V6 Cryptography | No | No cryptographic operations |

### Known Threat Patterns for Client-Side Storage

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via history replay | Tampering | Use `textContent` (not `innerHTML`) for all history item labels; query strings are user-authored text, treat as untrusted |
| localStorage key collision | Tampering | Namespace keys with `nitrofind-` prefix (`nitrofind-history`, `nitrofind-theme`) |
| localStorage unavailable | DoS (availability) | Try/catch all localStorage calls; degrade silently — history and theme are non-critical features |

**Security assessment:** Very low risk. The application is a local single-user offline tool (`localhost:5000`). The attack surface for localStorage-based XSS is near-zero (attacker would need local machine access). Standard precautions (textContent, namespaced keys, try/catch) are sufficient.

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `templates/index.html`, `static/js/app.js`, `static/css/style.css` — verified current implementation state
- `CLAUDE.md` — project constraints (vanilla JS, no npm, Python + Flask + ES stack fixed)
- `.planning/REQUIREMENTS.md` — HIST-01, HIST-02, THME-01 requirement text
- `.planning/ROADMAP.md` — Phase 13 success criteria
- CSS custom property specification — W3C standard; `html[data-theme]` scoping is standard CSS

### Secondary (MEDIUM confidence)
- MDN Web Docs localStorage API — standard browser API; synchronous, origin-scoped, 5MB limit
- WCAG 2.1 AA contrast ratio requirements — minimum 4.5:1 for normal text, 3:1 for large text

### Tertiary (LOW confidence)
- None — no unverified findings.

---

## Metadata

**Confidence breakdown:**
- Standard stack (localStorage + CSS custom properties): HIGH — native browser APIs, no versioning concerns
- Architecture (FOUC prevention pattern, data-theme on html): HIGH — well-established browser behavior
- Light theme token values: MEDIUM — teal-600 contrast calculated manually; should be verified in browser devtools
- Pitfalls: HIGH — derived from direct codebase analysis + well-known browser behaviors

**Research date:** 2026-07-06
**Valid until:** Stable — localStorage and CSS custom properties are stable APIs with no breaking changes expected. Light theme contrast values should be rechecked if any token values change.
