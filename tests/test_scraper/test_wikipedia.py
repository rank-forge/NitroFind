"""
Unit tests for nitrofind.scraper.wikipedia — SCRP-01 coverage.

Test strategy:
  - Instantiate WikipediaScraper with mocked MediaWikiAPI and SQLiteStateManager
  - Use unittest.mock.patch and MagicMock for all external calls
  - No live Wikipedia API or Qt event loop required

Requirement coverage:
  SCRP-01: walk_category returns page IDs from mocked category response
  SCRP-01: fetch_and_filter returns None for page with empty infobox (Pitfall 2)
  SCRP-01: fetch_and_filter returns correct document dict for page with infobox

Anti-patterns avoided:
  Pitfall 1: uses pageid not title to avoid redirect aliasing
  Pitfall 2: infobox empty-dict check (falsy, not is None)
  Pitfall 6: visited_categories set prevents cyclic category recursion
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# SCRP-01: Wikipedia scraping
# ---------------------------------------------------------------------------


def test_walk_category_returns_pageids():
    """SCRP-01: walk_category returns list of integer page IDs from category."""
    pytest.importorskip("nitrofind.scraper.wikipedia", reason="Wave 1 — WikipediaScraper not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_fetch_and_filter_skips_empty_infobox():
    """SCRP-01: fetch_and_filter returns None when page.infobox == {} (D-02, Pitfall 2)."""
    pytest.importorskip("nitrofind.scraper.wikipedia", reason="Wave 1 — WikipediaScraper not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_fetch_and_filter_returns_doc_with_infobox():
    """SCRP-01: fetch_and_filter returns document dict when infobox is populated."""
    pytest.importorskip("nitrofind.scraper.wikipedia", reason="Wave 1 — WikipediaScraper not yet implemented")
    pytest.skip("Wave 1 implementation")
