"""
LoadingWindow — frameless startup window shown while Elasticsearch warms up.

Design decisions:
- D-06: Uses QWidget (NOT QSplashScreen). QSplashScreen forces always-on-top
  behavior with platform-specific quirks; a FramelessWindowHint QWidget gives
  full control over layout, signals, and state machine.
- D-07: Error state shows Retry and Quit buttons; loading state shows spinner.

Copywriting Contract (verbatim strings required by UI-SPEC):
  App title:                "NitroFind"
  Loading status text:      "Starting search engine..."
  Error message (timeout):  "Could not connect to Elasticsearch. Check that
                             ES_HOME is set correctly and try again."
  Error message (crash):    "Elasticsearch exited unexpectedly. Check your
                             ES_HOME directory and try again."
  Retry button label:       "Retry"
  Quit button label:        "Quit"
"""

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


class LoadingWindow(QWidget):
    """
    Frameless 360x240 loading window with two states (UI-SPEC State Machine):

    State 1 — Loading (initial):
        Spinner visible + animating, status text "Starting search engine...",
        Retry and Quit buttons hidden.

    State 2 — Error (on ES failure):
        Spinner hidden, status text set to the reason, Retry and Quit visible.

    Signals:
        retry_clicked: emitted when Retry button is clicked. Plan 04 (main.py)
            connects this signal to the worker restart logic.
    """

    retry_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("loadingWindow")

        # --- Window flags and size ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(360, 240)

        # --- Center on primary screen ---
        # IN-02: guard against primaryScreen() returning None in headless/CI environments
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.move(screen.geometry().center() - self.rect().center())

        # --- Build child widgets ---
        self._title_label = QLabel("NitroFind")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet("font-size: 20pt; font-weight: 600;")

        self._spinner = SpinnerWidget()

        self._status_label = QLabel("Starting search engine...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("font-size: 11pt; font-weight: 400;")

        self._retry_button = QPushButton("Retry")
        self._retry_button.setObjectName("retryButton")
        self._retry_button.setVisible(False)

        self._quit_button = QPushButton("Quit")
        self._quit_button.setObjectName("quitButton")
        self._quit_button.setVisible(False)

        # --- Button row layout ---
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._retry_button)
        button_row.addSpacing(8)
        button_row.addWidget(self._quit_button)
        button_row.addStretch(1)

        # --- Main layout ---
        # Spacing tokens (UI-SPEC):
        #   xl = 32px  (top/bottom margin)
        #   2xl = 48px (side margin)
        #   lg = 24px  (title → spinner gap)
        #   sm = 8px   (spinner → status gap, base setSpacing)
        #   md = 16px  (button row top margin)
        layout = QVBoxLayout()
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(8)

        layout.addWidget(self._title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(24)  # lg: title → spinner
        layout.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        # 8px between spinner and status_label already covered by setSpacing(8)
        layout.addWidget(self._status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(16)  # md: status_label → button row
        layout.addLayout(button_row)

        self.setLayout(layout)

        # --- Stylesheet ---
        # Background applied via objectName so it targets only this window.
        # Button QSS applied here; main.py applies qt-material globally first.
        self.setStyleSheet("""
            QWidget#loadingWindow { background-color: #1e1e2e; }
            QPushButton#retryButton {
                background-color: #26a69a;
                color: #ffffff;
                border-radius: 4px;
                padding: 8px 24px;
                font-size: 10pt;
                font-weight: 600;
            }
            QPushButton#retryButton:hover {
                background-color: #2bbbad;
            }
            QPushButton#quitButton {
                background-color: transparent;
                color: #ef5350;
                border: 1px solid #ef5350;
                border-radius: 4px;
                padding: 8px 24px;
                font-size: 10pt;
                font-weight: 600;
            }
            QPushButton#quitButton:hover {
                background-color: rgba(239, 83, 80, 0.1);
            }
        """)

        # --- Signal wiring ---
        # retry_clicked signal consumed by main.py (Plan 04) for worker restart.
        self._retry_button.clicked.connect(self.retry_clicked.emit)
        # Quit exits the application directly — no confirmation dialog per
        # Copywriting Contract (startup-failure exit, not a data-destructive action).
        self._quit_button.clicked.connect(QApplication.instance().quit)

    # --- Public accessors (referenced by tests via attribute names) ---

    @property
    def spinner(self) -> SpinnerWidget:
        return self._spinner

    @property
    def status_label(self) -> QLabel:
        return self._status_label

    @property
    def retry_button(self) -> QPushButton:
        return self._retry_button

    @property
    def quit_button(self) -> QPushButton:
        return self._quit_button

    # --- State machine ---

    def show_error(self, reason: str) -> None:
        """
        Transition to State 2 (Error, D-07).

        Hides the spinner, sets the status label to the provided reason,
        and reveals the Retry and Quit buttons.

        Args:
            reason: The human-readable error message to display.
                    Plan 04 maps worker es_failed reasons to the two static
                    strings from the Copywriting Contract:
                    - "Could not connect to Elasticsearch. Check that
                       ES_HOME is set correctly and try again."
                    - "Elasticsearch exited unexpectedly. Check your
                       ES_HOME directory and try again."
                    Raw JVM stack traces must NOT be passed here; log those
                    to stderr in the worker (UI-SPEC Copywriting rules).
        """
        self._spinner.hide()
        self._status_label.setText(reason)
        self._retry_button.setVisible(True)
        self._quit_button.setVisible(True)

    def reset_to_loading(self) -> None:
        """
        Transition back to State 1 (Loading).

        Called by main.py when the Retry button fires: after terminating the
        stale ES process and restarting the worker thread, main.py calls this
        to restore the loading state so the user sees the spinner again.
        """
        self._spinner.show()
        self._status_label.setText("Starting search engine...")
        self._retry_button.setVisible(False)
        self._quit_button.setVisible(False)
