"""
Unit tests for nitrofind.scraper.blogs — SCRP-02 coverage.

Test strategy:
  - Mock requests.Session.get with unittest.mock
  - No live network access required

Requirement coverage:
  SCRP-02: blog fetcher returns None gracefully on HTTP 403 (Pitfall 3)
  SCRP-02: blog fetcher returns None when article container not found (Pitfall 4)
  SCRP-02: extract_plain_text returns no HTML tags in output (L-05)

Anti-patterns avoided:
  Pitfall 3: 403 → graceful skip + log (no browser impersonation)
  Pitfall 4: selectors come from config, not hardcoded
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# SCRP-02: Blog scraping
# ---------------------------------------------------------------------------


def test_fetch_article_returns_none_on_403():
    """SCRP-02, Pitfall 3: HTTP 403 is logged as warning and returns None (not raised)."""
    pytest.importorskip("nitrofind.scraper.blogs", reason="Wave 1 — BlogScraper not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_fetch_article_returns_none_on_missing_container():
    """SCRP-02, Pitfall 4: returns None when article_selector finds no container."""
    pytest.importorskip("nitrofind.scraper.blogs", reason="Wave 1 — BlogScraper not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_extract_plain_text_removes_html_tags():
    """SCRP-02, L-05: extracted body text contains no HTML tags (no < or > characters)."""
    pytest.importorskip("nitrofind.scraper.blogs", reason="Wave 1 — BlogScraper not yet implemented")
    pytest.skip("Wave 1 implementation")
