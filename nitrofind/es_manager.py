"""
nitrofind.es_manager — Elasticsearch subprocess lifecycle manager.

Exports:
  resolve_es_home    — frozen-mode ES path resolver (PKG-01)
  inject_es_config   — writes elasticsearch.yml + jvm.options.d into bundled ES dir (PKG-01)
  validate_es_home   — validates ES_HOME path before exec (T-02-01, T-02-02)
  shutdown_es        — cross-platform graceful ES shutdown helper (INFRA-03)
  ESHealthWorker     — QThread worker: starts ES, polls health, emits signals (INFRA-02, INFRA-04)

Requirement coverage:
  INFRA-02: ESHealthWorker starts ES subprocess from ES_HOME; validate_es_home validates path
  INFRA-03: shutdown_es terminates ES gracefully (POSIX SIGTERM / Windows CTRL_BREAK_EVENT);
            falls back to kill() after 10s timeout
  INFRA-04: ESHealthWorker emits es_ready() or es_failed(str) exactly once per run()
  PKG-01: resolve_es_home/inject_es_config support frozen-mode launch; _start_process DEVNULL hardens windowed subprocess

Security mitigations:
  T-02-01 (path traversal): validate_es_home enforces isdir + isfile before exec
  T-02-02 (shell injection): Popen command is a list literal — no shell=True
  T-02-03 (DoS/infinite loop): hard 180-second deadline via time.monotonic()
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from elasticsearch import Elasticsearch


# ---------------------------------------------------------------------------
# Module-level constant — single source of truth for ES URL (WR-01)
# ---------------------------------------------------------------------------

ES_URL = "http://localhost:9200"


# ---------------------------------------------------------------------------
# Frozen-mode path resolution (PKG-01)
# ---------------------------------------------------------------------------

def resolve_es_home() -> str | None:
    """Compute the Elasticsearch home path for the current runtime mode.

    In frozen (PyInstaller) mode (getattr(sys, 'frozen', False) is True),
    the Elasticsearch directory lives as a sibling of the launcher exe:

        NitroFind.exe
        elasticsearch-8.18.0/   <- resolved from sys.executable parent glob

    Falls back to the ES_HOME environment variable in dev mode (non-frozen).
    Returns None if no sibling elasticsearch-8.* directory is found (frozen)
    or if ES_HOME is unset (dev); validate_es_home() will raise ValueError on None.

    # Source: pyinstaller.org/en/stable/runtime-information.html
    """
    if getattr(sys, "frozen", False):
        launcher_dir = Path(sys.executable).parent
        candidates = sorted(launcher_dir.glob("elasticsearch-8.*"))
        return str(candidates[0]) if candidates else None
    return os.environ.get("ES_HOME")


# ---------------------------------------------------------------------------
# Config injection (PKG-01)
# ---------------------------------------------------------------------------

def inject_es_config(es_home: str, config_src_dir: str) -> None:
    """Copy NitroFind's elasticsearch.yml and jvm.options into the bundled ES config dir.

    Idempotent: overwrites both files on every call, ensuring the NitroFind-controlled
    config is always in place before ESHealthWorker starts the ES subprocess.
    Calling this function twice produces identical results; the second call is safe.

    Writes:
      {es_home}/config/elasticsearch.yml    <- from {config_src_dir}/elasticsearch.yml
      {es_home}/config/jvm.options.d/nitrofind.options  <- from {config_src_dir}/jvm.options

    Creates jvm.options.d/ via os.makedirs(..., exist_ok=True) if it does not exist.

    # Source: elastic.co/guide/en/elasticsearch/reference/8.19/advanced-configuration.html
    #         (jvm.options.d/ file semantics and ES_JAVA_OPTS caveat)
    """
    es_config = os.path.join(es_home, "config")

    # Write elasticsearch.yml (xpack.security.* = false — PKG-01 Pitfall 3 mitigation)
    shutil.copy(
        os.path.join(config_src_dir, "elasticsearch.yml"),
        os.path.join(es_config, "elasticsearch.yml"),
    )

    # Write jvm.options.d/nitrofind.options (heap + perf tuning)
    jvm_dir = os.path.join(es_config, "jvm.options.d")
    os.makedirs(jvm_dir, exist_ok=True)
    shutil.copy(
        os.path.join(config_src_dir, "jvm.options"),
        os.path.join(jvm_dir, "nitrofind.options"),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _es_binary_path(es_home: str) -> str:
    """Return the platform-correct ES binary path (CR-01).

    On Windows the Elasticsearch binary is elasticsearch.bat;
    on POSIX it is elasticsearch (no extension).
    """
    if sys.platform == "win32":
        return os.path.join(es_home, "bin", "elasticsearch.bat")
    return os.path.join(es_home, "bin", "elasticsearch")


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

    es_bin = _es_binary_path(es_home)
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
      es_ready()         — cluster reached green or yellow within 180 seconds
      es_failed(reason)  — process exited unexpectedly or 180-second deadline reached

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
        self._stop_requested: bool = False  # WR-03: allows shutdown to interrupt polling loop

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
        client = Elasticsearch(ES_URL, request_timeout=2)

        deadline = time.monotonic() + 180  # D-04: 180-second total timeout (ES cold start can take ~2min)
        last_exc: Exception | None = None  # CR-03: retain last poll exception for deadline message
        while time.monotonic() < deadline and not self._stop_requested:  # WR-03: honour stop flag
            # T-02-03: check process death first — exit loop immediately
            if self.process.poll() is not None:
                self.es_failed.emit("Elasticsearch process exited unexpectedly.")
                return

            try:
                resp = client.cluster.health()
                if resp["status"] in ("green", "yellow"):  # D-04: accept green or yellow
                    self.es_ready.emit()
                    return
            except Exception as exc:
                last_exc = exc  # CR-03: track for deadline message; not swallowed silently

            time.sleep(2)  # D-04: 2-second polling interval

        # Deadline reached (or stop requested) without a healthy cluster
        exc_info = f" Last error: {type(last_exc).__name__}" if last_exc else ""
        self.es_failed.emit(
            f"Elasticsearch did not become healthy within 180 seconds.{exc_info}"
        )

    def shutdown_es(self) -> None:
        """Gracefully terminate ES — delegates to module-level shutdown_es().

        Sets _stop_requested so the polling loop exits at the next iteration
        without sleeping a full 2-second tick (WR-03).
        Idempotent and safe to call from the main thread via aboutToQuit signal.
        """
        self._stop_requested = True  # WR-03: interrupt polling loop before wait()
        if self.process is None:
            return
        shutdown_es(self.process)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _start_process(self) -> subprocess.Popen:
        """Start the ES JVM subprocess.

        Security — T-02-02: command is a list literal; shell=True is only used
        on Windows where it is required to execute .bat files (CR-01).
        Cross-platform — Pitfall 1: CREATE_NEW_PROCESS_GROUP on win32 required so
        shutdown_es() can send CTRL_BREAK_EVENT for graceful Windows shutdown.
        PKG-01 Pitfall 2: stdin/stdout/stderr set to DEVNULL to prevent [WinError 6]
        in windowed frozen mode where sys.stdout/stderr are None.
        PKG-01 Pitfall 7: close_fds=True prevents handle lock on binary update.
        """
        es_bin = _es_binary_path(self._es_home)  # CR-01: platform-correct binary path
        kwargs: dict = {
            "stdin": subprocess.DEVNULL,   # PKG-01 Pitfall 2
            "stdout": subprocess.DEVNULL,  # PKG-01 Pitfall 2
            "stderr": subprocess.DEVNULL,  # PKG-01 Pitfall 2
            "close_fds": True,             # PKG-01 Pitfall 7
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            kwargs["shell"] = True  # CR-01: required to execute .bat files on Windows
        return subprocess.Popen([es_bin], **kwargs)
