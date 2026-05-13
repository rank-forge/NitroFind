"""
nitrofind.es_manager — Elasticsearch subprocess lifecycle manager.

Exports:
  validate_es_home   — validates ES_HOME path before exec (T-02-01, T-02-02)
  shutdown_es        — cross-platform graceful ES shutdown helper (INFRA-03)
  ESHealthWorker     — QThread worker: starts ES, polls health, emits signals (INFRA-02, INFRA-04)

Requirement coverage:
  INFRA-02: ESHealthWorker starts ES subprocess from ES_HOME; validate_es_home validates path
  INFRA-03: shutdown_es terminates ES gracefully (POSIX SIGTERM / Windows CTRL_BREAK_EVENT);
            falls back to kill() after 10s timeout
  INFRA-04: ESHealthWorker emits es_ready() or es_failed(str) exactly once per run()

Security mitigations:
  T-02-01 (path traversal): validate_es_home enforces isdir + isfile before exec
  T-02-02 (shell injection): Popen command is a list literal — no shell=True
  T-02-03 (DoS/infinite loop): hard 60-second deadline via time.monotonic()
"""

import os
import signal
import subprocess
import sys
import time

from PyQt6.QtCore import QThread, pyqtSignal
from elasticsearch import Elasticsearch


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_es_home(es_home: str | None) -> str:
    """Validate that es_home is a real directory containing an ES binary.

    Raises ValueError with D-02 messages on failure.
    Returns es_home unchanged on success.

    Security: T-02-01 — prevents arbitrary binary execution via malicious ES_HOME.
    """
    if not es_home:
        raise ValueError(
            "ES_HOME is not set. Set it to your Elasticsearch 8.18 directory."
        )
    if not os.path.isdir(es_home):
        raise ValueError(f"ES_HOME is not a directory: {es_home}")

    es_bin = os.path.join(es_home, "bin", "elasticsearch")
    if not os.path.isfile(es_bin):
        raise ValueError(f"Elasticsearch binary not found at: {es_bin}")

    return es_home


# ---------------------------------------------------------------------------
# Module-level shutdown helper (INFRA-03, Pattern 2, D-05, Pitfall 1)
# ---------------------------------------------------------------------------

def shutdown_es(process: subprocess.Popen) -> None:
    """Gracefully terminate the Elasticsearch subprocess.

    Cross-platform shutdown sequence (D-05):
      - POSIX: send SIGTERM via process.terminate()
      - Windows: send CTRL_BREAK_EVENT (requires CREATE_NEW_PROCESS_GROUP at Popen creation)
    Falls back to process.kill() if ES does not exit within 10 seconds (Pitfall 1 mitigation).

    Idempotent: returns immediately if process has already exited.
    """
    if process.poll() is not None:
        return  # already exited

    if sys.platform == "win32":
        # Pitfall 1: On Windows, terminate() calls TerminateProcess (forceful).
        # CTRL_BREAK_EVENT gives ES a chance to flush translog before dying.
        # Requires CREATE_NEW_PROCESS_GROUP at Popen creation time.
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


# ---------------------------------------------------------------------------
# ESHealthWorker QThread (INFRA-02, INFRA-04, Pattern 1, Pattern 4)
# ---------------------------------------------------------------------------

class ESHealthWorker(QThread):
    """QThread worker that starts Elasticsearch and polls cluster health.

    Emits exactly one signal per run() invocation:
      es_ready()         — cluster reached green or yellow within 60 seconds
      es_failed(reason)  — process exited unexpectedly or 60-second deadline reached

    Usage (main.py — Pattern 1, Pitfall 4):
        worker = ESHealthWorker(es_home)
        worker.es_ready.connect(on_es_ready)      # connect BEFORE start()
        worker.es_failed.connect(on_es_failed)
        worker.start()
    """

    es_ready = pyqtSignal()       # zero-arg — D-03, D-04
    es_failed = pyqtSignal(str)   # reason string — D-04

    def __init__(self, es_home: str) -> None:
        super().__init__()
        self._es_home = es_home
        self.process: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start ES subprocess and poll cluster health.

        Blocking — designed to run in a QThread (call via start(), not run()
        directly, in production). In unit tests call run() synchronously with
        mocked subprocess.Popen and Elasticsearch client.

        Emits exactly one signal: es_ready or es_failed.
        """
        self.process = self._start_process()
        client = Elasticsearch("http://localhost:9200", request_timeout=2)

        deadline = time.monotonic() + 60  # D-04: 60-second total timeout
        while time.monotonic() < deadline:
            # T-02-03: check process death first — exit loop immediately
            if self.process.poll() is not None:
                self.es_failed.emit("Elasticsearch process exited unexpectedly.")
                return

            try:
                resp = client.cluster.health()
                if resp["status"] in ("green", "yellow"):  # D-04: accept green or yellow
                    self.es_ready.emit()
                    return
            except Exception:
                pass  # ES not yet accepting connections — continue polling

            time.sleep(2)  # D-04: 2-second polling interval

        # Deadline reached without a healthy cluster
        self.es_failed.emit("Elasticsearch did not become healthy within 60 seconds.")

    def shutdown_es(self) -> None:
        """Gracefully terminate ES — delegates to module-level shutdown_es().

        Idempotent and safe to call from the main thread via aboutToQuit signal.
        """
        if self.process is None:
            return
        shutdown_es(self.process)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _start_process(self) -> subprocess.Popen:
        """Start the ES JVM subprocess.

        Security — T-02-02: command is a list literal; shell=True is never used.
        Cross-platform — Pitfall 1: CREATE_NEW_PROCESS_GROUP on win32 required so
        shutdown_es() can send CTRL_BREAK_EVENT for graceful Windows shutdown.
        """
        es_bin = os.path.join(self._es_home, "bin", "elasticsearch")
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        return subprocess.Popen([es_bin], **kwargs)
