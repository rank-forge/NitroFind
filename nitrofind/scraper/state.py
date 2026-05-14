"""
nitrofind.scraper.state — SQLite-based scraper resume state manager.

Exports:
  SQLiteStateManager  — open, is_visited, mark_visited, close, context manager

Requirement coverage:
  D-06: resume support — re-runs skip already-indexed page IDs / URLs via
        is_visited() check before fetching; mark_visited() records completion.

Security mitigations:
  T-02-05 (path traversal): db_path validated against project cwd before connect.
        The ':memory:' literal is allowed for in-process tests without file I/O.
        Any other path must resolve within Path.cwd() to prevent escape.
  T-02-06 (SQL injection): all SQL uses '?' parameterized placeholders exclusively.
        No f-string SQL interpolation appears anywhere in this module.
"""

import os
import sqlite3
from pathlib import Path


class SQLiteStateManager:
    """SQLite-backed state tracker for the NitroFind scraper.

    Tracks which page IDs / URLs have been indexed so re-runs skip already-visited
    items (D-06 resume support).

    Usage:
        with SQLiteStateManager("data/scraper_state.db") as state:
            if not state.is_visited(page_id):
                # fetch and index
                state.mark_visited(page_id, "wikipedia")

    Security: db_path must resolve within the current working directory to prevent
    path traversal attacks (T-02-05). Use ':memory:' for in-process tests.
    """

    def __init__(self, db_path: str) -> None:
        """Open (or create) the SQLite state database.

        Args:
            db_path: File path to the SQLite database, or ':memory:' for in-memory.

        Raises:
            ValueError: If db_path resolves outside the project working directory
                        (T-02-05 path traversal guard).
        """
        # T-02-05: path traversal guard — reject paths outside project cwd.
        # The ':memory:' special sqlite3 literal is exempted for tests.
        if db_path != ":memory:":
            resolved = Path(db_path).resolve()
            cwd_resolved = Path.cwd().resolve()
            if resolved != cwd_resolved and not str(resolved).startswith(str(cwd_resolved) + os.sep):
                raise ValueError(
                    f"db_path must be inside project directory: {db_path}"
                )

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
        """Return True if item_id has been marked visited; False otherwise.

        Args:
            item_id: The page ID (Wikipedia str(pageid)) or URL slug (blog).
        """
        cur = self._conn.execute(
            "SELECT 1 FROM visited WHERE id = ?", (item_id,)
        )
        return cur.fetchone() is not None

    def mark_visited(self, item_id: str, source: str) -> None:
        """Record item_id as visited.

        INSERT OR IGNORE ensures calling twice with the same id is a no-op
        (idempotent — safe for retry loops, D-06).

        Args:
            item_id: The page ID or URL slug.
            source:  Source label, e.g. 'wikipedia' or 'hagerty'.
        """
        self._conn.execute(
            "INSERT OR IGNORE INTO visited (id, source, indexed_at) VALUES (?, ?, datetime('now'))",
            (item_id, source),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __enter__(self):
        """Support use as a context manager — returns self."""
        return self

    def __exit__(self, *args):
        """Close the connection on context manager exit."""
        self.close()
