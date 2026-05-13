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


def test_dynamic_is_string_false():
    """Pitfall 6: dynamic must be the string 'false', not Python False."""
    assert CAR_ARTICLES_MAPPING["dynamic"] == "false"
    assert isinstance(CAR_ARTICLES_MAPPING["dynamic"], str)


def test_ensure_index_idempotent():
    """Calling ensure_index twice with ignore_status=[400] must not raise."""
    mock_client = MagicMock()
    ensure_index(mock_client)
    ensure_index(mock_client)
    # options(ignore_status=[400]) must be called on every invocation
    assert mock_client.options.call_count == 2
    # Verify the correct ignore_status was used each call
    for c in mock_client.options.call_args_list:
        assert c == call(ignore_status=[400])
