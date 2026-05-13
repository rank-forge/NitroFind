"""
tests/test_loading_window.py — INFRA-04 UI state-machine tests.

Tests the LoadingWindow state machine:
  - State 1 (loading): spinner visible, buttons hidden, correct status text
  - State 2 (error): spinner hidden, buttons visible, status text = reason
  - Retry button emits retry_clicked signal
  - reset_to_loading() restores State 1

These tests verify only state-machine correctness (widget visibility, text,
signal emission). Visual/animated behavior (spinner rotation, typography
rendering) is covered by the manual checkpoint in Plan 04.

Uses pytest-qt's qtbot fixture for widget lifecycle management and signal
assertion. Each test calls qtbot.addWidget(window) so pytest-qt cleans up
the widget after the test without leaking Qt resources.
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


def test_initial_state_is_loading(qtbot):
    """
    INFRA-04: LoadingWindow construction yields State 1 (loading).

    Spinner must be visible, buttons must be hidden, and status text
    must read exactly "Starting search engine..." (Copywriting Contract).
    """
    from nitrofind.ui.loading_window import LoadingWindow

    window = LoadingWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.spinner.isVisible() is True, "Spinner should be visible in loading state"
    assert window.retry_button.isVisible() is False, "Retry button should be hidden in loading state"
    assert window.quit_button.isVisible() is False, "Quit button should be hidden in loading state"
    assert window.status_label.text() == "Starting search engine...", (
        f"Expected 'Starting search engine...', got '{window.status_label.text()}'"
    )


def test_show_error_transitions_to_error_state(qtbot):
    """
    INFRA-04: show_error(reason) transitions LoadingWindow to State 2 (error, D-07).

    Spinner must be hidden, buttons visible, and status label updated to the
    provided reason string.
    """
    from nitrofind.ui.loading_window import LoadingWindow

    window = LoadingWindow()
    qtbot.addWidget(window)
    window.show()

    window.show_error("Test failure reason")

    assert window.spinner.isVisible() is False, "Spinner should be hidden in error state"
    assert window.retry_button.isVisible() is True, "Retry button should be visible in error state"
    assert window.quit_button.isVisible() is True, "Quit button should be visible in error state"
    assert window.status_label.text() == "Test failure reason", (
        f"Expected 'Test failure reason', got '{window.status_label.text()}'"
    )


def test_retry_button_emits_signal(qtbot):
    """
    INFRA-04: Clicking Retry emits the retry_clicked signal.

    The signal is consumed by main.py (Plan 04) to restart the ES worker.
    This test verifies the signal fires correctly from a simulated click.
    """
    from PyQt6.QtCore import Qt
    from nitrofind.ui.loading_window import LoadingWindow

    window = LoadingWindow()
    qtbot.addWidget(window)
    window.show()

    # Transition to error state so the Retry button becomes visible and clickable
    window.show_error("x")

    with qtbot.waitSignal(window.retry_clicked, timeout=1000):
        qtbot.mouseClick(window.retry_button, Qt.MouseButton.LeftButton)


def test_reset_to_loading_restores_state(qtbot):
    """
    INFRA-04: reset_to_loading() restores State 1 from State 2.

    After show_error(), calling reset_to_loading() must restore the spinner,
    reset the status text to "Starting search engine...", and re-hide the buttons.
    This is called by main.py when the user clicks Retry and the worker restarts.
    """
    from nitrofind.ui.loading_window import LoadingWindow

    window = LoadingWindow()
    qtbot.addWidget(window)
    window.show()

    # Drive to error state first
    window.show_error("Elasticsearch exited unexpectedly. Check your ES_HOME directory and try again.")

    # Restore loading state
    window.reset_to_loading()

    assert window.spinner.isVisible() is True, "Spinner should be visible after reset_to_loading()"
    assert window.retry_button.isVisible() is False, "Retry button should be hidden after reset_to_loading()"
    assert window.quit_button.isVisible() is False, "Quit button should be hidden after reset_to_loading()"
    assert window.status_label.text() == "Starting search engine...", (
        f"Expected 'Starting search engine...', got '{window.status_label.text()}'"
    )
