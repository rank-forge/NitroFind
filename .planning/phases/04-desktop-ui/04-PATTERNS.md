# Phase 4: Desktop UI - Pattern Map

**Mapped:** 2026-05-28
**Files analyzed:** 12
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `nitrofind/ui/main_window.py` | component (QMainWindow) | event-driven | `nitrofind/ui/loading_window.py` | role-match |
| `nitrofind/ui/result_delegate.py` | component (QStyledItemDelegate) | transform | `nitrofind/ui/spinner.py` | partial (custom widget painter) |
| `nitrofind/ui/filter_sidebar.py` | component (QWidget) | event-driven | `nitrofind/ui/loading_window.py` | role-match |
| `nitrofind/search/models.py` | model | transform | `nitrofind/search/models.py` (extend) | exact — extend in-place |
| `nitrofind/search/query_builder.py` | utility | transform | `nitrofind/search/query_builder.py` (extend) | exact — extend in-place |
| `nitrofind/search/engine.py` | service | event-driven | `nitrofind/search/engine.py` (extend) | exact — extend in-place |
| `tests/test_search/test_engine.py` | test | request-response | `tests/test_search/test_engine.py` (extend) | exact — extend in-place |
| `tests/test_ui/__init__.py` | config | — | `tests/test_search/__init__.py` | exact (empty package marker) |
| `tests/test_ui/test_main_window.py` | test | event-driven | `tests/test_loading_window.py` | exact (pytest-qt qtbot pattern) |
| `tests/test_ui/test_result_delegate.py` | test | transform | `tests/test_search/test_models.py` | role-match (unit dataclass/method) |
| `tests/test_ui/test_filter_sidebar.py` | test | event-driven | `tests/test_loading_window.py` | role-match (qtbot widget test) |
| `main.py` | config | request-response | `main.py` (extend) | exact — swap one import/construction |

---

## Pattern Assignments

### `nitrofind/ui/main_window.py` (component, event-driven)

**Analog:** `nitrofind/ui/loading_window.py`

**Replaces:** `StubMainWindow` in the same file. The class is replaced entirely; do not keep `StubMainWindow` as a live class (an alias is acceptable for one wave if needed by main.py until W0-EXT-03 lands).

**Imports pattern** (`loading_window.py` lines 21-31):
```python
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal

from nitrofind.ui.spinner import SpinnerWidget
```
Adapt: replace with `QMainWindow`, `QLineEdit`, `QListWidget`, `QSplitter`, `QTextBrowser`, `QTimer`, `QListWidgetItem`, `QAbstractItemView`; import `SearchEngine`, `FilterSidebar`, `ResultDelegate`, `_result_to_html`.

**Module docstring pattern** (`loading_window.py` lines 1-19):
```python
"""
LoadingWindow — frameless startup window shown while Elasticsearch warms up.

Design decisions:
- D-06: Uses QWidget (NOT QSplashScreen). ...

Copywriting Contract (verbatim strings required by UI-SPEC):
  ...
"""
```
Adapt: document `MainWindow`, list all Copywriting Contract strings from `04-UI-SPEC.md`.

**Logger pattern** (`engine.py` line 33):
```python
logger = logging.getLogger(__name__)
```
Copy verbatim. All logger calls use `%` formatting — never f-strings (CLAUDE.md convention, enforced by `test_logger_uses_percent_formatting` in `test_engine.py`).

**QWidget construction pattern** (`loading_window.py` lines 53-115):
```python
def __init__(self):
    super().__init__()
    self.setObjectName("loadingWindow")
    self.setWindowFlags(...)
    self.setFixedSize(360, 240)

    # --- Build child widgets ---
    self._title_label = QLabel("NitroFind")
    ...

    # --- Button row layout ---
    button_row = QHBoxLayout()
    button_row.addStretch(1)
    ...

    # --- Main layout ---
    layout = QVBoxLayout()
    layout.setContentsMargins(48, 32, 48, 32)
    layout.setSpacing(8)
    layout.addWidget(...)
    self.setLayout(layout)

    # --- Signal wiring ---
    self._retry_button.clicked.connect(self.retry_clicked.emit)
```
Adapt for `MainWindow.__init__`: use `QMainWindow`, `setCentralWidget()`, `QSplitter`, spacing tokens from `04-UI-SPEC.md` (8px `setSpacing`, 8px `setContentsMargins`). Wire debounce timer and signals AFTER building all child widgets.

**Signal wiring order** (`loading_window.py` lines 147-152 and `main.py` lines 206-211):
```python
# Signal wiring — connects AFTER all widget construction
self._retry_button.clicked.connect(self.retry_clicked.emit)
self._quit_button.clicked.connect(QApplication.instance().quit)
```
```python
# main.py pattern: connect ALL signals before worker.start()
worker.es_ready.connect(on_es_ready)
worker.es_failed.connect(on_es_failed)
loading_window.retry_clicked.connect(on_retry_clicked)
app.aboutToQuit.connect(shutdown_handler)
```
In `MainWindow`: connect `_debounce_timer.timeout` to `_execute_search`, `_search_bar.textChanged` to `_debounce_timer.start`, `_result_list.currentRowChanged` to `_on_result_hovered`, `_result_list.itemActivated` to `_on_result_activated` — all inside `__init__` before any `show()`.

**Debounce timer pattern** (RESEARCH.md Pattern 1, verbatim):
```python
self._debounce_timer = QTimer(self)
self._debounce_timer.setSingleShot(True)
self._debounce_timer.setInterval(300)   # SRCH-01
self._debounce_timer.timeout.connect(self._execute_search)
self._search_bar.textChanged.connect(self._debounce_timer.start)
```

**Stale result guard** (RESEARCH.md Pattern 2, verbatim):
```python
self._current_seq: int = 0

def _execute_search(self) -> None:
    self._current_seq += 1
    seq = self._current_seq
    self._engine.search(
        self._search_bar.text().strip(),
        filters=self._filter_sidebar.collect_filters(),
        callback=lambda results, took, s=seq: self._on_results(results, took, s),
        error_callback=self._on_search_error,
    )

def _on_results(self, results: list, took_ms: int, seq: int) -> None:
    if seq != self._current_seq:
        return  # stale — discard
    count = len(results)
    self._status_label.setText(f"{count} results ({took_ms / 1000:.2f}s)")
    self._populate_results(results)
```

**QSplitter layout** (RESEARCH.md Pattern 7 + UI-SPEC splitter sizes):
```python
splitter = QSplitter(Qt.Orientation.Horizontal)
splitter.addWidget(self._filter_sidebar)
splitter.addWidget(self._result_list)
splitter.addWidget(self._detail_pane)
splitter.setSizes([200, 320, 580])   # UI-SPEC: 200+320+580 = 1100px minimum window
```

**Public accessors pattern** (`loading_window.py` lines 154-170):
```python
@property
def spinner(self) -> SpinnerWidget:
    return self._spinner

@property
def status_label(self) -> QLabel:
    return self._status_label
```
Adapt: expose `_search_bar`, `_status_label`, `_result_list`, `_detail_pane`, `_filter_sidebar`, `_debounce_timer` as properties for test access (mirrors `loading_window.py` accessor convention).

**Window title pattern** (`main_window.py` line 20 and `main.py` line 117):
```python
# StubMainWindow
self.setWindowTitle("NitroFind — Ready")
# main.py on_es_ready:
main_window = StubMainWindow()
```
Adapt: set `"NitroFind — Ready"` at construction; update to `f"NitroFind — {query}"` in `_execute_search`. Em-dash (U+2014), not hyphen.

**Error handling pattern** (`engine.py` lines 106-108, `main.py` lines 125-146):
```python
# engine.py: errors delivered via signal, never raised
except Exception as exc:
    logger.warning("Search failed: %s: %s", type(exc).__name__, exc)
    self._signals.search_failed.emit(str(exc))

# main.py: raw exception mapped to static string for UI (T-04-03)
logger.warning("ESHealthWorker reported failure: %s", reason)
sys.stderr.write(f"[nitrofind] ES failure reason: {reason}\n")
# → static error string to UI label, never str(exc) directly
```
In `_on_search_error(self, msg: str)`: log with `%` format, set `self._status_label.setText("Search failed. Check Elasticsearch connection.")` — static string only (no raw `msg` in UI label).

---

### `nitrofind/ui/result_delegate.py` (component, transform)

**Analog:** `nitrofind/ui/spinner.py` (custom painter widget) + RESEARCH.md Pattern 3

**Imports pattern** (spinner.py lines 12-14):
```python
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QPen, QColor
```
Adapt:
```python
from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtGui import QTextDocument, QTextOption
from PyQt6.QtCore import Qt, QMargins, QRectF
```

**Module docstring pattern** (spinner.py lines 1-10):
```python
"""
SpinnerWidget — animated arc spinner using QPainter and QTimer.

UI-SPEC Pattern 5: 48x48 custom QWidget...

Anti-pattern guard: do NOT use QProgressBar in indeterminate mode.
...
"""
```
Adapt: document `ResultDelegate` and `_result_to_html`, cite UI-SPEC Pattern 3, note the `_make_doc` shared-helper anti-pattern (Pitfall 3).

**Core delegate pattern** (RESEARCH.md Pattern 3, verbatim — use this exactly):
```python
_ROW_PADDING = QMargins(8, 8, 8, 8)   # UI-SPEC spacing: 8px all sides

class ResultDelegate(QStyledItemDelegate):
    def _make_doc(self, html: str, width: int) -> QTextDocument:
        toption = QTextOption()
        toption.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        doc = QTextDocument()
        doc.setHtml(html)
        doc.setTextWidth(width)
        doc.setDefaultTextOption(toption)
        doc.setDocumentMargin(0)
        return doc

    def paint(self, painter, option, index):
        painter.save()
        html = index.data(Qt.ItemDataRole.UserRole)
        rect = option.rect.marginsRemoved(_ROW_PADDING)
        doc = self._make_doc(html, rect.width())
        painter.translate(rect.topLeft())
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        html = index.data(Qt.ItemDataRole.UserRole)
        rect = option.rect.marginsRemoved(_ROW_PADDING)
        doc = self._make_doc(html, rect.width())
        rect.setHeight(int(doc.size().height()))
        return rect.marginsAdded(_ROW_PADDING).size()
```
Critical: `_make_doc` called identically in both `paint()` and `sizeHint()` — prevents Pitfall 3 (height mismatch).

**HTML builder function** (UI-SPEC Component 3, verbatim):
```python
def _result_to_html(result: "ArticleResult") -> str:
    title = result.highlight_title[0] if result.highlight_title else result.title
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return (
        f"<b style='font-size:11pt'>{title}</b>"
        f"<br><span style='color:#80cbc4;font-size:9pt'>{result.source_domain}</span>"
        f"<br><span style='font-size:9pt'>{excerpt}</span>"
    )
```
This is a module-level free function, not a method. Import `ArticleResult` with `TYPE_CHECKING` guard if needed to avoid circular import.

---

### `nitrofind/ui/filter_sidebar.py` (component, event-driven)

**Analog:** `nitrofind/ui/loading_window.py`

**Imports pattern** (loading_window.py lines 21-31):
```python
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    ...
)
from PyQt6.QtCore import Qt, pyqtSignal
```
Adapt: use `QWidget`, `QVBoxLayout`, `QLabel`, `QCheckBox`, `QButtonGroup`. No `pyqtSignal` needed in the sidebar itself — state changes propagate via the checkboxes' `stateChanged` connecting to `_debounce_timer.start` in MainWindow.

**Module docstring pattern** (loading_window.py lines 1-19):
Document filter group values (from UI-SPEC Component 5 table), note hardcoded values and that ES aggregations are deferred to v2.

**QWidget construction pattern** (loading_window.py lines 52-115):
```python
def __init__(self, parent=None):
    super().__init__(parent)
    layout = QVBoxLayout()
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)
    # group headers and checkboxes
    self.setLayout(layout)
```
Adapt: build three groups (Manufacturer, Era, Body Style) with `QLabel` header and `QCheckBox` per value. Track checkbox instances in `dict[str, QCheckBox]` per group. Use `QButtonGroup(self)` with `setExclusive(True)` for each group to enforce single-select per dimension.

**collect_filters() pattern** (RESEARCH.md Pattern 5, adapted for UI-SPEC multi-group):
```python
def collect_filters(self) -> list[dict]:
    """Read checkbox state, return build_filter_clauses() result."""
    manufacturer = next(
        (k for k, cb in self._manufacturer_checks.items() if cb.isChecked()), None
    )
    era_bucket = next(
        (k for k, cb in self._era_checks.items() if cb.isChecked()), None
    )
    body_style = next(
        (k for k, cb in self._body_style_checks.items() if cb.isChecked()), None
    )
    return build_filter_clauses(
        manufacturer=manufacturer,
        era_bucket=era_bucket,
        body_style=body_style,
    )
```

**Public accessors pattern** (loading_window.py lines 154-170):
Expose checkbox dicts as properties for test access: `manufacturer_checks`, `era_checks`, `body_style_checks`.

---

### `nitrofind/search/models.py` (model, extend in-place)

**Analog:** `nitrofind/search/models.py` — extend in-place, do not restructure.

**Extend the dataclass** (models.py lines 23-49). Add one field in the optional fields block, after `excerpt`:
```python
# Current optional fields block (lines 39-49):
excerpt: str = ""
published_at: str | None = None
word_count: int = 0
has_infobox: bool = False
manufacturer: str | None = None
era_bucket: str | None = None
body_style: str | None = None
```
Add after `excerpt`:
```python
body: str = ""          # full article text for detail pane (W0-EXT-01)
```

**Extend from_es_hit** (models.py lines 51-87). In the `return cls(...)` block, add after `excerpt=src.get("excerpt", "")`:
```python
body=src.get("body", ""),
```

**Module docstring** (models.py lines 1-16): add `body` to the field list description. Add W0-EXT-01 reference.

**test_article_result_all_fields test** (test_models.py lines 56-65): update `expected_fields` set to include `"body"`.

---

### `nitrofind/search/query_builder.py` (utility, extend in-place)

**Analog:** `nitrofind/search/query_builder.py` — extend `_source` list in `build_search_body` only.

**`_source` list** (query_builder.py lines 241-246):
```python
"_source": [
    "title", "url", "source_domain", "excerpt",
    "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
],
```
Add `"body"` to the list (W0-EXT-01):
```python
"_source": [
    "title", "url", "source_domain", "excerpt", "body",
    "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
],
```
No other changes to `query_builder.py`.

---

### `nitrofind/search/engine.py` (service, extend in-place)

**Analog:** `nitrofind/search/engine.py` — two targeted changes for W0-EXT-02.

**Change 1 — `_SearchSignals.results_ready` signal** (engine.py line 48):
```python
# Current:
results_ready = pyqtSignal(list)   # list[ArticleResult] — emitted on success

# Change to:
results_ready = pyqtSignal(list, int)   # list[ArticleResult], took_ms — emitted on success
```

**Change 2 — `_SearchWorker.run()` emit** (engine.py lines 101-105):
```python
# Current:
results = [
    ArticleResult.from_es_hit(hit)
    for hit in resp["hits"]["hits"]
]
self._signals.results_ready.emit(results)

# Change to:
results = [
    ArticleResult.from_es_hit(hit)
    for hit in resp["hits"]["hits"]
]
took_ms = resp.get("took", 0)
self._signals.results_ready.emit(results, took_ms)
```

**Module docstring** (engine.py line 22): add W0-EXT-02 to the change log.

**`SearchEngine.search()` signature** (engine.py lines 133-141): update `callback` type annotation to `Callable[[list, int], None] | None` to reflect the new two-argument signal.

---

### `tests/test_search/test_engine.py` (test, extend in-place)

**Analog:** `tests/test_search/test_engine.py` — update lambda connections that consume `results_ready`.

**Pattern to update** — anywhere `results_ready` is connected with a single-argument lambda (engine.py test lines 222-223, 277, 291-293):
```python
# Current pattern (multiple locations):
signals.results_ready.connect(lambda results: received.extend(results))
signals.results_ready.connect(lambda results: received.append(results))

# Update to accept (list, int):
signals.results_ready.connect(lambda results, took: received.extend(results))
signals.results_ready.connect(lambda results, took: received.append(results))
```
Search for all occurrences of `results_ready.connect` in the file and update each. The `took` parameter is accepted but not used in existing tests — that is correct.

---

### `tests/test_ui/__init__.py` (config)

**Analog:** `tests/test_search/__init__.py` (empty package marker file).

Empty file. No content required.

---

### `tests/test_ui/test_main_window.py` (test, event-driven)

**Analog:** `tests/test_loading_window.py` — exact pattern for pytest-qt qtbot-based widget tests.

**File header pattern** (test_loading_window.py lines 1-31):
```python
"""
tests/test_ui/test_main_window.py — SRCH-01..04, UIPL-01, UIPL-02, UIPL-04 coverage.

Test strategy:
  - Use qtbot fixture from pytest-qt for widget lifecycle management
  - Mock SearchEngine with MagicMock — no live ES required
  - No module-level QApplication construction (pytest-qt handles this via qtbot)
  ...
"""

import pytest

try:
    import PyQt6  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PYQT6_AVAILABLE,
    reason="PyQt6 not installed",
)
```
Critical: do NOT use `_app = QApplication.instance() or QApplication(sys.argv)` (Pitfall 6 from RESEARCH.md). The `qtbot` fixture manages `QApplication` — using `qtbot` or `qapp` is sufficient.

**Widget construction pattern** (test_loading_window.py lines 33-51):
```python
def test_initial_state_is_loading(qtbot):
    from nitrofind.ui.loading_window import LoadingWindow

    window = LoadingWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.spinner.isVisible() is True
    ...
```
Adapt for MainWindow:
```python
def test_debounce_timer_interval(qtbot):
    from nitrofind.ui.main_window import MainWindow
    from unittest.mock import MagicMock

    engine = MagicMock()
    window = MainWindow(engine)
    qtbot.addWidget(window)

    assert window._debounce_timer.interval() == 300
    assert window._debounce_timer.isSingleShot() is True
```

**Signal waiting pattern** (test_loading_window.py lines 77-95):
```python
with qtbot.waitSignal(window.retry_clicked, timeout=1000):
    qtbot.mouseClick(window.retry_button, Qt.MouseButton.LeftButton)
```
Adapt for debounce timer test (from RESEARCH.md Code Examples):
```python
qtbot.keyClicks(window._search_bar, "Ferrari")
qtbot.waitSignal(window._debounce_timer.timeout, timeout=500)
engine.search.assert_called_once()
```

**Signal results mock pattern** (test_engine.py `_make_mock_client` lines 42-67):
```python
def _make_mock_engine():
    """Return a MagicMock SearchEngine with controllable search() behavior."""
    from unittest.mock import MagicMock
    engine = MagicMock()
    engine.search.return_value = None  # non-blocking API contract
    return engine
```
Use `MagicMock` for engine; invoke the callback directly in tests that need to check result population (call the captured callback argument manually rather than waiting for real QThreadPool dispatch).

---

### `tests/test_ui/test_result_delegate.py` (test, transform)

**Analog:** `tests/test_search/test_models.py` — pure unit tests, no Qt event loop needed for `_result_to_html`; minimal pytest-qt for delegate rendering.

**File header pattern** (test_models.py lines 1-16):
```python
"""
tests/test_ui/test_result_delegate.py — SRCH-02, UIPL-01 coverage.

Test strategy:
  - _result_to_html: pure function, no Qt required
  - ResultDelegate.sizeHint/paint: use qtbot for widget context
  - No live ES or SearchEngine required
...
"""
```

**Pure function test pattern** (test_models.py lines 28-40):
```python
def test_article_result_construction_required_fields():
    r = ArticleResult(title="Ferrari 308", url="http://x", source_domain="wikipedia.org", score=1.5)
    assert r.title == "Ferrari 308"
```
Adapt for `_result_to_html`:
```python
def test_result_to_html_uses_highlight_title_when_present():
    from nitrofind.ui.result_delegate import _result_to_html
    from nitrofind.search.models import ArticleResult

    r = ArticleResult(
        title="Ferrari 308", url="u", source_domain="wikipedia.org", score=1.5,
        highlight_title=["<b>Ferrari</b> 308"],
        highlight_body=["The <b>Ferrari</b> 308 GTB..."],
    )
    html = _result_to_html(r)
    assert "<b>Ferrari</b> 308" in html
    assert "wikipedia.org" in html
    assert "#80cbc4" in html   # domain color
```

**PyQt6 availability guard** (test_loading_window.py lines 23-30): use same `pytestmark` pattern for any tests that require `qtbot`.

---

### `tests/test_ui/test_filter_sidebar.py` (test, event-driven)

**Analog:** `tests/test_loading_window.py` — qtbot-based widget test.

**File header + pytestmark**: copy the `try/except PyQt6` + `pytestmark` block from `test_loading_window.py` lines 23-30 verbatim.

**Widget construction + accessor pattern** (test_loading_window.py lines 33-51):
```python
def test_collect_filters_returns_empty_when_nothing_checked(qtbot):
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    result = sidebar.collect_filters()
    assert result == []   # no filters when nothing checked
```

**State change test pattern** (test_loading_window.py lines 54-74):
```python
def test_show_error_transitions_to_error_state(qtbot):
    window = LoadingWindow()
    qtbot.addWidget(window)
    window.show()
    window.show_error("Test failure reason")
    assert window.status_label.text() == "Test failure reason"
```
Adapt: simulate checkbox click and verify `collect_filters()` returns the expected `build_filter_clauses()` result.

---

### `main.py` (config, extend in-place)

**Analog:** `main.py` — change two lines in `on_es_ready()`.

**Current construction** (main.py lines 115-119):
```python
main_window = StubMainWindow()
main_window.show()
state["main_window"] = main_window
loading_window.close()
```

**Updated construction** (W0-EXT-03):
```python
main_window = MainWindow(client)   # client already constructed above
main_window.show()
state["main_window"] = main_window
loading_window.close()
```

**Updated import** (main.py line 34):
```python
# Current:
from nitrofind.ui.main_window import StubMainWindow

# Change to:
from nitrofind.ui.main_window import MainWindow
```

No other changes to `main.py`. The `apply_stylesheet` call (line 74) and signal-before-start wiring (lines 206-211) are already correct and must not be reordered.

---

## Shared Patterns

### Logger Declaration
**Source:** `nitrofind/search/engine.py` line 33, `nitrofind/search/query_builder.py` line 27
**Apply to:** `main_window.py`, `result_delegate.py`, `filter_sidebar.py`
```python
import logging
logger = logging.getLogger(__name__)
```
All logger calls use `%` lazy formatting — never f-strings. Enforced by `test_logger_uses_percent_formatting` in `test_engine.py`; the same test pattern should be copied into `test_main_window.py`.

### PyQt6 Availability Guard in Tests
**Source:** `tests/test_loading_window.py` lines 23-30
**Apply to:** `tests/test_ui/test_main_window.py`, `tests/test_ui/test_result_delegate.py`, `tests/test_ui/test_filter_sidebar.py`
```python
try:
    import PyQt6  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PYQT6_AVAILABLE,
    reason="PyQt6 not installed",
)
```

### qtbot Widget Lifecycle
**Source:** `tests/test_loading_window.py` lines 33-51
**Apply to:** All `tests/test_ui/` test functions that create Qt widgets
```python
def test_something(qtbot):
    from nitrofind.ui.<module> import <Widget>
    widget = <Widget>(...)
    qtbot.addWidget(widget)   # pytest-qt cleans up after test
    widget.show()
    # assertions
```
Never create `QApplication(sys.argv)` in test files — `qtbot` manages this (Pitfall 6).

### Static Error Strings in UI Labels
**Source:** `main.py` lines 125-146 and `loading_window.py` lines 191-194
**Apply to:** `main_window.py` `_on_search_error()` method
```python
# main.py pattern (T-04-03):
logger.warning("ESHealthWorker reported failure: %s", reason)
sys.stderr.write(f"[nitrofind] ES failure reason: {reason}\n")
# → UI label receives ONLY static string, never str(exc) or raw reason
loading_window.show_error("Could not connect to Elasticsearch. ...")
```
In `_on_search_error`: log raw `msg` with `logger.warning`, set status label to the static string `"Search failed. Check Elasticsearch connection."`.

### Signals Connected Before Worker Start
**Source:** `main.py` lines 206-211, `engine.py` lines 165-175
**Apply to:** `main_window.py` `__init__` wiring
```python
# engine.py (T-03-06 pattern — enforced before pool.start):
if callback:
    signals.results_ready.connect(callback, Qt.ConnectionType.QueuedConnection)
if error_callback:
    signals.search_failed.connect(error_callback, Qt.ConnectionType.QueuedConnection)
worker = _SearchWorker(self._client, body, signals)
self._pool.start(worker)  # LAST — after all signal connections
```
In `MainWindow.__init__`: connect all signals (`_debounce_timer.timeout`, `_search_bar.textChanged`, `_result_list.currentRowChanged`, `_result_list.itemActivated`) before calling `self.show()`.

### Qt6 Enum Syntax
**Source:** `loading_window.py` lines 57-60, `spinner.py` lines 63-64, `main_window.py` (stub) line 23
**Apply to:** All new UI files
```python
# Correct Qt6 syntax (fully qualified enum):
Qt.WindowType.FramelessWindowHint
Qt.AlignmentFlag.AlignCenter
Qt.ItemDataRole.UserRole
Qt.Orientation.Horizontal
Qt.ScrollBarPolicy.ScrollBarAlwaysOff
QAbstractItemView.SelectionMode.SingleSelection
QPainter.RenderHint.Antialiasing
QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
```
Never use Qt5-style short-form enums (`Qt.AlignCenter`, `Qt.Horizontal`).

### Property Accessors for Test Access
**Source:** `loading_window.py` lines 154-170
**Apply to:** `main_window.py`, `filter_sidebar.py`
```python
@property
def status_label(self) -> QLabel:
    return self._status_label

@property
def retry_button(self) -> QPushButton:
    return self._retry_button
```
Expose private widget references as read-only properties with correct type annotations so tests can access them without name-mangling.

---

## No Analog Found

All files have close analogs in the codebase. No files require falling back to RESEARCH.md patterns exclusively — however, three files use RESEARCH.md as primary pattern source because no identical delegate/timer pattern exists yet:

| File | Analog Source | Notes |
|------|--------------|-------|
| `nitrofind/ui/result_delegate.py` | `spinner.py` (custom painter) + RESEARCH.md Pattern 3 | `QStyledItemDelegate` is new to this codebase; `spinner.py` provides the painter save/restore idiom; RESEARCH.md Pattern 3 provides the `_make_doc` helper verbatim |
| `nitrofind/ui/main_window.py` (debounce) | RESEARCH.md Pattern 1 | QTimer single-shot debounce has no existing analog; copy Pattern 1 verbatim |
| `nitrofind/ui/filter_sidebar.py` (QButtonGroup) | `loading_window.py` (QWidget skeleton) + RESEARCH.md Pattern 5 | `QButtonGroup` exclusive radio behavior has no existing analog |

---

## Metadata

**Analog search scope:** `nitrofind/ui/`, `nitrofind/search/`, `tests/`, `main.py`
**Files scanned:** 14 Python source files (all project Python files)
**Pattern extraction date:** 2026-05-28
