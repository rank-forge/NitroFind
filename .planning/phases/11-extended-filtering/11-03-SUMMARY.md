---
phase: 11-extended-filtering
plan: "03"
subsystem: ui
tags: [pyqt6, flask, javascript, css, filtering, elasticsearch]

# Dependency graph
requires:
  - phase: 11-02
    provides: Backend /api/search extended to accept year_from, year_to, country query params and apply ES range/term clauses

provides:
  - Year From, Year To, Country inputs in the filter row (templates/index.html)
  - currentFilters state extended with year_from/year_to/country keys and change-event wiring (static/js/app.js)
  - Consistent input styling using existing CSS token system (static/css/style.css)
  - Human-verified end-to-end FILT-01/02/03 behavior in the live UI

affects: [phase-12, any plan touching filter UI or /api/search query params]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Change event (not input event) for multi-keystroke filter inputs to avoid partial-value queries"
    - "Empty-param strip via URLSearchParams loop — generic, handles new keys without modification"
    - "CSS custom-property tokens for all input styling — no raw hex values"

key-files:
  created: []
  modified:
    - templates/index.html
    - static/js/app.js
    - static/css/style.css

key-decisions:
  - "Use change event (fires on blur/Enter) not input event for year number inputs — prevents spurious ES queries on each digit of a 4-digit year"
  - "Country filter is case-sensitive keyword match (as documented in RESEARCH.md Pitfall 3) — placeholder 'e.g. Germany' signals this convention to users"
  - "Client-side min/max on year inputs (1900-2099) is cosmetic only — _safe_int_param in server.py is the authoritative guard (T-11-02)"
  - "runSearch URLSearchParams spread and empty-param strip loop required zero modification — new keys handled generically"

patterns-established:
  - "Filter input pattern: add id to HTML, cache DOM element, extend currentFilters, assign in onFilterChange, bind change listener — the six-step pattern for new filter controls"

requirements-completed: [FILT-01, FILT-02, FILT-03]

# Metrics
duration: ~45min
completed: 2026-07-03
---

# Phase 11 Plan 03: Extended Filtering UI Summary

**Year From, Year To, and Country filter inputs added to the search filter row and wired end-to-end to the ES backend via existing change-event and URLSearchParams pipeline — human-verified for FILT-01, FILT-02, and FILT-03**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-07-03
- **Completed:** 2026-07-03
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 3

## Accomplishments

- Added `filter-year-from` (number), `filter-year-to` (number), and `filter-country` (text) inputs to `.filter-row` in `templates/index.html`, positioned between the existing `filter-body` select and the sort controls
- Extended `currentFilters` state object and added DOM cache constants (`filterYearFrom`, `filterYearTo`, `filterCountry`) with `change` event listeners wired to `onFilterChange` in `static/js/app.js`
- Added `.filter-row input[type="number"]` and `.filter-row input[type="text"]` CSS rules using existing token system (`var(--bg-input)`, `var(--accent)`, etc.) for visual consistency with existing selects
- Human verification passed all four checks: visual layout, FILT-01 year-range overlap, FILT-02 country keyword match, FILT-03 combination with empty-param stripping

## Task Commits

Each task was committed atomically:

1. **Task 1: Add year + country controls to the filter row and style them** — `a25890c` (feat)
2. **Task 2: Extend currentFilters state and wire new inputs with change events** — `8855650` (feat)
3. **Task 3: Human verification** — approved by user (no code commit; checkpoint resolved)

## Files Created/Modified

- `templates/index.html` — Three new filter inputs added inside `.filter-row`: `filter-year-from`, `filter-year-to`, `filter-country`
- `static/js/app.js` — `currentFilters` extended with three new keys; three DOM cache constants; three assignments in `onFilterChange`; three new `change` event listeners (total now 6)
- `static/css/style.css` — New rules for `.filter-row input[type="number"]`, `.filter-row input[type="text"]`, and their `:focus` variants using existing CSS custom properties

## Decisions Made

- Used `change` event (fires on blur/Enter) instead of `input` for all three new inputs. For the year number inputs this prevents spurious partial-year queries (e.g. querying `196` while the user is still typing `1965`). Applied consistently to the country input as well.
- Country placeholder set to `e.g. Germany` (capital G) to signal the case-sensitive keyword-match convention documented in RESEARCH.md Pitfall 3. Lowercase `germany` may yield zero results — this is expected behavior, not a bug.
- The `runSearch` URLSearchParams spread and empty-param strip loop required no changes — they handle new `currentFilters` keys generically, confirming the architecture from Phase 10.

## Deviations from Plan

None — plan executed exactly as written. The pre-existing `runSearch` empty-param strip loop handled the new keys without modification, as the plan anticipated.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. The feature uses existing Flask server and Elasticsearch node; no new packages or environment variables introduced.

## Threat Surface

No new attack surface introduced beyond what Plan 02 already documented. Client-side `min`/`max` attributes on year inputs are cosmetic. The authoritative coercion/guard is `_safe_int_param` in `server.py` (T-11-02). Country and year values flow through the existing `URLSearchParams` URL, which carries only car-spec filter terms — no secrets or PII.

## Next Phase Readiness

- FILT-01, FILT-02, FILT-03 requirements are fully implemented and verified
- The filter row now exposes all planned extended filtering controls
- Phase 11 is complete; any future filter additions follow the established six-step pattern (HTML id → DOM cache → currentFilters key → onFilterChange assignment → change listener)

---
*Phase: 11-extended-filtering*
*Completed: 2026-07-03*
