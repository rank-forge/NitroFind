"""
Unit tests for nitrofind.es_manager — INFRA-02, INFRA-03, INFRA-04 coverage.

Test strategy:
  - Call worker.run() directly (synchronously) — never worker.start()
  - Patch subprocess.Popen and nitrofind.es_manager.Elasticsearch
  - No live ES or Qt event loop required

Requirement coverage:
  INFRA-02: ESHealthWorker starts ES subprocess; validate_es_home validates ES_HOME
  INFRA-03: shutdown_es graceful termination + kill fallback
  INFRA-04: ESHealthWorker emits es_ready on healthy / es_failed on process death
"""

import os
import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch, call

import pytest

from nitrofind.es_manager import ESHealthWorker, shutdown_es, validate_es_home


# ---------------------------------------------------------------------------
# INFRA-02: ES_HOME validation
# ---------------------------------------------------------------------------

def test_missing_es_home():
    """validate_es_home(None) and validate_es_home('') both raise ValueError
    with a message starting with 'ES_HOME is not set'.

    WR-05: monkeypatch.delenv removed — validate_es_home() receives es_home as
    a direct argument and does not read from os.environ internally. The env
    manipulation was dead code that implied incorrect test semantics.
    """
    with pytest.raises(ValueError, match="ES_HOME is not set"):
        validate_es_home(None)

    with pytest.raises(ValueError, match="ES_HOME is not set"):
        validate_es_home("")


# ---------------------------------------------------------------------------
# INFRA-03: graceful shutdown
# ---------------------------------------------------------------------------

def test_shutdown_graceful():
    """shutdown_es calls terminate (POSIX) or send_signal(CTRL_BREAK_EVENT) (win32),
    then wait(timeout=10). Assert the correct branch for the current platform."""
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # process is alive

    shutdown_es(mock_process)

    if sys.platform == "win32":
        mock_process.send_signal.assert_called_once_with(signal.CTRL_BREAK_EVENT)
        mock_process.terminate.assert_not_called()
    else:
        mock_process.terminate.assert_called_once()
        mock_process.send_signal.assert_not_called()

    mock_process.wait.assert_called_once_with(timeout=10)


def test_shutdown_kills_on_timeout():
    """If wait raises TimeoutExpired, shutdown_es falls back to kill() then wait()."""
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # alive
    mock_process.wait.side_effect = [
        subprocess.TimeoutExpired(cmd="elasticsearch", timeout=10),
        None,  # second wait() after kill() succeeds
    ]

    shutdown_es(mock_process)

    mock_process.kill.assert_called_once()
    # wait called twice: first with timeout=10, second bare wait()
    assert mock_process.wait.call_count == 2


# ---------------------------------------------------------------------------
# INFRA-04: ESHealthWorker signal emission
# ---------------------------------------------------------------------------

def test_worker_emits_ready():
    """ESHealthWorker.run() emits es_ready when cluster.health() returns yellow."""
    ready_calls = []
    failed_calls = []

    mock_process = MagicMock()
    mock_process.poll.return_value = None  # process alive

    mock_health_resp = {"status": "yellow"}
    mock_client = MagicMock()
    mock_client.cluster.health.return_value = mock_health_resp

    with patch("nitrofind.es_manager.subprocess.Popen", return_value=mock_process), \
         patch("nitrofind.es_manager.Elasticsearch", return_value=mock_client):

        worker = ESHealthWorker("/fake/es_home")
        worker.es_ready.connect(lambda: ready_calls.append(True))
        worker.es_failed.connect(lambda reason: failed_calls.append(reason))

        worker.run()

    assert len(ready_calls) == 1, f"Expected 1 es_ready emission, got {len(ready_calls)}"
    assert len(failed_calls) == 0, f"Expected no es_failed, got {failed_calls}"


def test_worker_emits_failed():
    """ESHealthWorker.run() emits es_failed when process.poll() returns non-None."""
    ready_calls = []
    failed_calls = []

    mock_process = MagicMock()
    mock_process.poll.return_value = 1  # process exited (non-zero)

    mock_client = MagicMock()

    with patch("nitrofind.es_manager.subprocess.Popen", return_value=mock_process), \
         patch("nitrofind.es_manager.Elasticsearch", return_value=mock_client):

        worker = ESHealthWorker("/fake/es_home")
        worker.es_ready.connect(lambda: ready_calls.append(True))
        worker.es_failed.connect(lambda reason: failed_calls.append(reason))

        worker.run()

    assert len(ready_calls) == 0, f"Expected no es_ready, got {ready_calls}"
    assert len(failed_calls) == 1, f"Expected 1 es_failed emission, got {len(failed_calls)}"
    assert "exited unexpectedly" in failed_calls[0], \
        f"Expected 'exited unexpectedly' in message, got: {failed_calls[0]!r}"
