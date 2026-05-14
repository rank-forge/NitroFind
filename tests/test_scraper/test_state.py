"""
Unit tests for nitrofind.scraper.state — D-06 resume coverage.

Test strategy:
  - Use sqlite3 in-memory DB (':memory:') to avoid file I/O
  - No mocks needed — sqlite3 is stdlib

Requirement coverage:
  D-06: is_visited returns False for unseen ID; True after mark_visited
  D-06: mark_visited with INSERT OR IGNORE is idempotent (safe to call twice)
  D-06: visited state persists across close/reopen of the same DB file
"""

import pytest

# ---------------------------------------------------------------------------
# D-06: SQLite resume support
# ---------------------------------------------------------------------------


def test_is_visited_false_for_new_id():
    """D-06: is_visited returns False for an ID that has not been marked visited."""
    pytest.importorskip("nitrofind.scraper.state", reason="Wave 1 — SQLiteStateManager not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_mark_visited_idempotent():
    """D-06: mark_visited with INSERT OR IGNORE — calling twice does not raise."""
    pytest.importorskip("nitrofind.scraper.state", reason="Wave 1 — SQLiteStateManager not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_visited_persists_across_close_reopen():
    """D-06: visited state persists when DB is closed and reopened from same path."""
    pytest.importorskip("nitrofind.scraper.state", reason="Wave 1 — SQLiteStateManager not yet implemented")
    pytest.skip("Wave 1 implementation")
