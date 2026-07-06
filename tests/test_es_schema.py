"""
Unit tests for nitrofind.es_schema — SCHEMA-01..04 coverage.

Requirement coverage:
  SCHEMA-01: core identity fields (title, url, source_domain, article_id, scraped_at)
  SCHEMA-02: relevance scoring fields (published_at, word_count, has_infobox, image_count)
  SCHEMA-03: full text + display excerpt (body, excerpt)
  SCHEMA-04: automotive facet fields (manufacturer, production_start, production_end,
              body_style, era_bucket, country_of_origin)
  L-02: specs as flattened type
"""

from unittest.mock import MagicMock, call

import pytest

from nitrofind import es_schema
from nitrofind.es_schema import ensure_index, CAR_ARTICLES_MAPPING


def test_mapping_has_required_fields():
    """Assert every SCHEMA-01..04 field is present with the correct ES type."""
    props = CAR_ARTICLES_MAPPING["properties"]

    # SCHEMA-01: core identity fields
    assert "title" in props
    assert props["title"]["type"] == "text"
    for field in ("url", "source_domain", "article_id"):
        assert field in props
        assert props[field]["type"] == "keyword"
    assert "scraped_at" in props
    assert props["scraped_at"]["type"] == "date"

    # SCHEMA-02: relevance scoring fields
    assert "published_at" in props
    assert props["published_at"]["type"] == "date"
    assert "word_count" in props
    assert props["word_count"]["type"] == "integer"
    assert "has_infobox" in props
    assert props["has_infobox"]["type"] == "boolean"
    assert "image_count" in props
    assert props["image_count"]["type"] == "integer"

    # SCHEMA-03: full text + display excerpt
    assert "body" in props
    assert props["body"]["type"] == "text"
    assert "excerpt" in props
    assert props["excerpt"]["type"] == "keyword"  # Pitfall 5: keyword not text

    # SCHEMA-04: automotive facet fields
    for field in ("manufacturer", "body_style", "era_bucket", "country_of_origin"):
        assert field in props
        assert props[field]["type"] == "keyword"
    for field in ("production_start", "production_end"):
        assert field in props
        assert props[field]["type"] == "integer"

    # L-02: specs as flattened to prevent mapping explosion
    assert "specs" in props
    assert props["specs"]["type"] == "flattened"


def test_body_html_field_present():
    """Phase 9 / BUG-01: body_html field exists with type text and index=False."""
    props = CAR_ARTICLES_MAPPING["properties"]
    assert "body_html" in props, "body_html field missing from CAR_ARTICLES_MAPPING"
    assert props["body_html"]["type"] == "text"
    assert props["body_html"]["index"] is False, (
        f"body_html must have index=False (not tokenized); got {props['body_html'].get('index')!r}"
    )


def test_hero_image_url_field_present():
    """Detail pages can display an optional remote hero image URL."""
    props = CAR_ARTICLES_MAPPING["properties"]
    assert "hero_image_url" in props
    assert props["hero_image_url"]["type"] == "keyword"


def test_dynamic_is_string_false():
    """Pitfall 6: dynamic must be the string 'false', not Python False."""
    assert CAR_ARTICLES_MAPPING["dynamic"] == "false"
    assert isinstance(CAR_ARTICLES_MAPPING["dynamic"], str)


def test_ensure_index_idempotent():
    """Calling ensure_index twice with ignore_status=[400] must not raise."""
    mock_client = MagicMock()
    mock_client.options.return_value.cluster.health.return_value = {
        "status": "yellow",
        "timed_out": False,
    }
    ensure_index(mock_client)
    ensure_index(mock_client)
    # options(ignore_status=[400]) must be used for each create invocation
    assert mock_client.options.call_args_list.count(
        call(
            ignore_status=[400],
            request_timeout=es_schema.INDEX_REQUEST_TIMEOUT_SECONDS,
        )
    ) == 2


def test_ensure_index_waits_for_active_primary_shard():
    """ensure_index waits until car_articles has an active primary shard."""
    mock_client = MagicMock()
    optioned_client = mock_client.options.return_value
    optioned_client.cluster.health.return_value = {"status": "yellow", "timed_out": False}

    ensure_index(mock_client)

    mock_client.options.assert_any_call(
        request_timeout=es_schema.INDEX_REQUEST_TIMEOUT_SECONDS,
    )
    optioned_client.cluster.health.assert_called_once_with(
        index="car_articles",
        wait_for_status="yellow",
        wait_for_active_shards=1,
        timeout="120s",
    )


def test_ensure_index_raises_when_shard_not_active():
    """ensure_index raises before bulk indexing if car_articles stays red/timed out."""
    mock_client = MagicMock()
    mock_client.options.return_value.cluster.health.return_value = {
        "status": "red",
        "timed_out": True,
    }

    with pytest.raises(RuntimeError, match="car_articles index is not ready"):
        ensure_index(mock_client)


def test_ensure_index_includes_allocation_explain_in_failure():
    """Shard allocation diagnostics are attached to the readiness failure."""
    mock_client = MagicMock()
    optioned_client = mock_client.options.return_value
    optioned_client.cluster.health.return_value = {
        "status": "red",
        "timed_out": True,
    }
    optioned_client.cluster.allocation_explain.return_value = {
        "index": "car_articles",
        "shard": 0,
        "primary": True,
        "current_state": "unassigned",
        "unassigned_info": {
            "reason": "INDEX_CREATED",
            "details": "failed shard on node-1",
        },
    }

    with pytest.raises(RuntimeError, match="allocation_explain"):
        ensure_index(mock_client)
