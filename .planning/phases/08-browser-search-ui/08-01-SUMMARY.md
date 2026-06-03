---
phase: 08-browser-search-ui
plan: "01"
subsystem: browser-ui
tags: [flask, html, css, spa, dark-theme]
dependency_graph:
  requires: []
  provides:
    - "templates/index.html — three-state SPA skeleton with all element IDs for app.js"
    - "static/css/style.css — dark teal CSS custom properties + data-state view switching"
    - "nitrofind/server.py — render_template GET / route with explicit template/static roots"
  affects:
    - "nitrofind/server.py — GET / now calls render_template (not raw string)"
    - "tests/test_server.py — existing tests still pass (b'NitroFind' in title tag)"
tech_stack:
  added: []
  patterns:
    - "CSS data-state attribute selectors for SPA view switching (no JS show/hide)"
    - "Flask explicit template_folder/static_folder via _pkg_dir to resolve project-root templates"
    - "CSS custom properties on :root for dark theme token system"
key_files:
  created:
    - templates/index.html
    - static/css/style.css
  modified:
    - nitrofind/server.py
decisions:
  - "Used _pkg_dir = os.path.dirname(os.path.abspath(__file__)) to resolve templates/ and static/ at project root, not inside nitrofind/ package dir (Pitfall 1 from RESEARCH.md)"
  - "data-state=home hardcoded in HTML body tag to prevent flash of unstyled content before JS runs (Pitfall 6)"
  - "System-font stack chosen over self-hosted Geist/Outfit — offline-safe, zero setup (D-08)"
  - ".result-item.selected uses border-left: 2px solid var(--accent) for keyboard-nav cursor (D-11)"
  - "Manufacturer filter left as single-option select (no static list; no aggregation endpoint)"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-06-03"
  tasks_completed: 3
  files_modified: 3
---

# Phase 8 Plan 01: Flask Wiring + HTML Skeleton + CSS Theme Summary

Flask wired to serve `render_template("index.html")` from project-root templates/ and static/; three-state SPA skeleton and dark teal CSS custom property system created.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Rewire Flask GET / to render_template with explicit template/static roots | 99f6d60 | nitrofind/server.py |
| 2 | Create templates/index.html three-state SPA skeleton | d8131c2 | templates/index.html |
| 3 | Create static/css/style.css dark teal theme and state-machine layout | b016cfc | static/css/style.css |

## What Was Built

### Task 1 — Flask GET / rewiring (nitrofind/server.py)

Three edits to `nitrofind/server.py`:

1. Import line: `from flask import Flask, jsonify, render_template, request` (render_template added alphabetically)
2. Flask constructor: `_pkg_dir = os.path.dirname(os.path.abspath(__file__))` then `app = Flask(__name__, template_folder=os.path.join(_pkg_dir, "..", "templates"), static_folder=os.path.join(_pkg_dir, "..", "static"))` — required because Flask(__name__) inside nitrofind/server.py resolves root_path to nitrofind/, not project root
3. `index()` body: `return render_template("index.html")` with docstring updated to "NitroFind search UI (Phase 8)"
4. Module docstring: API-04 coverage and index export description updated to reflect rendered template

### Task 2 — templates/index.html (65 lines)

Single HTML5 document implementing three UI states in one DOM:
- `<body data-state="home">` — hardcoded at parse time for immediate CSS rendering
- **Home view**: `.home-view` with `<h1 class="logo">`, `.search-wrap`, `#search-input` (disabled), `#status-line`
- **Results view**: `.results-view` with `.top-bar` (`#search-input-results`), `.filter-row` (3 selects: `#filter-manufacturer` / `#filter-era` / `#filter-body`), `#stats-line`, `#results-list`
- **Article view**: `.article-view` with `#back-btn`, `#article-title`, `#article-source`, `#article-body`
- Static era options: 1950s–2020s; body style options: coupe/sedan/hatchback/convertible/SUV/truck
- No CDN links (offline constraint)

### Task 3 — static/css/style.css (306 lines)

Complete dark teal CSS theme:
- `:root` block with 10 custom properties: `--bg-primary: #0f1117` (off-black), `--bg-surface`, `--bg-input`, `--text-primary: #e6edf3`, `--text-secondary`, `--accent: #2dd4bf`, `--accent-hover`, `--border`, `--radius: 6px`, `--transition: 200ms ease`
- State machine via `body[data-state="results"]` and `body[data-state="article"]` attribute selectors — CSS owns show/hide, no JS needed
- Home view: flex column centered full-viewport
- Results view: sticky top-bar, flex filter-row, scrollable results-list
- Article view: max-width 800px centered
- `#search-input:disabled { cursor: not-allowed; opacity: 0.5 }` warmup state (D-07)
- `.result-item.selected { border-left: 2px solid var(--accent) }` keyboard nav (D-11)
- `.result-excerpt b { font-weight: 600 }` ES highlight rendering (SRCH-02)
- System-font stack; no CDN; no pure black; no neon glows

## Verification

All 5 existing `tests/test_server.py` tests pass after the render_template switch. Integration check confirmed: `GET /` returns 200 with `<!DOCTYPE html>` and `data-state="home"` in response body via Flask test client.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `static/js/app.js` does not exist yet — created in Plan 02. The `<script src="/static/js/app.js">` reference in `templates/index.html` will 404 until Plan 02 creates this file. This is expected and intentional: Plan 01 delivers the shell; Plan 02 delivers the JS behavior.
- `#search-input-results` is present in the DOM but wired to no behavior until app.js exists.

## Threat Flags

None — no new server-side attack surface introduced. Static template served from local disk; no user input reaches GET /. T-08-02 mitigation verified: no external http(s) .js/.css URLs in templates/index.html.

## Self-Check: PASSED

- `templates/index.html`: FOUND
- `static/css/style.css`: FOUND
- `nitrofind/server.py`: FOUND (modified)
- Commit 99f6d60: FOUND
- Commit d8131c2: FOUND
- Commit b016cfc: FOUND
- `pytest tests/test_server.py -x`: 5 passed
- Integration render_template check: 200 OK, DOCTYPE present, data-state=home present
