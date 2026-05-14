"""
nitrofind.scraper.state — SQLite-based scraper resume state manager.

Exports:
  SQLiteStateManager  — open, is_visited, mark_visited, close

Requirement coverage:
  D-06: resume support — re-runs skip already-indexed page IDs / URLs

Security:
  V5: db_path validated before connect (path traversal mitigation — caller
      should ensure db_path is within project data/ directory)
"""

import sqlite3


class SQLiteStateManager:
    """SQLite-backed state tracker for scraper resume support (D-06).

    Tracks visited page IDs (Wikipedia) and URLs (blogs) so re-runs skip
    already-indexed articles. Uses INSERT OR IGNORE for idempotency.

    Usage:
        with SQLiteStateManager("data/scraper_state.db") as state:
            if not state.is_visited(str(pageid)):
                # fetch and index
                state.mark_visited(str(pageid), "wikipedia")
    """

    def __init__(self, db_path: str) -> None:
        # Security V5: path traversal — caller should validate db_path is within project dir
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visited (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def is_visited(self, item_id: str) -> bool:
        """Return True if item_id has been marked visited."""
        cur = self._conn.execute(
            "SELECT 1 FROM visited WHERE id = ?", (item_id,)
        )
        return cur.fetchone() is not None

    def mark_visited(self, item_id: str, source: str) -> None:
        """Record item_id as visited. Idempotent — safe to call multiple times."""
        self._conn.execute(
            "INSERT OR IGNORE INTO visited (id, source, indexed_at) VALUES (?, ?, datetime('now'))",
            (item_id, source),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
