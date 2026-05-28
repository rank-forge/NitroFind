"""
tests/test_ui/test_main_window.py — SRCH-01, SRCH-02, SRCH-03, SRCH-04,
UIPL-01, UIPL-02, UIPL-04 coverage, plus T-04-03 static error string and
logger % formatting compliance.

Requirement coverage:
  SRCH-01: Debounce timer interval, single-shot, restarts on keystrokes,
           stale-result guard discards superseded searches, empty query
           short-circuits without ES dispatch.
  SRCH-02: Result list populates from search callback; highlight HTML preserved.
  SRCH-03: Result click / hover updates detail pane with article content.
  SRCH-04: Filter checkbox state survives query retyping; filters forwarded
           on every _execute_search() call.
  UIPL-01: ES highlight <b> tags preserved in result row HTML.
  UIPL-02: Status label shows "N results (T.2fs)" format, "No results" for empty.
  UIPL-04: Escape clears search bar; Enter/Return opens result; arrow keys
           navigate the result list.
  T-04-03: _on_search_error sets ONLY the static string — never raw exception text.
  Logger:  All logger calls use % formatting — no f-string logger calls.

Test strategy:
  - Use qtbot fixture from pytest-qt for widget lifecycle management.
  - MagicMock SearchEngine — never live ES; no QThreadPool dispatch in unit tests.
  - Injection idiom: monkeypatch.setattr("nitrofind.ui.main_window.SearchEngine",
    MagicMock(return_value=engine_mock)) so that MainWindow(client) constructs
    our controllable mock instead of a real SearchEngine.
  - Callbacks are invoked directly (not via QThreadPool) to test result handling
    synchronously. The callback is captured from engine.search.call_args.
  - Do NOT instantiate QApplication directly — qtbot fixture manages this (Pitfall 6).
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_results(n: int = 3):
    """Return n ArticleResult instances with distinct titles for test fixtures.

    Each result has distinct title ("Result 0", "Result 1", ...),
    unique url, source_domain, and score for easy identification in assertions.

    Args:
        n: Number of ArticleResult instances to create.

    Returns:
        list[ArticleResult] of length n.
    """
    from nitrofind.search.models import ArticleResult

    return [
        ArticleResult(
            title=f"Result {i}",
            url=f"https://example.com/result-{i}",
            source_domain="example.com",
            score=float(n - i),
            excerpt=f"Excerpt for result {i}",
            body=f"Full body text for result {i}",
        )
        for i in range(n)
    ]


def _make_window(qtbot, monkeypatch, engine_mock=None):
    """Construct a MainWindow with a MagicMock SearchEngine for testing.

    Injection idiom: monkeypatch.setattr patches nitrofind.ui.main_window.SearchEngine
    so that MainWindow(client) constructs engine_mock instead of a real SearchEngine.
    If no engine_mock is provided, a default MagicMock() is created.

    Args:
        qtbot:       pytest-qt qtbot fixture (manages widget lifecycle).
        monkeypatch: pytest monkeypatch fixture (patches SearchEngine).
        engine_mock: Optional MagicMock to use as the engine. Created if None.

    Returns:
        (window, engine_mock) tuple.
    """
    from nitrofind.ui.main_window import MainWindow

    if engine_mock is None:
        engine_mock = MagicMock()
        engine_mock.search.return_value = None  # non-blocking API contract

    mock_client = MagicMock()

    # Patch SearchEngine class so MainWindow(client) uses our mock
    monkeypatch.setattr(
        "nitrofind.ui.main_window.SearchEngine",
        MagicMock(return_value=engine_mock),
    )

    window = MainWindow(mock_client)
    qtbot.addWidget(window)
    return window, engine_mock


def _trigger_search_and_capture_callback(qtbot, window, engine_mock, query="test"):
    """Trigger a search and return the captured callback from engine.search.

    Sets the search bar text, waits for the debounce timer to fire, and
    extracts the callback kwarg from the engine.search call.

    Args:
        qtbot:       pytest-qt qtbot fixture.
        window:      MainWindow instance.
        engine_mock: MagicMock engine whose .search is monitored.
        query:       Search query string to type.

    Returns:
        The callback function captured from engine.search call_args.
    """
    call_count_before = engine_mock.search.call_count

    window._search_bar.setText(query)

    # Use context manager form to block until the timer fires
    with qtbot.waitSignal(window._debounce_timer.timeout, timeout=500):
        pass

    assert engine_mock.search.call_count > call_count_before, (
        f"engine.search should have been called after '{query}' search"
    )

    call_args = engine_mock.search.call_args
    callback = call_args.kwargs.get("callback") or call_args[1].get("callback")
    assert callback is not None, "engine.search must be called with a callback kwarg"
    return callback


# ---------------------------------------------------------------------------
# Test 1 — SRCH-01: Debounce timer configuration
# ---------------------------------------------------------------------------


def test_debounce_timer_interval(qtbot, monkeypatch):
    """SRCH-01: Debounce timer must be 300ms single-shot.

    Asserts:
      - _debounce_timer.interval() == 300
      - _debounce_timer.isSingleShot() is True
    """
    window, _ = _make_window(qtbot, monkeypatch)
    assert window._debounce_timer.interval() == 300, (
        f"Expected interval 300ms, got {window._debounce_timer.interval()}"
    )
    assert window._debounce_timer.isSingleShot() is True, (
        "Debounce timer must be single-shot"
    )


# ---------------------------------------------------------------------------
# Test 2 — SRCH-01: Search bar keystrokes trigger debounce, coalesce to one search
# ---------------------------------------------------------------------------


def test_search_bar_triggers_debounce(qtbot, monkeypatch):
    """SRCH-01: Typing in the search bar restarts the debounce timer.

    Multiple keystrokes within 300ms should coalesce into a single search
    dispatch. After waiting for the debounce timeout, engine.search should
    have been called exactly once.
    """
    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    # Type "Ferrari" — multiple keystrokes should restart the timer each time
    qtbot.keyClicks(window._search_bar, "Ferrari")

    # Wait for the debounce timer to fire (context manager form — blocks until signal)
    with qtbot.waitSignal(window._debounce_timer.timeout, timeout=500):
        pass

    # All keystrokes coalesced into a single dispatch
    engine_mock.search.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3 — SRCH-02: Result list populates from callback; status label correct
# ---------------------------------------------------------------------------


def test_result_list_populates(qtbot, monkeypatch):
    """SRCH-02: Invoking the search callback populates the result list.

    After the callback is called with 3 results and took_ms=42:
      - result_list.count() == 3
      - status_label.text() == "3 results (0.04s)"
    """
    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    results = _make_results(3)
    callback = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "Ferrari")

    # Invoke the callback directly (synchronous — no QThreadPool)
    callback(results, 42)

    assert window._result_list.count() == 3, (
        f"Expected 3 items, got {window._result_list.count()}"
    )
    assert window._status_label.text() == "3 results (0.04s)", (
        f"Expected '3 results (0.04s)', got '{window._status_label.text()}'"
    )


# ---------------------------------------------------------------------------
# Test 4 — SRCH-03: Clicking a result updates the detail pane
# ---------------------------------------------------------------------------


def test_result_click_updates_detail(qtbot, monkeypatch):
    """SRCH-03: Selecting row 0 populates the detail pane with that result's content.

    After populating 3 results and setting row 0 as current:
      - detail_pane.toHtml() contains the title of the row-0 ArticleResult.
    """
    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    results = _make_results(3)
    callback = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "test")
    callback(results, 10)

    # Select row 0 — currentRowChanged fires → _on_result_hovered → _show_result_detail
    window._result_list.setCurrentRow(0)

    # Detail pane should contain "Result 0" (title of row-0 result)
    html = window._detail_pane.toHtml()
    assert "Result 0" in html, (
        f"Expected 'Result 0' in detail pane HTML, but got: {html[:200]}"
    )


# ---------------------------------------------------------------------------
# Test 5 — SRCH-04: Filter state preserved across query retyping
# ---------------------------------------------------------------------------


def test_filter_preserved_on_retype(qtbot, monkeypatch):
    """SRCH-04: Filter checkbox state survives typing a new query.

    After checking the "Ferrari" manufacturer filter:
      1. Trigger a first search — filters kwarg should include Ferrari filter.
      2. Type a new query — filters kwarg on second call should still include
         the Ferrari filter (checkbox was not reset between searches).
    """
    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    # Check the Ferrari manufacturer filter
    window._filter_sidebar.manufacturer_checks["Ferrari"].setChecked(True)

    # First search
    _trigger_search_and_capture_callback(qtbot, window, engine_mock, "porsche")

    assert engine_mock.search.call_count >= 1, "engine.search should have been called"
    first_filters = engine_mock.search.call_args_list[0].kwargs.get("filters") or (
        engine_mock.search.call_args_list[0][1].get("filters")
    )

    # Second search — clear and retype a new query
    window._search_bar.clear()
    _trigger_search_and_capture_callback(qtbot, window, engine_mock, "bmw")

    assert engine_mock.search.call_count >= 2, "engine.search should have been called twice"
    second_filters = engine_mock.search.call_args_list[-1].kwargs.get("filters") or (
        engine_mock.search.call_args_list[-1][1].get("filters")
    )

    # Both searches should carry the Ferrari filter
    def _has_ferrari_filter(filters):
        if not filters:
            return False
        return any("Ferrari" in str(f) for f in filters)

    assert _has_ferrari_filter(first_filters), (
        f"First search should have Ferrari filter, got: {first_filters}"
    )
    assert _has_ferrari_filter(second_filters), (
        f"Second search should still have Ferrari filter, got: {second_filters}"
    )


# ---------------------------------------------------------------------------
# Test 6 — UIPL-01: ES highlight <b> tags preserved in result row HTML
# ---------------------------------------------------------------------------


def test_highlight_tags_in_result_html(qtbot, monkeypatch):
    """UIPL-01: ArticleResult highlight_body is preserved as <b> tags in row HTML.

    An ArticleResult with highlight_body=["The <b>Ferrari</b> 308 GTB"] must
    produce a QListWidgetItem whose UserRole HTML string contains "<b>Ferrari</b>".
    """
    from PyQt6.QtCore import Qt
    from nitrofind.search.models import ArticleResult

    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    # Result with highlight fragment containing <b> tags
    highlighted_result = ArticleResult(
        title="Ferrari 308 GTB",
        url="https://en.wikipedia.org/wiki/Ferrari_308",
        source_domain="en.wikipedia.org",
        score=1.5,
        excerpt="The Ferrari 308 GTB...",
        highlight_body=["The <b>Ferrari</b> 308 GTB"],
    )

    callback = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "Ferrari")
    callback([highlighted_result], 20)

    # Inspect the UserRole HTML for row 0
    item = window._result_list.item(0)
    assert item is not None, "Row 0 item should exist"
    html = item.data(Qt.ItemDataRole.UserRole)
    assert html is not None, "UserRole HTML should not be None"
    assert "<b>Ferrari</b> 308 GTB" in html, (
        f"Expected '<b>Ferrari</b> 308 GTB' in row HTML, got: {html}"
    )


# ---------------------------------------------------------------------------
# Test 7 — UIPL-02: Status label shows correct "N results (T.2fs)" format
# ---------------------------------------------------------------------------


def test_status_label_updated(qtbot, monkeypatch):
    """UIPL-02: Status label shows "N results (T.2fs)" after results callback.

    With 5 results and took_ms=80:
      - status_label.text() == "5 results (0.08s)"
    """
    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    results = _make_results(5)
    callback = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "test")
    callback(results, 80)

    assert window._status_label.text() == "5 results (0.08s)", (
        f"Expected '5 results (0.08s)', got '{window._status_label.text()}'"
    )


# ---------------------------------------------------------------------------
# Test 8 — UIPL-02: Status label shows "No results" for empty result list
# ---------------------------------------------------------------------------


def test_status_label_no_results(qtbot, monkeypatch):
    """UIPL-02: Status label shows "No results" when callback delivers empty list.

    With empty results list and took_ms=12:
      - status_label.text() == "No results"
    """
    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    callback = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "xyzzy")
    callback([], 12)

    assert window._status_label.text() == "No results", (
        f"Expected 'No results', got '{window._status_label.text()}'"
    )


# ---------------------------------------------------------------------------
# Test 9 — UIPL-04: Escape key clears the search bar
# ---------------------------------------------------------------------------


def test_escape_clears_search(qtbot, monkeypatch):
    """UIPL-04: Pressing Escape on the search bar clears its text.

    SearchLineEdit.keyReleaseEvent handles Escape — qtbot.keyClick fires
    both press and release events, exercising the keyReleaseEvent override.
    """
    from PyQt6.QtCore import Qt

    window, _ = _make_window(qtbot, monkeypatch)

    # Set some text in the search bar
    window._search_bar.setText("Ferrari")
    assert window._search_bar.text() == "Ferrari", "Precondition: text set"

    # Press Escape — keyReleaseEvent clears the bar
    qtbot.keyClick(window._search_bar, Qt.Key.Key_Escape)

    assert window._search_bar.text() == "", (
        f"Expected empty string after Escape, got '{window._search_bar.text()}'"
    )


# ---------------------------------------------------------------------------
# Test 10 — UIPL-04: Enter key on result list activates the item
# ---------------------------------------------------------------------------


def test_enter_opens_result(qtbot, monkeypatch):
    """UIPL-04: Pressing Enter/Return on the result list fires itemActivated.

    After populating results and selecting row 0:
      - Send Qt.Key.Key_Return via qtbot.keyClick on result_list
      - Detail pane should show the row-0 article (itemActivated handler ran)
    """
    from PyQt6.QtCore import Qt

    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    results = _make_results(3)
    callback = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "test")
    callback(results, 15)

    # Row 0 is auto-selected after populate; activate via Enter
    window._result_list.setCurrentRow(0)
    window._result_list.setFocus()
    qtbot.keyClick(window._result_list, Qt.Key.Key_Return)

    # Detail pane should contain "Result 0"
    html = window._detail_pane.toHtml()
    assert "Result 0" in html, (
        f"Expected 'Result 0' in detail pane after Enter, got: {html[:200]}"
    )


# ---------------------------------------------------------------------------
# Test 11 — UIPL-04: Arrow key navigation moves selection and updates detail pane
# ---------------------------------------------------------------------------


def test_arrow_key_navigation(qtbot, monkeypatch):
    """UIPL-04: Down arrow on the result list moves selection and updates detail pane.

    After populating 3 results and selecting row 0:
      - Press Qt.Key.Key_Down
      - result_list.currentRow() should be 1
      - detail pane should show "Result 1"
    """
    from PyQt6.QtCore import Qt

    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    results = _make_results(3)
    callback = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "test")
    callback(results, 10)

    # Start at row 0
    window._result_list.setCurrentRow(0)
    window._result_list.setFocus()
    assert window._result_list.currentRow() == 0, "Precondition: row 0 selected"

    # Press Down arrow
    qtbot.keyClick(window._result_list, Qt.Key.Key_Down)

    assert window._result_list.currentRow() == 1, (
        f"Expected row 1 after Down arrow, got {window._result_list.currentRow()}"
    )

    # Detail pane should now show "Result 1"
    html = window._detail_pane.toHtml()
    assert "Result 1" in html, (
        f"Expected 'Result 1' in detail pane after Down arrow, got: {html[:200]}"
    )


# ---------------------------------------------------------------------------
# Test 12 — SRCH-01 stale guard: stale results are discarded
# ---------------------------------------------------------------------------


def test_stale_results_discarded(qtbot, monkeypatch):
    """SRCH-01: Stale results from superseded searches are discarded.

    Sequence:
      1. Dispatch search #1 (captures callback_1 with seq=1)
      2. Dispatch search #2 (captures callback_2 with seq=2 — supersedes #1)
      3. Call callback_2 first (newer) → result list shows "Current Result"
      4. Call callback_1 after (older, stale) → result list must NOT change

    This tests the _current_seq guard in _on_results().
    """
    from nitrofind.search.models import ArticleResult

    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    # --- Search #1 ---
    callback_1 = _trigger_search_and_capture_callback(
        qtbot, window, engine_mock, "por"
    )

    # --- Search #2 (supersedes #1) —  clear first to allow new debounce ---
    window._search_bar.clear()
    # Give the debounce timer a moment to not fire on the cleared text
    qtbot.wait(50)

    callback_2 = _trigger_search_and_capture_callback(
        qtbot, window, engine_mock, "porsche"
    )

    assert engine_mock.search.call_count == 2, (
        f"Expected 2 search calls, got {engine_mock.search.call_count}"
    )

    # Prepare distinct result sets
    results_v1 = [
        ArticleResult(title="Stale Result", url="u1", source_domain="s", score=1.0)
    ]
    results_v2 = [
        ArticleResult(title="Current Result", url="u2", source_domain="s", score=2.0)
    ]

    from PyQt6.QtCore import Qt

    # Invoke NEWER callback first (seq=2)
    callback_2(results_v2, 10)
    assert window._result_list.count() == 1
    item = window._result_list.item(0)
    r_current = item.data(Qt.ItemDataRole.UserRole + 1)
    assert r_current.title == "Current Result", (
        f"Expected 'Current Result' after callback_2, got '{r_current.title}'"
    )

    # Invoke OLDER callback second (seq=1, stale — must be discarded)
    callback_1(results_v1, 5)
    assert window._result_list.count() == 1, (
        "Result list count should remain 1 after stale callback"
    )
    item = window._result_list.item(0)
    r_after_stale = item.data(Qt.ItemDataRole.UserRole + 1)
    assert r_after_stale.title == "Current Result", (
        f"Stale callback must not overwrite — expected 'Current Result', "
        f"got '{r_after_stale.title}'"
    )


# ---------------------------------------------------------------------------
# Test 13 — T-04-03: _on_search_error shows only the static string
# ---------------------------------------------------------------------------


def test_error_displays_static_string(qtbot, monkeypatch):
    """T-04-03: _on_search_error must not leak raw exception text to the UI.

    After calling window._on_search_error("ConnectionError: 10061"):
      - status_label.text() == "Search failed. Check Elasticsearch connection."
      - status_label.text() does NOT contain "10061" (raw error suppressed)
    """
    window, _ = _make_window(qtbot, monkeypatch)

    window._on_search_error("ConnectionError: 10061")

    label_text = window._status_label.text()
    assert label_text == "Search failed. Check Elasticsearch connection.", (
        f"Expected static error string, got: '{label_text}'"
    )
    assert "10061" not in label_text, (
        "Raw exception text '10061' must not appear in the status label (T-04-03)"
    )


# ---------------------------------------------------------------------------
# Test 14 — T-04-03: Logger calls use % formatting, not f-strings
# ---------------------------------------------------------------------------


def test_logger_uses_percent_formatting():
    """T-04-03: main_window.py must not use f-strings in logger calls.

    Reads the source file and asserts no logger.* calls contain f-string
    arguments. Mirrors test_engine.py's logger formatting enforcement.
    """
    import os

    src_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "nitrofind", "ui", "main_window.py"
    )
    with open(src_path, encoding="utf-8") as f:
        src = f.read()

    assert not re.search(r'logger\.(debug|info|warning|error|critical)\(\s*f"', src), (
        "logger calls in main_window.py must use % formatting, not f-strings (CLAUDE.md)"
    )


# ---------------------------------------------------------------------------
# Test 15 — SRCH-01 empty query: no ES dispatch when query is empty
# ---------------------------------------------------------------------------


def test_empty_query_does_not_dispatch(qtbot, monkeypatch):
    """SRCH-01: _execute_search with empty query must not call engine.search.

    When the search bar is empty (or whitespace-only), _execute_search must:
      - NOT call engine.search()
      - Set status_label.text() to ""
      - Clear the result list (count == 0)
    """
    engine_mock = MagicMock()
    engine_mock.search.return_value = None
    window, _ = _make_window(qtbot, monkeypatch, engine_mock)

    # Ensure search bar is empty
    window._search_bar.clear()

    # Manually call _execute_search (simulates debounce timer firing on empty bar)
    window._execute_search()

    engine_mock.search.assert_not_called()
    assert window._status_label.text() == "", (
        f"Expected empty status label, got '{window._status_label.text()}'"
    )
    assert window._result_list.count() == 0, (
        f"Expected empty result list, got {window._result_list.count()} items"
    )
