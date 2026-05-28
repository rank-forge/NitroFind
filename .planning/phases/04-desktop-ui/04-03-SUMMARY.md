---
phase: 04-desktop-ui
plan: "03"
subsystem: ui
tags:
  - phase-4
  - desktop-ui
  - main-window
  - search-line-edit
  - wave-3
dependency_graph:
  requires:
    - 04-01 (SearchEngine.search with callback+error_callback, results_ready(list,int))
    - 04-02 (ResultDelegate, _result_to_html, FilterSidebar, collect_filters)
  provides:
    - MainWindow(QMainWindow) for Plan 04 main.py swap
    - SearchLineEdit(QLineEdit) with keyReleaseEvent Escape handler
    - Full pytest-qt suite covering SRCH-01/02/03/04 + UIPL-01/02/04
  affects:
    - nitrofind/ui/main_window.py
    - tests/test_ui/test_main_window.py
tech_stack:
  added: []
  patterns:
    - "TDD GREEN task 1 (implementation) + task 2 (tests), all 15 pass"
    - "monkeypatch.setattr('nitrofind.ui.main_window.SearchEngine', ...) injection idiom"
    - "_trigger_search_and_capture_callback helper with context-manager waitSignal"
    - "QTimer single-shot 300ms debounce, _current_seq monotonic stale-result guard"
key_files:
  created:
    - tests/test_ui/test_main_window.py
  modified:
    - nitrofind/ui/main_window.py (407 lines: MainWindow + SearchLineEdit; StubMainWindow removed)
decisions:
  - "MainWindow(client) accepts Elasticsearch client and constructs SearchEngine internally — matches main.py W0-EXT-03 on_es_ready() pattern"
  - "monkeypatch.setattr injection over constructor injection — avoids test-only constructor argument; patches SearchEngine at module level so MainWindow(mock_client) receives engine_mock from __init__"
  - "keyReleaseEvent (not keyPressEvent) for Escape — UI-SPEC Pitfall 2; keyPressEvent fires before IME intercepts in some platforms"
  - "_trigger_search_and_capture_callback helper extracted to share callback-capture logic across 9 tests; uses context-manager waitSignal form to block until timer fires"
  - "StubMainWindow removed entirely — Plan 04 (W0-EXT-03) must update main.py import from StubMainWindow to MainWindow"
metrics:
  duration: "12 minutes"
  completed: "2026-05-28"
  tasks_completed: 2
  files_modified: 1
  files_created: 1
---

# Phase 4 Plan 03: MainWindow + SearchLineEdit Summary

**One-liner:** MainWindow replaces StubMainWindow with full debounce-search UI — QSplitter layout (200/320/580), 300ms single-shot timer, _current_seq stale-result guard, static error string (T-04-03), and 15 pytest-qt tests covering all SRCH/UIPL requirements.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Implement MainWindow + SearchLineEdit | 34c504d | nitrofind/ui/main_window.py |
| 2 | Build 15-test pytest-qt suite | fc60cac | tests/test_ui/test_main_window.py |

## MainWindow Public API

### Constructor

```python
def __init__(self, client) -> None:
    # client: Elasticsearch instance (not SearchEngine)
    # Constructs SearchEngine(client) internally
    # W0-EXT-03: MainWindow(client) matches main.py on_es_ready() pattern
```

### Property Accessors (test introspection — mirrors LoadingWindow convention)

```python
@property def search_bar(self) -> SearchLineEdit
@property def status_label(self) -> QLabel
@property def result_list(self) -> QListWidget
@property def detail_pane(self) -> QTextBrowser
@property def filter_sidebar(self) -> FilterSidebar
@property def debounce_timer(self) -> QTimer
```

### Key Methods

```python
def _execute_search(self) -> None
    # Empty query short-circuits (no ES dispatch), clears list + status
    # Non-empty: _current_seq += 1, seq=_current_seq, setWindowTitle, setText("Searching…")
    # Dispatches self._engine.search(query, filters=..., callback=lambda results, took, s=seq: ..., error_callback=...)

def _on_results(self, results: list, took_ms: int, seq: int) -> None
    # if seq != self._current_seq: return  # T-04-05 stale guard
    # Clears list, populates QListWidgetItem with UserRole=HTML, UserRole+1=ArticleResult
    # Sets status: "N results (T:.2fs)" or "No results"
    # Selects row 0 when results non-empty

def _on_search_error(self, msg: str) -> None
    # logger.warning("Search failed: %s", msg)  — % formatting only (T-04-03)
    # self._status_label.setText("Search failed. Check Elasticsearch connection.")  — static only

def _on_result_hovered(self, row: int) -> None
    # Fires on currentRowChanged — arrow keys and single-click
    # row < 0 → return

def _on_result_activated(self, item: QListWidgetItem) -> None
    # Fires on itemActivated — double-click and Enter key

def _show_result_detail(self, result: ArticleResult) -> None
    # Prefers result.body (W0-EXT-01) over result.excerpt for SRCH-03
    # detail_pane.setHtml(<h2> title, <p> domain · url, <hr>, <p> body_text)
```

### SearchLineEdit

```python
class SearchLineEdit(QLineEdit):
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.clear()
        super().keyReleaseEvent(event)
```

## MagicMock-SearchEngine Injection Idiom

```python
# In _make_window(qtbot, monkeypatch, engine_mock=None):
monkeypatch.setattr(
    "nitrofind.ui.main_window.SearchEngine",
    MagicMock(return_value=engine_mock),
)
window = MainWindow(mock_client)
```

This patches `SearchEngine` at the `nitrofind.ui.main_window` namespace so `MainWindow.__init__`'s `self._engine = SearchEngine(client)` receives `engine_mock`. The callback is captured from `engine_mock.search.call_args.kwargs["callback"]` after the debounce timer fires.

**Plan 04 reference:** Use the same idiom if further tests against MainWindow are needed.

## Test Counts

```
tests/test_ui/test_main_window.py — 15 tests, all pass

pytest tests/test_ui/test_main_window.py -x -m "not integration"
15 passed in 4.18s

pytest tests/ -x -m "not integration"
161 passed, 6 deselected in 8.55s
```

No regressions in Phase 1–3 tests.

## Plan 04 Compatibility

Plan 04 can update `main.py` with the following two-line change (W0-EXT-03) — no other changes required:

```python
# main.py line 34 — change import:
# from nitrofind.ui.main_window import StubMainWindow
from nitrofind.ui.main_window import MainWindow

# main.py on_es_ready() line 115 — change construction:
# main_window = StubMainWindow()
main_window = MainWindow(client)  # client already constructed above
```

`StubMainWindow` has been removed from `nitrofind/ui/main_window.py` (Plan 03). The `client` variable is already in scope in `on_es_ready()`.

## Copywriting Contract Compliance

All UI-SPEC verbatim strings implemented as required (zero deviations):

| Element | Implemented Copy | Tested |
|---------|-----------------|--------|
| Search bar placeholder | `"Search cars, manufacturers, models…"` (U+2026) | yes (source check) |
| Status: loading | `"Searching…"` | yes |
| Status: results | `"{N} results ({T:.2f}s)"` | test_status_label_updated |
| Status: no results | `"No results"` | test_status_label_no_results |
| Status: error | `"Search failed. Check Elasticsearch connection."` | test_error_displays_static_string |
| Detail pane initial | `"Select a result to read the article."` (centered, #80cbc4) | yes (source check) |
| Window title idle | `"NitroFind — Ready"` (U+2014 em-dash) | yes (source check) |
| Window title searching | `"NitroFind — {query}"` (U+2014 em-dash) | yes |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] qtbot.waitSignal outside context manager did not block**
- **Found during:** Task 2 initial test run (test_result_list_populates failed)
- **Issue:** First test version used `qtbot.waitSignal(signal, timeout=N)` without `with` context manager — this returns a SignalBlocker object immediately without waiting. `engine.search` was not called because the debounce timer had not fired yet when `assert engine_mock.search.called` ran.
- **Fix:** Changed all `waitSignal` calls to context manager form `with qtbot.waitSignal(...): pass` and extracted `_trigger_search_and_capture_callback` helper that encapsulates the pattern.
- **Files modified:** `tests/test_ui/test_main_window.py` (no committed RED phase — fixed before commit)
- **Commit:** fc60cac (task 2 commit contains the fixed version)

## Known Stubs

None — `MainWindow` is fully implemented with all handlers wired. `_show_result_detail` prefers `result.body` (W0-EXT-01) over `result.excerpt` — both are non-empty strings from ES documents, not placeholders.

## Threat Flags

No new threat surface introduced beyond what is documented in the plan's `<threat_model>`:
- T-04-02: QTextBrowser setOpenLinks(False), setOpenExternalLinks(False) confirmed in source
- T-04-03: Static error string enforced by test_error_displays_static_string
- T-04-05: Stale-result guard enforced by test_stale_results_discarded

## Self-Check: PASSED

Files exist on disk:
- `nitrofind/ui/main_window.py` — FOUND (407 lines, MainWindow + SearchLineEdit)
- `tests/test_ui/test_main_window.py` — FOUND (649 lines, 15 tests)

Commits present in git log:
- `34c504d` — FOUND (feat: MainWindow + SearchLineEdit)
- `fc60cac` — FOUND (feat: 15-test suite)

Content spot-checks confirmed:
- `class MainWindow(QMainWindow)` in main_window.py
- `class SearchLineEdit(QLineEdit)` in main_window.py
- `setInterval(300)` and `setSingleShot(True)` present
- `Key_Escape` in `keyReleaseEvent` (not `keyPressEvent`)
- `setSizes([200, 320, 580])` present
- `if seq != self._current_seq` stale guard present
- All 15 Copywriting Contract strings verbatim
- All 15 test functions present
- `pytestmark = pytest.mark.skipif` present
- No `QApplication(sys.argv)` in test file
- No f-string logger calls in main_window.py

Final test run: 161 passed, 0 failed, 6 deselected (integration).
