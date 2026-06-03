"""
Unit tests for nitrofind.es_manager — INFRA-02, INFRA-03 coverage.

Test strategy:
  - Call shutdown_es() directly — no QThread, no Qt event loop
  - Patch subprocess.Popen where needed
  - No live ES or Qt required

Requirement coverage:
  INFRA-02: validate_es_home validates ES_HOME path
  INFRA-03: shutdown_es terminates ES gracefully (POSIX SIGTERM); falls back to
            kill() after 10s timeout
"""

import subprocess
from unittest.mock import MagicMock, call

import pytest

from nitrofind.es_manager import shutdown_es, validate_es_home


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
# INFRA-03: graceful shutdown (Linux/WSL only — Windows branch removed)
# ---------------------------------------------------------------------------

def test_shutdown_graceful():
    """shutdown_es sends SIGTERM then waits (Linux/WSL only)."""
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # process is alive

    shutdown_es(mock_process)

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
