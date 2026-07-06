---
phase: 13-history-theme
plan: "01"
subsystem: testing
tags: [pytest, flask, template, dom-structure, tdd]

# Dependency graph
requires:
  - phase: 12-search-ux
    provides: tests/test_server.py with client_not_ready fixture and test_root_* pattern
provides:
  - Three RED template-structure tests locking DOM contract for HIST-01/02 and THME-01
affects: [13-02-PLAN.md, templates/index.html implementation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "client_not_ready fixture + GET / byte-substring assertion for template DOM structure tests"

key-files:
  created: []
  modified:
    - tests/test_server.py

key-decisions:
  - "Used existing client_not_ready fixture — no new fixture or test file needed; DOM structure is ES-readiness-independent"
  - "Ordered tests: history_list, theme_toggle, fouc_prevention_script matching plan acceptance criteria order"

patterns-established:
  - "Wave 0 RED scaffold: append template-structure tests to test_server.py before modifying templates — locks DOM contract before implementation"

requirements-completed: [HIST-01, HIST-02, THME-01]

# Metrics
duration: 2min
completed: 2026-07-06
---

# Phase 13 Plan 01: History & Theme RED Test Scaffold Summary

**Three RED pytest assertions locking id="history-list", id="theme-toggle", and FOUC-prevention script DOM contract before template implementation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-06T17:29:51Z
- **Completed:** 2026-07-06T17:31:53Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Appended three new test functions to `tests/test_server.py` after `test_root_uses_template`
- All three tests fail RED against current `templates/index.html` (none of the markers exist yet)
- Existing `test_root_returns_html` and `test_root_uses_template` remain green
- No new test file or fixture created — reused existing `client_not_ready` pattern exactly

## Task Commits

Each task was committed atomically:

1. **Task 1: Add three RED template-structure tests to test_server.py** - `0735d3e` (test)

**Plan metadata:** (see final commit below)

## Files Created/Modified
- `tests/test_server.py` - Appended `test_template_has_history_list`, `test_template_has_theme_toggle`, `test_template_has_fouc_prevention_script` with Phase 13 section header comment

## Decisions Made
- Used existing `client_not_ready` fixture with no modification — template rendering is independent of ES readiness state
- Added section comment `# Phase 13: History & Theme DOM structure — HIST-01/02, THME-01 (RED scaffold)` to group the new tests visually

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RED scaffold complete: `test_template_has_history_list`, `test_template_has_theme_toggle`, `test_template_has_fouc_prevention_script` all fail
- Plan 13-02 can now implement `templates/index.html`, `static/css/style.css`, and `static/js/app.js` with an executable definition of done
- Tests turn GREEN when: `id="history-list"` UL, `id="theme-toggle"` button, and FOUC inline script with `nitrofind-theme`/`dataset.theme` are added to the template

## Self-Check

- `tests/test_server.py` contains `def test_template_has_history_list` — FOUND
- `tests/test_server.py` contains `def test_template_has_theme_toggle` — FOUND
- `tests/test_server.py` contains `def test_template_has_fouc_prevention_script` — FOUND
- Commit `0735d3e` exists — FOUND

## Self-Check: PASSED

---
*Phase: 13-history-theme*
*Completed: 2026-07-06*
