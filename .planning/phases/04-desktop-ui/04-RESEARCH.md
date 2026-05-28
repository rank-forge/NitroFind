# Phase 4: Desktop UI - Research

**Researched:** 2026-05-28
**Domain:** PyQt6 desktop application — search UI, debounce, custom delegate, QSplitter layout, keyboard navigation, dark theme
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRCH-01 | Search results update as the user types, with 300ms debounce | QTimer single-shot debounce pattern verified via Qt Wiki and Qt Forum |
| SRCH-02 | Result list displays title, source domain, and highlighted excerpt | QListWidget + QStyledItemDelegate with QTextDocument HTML rendering verified |
| SRCH-03 | Selecting a result displays full article text inline (no browser) | QTextBrowser with openLinks=False verified via Qt official docs |
| SRCH-04 | Filter sidebar narrows results by manufacturer/era_bucket/body_style without clearing query | QCheckBox groups + build_filter_clauses() from Phase 3 query_builder verified |
| UIPL-01 | Query terms highlighted in result excerpts | ES highlighter already emits `<b>` tags; QTextDocument renders them |
| UIPL-02 | Result count and query time displayed below search box | QLabel updated via results_ready callback; ES `took` field in response |
| UIPL-03 | Dark theme by default | apply_stylesheet(app, theme="dark_teal.xml") already called in main.py |
| UIPL-04 | Arrow key navigation, Enter to open, Escape to clear search | QListWidget built-in arrow nav + itemActivated + keyReleaseEvent override |
</phase_requirements>

---

## Summary

Phase 4 replaces `StubMainWindow` in `nitrofind/ui/main_window.py` with a full `MainWindow` that wires the existing `SearchEngine` (Phase 3) to a PyQt6 UI. All search I/O already runs off the main thread via `_SearchWorker`/`QThreadPool` — the UI layer only needs to connect signals and update widgets.

The layout follows a standard two-panel desktop search pattern: a `QMainWindow` with a vertical layout containing a `QLineEdit` search bar at the top, a horizontal `QSplitter` below (left: filter sidebar + results list; right: detail pane). The filter sidebar uses `QCheckBox` groups bound to `build_filter_clauses()` from `query_builder.py`. The result list uses `QListWidget` with a `QStyledItemDelegate` that renders HTML `<b>` highlights via `QTextDocument`. The detail pane uses `QTextBrowser` with `openLinks=False` to display full article text inline.

Debounce is implemented with a single-shot `QTimer` (300ms) restarted on every `QLineEdit.textChanged` emission. A stale-result guard tracks a monotonically incrementing search sequence ID — callbacks ignore results from any search that is not the most recently dispatched. Dark theme (`dark_teal.xml`) is already applied in `main.py` before window construction; highlight contrast in the theme is `#000000` text on `#6effe8` background, which is readable. Escape key clearing uses `keyReleaseEvent` override (not `keyPressEvent`) due to a known cross-platform quirk with Escape in `QLineEdit`.

**Primary recommendation:** Build `MainWindow` as a `QMainWindow` subclass in `nitrofind/ui/main_window.py`, replacing `StubMainWindow`. Wire `SearchEngine` via the callback pattern already established in Phase 3. Use `QListWidget` + `QStyledItemDelegate` for the result list and `QTextBrowser` for the detail pane.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Debounce / search trigger | Frontend (PyQt6 main thread) | — | QTimer lives on the main thread; controls when SearchEngine.search() is called |
| ES query execution | Background thread (QThreadPool) | — | Already implemented in Phase 3 _SearchWorker; UI never touches ES directly |
| Result rendering (list) | Frontend (PyQt6 main thread) | — | QListWidget updated via results_ready signal callback |
| HTML highlight rendering | Frontend (QStyledItemDelegate) | — | QTextDocument renders `<b>` tags from ES highlighter response |
| Article detail display | Frontend (QTextBrowser) | — | Read-only render; body text from ArticleResult.excerpt / full body field |
| Filter state | Frontend (QCheckBox state) | ES query layer | UI reads checkbox state, builds filter_clauses, passes to SearchEngine.search() |
| Dark theme | Frontend (qt-material) | — | Already applied globally in main.py before window construction |
| Keyboard navigation | Frontend (QListWidget + keyReleaseEvent) | — | Qt built-in for arrows; custom override for Escape |
| Stale result guard | Frontend (sequence counter) | — | Increment on each search dispatch; callback ignores out-of-order results |

---

## Standard Stack

### Core (already installed in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyQt6 | 6.11.0 | Widgets, signals, event loop | Fixed per CLAUDE.md; already installed |
| qt-material | 2.17 | dark_teal.xml theme | Already applied in main.py |
| elasticsearch | 8.x | Search client (Phase 3) | Fixed per CLAUDE.md; already wired |

[VERIFIED: pip index versions] All versions confirmed against PyPI registry.

### Testing

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-qt | 4.5.0 | qtbot fixture, signal testing, headless widget tests | All UI unit tests in Phase 4 |
| pytest | existing | Test runner | All tests |

[VERIFIED: pip index versions] pytest-qt 4.5.0 is the current latest, already installed.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| QListWidget + delegate | QListView + custom model | For 20-100 results QListWidget is simpler; MVC overhead not justified until result counts exceed ~500 |
| QTextBrowser | QTextEdit (read-only) | QTextBrowser is QTextEdit with openLinks/navigation built in; slightly cleaner API for display-only use |
| QTimer debounce | Per-keystroke search | Timer approach prevents ES hammering at every keystroke; 300ms is the SRCH-01 requirement |

**Installation:** No new packages required. All dependencies are already installed in the project venv.

---

## Package Legitimacy Audit

Phase 4 installs no new packages. All packages used (PyQt6, qt-material, pytest-qt) were installed in prior phases and have already been verified.

| Package | Registry | Age | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|
| PyQt6 | PyPI | 5+ yrs | [OK] | Approved — already installed |
| qt-material | PyPI | 5+ yrs | [OK] | Approved — already installed |
| pytest-qt | PyPI | 10+ yrs | [OK] | Approved — already installed |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
User types in QLineEdit
        |
        | textChanged signal
        v
  QTimer.start(300ms) ← restart on each keystroke
        |
        | timeout signal (300ms after last keystroke)
        v
  _collect_filters() → build_filter_clauses()
        |
        | SearchEngine.search(query, filters, callback=on_results)
        v
  _SearchWorker (background thread via QThreadPool)
        |
        | results_ready signal (QueuedConnection → main thread)
        v
  on_results(results: list[ArticleResult])
        |   |
        |   | guard: sequence_id matches current? → discard if stale
        v   v
  QListWidget.clear() + populate items
  QLabel (result count + query time from ES `took`)
        |
        | currentRowChanged / itemActivated signal
        v
  QTextBrowser.setHtml(article body)
```

### Recommended Project Structure

```
nitrofind/ui/
├── main_window.py       # MainWindow (replaces StubMainWindow)
├── result_delegate.py   # QStyledItemDelegate for result rows
├── filter_sidebar.py    # QWidget with QCheckBox groups
├── loading_window.py    # unchanged from Phase 1
└── spinner.py           # unchanged from Phase 1
```

### Pattern 1: QTimer 300ms Debounce

**What:** Restart a single-shot QTimer on each `textChanged` emission. When the timer fires (user paused typing), execute the search.
**When to use:** Any text input that triggers expensive operations (ES queries)

```python
# Source: Qt Wiki — https://wiki.qt.io/Delay_action_to_wait_for_user_interaction
# [VERIFIED: Qt official wiki]
class MainWindow(QMainWindow):
    def __init__(self, engine: SearchEngine):
        super().__init__()
        self._engine = engine
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)   # fire exactly once per start()
        self._debounce_timer.setInterval(300)       # 300ms — SRCH-01 requirement
        self._debounce_timer.timeout.connect(self._execute_search)

        self._search_bar = QLineEdit()
        self._search_bar.textChanged.connect(self._debounce_timer.start)
        # QTimer.start(msec) or plain start() both work;
        # calling start() when already running restarts the countdown.

    def _execute_search(self) -> None:
        query = self._search_bar.text().strip()
        filters = self._filter_sidebar.collect_filters()
        self._current_seq += 1
        seq = self._current_seq
        self._engine.search(
            query,
            filters=filters,
            callback=lambda r, s=seq: self._on_results(r, s),
            error_callback=self._on_search_error,
        )
```

### Pattern 2: Stale Result Guard (Sequence Counter)

**What:** Track a monotonically increasing search sequence ID. Each results callback checks whether its ID matches the current ID; if not, the results are from a superseded search and are discarded.
**When to use:** Any UI where new searches can be dispatched before prior ones complete.

```python
# [ASSUMED] — standard web/UI pattern; no specific library citation needed
class MainWindow(QMainWindow):
    def __init__(self, ...):
        self._current_seq = 0   # incremented on each search dispatch

    def _on_results(self, results: list, seq: int) -> None:
        if seq != self._current_seq:
            return   # stale result from a superseded search — discard
        self._populate_results(results)
```

### Pattern 3: QStyledItemDelegate with QTextDocument for HTML Highlighting

**What:** Custom delegate renders each result row as multi-line HTML using QTextDocument.
**When to use:** Result list needs to display title, domain, and `<b>`-tagged excerpt.

```python
# Source: pythonguis.com/faq/cloud-around-the-text-in-qtextedit/
# [CITED: https://www.pythonguis.com/faq/cloud-around-the-text-in-qtextedit/]
from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtGui import QTextDocument, QTextOption
from PyQt6.QtCore import Qt, QMargins

_ROW_PADDING = QMargins(8, 6, 8, 6)

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
        html = index.data(Qt.ItemDataRole.UserRole)  # pre-built HTML string
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

The HTML string stored in `UserRole` is built from `ArticleResult` fields:

```python
def _result_to_html(result: ArticleResult) -> str:
    # Use highlight_title if present, otherwise plain title
    title = result.highlight_title[0] if result.highlight_title else result.title
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return (
        f"<b style='font-size:11pt'>{title}</b>"
        f"<br><span style='color:#80cbc4;font-size:9pt'>{result.source_domain}</span>"
        f"<br><span style='font-size:9pt'>{excerpt}</span>"
    )
```

### Pattern 4: QTextBrowser for Inline Article Detail

**What:** Read-only HTML display pane; no external navigation.
**When to use:** Displaying full article body text selected from result list.

```python
# Source: Qt official docs — https://doc.qt.io/qt-6/qtextbrowser.html
# [VERIFIED: Qt official docs]
from PyQt6.QtWidgets import QTextBrowser

detail_pane = QTextBrowser()
detail_pane.setOpenLinks(False)       # prevent navigation away
detail_pane.setOpenExternalLinks(False)  # already False by default; explicit for clarity
# To display a result:
detail_pane.setHtml(f"<h2>{result.title}</h2><p>{result.excerpt}</p>")
# Or for full body when body field is available in ArticleResult
```

Note: `ArticleResult` from Phase 3 does not include a `body` field — only `excerpt` (300 chars). The detail pane will display the excerpt text. If full-body display is desired, the `_source` list in `build_search_body` and `ArticleResult.from_es_hit` must be extended to include `body`. This is a Phase 4 decision point.

### Pattern 5: Filter Sidebar with QCheckBox Groups

**What:** Independent QCheckBox widgets for each filter value, grouped by category. On any `stateChanged`, re-execute the debounce search.
**When to use:** Multi-value filter sidebar.

```python
# [ASSUMED] — standard PyQt6 checkbox pattern
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLabel
from nitrofind.search.query_builder import build_filter_clauses

class FilterSidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Manufacturer checkboxes populated from known values or dynamically
        self._manufacturer_checks: dict[str, QCheckBox] = {}
        self._era_checks: dict[str, QCheckBox] = {}
        self._body_style_checks: dict[str, QCheckBox] = {}

    def collect_filters(self) -> list[dict]:
        """Read checkbox state and return build_filter_clauses() result."""
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

Note: `build_filter_clauses` accepts single values (SRCH-04 requires narrowing by one value per dimension). Multi-select per dimension would require extending the query builder; that is out of scope for Phase 4.

### Pattern 6: QListWidget Arrow Key + Enter Navigation + Escape Clearing

**What:** QListWidget handles arrow key navigation natively via `currentRowChanged`. `itemActivated` fires on Enter/Return press or double-click. Escape clearing requires `keyReleaseEvent` override on QLineEdit.
**When to use:** Keyboard-navigable result list with search clear.

```python
# Source: Qt docs — https://doc.qt.io/qt-6/qlistwidget.html
# [VERIFIED: Qt official docs — itemActivated fires on Return/Enter key]
self._result_list.currentRowChanged.connect(self._on_result_hovered)
self._result_list.itemActivated.connect(self._on_result_activated)

# Escape key — MUST use keyReleaseEvent, not keyPressEvent on QLineEdit
# [CITED: https://forum.qt.io/topic/31602 — Escape only fires on release, hardware-dependent]
class SearchLineEdit(QLineEdit):
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clear()
        super().keyReleaseEvent(event)
```

### Pattern 7: Main Window Layout (QSplitter)

**What:** Central widget is a QWidget with a QVBoxLayout; top row is the search bar + status label; bottom is a horizontal QSplitter (filter sidebar left, result list center-left, detail pane right).
**When to use:** Standard two-panel search application layout.

```python
# Source: Qt docs — https://doc.qt.io/qt-6/qsplitter.html
# [VERIFIED: Qt official docs]
from PyQt6.QtWidgets import QSplitter
from PyQt6.QtCore import Qt

splitter = QSplitter(Qt.Orientation.Horizontal)
splitter.addWidget(self._filter_sidebar)    # ~200px
splitter.addWidget(self._result_list)       # ~300px
splitter.addWidget(self._detail_pane)       # remaining space
splitter.setSizes([200, 300, 600])

central = QWidget()
layout = QVBoxLayout(central)
layout.addWidget(self._search_bar)
layout.addWidget(self._status_label)
layout.addWidget(splitter)
self.setCentralWidget(central)
```

### Pattern 8: Status Label (UIPL-02)

```python
# [ASSUMED] — standard PyQt6 label update pattern
def _on_results(self, results: list, seq: int, took_ms: int = 0) -> None:
    if seq != self._current_seq:
        return
    count = len(results)
    self._status_label.setText(f"{count} results ({took_ms}ms)")
    self._populate_results(results)
```

The ES response includes a `took` key (integer milliseconds). The `_SearchWorker.run()` method currently does not expose it to callers. `results_ready` emits `list[ArticleResult]` only. To support UIPL-02, the worker needs to emit `took` as well — either via a second signal or by wrapping results in a tuple. This is a Phase 4 implementation decision.

### Anti-Patterns to Avoid

- **Accessing ES from the main thread:** Never call `client.search()` directly from a slot; always use `SearchEngine.search()` which dispatches to `_SearchWorker`. Main thread ES calls block the UI event loop.
- **Rebuilding QTextDocument on every paint():** QTextDocument construction is expensive. For large result lists (>50 items), consider caching documents by item data. For 20-item default page size, rebuilding per-paint is acceptable.
- **Connecting signals after pool.start():** Phase 3 engine already enforces connect-before-start. Do not deviate from this pattern in Phase 4 UI code.
- **Using keyPressEvent for Escape on QLineEdit:** Known cross-platform issue — Escape fires only on release. Use `keyReleaseEvent` instead.
- **Passing raw user input as ES DSL keys:** `SearchEngine.search(query_text)` places user text inside a `multi_match.query` string value — never as a DSL key name. This is already enforced in Phase 3 (T-03-01).
- **Creating a new QApplication in tests:** `QApplication` cannot be created twice in one process. Use the `qapp` or `qtbot` fixtures from pytest-qt, which manage a shared application instance.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML rich text rendering in list items | Custom painter with QPainter text drawing | QTextDocument inside QStyledItemDelegate | QTextDocument handles wrapping, HTML tags, font metrics automatically |
| Background thread for ES calls | Manual threading.Thread + queue | SearchEngine._SearchWorker via QThreadPool | Already built in Phase 3; thread-safe via Qt signals |
| Filter-to-ES-query translation | Custom dict construction | build_filter_clauses() from query_builder | Already built in Phase 3; handles term filters correctly |
| Dark theme CSS | Custom QSS stylesheet | apply_stylesheet(app, "dark_teal.xml") | Already applied in main.py; overriding it causes partial styling |
| Widget testing infrastructure | Manual QApplication lifecycle | pytest-qt qtbot fixture | Handles QApplication singleton, headless rendering, signal waiting |

**Key insight:** Phase 3 provides `SearchEngine`, `build_filter_clauses`, and `ArticleResult` — Phase 4 is almost entirely UI wiring. Avoid re-implementing what the search layer already provides.

---

## Common Pitfalls

### Pitfall 1: Stale Search Results Overwriting Current Results

**What goes wrong:** User types "ferrari", debounce fires, ES takes 200ms. User immediately types "lamborghini", debounce fires again, this ES query returns in 50ms. The lamborghini results display — then the ferrari results arrive and overwrite them.
**Why it happens:** QThreadPool workers run concurrently; result order is non-deterministic.
**How to avoid:** Implement the sequence counter pattern (Pattern 2). Increment `_current_seq` on each dispatch; ignore results in callbacks where `seq != self._current_seq`.
**Warning signs:** Result list "jumps" to different content after appearing correct.

### Pitfall 2: Escape Key Not Firing in keyPressEvent

**What goes wrong:** `QLineEdit` subclass overrides `keyPressEvent`, checks for `Key_Escape`, but nothing happens when Escape is pressed.
**Why it happens:** Escape is hardware/OS-dependent and may only trigger `keyReleaseEvent`. Multiple Qt Forum reports confirm this is consistent on some keyboards/platforms.
**How to avoid:** Override `keyReleaseEvent` instead of `keyPressEvent` for the Escape key. [CITED: https://forum.qt.io/topic/31602]
**Warning signs:** `keyPressEvent` override works for all alphanumeric keys but silently ignores Escape.

### Pitfall 3: QTextDocument sizeHint/paint Mismatch

**What goes wrong:** `QListWidget` items are truncated or have excessive blank space because `sizeHint()` computes a different height than `paint()` renders.
**Why it happens:** `sizeHint` and `paint` use different `QTextDocument` configurations (e.g., different `textWidth` or margin settings).
**How to avoid:** Extract `_make_doc(html, width)` as a shared helper method. Both `sizeHint` and `paint` must call identical setup code. [CITED: https://www.pythonguis.com/faq/cloud-around-the-text-in-qtextedit/]
**Warning signs:** List items overlap each other or show large gaps.

### Pitfall 4: qt-material Theme Applied After Window Construction

**What goes wrong:** Some widgets retain default Qt styling (light background, dark text) while others pick up the dark theme.
**Why it happens:** `apply_stylesheet()` only themes widgets created after it is called.
**How to avoid:** `apply_stylesheet(app, theme="dark_teal.xml")` is already called before any window construction in `main.py`. Phase 4 must not call it again or reorder construction.
**Warning signs:** Some widgets appear with default white background inside the dark-themed window.

### Pitfall 5: Direct ES Call from Main Thread

**What goes wrong:** Typing a character in the search box causes the UI to freeze for 50–200ms while the ES round-trip completes.
**Why it happens:** `client.search()` is a blocking network call. If called directly in a slot (main thread), it blocks the Qt event loop.
**How to avoid:** Always call `SearchEngine.search()` which dispatches to `_SearchWorker` on a background thread. Never call `client.search()` directly from any slot or signal handler.
**Warning signs:** UI becomes unresponsive during typing; search bar stops accepting input momentarily.

### Pitfall 6: QApplication Instantiated Twice in Tests

**What goes wrong:** Test file creates `QApplication(sys.argv)` at module level, but `pytest-qt` also creates one, causing a `RuntimeError`.
**Why it happens:** Qt only allows one `QApplication` per process. The existing `test_engine.py` uses `_app = QApplication.instance() or QApplication(sys.argv)` — the `or` guard is the correct pattern, but the `qtbot` fixture from pytest-qt handles this automatically.
**How to avoid:** In Phase 4 test files, use the `qtbot` fixture or `qapp` fixture from pytest-qt instead of manually creating a `QApplication`. Do not use the module-level `_app = ...` pattern in new test files.
**Warning signs:** Tests fail with `RuntimeError: QApplication has already been created`.

### Pitfall 7: ArticleResult Missing `body` Field for Detail Pane

**What goes wrong:** Detail pane only shows 300-char excerpt instead of full article body.
**Why it happens:** `ArticleResult` only has `excerpt`; `body` is not in `_source` list in `build_search_body`.
**How to avoid:** Either (a) display excerpt only in detail pane and accept 300-char limit, or (b) add `body` to the `_source` list and to `ArticleResult`. Decision for Phase 4 implementation.
**Warning signs:** Clicking a result shows only partial text; article "ends" mid-sentence.

### Pitfall 8: dark_teal Selection Contrast with `<b>` Highlighted Text

**What goes wrong:** `<b>` highlight tags from ES use the item's text color — but when the item is selected, selection-background is `#6effe8` (cyan) and selection-color is `#000000`. The `<b>` tags in the HTML fragment may not inherit the selection color.
**Why it happens:** `QTextDocument.drawContents()` uses the document's stylesheet colors, not the Qt selection palette.
**How to avoid:** Set a custom selection-style in the HTML or skip `<b>` in favor of a `<span style="background:#ffeb3b">` highlight style. Alternatively, strip HTML tags from the displayed excerpt when the item is selected and re-render. Simpler: accept that `<b>` bold markers remain visible even when selected.
**Warning signs:** Selected items show `<b>Ferrari 308</b>` with strange contrast.

---

## Code Examples

### Connecting SearchEngine to Result List

```python
# Source: Phase 3 engine.py comment (Usage pattern documented there)
# [VERIFIED: codebase — engine.py line 126]
engine = SearchEngine(client)

# In MainWindow:
self._current_seq = 0

def _execute_search(self) -> None:
    self._current_seq += 1
    seq = self._current_seq
    engine.search(
        self._search_bar.text().strip(),
        filters=self._filter_sidebar.collect_filters(),
        callback=lambda results, s=seq: self._on_results(results, s),
        error_callback=self._on_search_error,
    )

def _on_results(self, results, seq):
    if seq != self._current_seq:
        return
    self._result_list.clear()
    for r in results:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, _result_to_html(r))
        item.setData(Qt.ItemDataRole.UserRole + 1, r)  # store ArticleResult for detail pane
        self._result_list.addItem(item)
```

### Reading ES `took` from SearchEngine

The current `_SearchWorker.run()` emits only `list[ArticleResult]`. To expose `took_ms` (UIPL-02), one approach is to extend `_SearchSignals` with a second signal or change `results_ready` to emit a tuple. The simplest change consistent with the existing pattern:

```python
# Extension to _SearchSignals in engine.py (Phase 4 may add this):
results_ready = pyqtSignal(list, int)  # list[ArticleResult], took_ms
# In _SearchWorker.run():
took_ms = resp.get("took", 0)
self._signals.results_ready.emit(results, took_ms)
```

This is a two-line change to Phase 3 engine.py. The plan should include it explicitly.

### pytest-qt Test Pattern for UI Widgets

```python
# Source: pytest-qt docs — https://pytest-qt.readthedocs.io/en/latest/intro.html
# [VERIFIED: pytest-qt official docs]
def test_search_bar_triggers_debounce(qtbot):
    from nitrofind.ui.main_window import MainWindow
    from unittest.mock import MagicMock
    engine = MagicMock()
    window = MainWindow(engine)
    qtbot.addWidget(window)
    qtbot.keyClicks(window._search_bar, "Ferrari")
    # wait for debounce timer
    qtbot.waitSignal(window._debounce_timer.timeout, timeout=500)
    engine.search.assert_called_once()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-keystroke ES search | Debounced QTimer (300ms) | Phase 4 specification | Reduces ES calls by ~10x during active typing |
| StubMainWindow (Phase 1 placeholder) | Full MainWindow with search/filter/detail | Phase 4 | Replaces placeholder entirely |
| Manual threading.Thread for background work | QThreadPool + QRunnable (Phase 3) | Phase 3 | Already in place; Phase 4 UI just connects signals |

**Deprecated/outdated:**
- `StubMainWindow` in `nitrofind/ui/main_window.py`: replace entirely with `MainWindow` in Phase 4.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Filter sidebar uses single-select per dimension (one manufacturer, one era, one body style) | Pattern 5 | If multi-select is required, `build_filter_clauses` must be extended and the sidebar pattern changes |
| A2 | Detail pane displays `excerpt` (300 chars); full `body` requires schema/model extension | Pattern 4, Pitfall 7 | If full body is required, add `body` to `_source` and `ArticleResult` — a Phase 4 mini-task |
| A3 | Filter values (manufacturers, era buckets, body styles) are hardcoded or known at dev time | Pattern 5 | If filter values must be populated dynamically from ES aggregations, a separate ES aggregation query is needed at startup |
| A4 | `results_ready` signal change from `pyqtSignal(list)` to `pyqtSignal(list, int)` is safe | Code Examples | If other consumers of `results_ready` exist (none found in codebase), they would need updating |

---

## Open Questions

1. **Full article body in detail pane vs. excerpt-only**
   - What we know: `ArticleResult` has `excerpt` (300 chars); no `body` field.
   - What's unclear: Does Phase 4 require full body display (SRCH-03 says "full article text")?
   - Recommendation: Add `body` to `_source` list and `ArticleResult` dataclass in Phase 4. Two-line change. Plan it as Wave 0 task.

2. **Filter values source**
   - What we know: SRCH-04 requires filtering by manufacturer, era_bucket, body_style.
   - What's unclear: Where do the checkbox labels come from? Hardcoded known values or ES aggregation at startup?
   - Recommendation: Start with hardcoded era values (1950s–2010s) and a representative manufacturer list. ES aggregation is v2.

3. **UIPL-02: `took_ms` signal extension**
   - What we know: `results_ready` currently emits `list` only.
   - What's unclear: Is changing the signal signature acceptable (could break existing test connections)?
   - Recommendation: Change `results_ready` to `pyqtSignal(list, int)` in Phase 4 Wave 0. Update `test_engine.py` connection tests to match new signature.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PyQt6 | All UI widgets | Yes | 6.11.0 | — |
| qt-material | Dark theme | Yes | 2.17 | QDarkStyle (per CLAUDE.md alternatives) |
| pytest-qt | UI unit tests | Yes | 4.5.0 | — |
| Elasticsearch (local node) | Integration tests only | Not verified (requires ES_HOME) | 8.18 | Skip with @pytest.mark.integration |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** ES node — integration tests require live ES (already guarded with `@pytest.mark.integration` pattern from Phase 3).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt 4.5.0 |
| Config file | `pytest.ini` (exists — `markers` only; `qt_api` not set; PyQt6 auto-detected) |
| Quick run command | `pytest tests/test_ui/ -m "not integration" -x` |
| Full suite command | `pytest tests/ -m "not integration" -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRCH-01 | Debounce timer fires 300ms after last keystroke | unit | `pytest tests/test_ui/test_main_window.py::test_debounce_timer_interval -x` | No — Wave 0 |
| SRCH-01 | textChanged connects to debounce timer restart | unit | `pytest tests/test_ui/test_main_window.py::test_search_bar_triggers_debounce -x` | No — Wave 0 |
| SRCH-02 | Result list populates title, domain, excerpt from ArticleResult | unit | `pytest tests/test_ui/test_main_window.py::test_result_list_populates -x` | No — Wave 0 |
| SRCH-02 | HTML `<b>` tags from highlight_body rendered by delegate | unit | `pytest tests/test_ui/test_result_delegate.py::test_html_result_to_html -x` | No — Wave 0 |
| SRCH-03 | Clicking result updates detail pane with article text | unit | `pytest tests/test_ui/test_main_window.py::test_result_click_updates_detail -x` | No — Wave 0 |
| SRCH-04 | Filter checkbox state passed to engine.search() filters arg | unit | `pytest tests/test_ui/test_filter_sidebar.py::test_collect_filters -x` | No — Wave 0 |
| SRCH-04 | Typing new query preserves filter checkbox state | unit | `pytest tests/test_ui/test_main_window.py::test_filter_preserved_on_retype -x` | No — Wave 0 |
| UIPL-01 | `<b>` tags from ES highlight in result HTML | unit | `pytest tests/test_ui/test_main_window.py::test_highlight_tags_in_result_html -x` | No — Wave 0 |
| UIPL-02 | Status label updated with result count and timing | unit | `pytest tests/test_ui/test_main_window.py::test_status_label_updated -x` | No — Wave 0 |
| UIPL-03 | apply_stylesheet called with dark_teal.xml before MainWindow | unit | verified by main.py code review — no new test needed | Existing (main.py) |
| UIPL-04 | Escape clears search bar | unit | `pytest tests/test_ui/test_main_window.py::test_escape_clears_search -x` | No — Wave 0 |
| UIPL-04 | itemActivated fires on Return key | unit | `pytest tests/test_ui/test_main_window.py::test_enter_opens_result -x` | No — Wave 0 |
| UIPL-04 | Arrow key changes current row | unit | `pytest tests/test_ui/test_main_window.py::test_arrow_key_navigation -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_ui/ -m "not integration" -x`
- **Per wave merge:** `pytest tests/ -m "not integration" -x`
- **Phase gate:** Full suite (including existing Phase 1-3 tests) green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ui/__init__.py` — package marker
- [ ] `tests/test_ui/test_main_window.py` — covers SRCH-01, SRCH-02, SRCH-03, SRCH-04, UIPL-01, UIPL-02, UIPL-04
- [ ] `tests/test_ui/test_result_delegate.py` — covers SRCH-02, UIPL-01
- [ ] `tests/test_ui/test_filter_sidebar.py` — covers SRCH-04

---

## Security Domain

`security_enforcement` is not set to false in `.planning/config.json` — security domain is required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Local desktop app, no auth |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Single-user local tool |
| V5 Input Validation | Yes | Query text passed to `build_search_body` which places it inside `multi_match.query` string — not as DSL key (T-03-01 from Phase 3, already enforced) |
| V6 Cryptography | No | No secrets or tokens in UI layer |

### Known Threat Patterns for PyQt6 + ES UI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Query injection via search bar | Tampering | Already mitigated in Phase 3 (T-03-01): user text never used as DSL key, only as `multi_match.query` string value |
| XSS via HTML rendering in QTextBrowser | Tampering | QTextBrowser renders a controlled subset of HTML (Qt Rich Text) — no `<script>` execution; no web engine involved |
| Path traversal via filter values | Tampering | Filter values are used only as ES `term` query values — no file system access |
| UI thread ES calls blocking event loop | Denial of Service | Mitigated by SearchEngine architecture (Phase 3) — never call ES directly from main thread |

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 4 |
|-----------|------------------|
| Python + Elasticsearch + PyQt6 — fixed, no substitutions | No alternative UI frameworks; no web views |
| No AI/ML — pure function_score relevance | No semantic search, no ML ranking in UI |
| Offline at search time | No network calls from UI layer; all data from local ES |
| Database size under 2 GB | Scraper constraint; no UI impact |
| PyQt6 6.11.0 | Confirmed installed; use Qt6 enum syntax (e.g., `Qt.AlignmentFlag.AlignCenter`) |
| elasticsearch-dsl merged into core at 8.18 — no separate install | No `elasticsearch-dsl` import; use `elasticsearch` directly |
| apply_stylesheet before window construction | Already in main.py; Phase 4 must not reorder |
| Logger uses % formatting throughout | All new logger calls in UI code must use `%` format, not f-strings |
| `logger = logging.getLogger(__name__)` per module | Each new UI module gets its own module-level logger |

---

## Sources

### Primary (HIGH confidence)

- Qt official docs — `QListWidget` signals: https://doc.qt.io/qt-6/qlistwidget.html — itemActivated fires on Enter/Return key confirmed
- Qt official docs — `QTextBrowser`: https://doc.qt.io/qt-6/qtextbrowser.html — openLinks, openExternalLinks defaults confirmed
- Qt official docs — `QSplitter`: https://doc.qt.io/qt-6/qsplitter.html — addWidget() instead of setLayout() confirmed
- Qt Wiki — debounce pattern: https://wiki.qt.io/Delay_action_to_wait_for_user_interaction — QTimer single-shot pattern confirmed
- Codebase — `nitrofind/search/engine.py` — SearchEngine.search() callback contract verified
- Codebase — `nitrofind/search/query_builder.py` — build_filter_clauses() API verified
- Codebase — `nitrofind/search/models.py` — ArticleResult fields verified
- Codebase — `main.py` — apply_stylesheet(app, "dark_teal.xml") called before window construction verified
- PyPI — package versions: PyQt6 6.11.0, qt-material 2.17, pytest-qt 4.5.0 all confirmed installed

### Secondary (MEDIUM confidence)

- pythonguis.com — QTextDocument in QStyledItemDelegate: https://www.pythonguis.com/faq/cloud-around-the-text-in-qtextedit/ — sizeHint/paint shared helper pattern
- pythonguis.com — QThreadPool multithreading: https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/ — WorkerSignals pattern
- qt-material GitHub — dark_teal.qss: https://github.com/UN-GCPDS/qt-material/blob/master/examples/exporter/dark_teal.qss — selection colors confirmed (#6effe8 background, #000000 text)

### Tertiary (LOW confidence)

- Qt Forum — Escape key in QLineEdit: https://forum.qt.io/topic/31602 — keyReleaseEvent recommended; behavior is hardware-dependent
- Qt Forum — QListWidget vs QListView: https://forum.qt.io/topic/94678 — QListWidget adequate for < ~500 items; community consensus only

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages confirmed installed with pip index versions
- Architecture: HIGH — PyQt6 widget APIs confirmed via official Qt docs
- Pitfalls: MEDIUM — most verified via official docs; Escape key pitfall is MEDIUM (forum + community, hardware-dependent)
- Test approach: HIGH — pytest-qt confirmed installed; qtbot fixture verified via official docs

**Research date:** 2026-05-28
**Valid until:** 2026-07-28 (60 days — PyQt6 is stable; qt-material releases infrequently)
