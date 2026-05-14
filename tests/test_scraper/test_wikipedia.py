"""
Unit tests for nitrofind.scraper.wikipedia — SCRP-01 coverage.

Test strategy:
  - Instantiate WikipediaScraper with mocked MediaWikiAPI and SQLiteStateManager
  - Use unittest.mock.patch and MagicMock for all external calls
  - No live Wikipedia API or Qt event loop required

Requirement coverage:
  SCRP-01: walk_category avoids infinite recursion via visited_categories cycle guard
  SCRP-01: fetch_and_filter returns None for page with empty infobox (Pitfall 2)
  SCRP-01: fetch_and_filter returns correct document dict for page with infobox
  SCRP-01: pageid + auto_suggest=False used for fetch (Pitfall 1)
  D-06: yield_documents skips pageids already in state
  Security/etiquette: User-Agent set on both MediaWikiAPI and requests.Session

Anti-patterns avoided:
  Pitfall 1: uses pageid not title to avoid redirect aliasing
  Pitfall 2: infobox empty-dict check (falsy, not is None)
  Pitfall 6: visited_categories set prevents cyclic category recursion
"""

from unittest.mock import MagicMock, patch, call

import pytest

from nitrofind.scraper.wikipedia import WikipediaScraper

# Sample config for all tests — rate_limit_seconds=0 so time.sleep is instant
SAMPLE_CONFIG = {
    "wikipedia": {
        "root_categories": ["Category:Sports cars"],
        "max_depth": 2,
        "rate_limit_seconds": 0,
        "user_agent": "NitroFind/1.0 (test)",
    }
}


# ---------------------------------------------------------------------------
# SCRP-01: category walk — Pitfall 6 cycle guard
# ---------------------------------------------------------------------------

def test_walk_category_avoids_cycles():
    """Pitfall 6: _walk_category does not recurse into an already-visited subcategory."""
    mock_wiki = MagicMock()
    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)

        visited: set = set()
        # Pre-populate the visited set with the subcategory we expect to recurse into
        subcat = "Category:Italian sports cars"
        visited.add(subcat)

        # _get_category_members_raw returns one page ID and one subcat title
        call_results = {
            ("Category:Sports cars", "page"): [111],
            ("Category:Sports cars", "subcat"): [subcat],
        }

        def fake_get(cat_title, cmtype, return_titles=False):
            items = call_results.get((cat_title, cmtype), [])
            return items

        scraper._get_category_members_raw = fake_get

        result = scraper._walk_category(
            category_title=subcat,  # Already in visited — should return []
            depth=1,
            visited_categories=visited,
        )

    assert result == [], f"Expected [] for already-visited category, got {result!r}"


# ---------------------------------------------------------------------------
# SCRP-01: infobox filter — Pitfall 2
# ---------------------------------------------------------------------------

def test_fetch_and_filter_skips_empty_infobox():
    """Returns None when page.infobox == {} (D-02, Pitfall 2 — falsy check, not is None)."""
    mock_page = MagicMock()
    mock_page.infobox = {}  # empty dict — falsy; must NOT be treated as None

    mock_wiki = MagicMock()
    mock_wiki.page.return_value = mock_page

    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)
        result = scraper._fetch_and_build_doc(pageid=12345)

    assert result is None, f"Expected None for page with empty infobox, got {result!r}"


# ---------------------------------------------------------------------------
# SCRP-01: document construction
# ---------------------------------------------------------------------------

def test_fetch_and_build_doc_returns_full_doc_for_infobox_page():
    """Returns a complete document dict for a page with a non-empty infobox."""
    mock_page = MagicMock()
    mock_page.pageid = 12345
    mock_page.title = "Ferrari 308"
    mock_page.url = "https://en.wikipedia.org/wiki/Ferrari_308"
    mock_page.content = "A real plain text body about Ferrari 308"
    mock_page.images = ["img1.jpg", "img2.jpg", "img3.jpg", "img4.jpg"]
    mock_page.infobox = {
        "manufacturer": "Ferrari",
        "production": "1975 to 1985",
    }

    mock_wiki = MagicMock()
    mock_wiki.page.return_value = mock_page

    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)
        doc = scraper._fetch_and_build_doc(pageid=12345)

    assert doc is not None, "Expected a doc dict, got None"
    assert doc["article_id"] == "12345"
    assert doc["source_domain"] == "en.wikipedia.org"
    assert doc["has_infobox"] is True
    assert doc["manufacturer"] == "Ferrari"
    assert doc["production_start"] == 1975
    assert doc["era_bucket"] == "1970s"
    assert doc["image_count"] == 4
    assert doc["body"] == "A real plain text body about Ferrari 308"
    assert len(doc["excerpt"]) <= 300


def test_pageid_used_with_auto_suggest_false():
    """Pitfall 1: _fetch_and_build_doc calls self._wiki.page with pageid=<int> and auto_suggest=False."""
    mock_page = MagicMock()
    mock_page.pageid = 99999
    mock_page.title = "Test Car"
    mock_page.url = "https://en.wikipedia.org/wiki/Test_Car"
    mock_page.content = "Test body text"
    mock_page.images = []
    mock_page.infobox = {"manufacturer": "TestCo"}

    mock_wiki = MagicMock()
    mock_wiki.page.return_value = mock_page

    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)
        scraper._fetch_and_build_doc(pageid=99999)

    # Assert pageid kwarg and auto_suggest=False were passed
    mock_wiki.page.assert_called_once()
    call_kwargs = mock_wiki.page.call_args[1]
    assert call_kwargs.get("pageid") == 99999, \
        f"Expected pageid=99999 in kwargs, got {call_kwargs!r}"
    assert call_kwargs.get("auto_suggest") is False, \
        f"Expected auto_suggest=False in kwargs, got {call_kwargs!r}"


# ---------------------------------------------------------------------------
# D-06: skip-if-visited
# ---------------------------------------------------------------------------

def test_yield_documents_skips_already_visited():
    """D-06: yield_documents does NOT call wiki.page for a pageid that is_visited."""
    mock_wiki = MagicMock()

    # Build a valid page mock for pageid 100 (not visited)
    mock_page_100 = MagicMock()
    mock_page_100.pageid = 100
    mock_page_100.title = "Unvisited Car"
    mock_page_100.url = "https://en.wikipedia.org/wiki/Unvisited_Car"
    mock_page_100.content = "Body text for unvisited car article"
    mock_page_100.images = []
    mock_page_100.infobox = {"manufacturer": "SomeMaker"}

    mock_wiki.page.return_value = mock_page_100

    mock_state = MagicMock()
    # pageid 99 is already visited, pageid 100 is not
    mock_state.is_visited.side_effect = lambda x: x == "99"

    def fake_get_members(cat_title, cmtype, return_titles=False):
        """Return fixed page IDs for 'page' calls, empty list for 'subcat' calls.

        Returning empty subcategory list prevents recursion so the test only
        exercises yield_documents' skip-if-visited logic, not the walk.
        """
        if cmtype == "page":
            return [99, 100]
        return []  # no subcategories — prevents uncontrolled recursion

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki), \
         patch.object(
             WikipediaScraper,
             "_get_category_members_raw",
             side_effect=fake_get_members,
         ):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)
        docs = list(scraper.yield_documents())

    # wiki.page should NEVER have been called with pageid=99
    for call_item in mock_wiki.page.call_args_list:
        kwargs = call_item[1]
        assert kwargs.get("pageid") != 99, \
            f"wiki.page was called with pageid=99 but it should have been skipped"

    # Should have yielded exactly 1 doc (for pageid 100)
    assert len(docs) == 1, f"Expected 1 doc (pageid 100), got {len(docs)}: {docs!r}"


# ---------------------------------------------------------------------------
# Security/etiquette: User-Agent
# ---------------------------------------------------------------------------

def test_user_agent_set_from_config():
    """User-Agent is set from config on both MediaWikiAPI client and requests.Session."""
    mock_wiki = MagicMock()
    mock_state = MagicMock()

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)

    # MediaWikiAPI config.user_agent must be set to the configured value
    assert mock_wiki.config.user_agent == "NitroFind/1.0 (test)", \
        f"Expected wiki.config.user_agent == 'NitroFind/1.0 (test)', got {mock_wiki.config.user_agent!r}"

    # requests.Session headers must also have the User-Agent
    assert scraper._session.headers.get("User-Agent") == "NitroFind/1.0 (test)" or \
        scraper._session.headers["User-Agent"] == "NitroFind/1.0 (test)", \
        f"Expected session User-Agent == 'NitroFind/1.0 (test)', got {dict(scraper._session.headers)!r}"


# ---------------------------------------------------------------------------
# Integration test (excluded from quick suite via -m "not integration")
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_real_wikipedia_page_fetch():
    """Live integration test — fetches a real Wikipedia page.

    Requires internet access. Excluded from CI via -m "not integration".
    Skips if network is unavailable.
    """
    import socket

    try:
        socket.create_connection(("en.wikipedia.org", 443), timeout=5)
    except OSError:
        pytest.skip("No internet access — skipping live Wikipedia integration test")

    from nitrofind.scraper.state import SQLiteStateManager

    state = SQLiteStateManager(":memory:")
    scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=state)

    result = scraper._fetch_and_build_doc(pageid=57328)  # Ferrari 308 pageid

    assert result is not None, "Expected a doc dict for Ferrari 308, got None"
    assert result["article_id"].isdigit(), \
        f"Expected article_id to be a digit string, got {result['article_id']!r}"
    state.close()
