---
phase: 10-search-quality-sort
plan: "02"
subsystem: ui-sort-controls
tags: [sort, ui, filter-row, vanilla-js, css-tokens]
dependency_graph:
  requires: [10-01]
  provides: [sort-ui, sort-param-wiring]
  affects: [templates/index.html, static/js/app.js, static/css/style.css]
tech_stack:
  added: []
  patterns: [sort-toggle-buttons, currentSort-state, dataset-sort-wiring]
key_files:
  created: []
  modified:
    - templates/index.html
    - static/js/app.js
    - static/css/style.css
decisions:
  - Sort choice persists across new queries (not reset per search — per RESEARCH Pitfall 5)
  - sort= param omitted entirely for relevance (ES default _score desc; mirrors empty-filter-strip pattern)
  - classList.toggle("active", condition) mirrors existing updateSelection pattern for active-state management
metrics:
  duration_minutes: 2
  completed_date: "2026-06-26"
  tasks_completed: 2
  files_modified: 3
status: awaiting-human-checkpoint
---

# Phase 10 Plan 02: Sort Controls UI Summary

**One-liner:** Three sort toggle buttons (Relevance/Newest/Largest) in the filter row, driven by `currentSort` module-level state, toggling `active` class and appending `sort=` to `/api/search` requests (omitted for relevance default).

## What Was Built

Two frontend changes completing the SORT-01 requirement:

1. **Sort button markup + styling (Task 1):** Three `<button type="button">` elements inside a `.sort-controls` container appended to `.filter-row` in `templates/index.html`. Buttons carry `data-sort="relevance"`, `data-sort="date"`, and `data-sort="size"`. The Relevance button has the `active` class by default. CSS rules `.sort-btn` and `.sort-btn.active` added to `static/css/style.css` reusing all existing design tokens (`--bg-input`, `--accent`, `--border`, `--radius`, `--transition`, `--text-primary`); no new CSS variables introduced.

2. **JS state + handler + runSearch wiring (Task 2):** `let currentSort = "relevance"` added to module-level state; `sortBtns` cached via `querySelectorAll`. `onSortChange(newSort)` updates `currentSort`, toggles `active` class on all buttons via `classList.toggle("active", btn.dataset.sort === newSort)`, and re-runs `runSearch(currentQuery)` when a query is active. Each button wired with `addEventListener("click", ...)`. `runSearch` appends `params.set("sort", currentSort)` only when `currentSort !== "relevance"`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Sort button markup + styling | f4964eb | templates/index.html, static/css/style.css |
| 2 | currentSort state, onSortChange handler, sort param in runSearch | 068832f | static/js/app.js |

## Awaiting Human Checkpoint

Task 3 is a `checkpoint:human-verify` that requires a running app with a populated ES index.

**Verification steps (from plan):**
1. Search for `ferrari`. Confirm three sort buttons appear in the filter row with "Relevance" showing active style.
2. Click "Newest" — button becomes active, results reorder newest-first.
3. Click "Largest" — button becomes active, results reorder largest-first.
4. Click "Relevance" — button becomes active, original relevance-scored order restored.
5. With "Newest" active, type `mustang` — sort choice persists (newest-first, button stays active).

**Resume signal:** Type "approved" if all five checks pass, or describe what went wrong.

## Verification Results

Automated checks (Tasks 1-2):
- `grep -c 'class="sort-btn' templates/index.html` → 3
- `grep -q 'data-sort="relevance/date/size"'` → all present
- `grep -q '.sort-btn' static/css/style.css` + `.sort-btn.active` → present
- `node --check static/js/app.js` → exit 0
- `python3 -m pytest tests/ -q -m "not integration"` → 170 passed, 5 deselected

## Key Decisions

1. **Sort persists across new queries** — `currentSort` is never reset in `runSearch`; matches RESEARCH Pitfall 5 guidance.
2. **`sort=` omitted for relevance** — mirrors the empty-filter-strip pattern; ES default `_score desc` is the correct behavior without an explicit `sort` clause.
3. **`classList.toggle("active", condition)` pattern** — matches the existing `updateSelection` `classList.toggle("selected", i === selectedIndex)` pattern for consistency.

## Deviations from Plan

None — plan executed exactly as written. All four edits from Task 2 action description applied verbatim.

## Threat Surface Scan

No new network endpoints or auth paths introduced. The `sort=` value sent from the browser is bounded by the three `data-sort` attribute values set in static markup; the server-side `_VALID_SORTS` allowlist from Plan 01 (T-10-SORT) remains the authoritative guard. T-10-UI-SORT and T-10-UI-XSS dispositions from the plan's threat model are satisfied.

## Self-Check: PASSED

Files modified:
- FOUND: templates/index.html (modified)
- FOUND: static/js/app.js (modified)
- FOUND: static/css/style.css (modified)

Commits:
- FOUND: f4964eb (feat(10-02): add sort button markup and styling)
- FOUND: 068832f (feat(10-02): wire currentSort state, onSortChange handler...)
