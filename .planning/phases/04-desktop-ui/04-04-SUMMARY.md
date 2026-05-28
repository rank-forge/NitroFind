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
    - Human-verification checkpoint for Phase 4 end-to-end success criteria
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
decisions:
  - "W0-EXT-03: MainWindow(client) constructed in on_es_ready() — client already in scope from Elasticsearch(ES_URL) call on line 103"
  - "No structural changes: state dict, signal wiring, apply_stylesheet order, shutdown_handler all unchanged from Phase 1 Plan 04"
metrics:
  duration: "1 minute"
  completed: "2026-05-28"
  tasks_completed: 1
  tasks_pending_human_verify: 1
  files_modified: 1
  files_created: 0
---

# Phase 4 Plan 04: main.py Wiring + Human Verification Summary

**One-liner:** Swapped StubMainWindow for MainWindow(client) in main.py on_es_ready() — W0-EXT-03 wiring change; human-verification checkpoint pending for Phase 4 end-to-end success criteria 1-5.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Update main.py to construct MainWindow(client) in place of StubMainWindow() | d30ecf9 | main.py |

## Tasks Pending (Checkpoint)

| # | Task | Type | Status |
|---|------|------|--------|
| 2 | End-to-end human verification of Phase 4 success criteria 1-5 | checkpoint:human-verify | Awaiting human |

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
- Module docstring line 9 (`StubMainWindow` → `MainWindow`)
- `on_es_ready` docstring (`StubMainWindow` → `MainWindow (W0-EXT-03)`)
- `state` dict comment (`type: StubMainWindow | None` → `type: MainWindow | None`)

## Acceptance Criteria Verification

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

## UIPL-03 Ordering Preserved

`apply_stylesheet(app, theme="dark_teal.xml")` remains on line 74 — confirmed to appear before `MainWindow(client)` on line 115. UIPL-03 requirement unbroken.

## Phase 4 Completion Status

| Requirement | Automated Verification | Human Verification |
|-------------|----------------------|--------------------|
| SRCH-01: debounced search (300ms) | PASS (test_debounce_timer_fires_after_delay, Plan 03) | Pending checkpoint |
| SRCH-02: result rows with title/domain/highlight | PASS (test_result_list_populates, Plan 03) | Pending checkpoint |
| SRCH-03: detail pane on click/Enter, no browser | PASS (test_result_click_populates_detail_pane, Plan 03) | Pending checkpoint |
| SRCH-04: filter persistence across queries | PASS (test_filter_persistence, Plan 03) | Pending checkpoint |
| UIPL-01: highlight bold in excerpts | PASS (test_result_to_html_uses_highlight, Plan 02) | Pending checkpoint |
| UIPL-02: status label with took_ms | PASS (test_status_label_updated, Plan 03) | Pending checkpoint |
| UIPL-03: dark_teal theme before window construction | PASS (grep ordering assertion) | Pending checkpoint |
| UIPL-04: Escape/arrows/Enter keyboard nav | PASS (test_escape_clears_search, etc., Plan 03) | Pending checkpoint |

All automated checks PASS. Human verification (Task 2 checkpoint) will confirm live ES behavior.

## Deviations from Plan

### Additional Changes (Minor Documentation Fix)

Beyond the two-line plan-specified change, four docstring/comment references to `StubMainWindow` were updated to `MainWindow` for internal consistency. These are comments only — no behavioral change.

None of the plan's "DO NOT touch" items were modified (apply_stylesheet, ESHealthWorker signal wiring, shutdown_handler, state dict pattern, logger calls).

## Known Stubs

None — the main.py wiring change is complete. MainWindow is fully implemented in Plan 03.

## Threat Flags

No new threat surface introduced. The import swap is the only change; all threat mitigations from the plan's STRIDE register remain in place:
- T-04-W3-01: main.py module-spec smoke test passed (no import-time crash)
- T-04-W3-02: apply_stylesheet ordering confirmed by line-number assertion
- T-04-W3-03: _on_search_error static string enforced by existing unit test
- T-04-W3-04: shutdown_handler/aboutToQuit unchanged from Phase 1

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
