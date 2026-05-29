"""
Unit tests for nitrofind.es_manager.resolve_es_home — PKG-01 coverage.

Test strategy:
  - Use tmp_path to create a fake launcher directory with sibling ES directory
  - Use monkeypatch to patch sys.frozen and sys.executable for frozen-mode simulation
  - Use monkeypatch.setenv / monkeypatch.delenv to control ES_HOME env var
  - No live ES or subprocess required

Requirement coverage:
  PKG-01: resolve_es_home() returns sibling elasticsearch-8.* path in frozen mode
  PKG-01: resolve_es_home() returns None in frozen mode when no sibling es dir exists
  PKG-01: resolve_es_home() returns ES_HOME env var value in dev mode
  PKG-01: resolve_es_home() returns None in dev mode when ES_HOME is unset
"""

import sys
from pathlib import Path

import pytest

from nitrofind.es_manager import resolve_es_home


# ---------------------------------------------------------------------------
# Dev mode tests
# ---------------------------------------------------------------------------

def test_dev_mode_returns_env_var(monkeypatch):
    """resolve_es_home() returns ES_HOME env var value in dev mode (no sys.frozen)."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("ES_HOME", "/dev/es/home")

    result = resolve_es_home()

    assert result == "/dev/es/home"


def test_dev_mode_returns_none_when_env_unset(monkeypatch):
    """resolve_es_home() returns None in dev mode when ES_HOME is not set."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("ES_HOME", raising=False)

    result = resolve_es_home()

    assert result is None


# ---------------------------------------------------------------------------
# Frozen mode tests
# ---------------------------------------------------------------------------

def test_frozen_mode_finds_sibling_es_dir(tmp_path, monkeypatch):
    """resolve_es_home() returns sibling elasticsearch-8.* directory path in frozen mode."""
    # Create fake launcher and sibling ES directory
    fake_exe = tmp_path / "NitroFind.exe"
    fake_exe.touch()
    es_dir = tmp_path / "elasticsearch-8.18.0"
    es_dir.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    result = resolve_es_home()

    assert result == str(es_dir)


def test_frozen_mode_returns_none_when_no_sibling(tmp_path, monkeypatch):
    """resolve_es_home() returns None in frozen mode when no sibling elasticsearch-8.* dir exists."""
    # Only the launcher, no ES sibling directory
    fake_exe = tmp_path / "NitroFind.exe"
    fake_exe.touch()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    result = resolve_es_home()

    assert result is None
