"""
Unit tests for ESHealthWorker._start_process DEVNULL + close_fds kwargs — PKG-01 coverage.

Test strategy:
  - Pre-create fake ES binary files in tmp_path so _es_binary_path lookup passes
  - Patch nitrofind.es_manager.subprocess.Popen to intercept the Popen call
  - Call worker._start_process() directly (not worker.run()) to isolate subprocess kwargs
  - Assert DEVNULL on all three std handles and close_fds=True (PKG-01 Pitfall 2 + 7)
  - Assert platform-conditional kwargs via monkeypatching sys.platform

Requirement coverage:
  PKG-01 Pitfall 2: DEVNULL redirects prevent [WinError 6] in windowed frozen mode
  PKG-01 Pitfall 7: close_fds=True prevents handle lock on binary update
"""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from nitrofind.es_manager import ESHealthWorker


# ---------------------------------------------------------------------------
# DEVNULL + close_fds contract
# ---------------------------------------------------------------------------

def test_start_process_uses_devnull_handles(tmp_path):
    """PKG-01 Pitfall 2: _start_process passes DEVNULL for all std handles and close_fds=True."""
    # Pre-create fake ES binary files for both platforms
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "elasticsearch").touch()
    (bin_dir / "elasticsearch.bat").touch()

    with patch("nitrofind.es_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        worker = ESHealthWorker(str(tmp_path))
        worker._start_process()

    call_kwargs = mock_popen.call_args[1]
    assert call_kwargs.get("stdin") == subprocess.DEVNULL, \
        "stdin must be subprocess.DEVNULL (PKG-01 Pitfall 2)"
    assert call_kwargs.get("stdout") == subprocess.DEVNULL, \
        "stdout must be subprocess.DEVNULL (PKG-01 Pitfall 2)"
    assert call_kwargs.get("stderr") == subprocess.DEVNULL, \
        "stderr must be subprocess.DEVNULL (PKG-01 Pitfall 2)"
    assert call_kwargs.get("close_fds") is True, \
        "close_fds must be True (PKG-01 Pitfall 7)"


# ---------------------------------------------------------------------------
# Platform branch tests
# ---------------------------------------------------------------------------

def test_start_process_win32_branch(tmp_path, monkeypatch):
    """PKG-01: win32 branch sets creationflags=CREATE_NEW_PROCESS_GROUP and shell=True.

    CREATE_NEW_PROCESS_GROUP only exists on Windows; use a sentinel int on POSIX hosts
    so the test can run cross-platform.  The value 512 matches the Windows constant.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "elasticsearch").touch()
    (bin_dir / "elasticsearch.bat").touch()

    monkeypatch.setattr(sys, "platform", "win32")
    # CREATE_NEW_PROCESS_GROUP is Windows-only; provide a sentinel so the
    # attribute lookup inside _start_process doesn't fail on Linux hosts.
    CREATE_NEW_PROCESS_GROUP_VALUE = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 512)
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", CREATE_NEW_PROCESS_GROUP_VALUE, raising=False)

    with patch("nitrofind.es_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        worker = ESHealthWorker(str(tmp_path))
        worker._start_process()

    call_kwargs = mock_popen.call_args[1]
    assert call_kwargs.get("creationflags") == CREATE_NEW_PROCESS_GROUP_VALUE, \
        "win32 branch must set creationflags=CREATE_NEW_PROCESS_GROUP"
    assert call_kwargs.get("shell") is True, \
        "win32 branch must set shell=True (required for .bat execution)"


def test_start_process_posix_branch(tmp_path, monkeypatch):
    """PKG-01: POSIX branch does not set creationflags or shell kwargs."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "elasticsearch").touch()
    (bin_dir / "elasticsearch.bat").touch()

    monkeypatch.setattr(sys, "platform", "linux")

    with patch("nitrofind.es_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        worker = ESHealthWorker(str(tmp_path))
        worker._start_process()

    call_kwargs = mock_popen.call_args[1]
    assert "creationflags" not in call_kwargs, \
        "POSIX branch must not set creationflags"
    assert "shell" not in call_kwargs, \
        "POSIX branch must not set shell"
