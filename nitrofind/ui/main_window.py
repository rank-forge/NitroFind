"""
MainWindow — full search UI window for NitroFind (Phase 4, Plan 03).

Replaces StubMainWindow with a complete QMainWindow that wires the search bar,
debounce timer, filter sidebar, result list, and detail pane together.

Copywriting Contract (verbatim strings required by UI-SPEC):
  Search bar placeholder:  "Search cars, manufacturers, models…"   (U+2026)
  Status idle:             ""
  Status loading:          "Searching…"
  Status results:          "{N} results ({T:.2f}s)"  (N=len, T=took_ms/1000)
  Status no results:       "No results"
  Status error:            "Search failed. Check Elasticsearch connection."
  Detail pane initial:     "Select a result to read the article."  (centered, color #80cbc4)
  Window title idle:       "NitroFind — Ready"         (em-dash U+2014, NOT hyphen)
  Window title searching:  "NitroFind — {query}"       (em-dash U+2014, NOT hyphen)
  Empty result list label: "No articles match your search.\nTry different keywords or adjust filters."

UI-SPEC Component references:
  Component 1: SearchLineEdit
  Component 2: Status Label
  Component 4: Result List (QListWidget + ResultDelegate)
  Component 5: FilterSidebar
  Component 6: Detail Pane (QTextBrowser)
  Component 7: Stale Result Guard

Security mitigations:
  T-04-02 (XSS): QTextBrowser renders Qt Rich Text only — setOpenLinks(False),
           setOpenExternalLinks(False) explicit per UI-SPEC Component 6.
  T-04-03 (Info Disclosure): _on_search_error logs raw msg via % formatting,
           sets status label ONLY to the static literal string.
  T-04-04 (DoS): MainWindow NEVER calls client.search() directly — all ES I/O
           routed through self._engine.search() which dispatches to QThreadPool.
  T-04-05 (Stale results): _current_seq monotonic counter guards _on_results().

StubMainWindow alias removed — Plan 04 must update main.py to import MainWindow
directly and call MainWindow(client) in on_es_ready().
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent

from nitrofind.search.engine import SearchEngine
from nitrofind.search.models import ArticleResult  # noqa: F401 (used in type hints)
from nitrofind.ui.result_delegate import ResultDelegate, _result_to_html
from nitrofind.ui.filter_sidebar import FilterSidebar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SearchLineEdit — QLineEdit subclass with Escape-to-clear override
# ---------------------------------------------------------------------------


class SearchLineEdit(QLineEdit):
    """QLineEdit subclass that clears on Escape key release.

    UI-SPEC Component 1:
      Overrides keyReleaseEvent (NOT keyPressEvent) for Escape handling.
      Escape only fires reliably on release — hardware-dependent cross-platform
      quirk documented in 04-RESEARCH.md Pitfall 2.
    """

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        """Clear the search bar when Escape is released.

        Escape clears the bar before calling super(), so the clear happens
        regardless of any upstream handlers. textChanged fires after clear(),
        which triggers the debounce timer, which calls _execute_search(),
        which detects an empty query and clears the result list.

        Args:
            event: Key release event from Qt.
        """
        if event.key() == Qt.Key.Key_Escape:
            self.clear()
        super().keyReleaseEvent(event)


# ---------------------------------------------------------------------------
# MainWindow — full search UI
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """Full search UI window: SearchLineEdit + status label + splitter with
    FilterSidebar, QListWidget result list, and QTextBrowser detail pane.

    Constructor accepts an Elasticsearch client and constructs SearchEngine
    internally (matches the main.py W0-EXT-03 pattern: MainWindow(client)).

    All six child widgets are exposed as read-only @property accessors for
    test introspection — mirrors the LoadingWindow accessor convention.

    Sequence counter (stale-result guard, T-04-05):
      _current_seq is incremented before every search dispatch. _on_results()
      discards any callback whose seq does not match _current_seq.
    """

    def __init__(self, client) -> None:
        """Construct MainWindow.

        Args:
            client: Elasticsearch client instance (not a SearchEngine — matches
                    main.py on_es_ready() pattern where MainWindow(client) is
                    called with the raw client created in that function).
        """
        super().__init__()

        # Construct SearchEngine from the raw ES client (W0-EXT-03 contract)
        self._engine = SearchEngine(client)

        # Stale-result guard counter (T-04-05)
        self._current_seq: int = 0

        # Window properties
        self.setWindowTitle("NitroFind — Ready")  # U+2014 em-dash
        self.setMinimumSize(1100, 700)

        # ------------------------------------------------------------------
        # Build child widgets
        # Construction order mirrors loading_window.py convention:
        # widgets first, layout second, signal wiring last.
        # ------------------------------------------------------------------

        # Search bar (UI-SPEC Component 1)
        self._search_bar = SearchLineEdit()
        self._search_bar.setPlaceholderText("Search cars, manufacturers, models…")  # U+2026
        self._search_bar.setClearButtonEnabled(True)
        self._search_bar.setFixedHeight(40)

        # Status label (UI-SPEC Component 2)
        self._status_label = QLabel("")
        self._status_label.setFixedHeight(20)
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        # Debounce timer (UI-SPEC Component 1, SRCH-01)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)

        # Filter sidebar (UI-SPEC Component 5)
        self._filter_sidebar = FilterSidebar()
        self._filter_sidebar.setMinimumWidth(160)
        self._filter_sidebar.setMaximumWidth(240)

        # Result list (UI-SPEC Component 4)
        self._result_list = QListWidget()
        self._result_list.setUniformItemSizes(False)
        self._result_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._result_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._result_list.setItemDelegate(ResultDelegate(self._result_list))

        # Detail pane (UI-SPEC Component 6)
        self._detail_pane = QTextBrowser()
        self._detail_pane.setOpenLinks(False)
        self._detail_pane.setOpenExternalLinks(False)
        self._detail_pane.setHtml(
            "<p style='color:#80cbc4;font-size:10pt;margin-top:32px;text-align:center'>"
            "Select a result to read the article."
            "</p>"
        )

        # ------------------------------------------------------------------
        # Build layout
        # QVBoxLayout (spacing=8, margins=8) containing:
        #   search row (QHBoxLayout with search bar only)
        #   status label
        #   QSplitter (sidebar | result_list | detail_pane)
        # ------------------------------------------------------------------
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Search row
        search_row = QHBoxLayout()
        search_row.addWidget(self._search_bar)
        main_layout.addLayout(search_row)

        # Status label
        main_layout.addWidget(self._status_label)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._filter_sidebar)
        splitter.addWidget(self._result_list)
        splitter.addWidget(self._detail_pane)
        splitter.setSizes([200, 320, 580])
        main_layout.addWidget(splitter)

        self.setCentralWidget(central_widget)

        # ------------------------------------------------------------------
        # Wire signals AFTER widget construction
        # (mirrors engine.py T-03-06 and loading_window.py convention)
        # ------------------------------------------------------------------

        # Debounce: textChanged restarts the 300ms countdown (SRCH-01)
        self._search_bar.textChanged.connect(self._debounce_timer.start)
        self._debounce_timer.timeout.connect(self._execute_search)

        # Filter checkboxes also trigger debounce (SRCH-04)
        for cb in self._filter_sidebar.manufacturer_checks.values():
            cb.stateChanged.connect(self._debounce_timer.start)
        for cb in self._filter_sidebar.era_checks.values():
            cb.stateChanged.connect(self._debounce_timer.start)
        for cb in self._filter_sidebar.body_style_checks.values():
            cb.stateChanged.connect(self._debounce_timer.start)

        # Result selection: arrow-key hover and click both update detail pane
        self._result_list.currentRowChanged.connect(self._on_result_hovered)
        self._result_list.itemActivated.connect(self._on_result_activated)

    # ------------------------------------------------------------------
    # Public property accessors (test introspection — mirrors loading_window.py)
    # ------------------------------------------------------------------

    @property
    def search_bar(self) -> SearchLineEdit:
        """Read-only accessor: the SearchLineEdit widget."""
        return self._search_bar

    @property
    def status_label(self) -> QLabel:
        """Read-only accessor: the status QLabel widget."""
        return self._status_label

    @property
    def result_list(self) -> QListWidget:
        """Read-only accessor: the QListWidget result list."""
        return self._result_list

    @property
    def detail_pane(self) -> QTextBrowser:
        """Read-only accessor: the QTextBrowser detail pane."""
        return self._detail_pane

    @property
    def filter_sidebar(self) -> FilterSidebar:
        """Read-only accessor: the FilterSidebar widget."""
        return self._filter_sidebar

    @property
    def debounce_timer(self) -> QTimer:
        """Read-only accessor: the debounce QTimer."""
        return self._debounce_timer

    # ------------------------------------------------------------------
    # Search dispatch (UI-SPEC Component 7, SRCH-01)
    # ------------------------------------------------------------------

    def _execute_search(self) -> None:
        """Fire the search after the debounce timer expires.

        If the query is empty (after strip), clear the result list and reset
        the status label without dispatching to Elasticsearch.
        Otherwise, increment _current_seq, update the window title and status
        label to "Searching…", then dispatch to SearchEngine.search() with
        the current filter state.
        """
        query = self._search_bar.text().strip()
        if not query:
            self._result_list.clear()
            self._status_label.setText("")
            self.setWindowTitle("NitroFind — Ready")
            return

        # Increment sequence counter BEFORE dispatch (T-04-05 stale guard)
        self._current_seq += 1
        seq = self._current_seq

        self.setWindowTitle(f"NitroFind — {query}")
        self._status_label.setText("Searching…")

        self._engine.search(
            query,
            filters=self._filter_sidebar.collect_filters(),
            callback=lambda results, took, s=seq: self._on_results(results, took, s),
            error_callback=self._on_search_error,
        )

    # ------------------------------------------------------------------
    # Result callbacks
    # ------------------------------------------------------------------

    def _on_results(self, results: list, took_ms: int, seq: int) -> None:
        """Handle results delivered by SearchEngine via QueuedConnection.

        Discards stale results (seq != _current_seq) to prevent an older
        slow search from overwriting a newer faster search's results (T-04-05).

        Args:
            results:  list[ArticleResult] from SearchEngine.
            took_ms:  Query time in milliseconds from ES response "took" field.
            seq:      Sequence counter value captured at dispatch time.
        """
        if seq != self._current_seq:
            return  # stale — discard (T-04-05)

        self._result_list.clear()

        if not results:
            self._status_label.setText("No results")
            self._detail_pane.setHtml(
                "<p style='color:#80cbc4;font-size:10pt;margin-top:32px;text-align:center'>"
                "Select a result to read the article."
                "</p>"
            )
            return

        self._status_label.setText(f"{len(results)} results ({took_ms / 1000:.2f}s)")

        for r in results:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, _result_to_html(r))
            item.setData(Qt.ItemDataRole.UserRole + 1, r)
            self._result_list.addItem(item)

        # Select row 0 so arrow-key navigation has a starting position
        # and the detail pane shows the first article immediately
        self._result_list.setCurrentRow(0)

    def _on_search_error(self, msg: str) -> None:
        """Handle search failure delivered by SearchEngine.search_failed signal.

        Logs the raw error message for developer diagnostics (% formatting,
        never f-string in logger call — CLAUDE.md convention, T-04-03).
        Sets the status label to the static error string ONLY — never str(msg)
        in the visible UI (T-04-03 Information Disclosure mitigation).

        Args:
            msg: Raw error message string from the exception in _SearchWorker.
        """
        logger.warning("Search failed: %s", msg)
        self._status_label.setText(
            "Search failed. Check Elasticsearch connection."
        )

    # ------------------------------------------------------------------
    # Result selection handlers
    # ------------------------------------------------------------------

    def _on_result_hovered(self, row: int) -> None:
        """Update the detail pane when the current result row changes.

        Called by currentRowChanged signal — fires on arrow-key navigation
        and single-click selection. Detail pane updates on hover, not only
        on activation (UI-SPEC Interaction Contracts).

        Args:
            row: The new current row index (-1 if no selection).
        """
        if row < 0:
            return
        item = self._result_list.item(row)
        if item is None:
            return
        result: ArticleResult = item.data(Qt.ItemDataRole.UserRole + 1)
        self._show_result_detail(result)

    def _on_result_activated(self, item: QListWidgetItem) -> None:
        """Update the detail pane when a result is activated (double-click or Enter).

        Called by itemActivated signal — fires on double-click AND Return/Enter
        key press (UIPL-04 Enter-to-open requirement).

        Args:
            item: The activated QListWidgetItem.
        """
        if item is None:
            return
        result: ArticleResult = item.data(Qt.ItemDataRole.UserRole + 1)
        self._show_result_detail(result)

    def _show_result_detail(self, result: ArticleResult) -> None:
        """Render the detail pane HTML for the given result.

        Prefers result.body (full article text, W0-EXT-01) over result.excerpt
        when body is non-empty (SRCH-03 full article text requirement).

        Args:
            result: ArticleResult to render in the detail pane.
        """
        if result is None:
            return
        body_text = result.body if result.body else result.excerpt
        self._detail_pane.setHtml(
            f"<h2 style='font-size:14pt'>{result.title}</h2>"
            f"<p style='color:#80cbc4;font-size:9pt'>{result.source_domain} · {result.url}</p>"
            f"<hr>"
            f"<p style='font-size:10pt;line-height:1.5'>{body_text}</p>"
        )
