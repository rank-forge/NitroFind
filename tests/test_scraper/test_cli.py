"""
Unit tests for scripts/scraper.py — CLI integration coverage.

Test strategy:
  - All tests mock external dependencies (Elasticsearch, scrapers, streaming_bulk)
  - No live ES, no live network required
  - streaming_bulk patched at nitrofind.scraper.indexer.streaming_bulk (where it is
    actually imported), not at scripts.scraper.streaming_bulk (never imported there)

Requirement coverage:
  SCRP-01: --wikipedia flag routes to WikipediaScraper only
  SCRP-02: --blogs flag routes to BlogScraper only
  SCRP-03: wiring verified via mocked index_all call counts
  SCRP-04: yaml.safe_load enforcement + ES reachability gate

Security coverage:
  T-02-01: yaml.safe_load enforced — malicious YAML payload does not execute
  T-02-21: ES reachability gate — CLI exits 1 if ES unreachable
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from scripts import scraper as cli

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_config(tmp_path):
    """Write a minimal valid scraper.yaml to tmp_path and return the path str."""
    config = {
        "wikipedia": {
            "root_categories": ["Category:Automobiles by manufacturer"],
            "max_depth": 1,
            "rate_limit_seconds": 0,
            "user_agent": "NitroFind-test/1.0",
        },
        "blogs": {
            "size_halt_bytes": 1_800_000_000,
            "headers": {"User-Agent": "NitroFind-test/1.0"},
            "targets": [
                {
                    "name": "test_blog",
                    "enabled": False,
                    "base_url": "https://example.com/",
                    "article_list_url": "https://example.com/articles/",
                    "article_selector": "div.content",
                    "listing_selector": "a.article",
                }
            ],
        },
    }
    config_path = tmp_path / "scraper.yaml"
    config_path.write_text(yaml.dump(config))
    return str(config_path)


def _make_mock_es():
    """Return a MagicMock ES client where .info() succeeds and stats return small size."""
    mock_client = MagicMock()
    mock_client.info.return_value = {"version": {"number": "8.18.0"}}
    mock_client.indices.stats.return_value = {
        "indices": {
            "car_articles": {
                "primaries": {"store": {"size_in_bytes": 1_000_000}},
                "total": {"store": {"size_in_bytes": 2_000_000}},
            }
        }
    }
    return mock_client


def _fake_docs(n=3):
    """Return n minimal doc dicts with article_id."""
    return [
        {"article_id": f"doc_{i}", "title": f"Article {i}", "body": "text"}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Help / argparse
# ---------------------------------------------------------------------------


def test_help_exits_zero():
    """--help exits 0 and stdout contains all four flags."""
    result = subprocess.run(
        [sys.executable, "scripts/scraper.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--wikipedia" in result.stdout
    assert "--blogs" in result.stdout
    assert "--all" in result.stdout
    assert "--config" in result.stdout


# ---------------------------------------------------------------------------
# Config loading + yaml safety
# ---------------------------------------------------------------------------


def test_load_config_rejects_yaml_load_in_source():
    """T-02-01 regression guard: source must use yaml.safe_load, never yaml.load(."""
    source_path = Path(__file__).parent.parent.parent / "scripts" / "scraper.py"
    source = source_path.read_text()
    assert "yaml.safe_load" in source, "yaml.safe_load must be present in scripts/scraper.py"
    assert "yaml.load(" not in source, "yaml.load( must NOT be present in scripts/scraper.py"


def test_main_uses_yaml_safe_load(tmp_path):
    """T-02-01: malicious YAML payload does not execute; CLI exits 1 on parse error.

    yaml.safe_load raises yaml.YAMLError for !!python/object tags — it does NOT
    execute arbitrary Python constructors. This test confirms the security boundary.
    On POSIX, also confirms /tmp/pwned was not created.
    """
    # Write a YAML payload that yaml.load (unsafe) would execute as code
    evil_yaml = "exploit: !!python/object/apply:os.system ['touch /tmp/pwned']\n"
    evil_path = tmp_path / "evil.yaml"
    evil_path.write_text(evil_yaml)

    # Ensure the side-effect file does not already exist
    pwned_path = "/tmp/pwned"
    if sys.platform != "win32" and os.path.exists(pwned_path):
        os.remove(pwned_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--config", str(evil_path)])

    assert exc_info.value.code == 1

    # Confirm the side-effect was NOT created (yaml.safe_load blocks it)
    if sys.platform != "win32":
        assert not os.path.exists(pwned_path), "/tmp/pwned was created — yaml.safe_load bypassed!"


# ---------------------------------------------------------------------------
# ES reachability gate
# ---------------------------------------------------------------------------


def test_create_client_exits_on_unreachable_es():
    """T-02-21: _create_client exits 1 when ES .info() raises ConnectionError."""
    with patch("scripts.scraper.Elasticsearch") as MockES:
        mock_instance = MagicMock()
        mock_instance.info.side_effect = ConnectionError("Connection refused")
        MockES.return_value = mock_instance

        with pytest.raises(SystemExit) as exc_info:
            cli._create_client()

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Source flag routing
# ---------------------------------------------------------------------------


def test_main_runs_wikipedia_only_with_flag(tmp_config):
    """--wikipedia flag routes to WikipediaScraper; BlogScraper must NOT be instantiated."""
    docs = _fake_docs(3)
    mock_client = _make_mock_es()
    bulk_results = iter([(True, {}) for _ in docs])

    with patch("scripts.scraper.Elasticsearch", return_value=mock_client), \
         patch("scripts.scraper.ensure_index") as mock_ensure, \
         patch("scripts.scraper.WikipediaScraper") as MockWiki, \
         patch("scripts.scraper.BlogScraper") as MockBlog, \
         patch("nitrofind.scraper.indexer.streaming_bulk", return_value=bulk_results):

        MockWiki.return_value.yield_documents.return_value = iter(docs)

        result = cli.main(["--wikipedia", "--config", tmp_config])

    assert result == 0
    MockWiki.assert_called_once()
    MockBlog.assert_not_called()
    mock_ensure.assert_called_once_with(mock_client)


def test_main_runs_blogs_only_with_flag(tmp_config):
    """--blogs flag routes to BlogScraper; WikipediaScraper must NOT be instantiated."""
    docs = _fake_docs(2)
    mock_client = _make_mock_es()
    bulk_results = iter([(True, {}) for _ in docs])

    with patch("scripts.scraper.Elasticsearch", return_value=mock_client), \
         patch("scripts.scraper.ensure_index"), \
         patch("scripts.scraper.WikipediaScraper") as MockWiki, \
         patch("scripts.scraper.BlogScraper") as MockBlog, \
         patch("nitrofind.scraper.indexer.streaming_bulk", return_value=bulk_results):

        MockBlog.return_value.yield_documents.return_value = iter(docs)

        result = cli.main(["--blogs", "--config", tmp_config])

    assert result == 0
    MockBlog.assert_called_once()
    MockWiki.assert_not_called()


def test_main_runs_both_with_all_flag(tmp_config):
    """--all flag runs both WikipediaScraper and BlogScraper in order."""
    wiki_docs = _fake_docs(3)
    blog_docs = _fake_docs(2)
    mock_client = _make_mock_es()
    # two separate BulkIndexer.index_all calls — each gets its own bulk stream
    bulk_results_wiki = iter([(True, {}) for _ in wiki_docs])
    bulk_results_blog = iter([(True, {}) for _ in blog_docs])

    with patch("scripts.scraper.Elasticsearch", return_value=mock_client), \
         patch("scripts.scraper.ensure_index"), \
         patch("scripts.scraper.WikipediaScraper") as MockWiki, \
         patch("scripts.scraper.BlogScraper") as MockBlog, \
         patch("nitrofind.scraper.indexer.streaming_bulk",
               side_effect=[bulk_results_wiki, bulk_results_blog]):

        MockWiki.return_value.yield_documents.return_value = iter(wiki_docs)
        MockBlog.return_value.yield_documents.return_value = iter(blog_docs)

        result = cli.main(["--all", "--config", tmp_config])

    assert result == 0
    MockWiki.assert_called_once()
    MockBlog.assert_called_once()


def test_main_runs_both_with_no_flag(tmp_config):
    """D-04: no flag behaves identically to --all (both scrapers run)."""
    wiki_docs = _fake_docs(2)
    blog_docs = _fake_docs(1)
    mock_client = _make_mock_es()
    bulk_results_wiki = iter([(True, {}) for _ in wiki_docs])
    bulk_results_blog = iter([(True, {}) for _ in blog_docs])

    with patch("scripts.scraper.Elasticsearch", return_value=mock_client), \
         patch("scripts.scraper.ensure_index"), \
         patch("scripts.scraper.WikipediaScraper") as MockWiki, \
         patch("scripts.scraper.BlogScraper") as MockBlog, \
         patch("nitrofind.scraper.indexer.streaming_bulk",
               side_effect=[bulk_results_wiki, bulk_results_blog]):

        MockWiki.return_value.yield_documents.return_value = iter(wiki_docs)
        MockBlog.return_value.yield_documents.return_value = iter(blog_docs)

        result = cli.main(["--config", tmp_config])

    assert result == 0
    MockWiki.assert_called_once()
    MockBlog.assert_called_once()


# ---------------------------------------------------------------------------
# Order of operations
# ---------------------------------------------------------------------------


def test_main_calls_ensure_index_before_scrape(tmp_config):
    """ensure_index must be called exactly once before any BulkIndexer.index_all call."""
    docs = _fake_docs(1)
    mock_client = _make_mock_es()
    call_order = []
    bulk_results = iter([(True, {}) for _ in docs])

    def track_ensure(client):
        call_order.append("ensure_index")

    with patch("scripts.scraper.Elasticsearch", return_value=mock_client), \
         patch("scripts.scraper.ensure_index", side_effect=track_ensure) as mock_ensure, \
         patch("scripts.scraper.WikipediaScraper") as MockWiki, \
         patch("scripts.scraper.BlogScraper") as MockBlog, \
         patch("nitrofind.scraper.indexer.streaming_bulk", return_value=bulk_results):

        MockWiki.return_value.yield_documents.return_value = iter(docs)
        MockBlog.return_value.yield_documents.return_value = iter([])

        original_run_wiki = cli._run_wikipedia

        def tracking_run_wiki(config, state, client):
            call_order.append("run_wikipedia")
            return original_run_wiki(config, state, client)

        with patch("scripts.scraper._run_wikipedia", side_effect=tracking_run_wiki):
            result = cli.main(["--wikipedia", "--config", tmp_config])

    assert result == 0
    mock_ensure.assert_called_once_with(mock_client)
    assert call_order.index("ensure_index") < call_order.index("run_wikipedia"), (
        "ensure_index must be called before _run_wikipedia"
    )
