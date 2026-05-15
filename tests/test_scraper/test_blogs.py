"""
Unit tests for nitrofind.scraper.blogs — SCRP-02 coverage.

Test strategy:
  - Mock requests.Session.get with unittest.mock
  - Inject mock session directly onto scraper instance after construction
  - No live network access required

Requirement coverage:
  SCRP-02: blog fetcher returns None gracefully on HTTP 403 (Pitfall 3)
  SCRP-02: blog fetcher returns None when article container not found (Pitfall 4)
  SCRP-02: blog fetcher returns None for suspiciously short body (<100 chars) (Pitfall 4)
  SCRP-02: extract_plain_text returns no HTML tags in output (L-05)
  SCRP-02: yielded document has correct shape (title, url, source_domain, article_id,
           scraped_at, body, excerpt, word_count, has_infobox, image_count, era_bucket)
  SCRP-02: fallback chain advances to next enabled target on listing 403 (Pitfall 3)
  D-06: URL already in state is skipped without fetching the article
  Security/etiquette: User-Agent is HONEST_USER_AGENT; does not contain "Mozilla"

Anti-patterns avoided:
  Pitfall 3: 403 → graceful skip + log (no browser impersonation)
  Pitfall 4: selectors come from config, not hardcoded
"""

import requests
from unittest.mock import MagicMock

import pytest

from nitrofind.scraper.blogs import BlogScraper, HONEST_USER_AGENT

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

# Sample config with rate_limit_seconds=0 so tests run instantly
_SAMPLE_CONFIG = {
    "blogs": {
        "rate_limit_seconds": 0,
        "targets": [
            {
                "name": "hagerty",
                "enabled": True,
                "base_url": "https://www.hagerty.com/media/",
                "article_list_url": "https://www.hagerty.com/media/all-articles/",
                "article_selector": "article.post",
                "listing_selector": "a.article-link",
            }
        ],
    }
}

# HTML with a valid article container and a body long enough to clear 100 chars
_VALID_ARTICLE_HTML = (
    "<html><body>"
    "<article class='post'>"
    "<h1>Test Title</h1>"
    "<p>Real body text about Ferrari that is sufficiently long to clear the "
    "100-char threshold for the test of valid article content.</p>"
    "</article>"
    "</body></html>"
)

# Minimal listing HTML with one article link pointing to the verified domain
_LISTING_HTML = (
    "<html><body>"
    "<a class='article-link' href='/media/test-article'>Test Article</a>"
    "</body></html>"
)


def _make_mock_response(status_code: int = 200, text: str = "") -> MagicMock:
    """Return a MagicMock simulating a requests.Response with raise_for_status."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    if status_code >= 400:
        http_err = requests.HTTPError(response=MagicMock(status_code=status_code))
        mock_resp.raise_for_status.side_effect = http_err
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


def _make_scraper(config=None, state=None):
    """Build a BlogScraper with a fresh mock state."""
    if config is None:
        config = _SAMPLE_CONFIG
    if state is None:
        state = MagicMock()
        state.is_visited.return_value = False
    return BlogScraper(config=config, state=state)


# ---------------------------------------------------------------------------
# SCRP-02: HTTP error handling
# ---------------------------------------------------------------------------


def test_fetch_article_returns_none_on_403(caplog):
    """SCRP-02, Pitfall 3: HTTP 403 is logged as warning and _fetch_article returns None."""
    scraper = _make_scraper()

    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(status_code=403)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]

    import logging
    with caplog.at_level(logging.WARNING, logger="nitrofind.scraper.blogs"):
        result = scraper._fetch_article("https://www.hagerty.com/media/test-article", target)

    assert result is None
    assert any("403" in rec.message for rec in caplog.records), (
        f"Expected warning containing '403'; got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# SCRP-02: Selector mismatch
# ---------------------------------------------------------------------------


def test_fetch_article_returns_none_on_missing_container(caplog):
    """SCRP-02, Pitfall 4: _fetch_article returns None when article_selector finds no container."""
    scraper = _make_scraper()

    # HTML that does NOT contain <article class='post'>
    html_no_container = "<html><body><div class='other'>Some content here</div></body></html>"

    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(text=html_no_container)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]

    import logging
    with caplog.at_level(logging.WARNING, logger="nitrofind.scraper.blogs"):
        result = scraper._fetch_article("https://www.hagerty.com/media/test-article", target)

    assert result is None
    assert any("Article container not found" in rec.message for rec in caplog.records), (
        f"Expected 'Article container not found' warning; got: {[r.message for r in caplog.records]}"
    )


def test_fetch_article_returns_none_on_short_body(caplog):
    """SCRP-02, Pitfall 4: _fetch_article returns None when body text is <100 characters."""
    scraper = _make_scraper()

    # HTML with the right container but body text shorter than 100 chars
    html_short_body = (
        "<html><body>"
        "<article class='post'><h1>Short</h1><p>Too short.</p></article>"
        "</body></html>"
    )

    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(text=html_short_body)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]

    import logging
    with caplog.at_level(logging.WARNING, logger="nitrofind.scraper.blogs"):
        result = scraper._fetch_article("https://www.hagerty.com/media/short-article", target)

    assert result is None
    assert any("suspiciously short" in rec.message for rec in caplog.records), (
        f"Expected 'suspiciously short' warning; got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# SCRP-02: HTML stripping
# ---------------------------------------------------------------------------


def test_extract_plain_text_removes_html_tags():
    """SCRP-02, L-05: extracted body text contains no HTML tags (no < or > characters)."""
    scraper = _make_scraper()

    html = (
        "<html><body>"
        "<article class='post'>"
        "<h1>Title</h1>"
        "<p>Real <strong>body</strong> text about Ferrari that is long enough to "
        "pass the minimum 100-character check for the body field in the document.</p>"
        "</article>"
        "</body></html>"
    )

    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(text=html)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]
    doc = scraper._fetch_article("https://www.hagerty.com/media/ferrari-test", target)

    assert doc is not None, "Expected a document dict, got None"
    assert "<" not in doc["body"], f"Body contains '<': {doc['body']!r}"
    assert ">" not in doc["body"], f"Body contains '>': {doc['body']!r}"
    assert "Real body text about Ferrari" in doc["body"]


# ---------------------------------------------------------------------------
# SCRP-02: Document shape
# ---------------------------------------------------------------------------


def test_doc_has_correct_shape():
    """SCRP-02: yielded doc has required keys with correct values for blog-specific fields."""
    scraper = _make_scraper()

    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(text=_VALID_ARTICLE_HTML)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]
    doc = scraper._fetch_article(
        "https://www.hagerty.com/media/ferrari-history", target
    )

    assert doc is not None, "Expected a document dict, got None"

    required_keys = {
        "title", "url", "source_domain", "article_id", "scraped_at",
        "body", "excerpt", "word_count", "has_infobox", "image_count", "era_bucket",
    }
    assert required_keys.issubset(doc.keys()), (
        f"Missing keys: {required_keys - doc.keys()}"
    )

    assert doc["has_infobox"] is False
    assert doc["era_bucket"] == "Unknown"
    assert doc["source_domain"] == "www.hagerty.com"
    assert doc["article_id"] == "ferrari-history"
    assert isinstance(doc["article_id"], str) and doc["article_id"]
    assert doc["url"] == "https://www.hagerty.com/media/ferrari-history"


# ---------------------------------------------------------------------------
# SCRP-02: Fallback chain
# ---------------------------------------------------------------------------


def test_fallback_chain_advances_on_403(caplog):
    """SCRP-02, Pitfall 3: first target 403 listing → fallback to second target."""
    config_two_targets = {
        "blogs": {
            "rate_limit_seconds": 0,
            "targets": [
                {
                    "name": "hagerty",
                    "enabled": True,
                    "base_url": "https://www.hagerty.com/media/",
                    "article_list_url": "https://www.hagerty.com/media/all-articles/",
                    "article_selector": "article.post",
                    "listing_selector": "a.article-link",
                },
                {
                    "name": "hemmings",
                    "enabled": True,
                    "base_url": "https://www.hemmings.com/stories/",
                    "article_list_url": "https://www.hemmings.com/stories/",
                    "article_selector": "article.post",
                    "listing_selector": "a.article-link",
                },
            ],
        }
    }

    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    scraper = BlogScraper(config=config_two_targets, state=mock_state)

    # Listing HTML for the second target with one article link
    hemmings_listing = (
        "<html><body>"
        "<a class='article-link' href='/stories/pontiac-gto'>Pontiac GTO</a>"
        "</body></html>"
    )

    def mock_get(url, **kwargs):
        if "hagerty.com" in url and "all-articles" in url:
            # First target listing returns 403
            return _make_mock_response(status_code=403)
        elif "hemmings.com" in url and url.endswith("/stories/"):
            # Second target listing returns 200
            return _make_mock_response(text=hemmings_listing)
        else:
            # Article page returns 200 with valid content
            return _make_mock_response(text=_VALID_ARTICLE_HTML)

    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.side_effect = mock_get
    scraper._session = mock_session

    import logging
    with caplog.at_level(logging.WARNING, logger="nitrofind.scraper.blogs"):
        docs = list(scraper.yield_documents())

    # Should have yielded from hemmings (second target)
    assert len(docs) >= 1, f"Expected at least one doc from second target; got: {docs}"
    assert any(doc["source_domain"] == "www.hemmings.com" for doc in docs), (
        f"Expected source_domain 'www.hemmings.com'; got domains: "
        f"{[d['source_domain'] for d in docs]}"
    )

    # First target's 403 should be logged as a warning mentioning "hagerty"
    assert any(
        "hagerty" in rec.message.lower() for rec in caplog.records
    ), f"Expected warning mentioning 'hagerty'; got: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# D-06: Skip-if-visited
# ---------------------------------------------------------------------------


def test_state_visited_url_is_skipped():
    """D-06: is_visited(url) returning True skips the article without fetching it."""
    mock_state = MagicMock()
    # The article URL that would be discovered from the listing
    article_url = "https://www.hagerty.com/media/foo"
    mock_state.is_visited.side_effect = lambda url: url == article_url

    scraper = _make_scraper(state=mock_state)

    listing_html = (
        "<html><body>"
        "<a class='article-link' href='/media/foo'>Foo Article</a>"
        "</body></html>"
    )

    call_tracker = []

    def mock_get(url, **kwargs):
        call_tracker.append(url)
        if "all-articles" in url:
            return _make_mock_response(text=listing_html)
        else:
            # Article page should NEVER be called
            return _make_mock_response(text=_VALID_ARTICLE_HTML)

    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.side_effect = mock_get
    scraper._session = mock_session

    docs = list(scraper.yield_documents())

    # No documents should be yielded — URL was already visited
    assert docs == [], f"Expected no docs; got: {docs}"
    # Article URL must NOT have been fetched
    assert article_url not in call_tracker, (
        f"Article URL was fetched despite is_visited=True: {call_tracker}"
    )


# ---------------------------------------------------------------------------
# Security/etiquette: User-Agent
# ---------------------------------------------------------------------------


def test_honest_user_agent_not_mozilla():
    """Session User-Agent is HONEST_USER_AGENT and does not contain 'Mozilla'."""
    scraper = _make_scraper()

    ua = scraper._session.headers["User-Agent"]
    assert ua == HONEST_USER_AGENT, (
        f"Expected HONEST_USER_AGENT; got: {ua!r}"
    )
    assert "Mozilla" not in ua, (
        f"User-Agent must not contain 'Mozilla' (no browser impersonation); got: {ua!r}"
    )
