"""
Unit tests for nitrofind.es_manager.resolve_es_home — PKG-01 coverage.

Phase 6 (CLEN-01): The frozen-mode branch was removed from resolve_es_home().
resolve_es_home() now unconditionally returns os.environ.get("ES_HOME"),
regardless of sys.frozen. Frozen-mode tests are removed accordingly.

Requirement coverage:
  PKG-01: resolve_es_home() returns ES_HOME env var value when set
  PKG-01: resolve_es_home() returns None when ES_HOME is unset
"""

import sys

import pytest

from nitrofind.es_manager import resolve_es_home


def test_returns_env_var(monkeypatch):
    """resolve_es_home() returns ES_HOME env var value when set."""
    monkeypatch.setenv("ES_HOME", "/dev/es/home")

    result = resolve_es_home()

    assert result == "/dev/es/home"


def test_returns_none_when_env_unset(monkeypatch):
    """resolve_es_home() returns None when ES_HOME is not set."""
    monkeypatch.delenv("ES_HOME", raising=False)

    result = resolve_es_home()

    assert result is None
