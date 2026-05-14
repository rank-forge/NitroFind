"""
Unit tests for nitrofind.scraper.state — D-06 resume coverage.

Test strategy:
  - Use sqlite3 in-memory DB (':memory:') to avoid file I/O
  - No mocks needed — sqlite3 is stdlib
  - tmp_path fixture (pytest builtin) for persistence test

Requirement coverage:
  D-06: is_visited returns False for unseen ID; True after mark_visited
  D-06: mark_visited with INSERT OR IGNORE is idempotent (safe to call twice)
  D-06: visited state persists across close/reopen of the same DB file
  T-02-05: path traversal guard rejects db_path with '..' component
  T-02-06: context manager closes connection on __exit__
"""

import sqlite3
import pytest
from nitrofind.scraper.state import SQLiteStateManager

# ---------------------------------------------------------------------------
# D-06: SQLite resume support
# ---------------------------------------------------------------------------


def test_is_visited_false_for_new_id():
    """D-06: is_visited returns False for an ID that has not been marked visited."""
    state = SQLiteStateManager(":memory:")
    assert state.is_visited("page_123") is False
    state.close()


def test_mark_visited_sets_true():
    """D-06: after mark_visited, is_visited returns True."""
    state = SQLiteStateManager(":memory:")
    state.mark_visited("page_123", "wikipedia")
    assert state.is_visited("page_123") is True
    state.close()


def test_mark_visited_idempotent():
    """D-06: mark_visited with INSERT OR IGNORE — calling twice does not raise."""
    state = SQLiteStateManager(":memory:")
    state.mark_visited("page_123", "wikipedia")
    state.mark_visited("page_123", "wikipedia")  # second call must not raise
    assert state.is_visited("page_123") is True
    state.close()


def test_visited_persists_across_close_reopen(tmp_path):
    """D-06: visited state persists when DB is closed and reopened from same path."""
    db_file = str(tmp_path / "state.db")
    state = SQLiteStateManager(db_file)
    state.mark_visited("wiki_page_456", "wikipedia")
    state.close()

    # Reopen the same file
    state2 = SQLiteStateManager(db_file)
    assert state2.is_visited("wiki_page_456") is True
    state2.close()


# ---------------------------------------------------------------------------
# T-02-06: context manager closes connection
# ---------------------------------------------------------------------------


def test_context_manager_closes_connection():
    """T-02-06: __exit__ closes the connection (sqlite3.ProgrammingError on subsequent use)."""
    with SQLiteStateManager(":memory:") as state:
        state.mark_visited("ctx_page", "wikipedia")
        assert state.is_visited("ctx_page") is True
    # After __exit__, connection should be closed
    try:
        state._conn.execute("SELECT 1")
        assert False, "Expected sqlite3.ProgrammingError — connection should be closed"
    except sqlite3.ProgrammingError:
        pass  # Expected: connection is closed


# ---------------------------------------------------------------------------
# T-02-05: path traversal guard
# ---------------------------------------------------------------------------


def test_db_path_traversal_rejected():
    """T-02-05: db_path containing '..' is rejected with ValueError."""
    with pytest.raises(ValueError, match="db_path must be inside project directory"):
        SQLiteStateManager("../etc/passwd")
