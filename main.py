"""
main.py — NitroFind application entry point.

Wires all Phase 1 components together:
  1. Validates ES_HOME before any Qt object is created (INFRA-02 negative path, T-04-01)
  2. Creates QApplication and applies qt-material dark theme (UIPL-03)
  3. Constructs LoadingWindow and ESHealthWorker
  4. Connects all signals before worker.start() (Pitfall 4 — race condition prevention)
  5. On es_ready: calls ensure_index, shows MainWindow (INFRA-02, SCHEMA-01..04, W0-EXT-03)
  6. On es_failed: maps reason to Copywriting Contract error text and calls show_error (D-07)
  7. On Retry: shuts down stale worker, creates a fresh ESHealthWorker (D-07)
  8. On quit (aboutToQuit): calls worker.shutdown_es() to prevent orphan JVM (INFRA-03)

Execution sequence (PATTERNS.md Shared Patterns, Pitfall 4):
  validate_es_home() → QApplication → apply_stylesheet → LoadingWindow → ESHealthWorker
  → connect signals → show → worker.start() → app.exec()

Security mitigations:
  T-04-01: validate_es_home called BEFORE QApplication construction.
  T-04-03: on_es_failed maps raw reason to static strings; raw reason logged to stderr only.
"""

import logging
import sys
import os

from PyQt6.QtWidgets import QApplication
from elasticsearch import Elasticsearch
from qt_material import apply_stylesheet

from nitrofind.es_manager import ES_URL, ESHealthWorker, inject_es_config, resolve_es_home, validate_es_home
from nitrofind.es_schema import ensure_index
from nitrofind.ui.loading_window import LoadingWindow
from nitrofind.ui.main_window import MainWindow

# ---------------------------------------------------------------------------
# Module logger — raw reason strings (JVM output) go here, never to the UI label
# ---------------------------------------------------------------------------
logger = logging.getLogger("nitrofind.main")


def main() -> None:
    """NitroFind application entry point.

    Validates ES_HOME, builds the Qt application, wires all signals, and
    enters the Qt event loop. Uses a mutable state dict so nested handler
    functions can update the active worker reference across Retry cycles.
    """
    # ------------------------------------------------------------------
    # PKG-01: Guard sys.stdout/stderr against None in windowed frozen mode.
    # PyInstaller console=False sets these streams to None; logging.basicConfig
    # and sys.stderr.write both raise AttributeError if the stream is None.
    # This guard must come BEFORE logging.basicConfig and any sys.stderr write.
    # Source: PATTERNS.md "main.py insertion point 2"
    # ------------------------------------------------------------------
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    # ------------------------------------------------------------------
    # Step 1: Validate ES_HOME BEFORE constructing any Qt object.
    # A ValueError here exits with a stderr message and non-zero status.
    # No QApplication is created, so no UI window can flash (T-04-01).
    # ------------------------------------------------------------------
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    es_home_raw = resolve_es_home()  # PKG-01: frozen-mode resolves from sys.executable; dev-mode reads ES_HOME

    # ------------------------------------------------------------------
    # PKG-01: Inject NitroFind's config into the bundled ES directory BEFORE
    # validate_es_home and BEFORE ESHealthWorker.start(). Without injection,
    # ES 8.x boots with security-enabled defaults — TLS + auth — which causes
    # the cluster health probe to fail with SSL/auth errors (Pitfall 3).
    # In frozen mode, config_src resolves to sys._MEIPASS/config/;
    # in dev mode, to <repo>/config/ (os.path.dirname(__file__) relative).
    # ------------------------------------------------------------------
    if getattr(sys, "frozen", False):
        config_src = os.path.join(sys._MEIPASS, "config")  # type: ignore[attr-defined]
    else:
        config_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

    if es_home_raw:
        try:
            inject_es_config(es_home_raw, config_src)
        except OSError as exc:
            logger.warning("inject_es_config failed: %s", exc)
    try:
        es_home = validate_es_home(es_home_raw)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 2: Create QApplication.
    # ------------------------------------------------------------------
    app = QApplication(sys.argv)

    # ------------------------------------------------------------------
    # Step 3: Apply qt-material theme IMMEDIATELY after QApplication,
    # before any window is constructed (PATTERNS.md qt-material order,
    # UIPL-03). Calling this after a window exists leaves some widgets
    # using default Qt styling.
    # ------------------------------------------------------------------
    apply_stylesheet(app, theme="dark_teal.xml")

    # ------------------------------------------------------------------
    # Step 4: Construct LoadingWindow (displays immediately on show()).
    # ------------------------------------------------------------------
    loading_window = LoadingWindow()

    # ------------------------------------------------------------------
    # Mutable state dict — allows on_retry_clicked() to replace the
    # active worker reference without nonlocal (which requires Python 3.x
    # closure semantics but is fragile with reassignment). The dict acts
    # as a single mutable container that all closures share via reference.
    # ------------------------------------------------------------------
    state = {
        "worker": None,   # type: ESHealthWorker | None
        "main_window": None,  # type: MainWindow | None
    }

    # ------------------------------------------------------------------
    # Handler: ES started successfully (es_ready signal)
    # ------------------------------------------------------------------
    def on_es_ready() -> None:
        """Called in the GUI thread when ESHealthWorker emits es_ready.

        Creates an Elasticsearch client, calls ensure_index() to realize
        the SCHEMA-01..04 fields in a live index, then swaps LoadingWindow
        for MainWindow (W0-EXT-03).
        """
        try:
            client = Elasticsearch(ES_URL)  # WR-01: use shared ES_URL constant
            ensure_index(client)
        except Exception as exc:
            # CR-02: guard against TransportError, ConnectionError, mapping conflicts, etc.
            # Qt swallows unhandled exceptions from signal handlers — explicit handling
            # required so show_error() is reached and the UI does not freeze.
            logger.warning("ensure_index failed: %s", exc)
            loading_window.show_error(
                "Could not connect to Elasticsearch. Check that ES_HOME is set correctly and try again."
            )
            return

        main_window = MainWindow(client)
        main_window.show()
        # Keep a reference so the GC does not destroy it while the window is shown
        state["main_window"] = main_window

        loading_window.close()

    # ------------------------------------------------------------------
    # Handler: ES failed to become healthy (es_failed signal)
    # ------------------------------------------------------------------
    def on_es_failed(reason: str) -> None:
        """Called in the GUI thread when ESHealthWorker emits es_failed.

        Maps the worker reason string to one of the two static Copywriting
        Contract messages (UI-SPEC, T-04-03). Raw reason is logged to
        stderr only — never surfaced in the visible label.
        """
        # Log raw reason for developer diagnostics (stderr, not UI label)
        logger.warning("ESHealthWorker reported failure: %s", reason)
        sys.stderr.write(f"[nitrofind] ES failure reason: {reason}\n")

        # Map to Copywriting Contract error text (UI-SPEC Copywriting Contract)
        if "exited unexpectedly" in reason:
            error_text = (
                "Elasticsearch exited unexpectedly. Check your ES_HOME directory and try again."
            )
        else:
            error_text = (
                "Could not connect to Elasticsearch. Check that ES_HOME is set correctly and try again."
            )

        loading_window.show_error(error_text)

    # ------------------------------------------------------------------
    # Handler: Retry button clicked (retry_clicked signal from LoadingWindow)
    # ------------------------------------------------------------------
    def on_retry_clicked() -> None:
        """Terminate the stale ES process, create a fresh ESHealthWorker, restart.

        Sequence (D-07):
          1. If old worker still has a live process, call shutdown_es() then wait()
          2. Reset the loading window to the spinner state
          3. Build a new ESHealthWorker and reconnect signals (signals are per-instance)
          4. Update state["worker"] so shutdown_handler sees the current instance
          5. Start the new worker
        """
        old_worker: ESHealthWorker | None = state["worker"]
        if old_worker is not None:
            old_worker.shutdown_es()
            old_worker.wait()  # wait for QThread.run() to return before creating a new one

        # Return loading window to initial state (spinner visible, buttons hidden)
        loading_window.reset_to_loading()

        # Create a fresh worker and reconnect all signals (signals are per-instance;
        # connecting to old_worker's signals would do nothing for the new instance)
        new_worker = ESHealthWorker(es_home)
        new_worker.es_ready.connect(on_es_ready)
        new_worker.es_failed.connect(on_es_failed)
        # retry_clicked is still connected to on_retry_clicked from the original connection
        # below — that connection is still valid because loading_window.retry_clicked fires
        # and calls this same closure regardless of which worker instance is active.

        state["worker"] = new_worker
        new_worker.start()

    # ------------------------------------------------------------------
    # Handler: App is about to quit (QApplication.aboutToQuit signal)
    # Fires on window close, Cmd/Alt+Q, or app.quit() — all clean exits.
    # Does NOT fire on a Python segfault (residual orphan-JVM risk: T-04-02 accepted).
    # ------------------------------------------------------------------
    def shutdown_handler() -> None:
        """Gracefully terminate the ES subprocess before the process exits (INFRA-03).

        Uses state["worker"] so it always sees the most recently created worker
        instance — including after a Retry cycle replaced the original.
        """
        current_worker: ESHealthWorker | None = state["worker"]
        if current_worker is not None:
            current_worker.shutdown_es()   # idempotent — safe if already exited
            current_worker.wait()           # ensure QThread.run() returns before exit

    # ------------------------------------------------------------------
    # Step 5: Construct ESHealthWorker.
    # ------------------------------------------------------------------
    worker = ESHealthWorker(es_home)
    state["worker"] = worker

    # ------------------------------------------------------------------
    # Step 6: Connect ALL signals BEFORE worker.start() (Pitfall 4).
    # A signal emitted between start() and connect() would be lost in a
    # race condition; connecting first guarantees delivery.
    # ------------------------------------------------------------------
    worker.es_ready.connect(on_es_ready)
    worker.es_failed.connect(on_es_failed)
    loading_window.retry_clicked.connect(on_retry_clicked)
    app.aboutToQuit.connect(shutdown_handler)

    # ------------------------------------------------------------------
    # Step 7: Show the loading window, then start the worker thread.
    # ------------------------------------------------------------------
    loading_window.show()
    worker.start()

    # ------------------------------------------------------------------
    # Step 8: Enter the Qt event loop (blocks until app.quit() or last
    # window is closed). sys.exit propagates the return code to the OS.
    # ------------------------------------------------------------------
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
