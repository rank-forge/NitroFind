---
phase: 04-desktop-ui
plan: "02"
subsystem: ui
tags:
  - phase-4
  - desktop-ui
  - delegate
  - filter-sidebar
  - wave-2
dependency_graph:
  requires:
    - 04-01
    - 03-search-logic-relevance-scoring/03-*
  provides:
    - ResultDelegate class for Plan 03 MainWindow result list rendering
    - _result_to_html function for HTML fragment generation with ES highlights
    - FilterSidebar class with collect_filters() for Plan 03 MainWindow filter wiring
  affects:
    - nitrofind/ui/result_delegate.py
    - nitrofind/ui/filter_sidebar.py
    - tests/test_ui/test_result_delegate.py
    - tests/test_ui/test_filter_sidebar.py
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN per task (test commit before implementation commit)"
    - "QStyledItemDelegate with shared _make_doc helper (Pitfall 3 mitigated)"
    - "QButtonGroup(setExclusive=False) + manual stateChanged uncheck-siblings"
    - "TYPE_CHECKING guard for ArticleResult import in result_delegate.py"
key_files:
  created:
    - nitrofind/ui/result_delegate.py
    - nitrofind/ui/filter_sidebar.py
    - tests/test_ui/test_result_delegate.py
    - tests/test_ui/test_filter_sidebar.py
decisions:
  - "Single-select idiom: QButtonGroup(setExclusive=False) + manual stateChanged uncheck-siblings — allows zero-selection (unchecking active box yields no filter) while enforcing at-most-one per group"
  - "ArticleResult imported under TYPE_CHECKING guard in result_delegate.py to avoid runtime circular import risk"
  - "Test fix: QStyledItemDelegate is QObject not QWidget — removed qtbot.addWidget call; used QStyleOptionViewItem directly instead of removed viewOptions() Qt6 API"
metrics:
  duration: "5 minutes"
  completed: "2026-05-28"
  tasks_completed: 2
  files_modified: 0
  files_created: 4
---

# Phase 4 Plan 02: ResultDelegate and FilterSidebar Summary

**One-liner:** ResultDelegate renders multi-line HTML result rows with ES highlight tags via shared _make_doc helper; FilterSidebar enforces single-select per group and delegates to build_filter_clauses() via collect_filters().

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 (RED) | Failing tests for ResultDelegate + _result_to_html | d8e8295 | tests/test_ui/test_result_delegate.py |
| 1 (GREEN) | Implement ResultDelegate, _make_doc, _result_to_html | 25f4571 | nitrofind/ui/result_delegate.py, tests/test_ui/test_result_delegate.py |
| 2 (RED) | Failing tests for FilterSidebar single-select + collect_filters | 48ffc93 | tests/test_ui/test_filter_sidebar.py |
| 2 (GREEN) | Implement FilterSidebar with three groups and collect_filters | 6d42623 | nitrofind/ui/filter_sidebar.py, tests/test_ui/test_filter_sidebar.py |

## Final File Paths and Exported Names

| File | Exports |
|------|---------|
| `nitrofind/ui/result_delegate.py` | `_ROW_PADDING`, `_result_to_html`, `ResultDelegate` |
| `nitrofind/ui/filter_sidebar.py` | `MANUFACTURERS`, `ERAS`, `BODY_STYLES`, `FilterSidebar` |
| `tests/test_ui/test_result_delegate.py` | 7 unit tests |
| `tests/test_ui/test_filter_sidebar.py` | 9 unit tests |

## Single-Select Implementation Idiom

**Chosen:** `QButtonGroup(setExclusive=False)` + manual `_uncheck_siblings` handler wired to each checkbox's `stateChanged` signal.

**Rationale:** `QButtonGroup.setExclusive(True)` was rejected because it prevents the user from unchecking the currently active box — clicks on the active button are silently ignored. The manual idiom keeps `setExclusive(False)` (so Qt doesn't block unchecks) and enforces the at-most-one constraint by calling `blockSignals(True) / setChecked(False) / blockSignals(False)` on all sibling checkboxes when any one becomes checked. This allows zero-selection (no filter on a dimension) while still enforcing mutual exclusion within the group.

## Test Counts and pytest Output

```
tests/test_ui/test_result_delegate.py — 7 tests
tests/test_ui/test_filter_sidebar.py  — 9 tests

pytest tests/test_ui/ -x -m "not integration"
16 passed in 0.60s

pytest tests/ -x -m "not integration"
146 passed, 6 deselected in 5.09s
```

No regressions in Phase 1-3 tests.

## Key Implementation Details

### result_delegate.py

- `_ROW_PADDING = QMargins(8, 8, 8, 8)` — UI-SPEC 8-point grid compliance
- `_result_to_html(result)` — free function, not a method; prefers `highlight_title[0]` / `highlight_body[0]` when truthy; falls back to `result.title` / `result.excerpt`
- `ResultDelegate._make_doc(html, width)` — shared helper called identically by `paint()` and `sizeHint()` (Pitfall 3 mitigated)
- `paint()` uses `painter.save()` / `painter.translate()` / `doc.drawContents(painter)` / `painter.restore()` pattern
- `sizeHint()` computes `doc.size().height()` + `_ROW_PADDING` for accurate row height
- `ArticleResult` imported under `TYPE_CHECKING` guard to avoid runtime circular import
- Color `#80cbc4` used for source domain text (muted teal variant of dark_teal accent)

### filter_sidebar.py

- `MANUFACTURERS` (10), `ERAS` (8), `BODY_STYLES` (8) — module-level constants, exact UI-SPEC values
- `FilterSidebar.__init__` builds three sections via `_build_group()` with `QLabel` header + `QCheckBox` per value
- `collect_filters()` uses `next((k for k, cb in d.items() if cb.isChecked()), None)` for each group
- `manufacturer_checks`, `era_checks`, `body_style_checks` read-only `@property` accessors for test introspection
- All Qt6 fully-qualified enums (`Qt.AlignmentFlag.AlignLeft`, `Qt.CheckState.Checked`, etc.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] QStyledItemDelegate is not a QWidget — qtbot.addWidget fails**
- **Found during:** Task 1 GREEN run
- **Issue:** Test `test_make_doc_returns_document_with_zero_margin` called `qtbot.addWidget(delegate)` but `QStyledItemDelegate` inherits from `QObject`, not `QWidget`. pytest-qt raises `TypeError`.
- **Fix:** Removed the `addWidget` call. The `qtbot` fixture still ensures a `QApplication` is running.
- **Files modified:** `tests/test_ui/test_result_delegate.py`
- **Commit:** 25f4571

**2. [Rule 3 - Blocking] `QListWidget.viewOptions()` removed in Qt6**
- **Found during:** Task 1 GREEN run
- **Issue:** Test `test_size_hint_returns_positive_height` called `list_widget.viewOptions()` which no longer exists in Qt6. `AttributeError` raised.
- **Fix:** Replaced with `QStyleOptionViewItem()` constructed directly and rect set manually to simulate 400px width.
- **Files modified:** `tests/test_ui/test_result_delegate.py`
- **Commit:** 25f4571

## Plan 03 Compatibility Confirmation

Plan 03 (MainWindow) can import the following without modification:

```python
from nitrofind.ui.result_delegate import ResultDelegate, _result_to_html
from nitrofind.ui.filter_sidebar import FilterSidebar
```

Data role contract (set by MainWindow, read by ResultDelegate):
- `Qt.ItemDataRole.UserRole` → HTML string from `_result_to_html(result)`
- `Qt.ItemDataRole.UserRole + 1` → `ArticleResult` object for detail pane

`collect_filters()` return contract: `list[dict]` matching `build_filter_clauses()` output.

## Known Stubs

None — both modules contain fully implemented, data-driven logic. No hardcoded empty values or placeholder text flow to rendering.

## Threat Flags

No new threat surface introduced beyond what is documented in the plan's `<threat_model>`:
- T-04-04: HTML rendered exclusively by Qt Rich Text QTextDocument (no QtWebEngine)
- T-04-05: Filter values from module-level constants only (never user input)

## Self-Check: PASSED

All created files verified to exist on disk:
- `nitrofind/ui/result_delegate.py` — FOUND
- `nitrofind/ui/filter_sidebar.py` — FOUND
- `tests/test_ui/test_result_delegate.py` — FOUND
- `tests/test_ui/test_filter_sidebar.py` — FOUND

All task commits present in git log:
- `d8e8295` — FOUND (RED task 1)
- `25f4571` — FOUND (GREEN task 1)
- `48ffc93` — FOUND (RED task 2)
- `6d42623` — FOUND (GREEN task 2)

Final test run: 146 passed, 0 failed, 6 deselected (integration).
