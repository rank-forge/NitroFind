"""
Unit + integration tests for nitrofind.scraper.indexer — SCRP-03, SCRP-04 coverage.

Test strategy:
  - Unit: mock streaming_bulk and indices.stats to test halt logic
  - Integration: marked @pytest.mark.integration; requires live ES node

Requirement coverage:
  SCRP-03: indexing same article twice produces no duplicate count increase
  SCRP-04: index_all() halts and logs warning before 1.8 GB

Anti-patterns avoided:
  Pitfall 8: size check uses primaries.store.size_in_bytes (not total)
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from nitrofind.scraper.indexer import BulkIndexer, build_action, SIZE_HALT_BYTES, CHECK_EVERY_N_DOCS

# ---------------------------------------------------------------------------
# SCRP-03: document ID deduplication
# ---------------------------------------------------------------------------


def test_build_action_sets_id_from_article_id():
    """SCRP-03: build_action sets _id from doc['article_id'] for ES deduplication."""
    doc = {"article_id": "12345", "title": "Ferrari 308", "body": "text"}
    action = build_action(doc)
    assert action["_index"] == "car_articles"
    assert action["_id"] == "12345"
    assert action["title"] == "Ferrari 308"
    assert action["body"] == "text"
    assert action["article_id"] == "12345"


def test_build_action_includes_all_doc_fields():
    """build_action includes all original doc fields in the returned action."""
    doc = {"article_id": "42", "title": "X", "manufacturer": "BMW"}
    action = build_action(doc)
    assert action["_index"] == "car_articles"
    assert action["_id"] == "42"
    assert action["manufacturer"] == "BMW"


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_module_constants():
    """SIZE_HALT_BYTES == 1_800_000_000 and CHECK_EVERY_N_DOCS == 100."""
    assert SIZE_HALT_BYTES == 1_800_000_000
    assert CHECK_EVERY_N_DOCS == 100


# ---------------------------------------------------------------------------
# Pitfall 8: primaries vs total
# ---------------------------------------------------------------------------


def test_index_size_bytes_reads_primaries():
    """Pitfall 8: _index_size_bytes uses primaries.store.size_in_bytes (not total)."""
    mock_client = MagicMock()
    mock_client.indices.stats.return_value = {
        "indices": {
            "car_articles": {
                "primaries": {"store": {"size_in_bytes": 500_000_000}},
                "total": {"store": {"size_in_bytes": 1_000_000_000}},
            }
        }
    }
    mock_client.indices.stats.call_args  # ensure it's a mock

    indexer = BulkIndexer(client=mock_client, state=MagicMock())
    size = indexer._index_size_bytes()
    # Must return primaries value, not total
    assert size == 500_000_000


# ---------------------------------------------------------------------------
# SCRP-04: size guard halt
# ---------------------------------------------------------------------------


def test_size_guard_halts_indexing(caplog):
    """SCRP-04: BulkIndexer.index_all() returns early when index size >= 1.8 GB."""
    import logging
    mock_client = MagicMock()
    # Stats returns a size over the halt threshold
    mock_client.indices.stats.return_value = {
        "indices": {
            "car_articles": {
                "primaries": {"store": {"size_in_bytes": SIZE_HALT_BYTES + 1}},
                "total": {"store": {"size_in_bytes": SIZE_HALT_BYTES * 2}},
            }
        }
    }

    # streaming_bulk yields (ok=True, info) for 150 docs so size check fires at 100
    mock_bulk_results = iter([(True, {}) for _ in range(150)])

    fake_actions = [{"_index": "car_articles", "_id": str(i)} for i in range(150)]

    with caplog.at_level(logging.WARNING, logger="nitrofind.scraper.indexer"):
        with patch("nitrofind.scraper.indexer.streaming_bulk", return_value=mock_bulk_results):
            indexer = BulkIndexer(client=mock_client, state=MagicMock())
            count = indexer.index_all(iter(fake_actions))

    # Halted after size check at CHECK_EVERY_N_DOCS (100), so count <= 150
    assert count <= 150
    # Warning must contain both literal substrings
    warning_messages = " ".join(caplog.messages)
    assert "Halting scraper" in warning_messages, f"Expected 'Halting scraper' in warnings: {caplog.messages}"
    assert "SCRP-04" in warning_messages, f"Expected 'SCRP-04' in warnings: {caplog.messages}"


def test_index_all_counts_successful_docs():
    """index_all returns count of successfully indexed docs when below size threshold."""
    mock_client = MagicMock()
    # Size always below halt threshold
    mock_client.indices.stats.return_value = {
        "indices": {
            "car_articles": {
                "primaries": {"store": {"size_in_bytes": 100_000_000}},
                "total": {"store": {"size_in_bytes": 200_000_000}},
            }
        }
    }

    # 100 successful results (size check fires exactly once — returns non-halting)
    mock_bulk_results = iter([(True, {}) for _ in range(100)])
    fake_actions = [{"_index": "car_articles", "_id": str(i)} for i in range(100)]

    with patch("nitrofind.scraper.indexer.streaming_bulk", return_value=mock_bulk_results):
        indexer = BulkIndexer(client=mock_client, state=MagicMock())
        count = indexer.index_all(iter(fake_actions))

    assert count == 100


# ---------------------------------------------------------------------------
# SCRP-03: live deduplication (integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_deduplication_no_duplicate_docs():
    """SCRP-03: indexing same article_id twice does not increase doc count (live ES)."""
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")

    from elasticsearch import Elasticsearch
    from nitrofind.es_manager import ES_URL
    from nitrofind.es_schema import ensure_index

    client = Elasticsearch(ES_URL)
    ensure_index(client)

    test_doc = {
        "article_id": "test_dedup_xyz_plan02",
        "title": "Test Dedup Article",
        "body": "Test body text",
        "source_domain": "test",
        "scraped_at": "2026-01-01T00:00:00Z",
    }

    action1 = build_action(test_doc)
    action2 = build_action(test_doc)  # identical _id

    indexer = BulkIndexer(client=client, state=MagicMock())
    indexer.index_all(iter([action1]))
    indexer.index_all(iter([action2]))

    # Refresh so count is accurate
    client.indices.refresh(index="car_articles")

    resp = client.count(
        index="car_articles",
        query={"term": {"article_id": "test_dedup_xyz_plan02"}},
    )
    assert resp["count"] == 1, f"Expected count=1 after dedup, got {resp['count']}"
