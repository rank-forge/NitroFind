---
phase: 04-desktop-ui
plan: "04"
subsystem: ui
tags:
  - phase-4
  - desktop-ui
  - wiring
  - human-verify
  - wave-4

dependency_graph:
  requires:
    - 04-01 (ArticleResult.body, results_ready(list,int))
    - 04-02 (ResultDelegate, FilterSidebar)
    - 04-03 (MainWindow, SearchLineEdit)
  provides:
    - main.py fully wired to MainWindow(client) — W0-EXT-03 complete
    - All five Phase 4 ROADMAP success criteria human-verified end-to-end
  affects:
    - main.py

tech_stack:
  added: []
  patterns:
    - "Two-line surgical import swap — no new logic, only wiring change"
    - "apply_stylesheet ordering preserved before MainWindow construction (UIPL-03)"

key_files:
  created: []
  modified:
    - main.py (import swap line 34; construction swap line 115; docstring updates)

key-decisions:
  - "W0-EXT-03: MainWindow(client) constructed in on_es_ready() — client already in scope from Elasticsearch(ES_URL) call on line 103"
  - "No structural changes: state dict, signal wiring, apply_stylesheet order, shutdown_handler all unchanged from Phase 1 Plan 04"
  - "Human verified all 20 end-to-end steps against live ES with real indexed data — approved"

patterns-established:
  - "Surgical two-line wiring change as final integration step — keeps Phase 1-3 plumbing intact"

requirements-completed:
  - UIPL-03

metrics:
  duration: "2 minutes"
  completed: "2026-05-28"
  tasks_completed: 2
  files_modified: 1
  files_created: 0
---

# Phase 4 Plan 04: main.py Wiring + Human Verification Summary

**One-liner:** Swapped StubMainWindow for MainWindow(client) in main.py on_es_ready() (W0-EXT-03) and human-verified all five Phase 4 ROADMAP success criteria end-to-end against live ES with real indexed data.

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-28
- **Completed:** 2026-05-28
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- main.py wired to the real MainWindow — two-line import and construction swap completing W0-EXT-03
- Full Phase 4 end-to-end verified by human against live Elasticsearch with real indexed articles (all 20 steps passed)
- All eight requirements (SRCH-01..04, UIPL-01..04) confirmed against live ES behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Update main.py to construct MainWindow(client)** - `d30ecf9` (feat)
2. **Task 2: End-to-end human verification — APPROVED** - no code change; checkpoint outcome recorded

**Plan metadata:** (this docs commit)

## Files Created/Modified

- `main.py` — import swapped to MainWindow; StubMainWindow construction replaced with MainWindow(client); four docstring/comment references updated for internal consistency

## main.py Diff (W0-EXT-03)

```python
# Line 34 — import change:
# Before: from nitrofind.ui.main_window import StubMainWindow
# After:
from nitrofind.ui.main_window import MainWindow

# Line 115 (inside on_es_ready) — construction change:
# Before: main_window = StubMainWindow()
# After:
main_window = MainWindow(client)
```

Additional docstring/comment updates to remove StubMainWindow references (4 occurrences total):
- Module docstring line 9 (`StubMainWindow` -> `MainWindow`)
- `on_es_ready` docstring (`StubMainWindow` -> `MainWindow (W0-EXT-03)`)
- `state` dict comment (`type: StubMainWindow | None` -> `type: MainWindow | None`)

## Automated Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `from nitrofind.ui.main_window import MainWindow` present | PASS |
| No `StubMainWindow` anywhere in main.py (`grep -c` returns 0) | PASS |
| `MainWindow(client)` inside `on_es_ready` | PASS |
| `apply_stylesheet` at line 74 — before `MainWindow(client)` at line 115 | PASS |
| `grep -c "MainWindow" main.py` returns 5 (>= 2) | PASS |
| `pytest tests/ -x -m "not integration"` exits 0 | PASS — 161 passed, 6 deselected |
| Module-spec smoke test prints 'main.py imports clean' | PASS |

## Full Non-Integration Test Suite Output

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
PyQt6 6.11.0 -- Qt runtime 6.11.0 -- Qt compiled 6.11.0
rootdir: /mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind
configfile: pytest.ini
plugins: qt-4.5.0, vcr-1.0.2
collected 167 items / 6 deselected / 161 selected

tests/test_es_manager.py .....                                           [  3%]
tests/test_es_schema.py ...                                              [  4%]
tests/test_loading_window.py ....                                        [  7%]
tests/test_lockfile.py ...                                               [  9%]
tests/test_scraper/test_blogs.py ........                                [ 14%]
tests/test_scraper/test_cleaner.py ..........                            [ 20%]
tests/test_scraper/test_cli.py .........                                 [ 26%]
tests/test_scraper/test_indexer.py ......                                [ 29%]
tests/test_scraper/test_state.py ......                                  [ 33%]
tests/test_scraper/test_wikipedia.py ......                              [ 37%]
tests/test_search/test_engine.py ................................        [ 57%]
tests/test_search/test_models.py ..........                              [ 63%]
tests/test_search/test_query_builder.py ............................     [ 80%]
tests/test_ui/test_filter_sidebar.py .........                           [ 86%]
tests/test_ui/test_main_window.py ...............                        [ 95%]
tests/test_ui/test_result_delegate.py .......                            [100%]

====================== 161 passed, 6 deselected in 7.35s =======================
```

No regressions in Phase 1-4 tests.

## Human Verification Result — APPROVED

The user ran the full 20-step verification against a live Elasticsearch instance with real indexed articles. All steps passed.

| Step | Description | Result |
|------|-------------|--------|
| 3-5 | App launches, LoadingWindow spinner appears, ES becomes healthy, main window opens | PASS |
| 6 | SRCH-01: Search results appear within ~300ms of typing pause; debounce suppresses per-keystroke updates | PASS |
| 7 | SRCH-02: Result rows show bold title, muted teal source domain, highlighted excerpt terms in bold | PASS |
| 8 | SRCH-03: Clicking a result populates detail pane with full article body — no external browser opens | PASS |
| 9-10 | SRCH-03: Arrow navigation and Enter key update/open detail pane | PASS |
| 11-13 | SRCH-04 / UIPL-01: Filter sidebar narrows results; filter state persists when query is retyped; multi-filter works | PASS |
| 14 | UIPL-03: Dark teal theme applied uniformly — no widgets render with default Qt light styling | PASS |
| 15-16 | UIPL-04: Escape clears search bar, result list, status label, and resets window title to "NitroFind — Ready" | PASS |
| 17 | UIPL-02: Status label shows "N results (T:.2fs)" with two decimal places | PASS |
| 18 | Status label shows "No results" for zero-result query | PASS |
| 19 | (Optional) Error path: status label shows static "Search failed. Check Elasticsearch connection." on ES down | PASS |
| 20 | Clean shutdown: no orphaned Elasticsearch JVM processes after app quit | PASS |

**Resume signal received:** "approved" — all 20 steps confirmed.

## Phase 4 Requirements Completion

| Requirement | Automated | Human-Verified | Status |
|-------------|-----------|---------------|--------|
| SRCH-01: debounced search (300ms) | PASS (Plan 03) | PASS (step 6) | COMPLETE |
| SRCH-02: result rows with title/domain/highlight | PASS (Plan 03) | PASS (step 7) | COMPLETE |
| SRCH-03: detail pane on click/Enter, no browser | PASS (Plan 03) | PASS (steps 8-10) | COMPLETE |
| SRCH-04: filter persistence across queries | PASS (Plan 03) | PASS (steps 11-13) | COMPLETE |
| UIPL-01: highlight bold in excerpts | PASS (Plan 02) | PASS (step 7) | COMPLETE |
| UIPL-02: status label with took_ms | PASS (Plan 03) | PASS (step 17) | COMPLETE |
| UIPL-03: dark_teal theme before window construction | PASS (grep ordering) | PASS (step 14) | COMPLETE |
| UIPL-04: Escape/arrows/Enter keyboard nav | PASS (Plan 03) | PASS (steps 15-16, 9-10) | COMPLETE |

All eight Phase 4 requirements fully verified. Phase 4 is complete.

## Decisions Made

- W0-EXT-03 implemented as a surgical two-line change — no refactoring of the Phase 1 startup flow needed; `client` was already in scope at the `on_es_ready` call site
- Human verification served as the authoritative gate for live-ES behavior that unit tests with mocked engines cannot cover (dark theme rendering, debounce feel, visual highlight contrast)

## Deviations from Plan

### Additional Changes (Minor Documentation Fix)

Beyond the two-line plan-specified change, four docstring/comment references to `StubMainWindow` were updated to `MainWindow` for internal consistency. These are comments only — no behavioral change.

None of the plan's "DO NOT touch" items were modified (apply_stylesheet, ESHealthWorker signal wiring, shutdown_handler, state dict pattern, logger calls).

**Total deviations:** 0 auto-fixed. Plan executed as written plus minor comment cleanup.

## Issues Encountered

None — Task 1 applied cleanly; Task 2 (human verify) passed all 20 steps without issues.

## User Setup Required

None — no external service configuration required beyond what Phase 1 already established (Elasticsearch 8.x installed and indexed data from Phase 2).

## Next Phase Readiness

Phase 4 is complete. All desktop UI functionality is delivered and verified:
- Search bar with 300ms debounce
- Result list with styled delegate and ES highlights
- Detail pane with full article body
- Filter sidebar with persistence
- Dark teal theme, keyboard navigation, clean shutdown

No blockers for Phase 5 (packaging / distribution).

## Known Stubs

None — all Phase 4 components are fully implemented and human-verified with live data.

## Threat Flags

No new threat surface introduced. All STRIDE mitigations from the plan's threat register confirmed:
- T-04-W3-01: main.py module-spec smoke test passed (no import-time crash)
- T-04-W3-02: apply_stylesheet ordering confirmed by line-number assertion
- T-04-W3-03: _on_search_error static string enforced by existing unit test and human step 19
- T-04-W3-04: shutdown_handler/aboutToQuit unchanged from Phase 1; human step 20 confirmed clean shutdown

## Self-Check: PASSED

File exists on disk:
- `main.py` — FOUND (228 lines, MainWindow import + construction)

Task commit present in git log:
- `d30ecf9` — FOUND (feat(04-04): wire MainWindow(client) into main.py)

Content spot-checks:
- `from nitrofind.ui.main_window import MainWindow` — present
- `main_window = MainWindow(client)` — present (line 115)
- `StubMainWindow` — absent (0 occurrences)
- `apply_stylesheet(app, theme="dark_teal.xml")` — present at line 74 (before line 115)

---
*Phase: 04-desktop-ui*
*Completed: 2026-05-28*
