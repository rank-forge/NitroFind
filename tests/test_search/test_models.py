"""
Unit tests for nitrofind.search.models — RLVN-01..04 coverage.

Test strategy:
  - Unit: test ArticleResult construction and from_es_hit classmethod
  - No ES connection or Qt event loop required

Requirement coverage:
  RLVN-01: ArticleResult has published_at field with safe default None
  RLVN-02: ArticleResult has word_count field with safe default 0
  RLVN-03: ArticleResult has has_infobox field with safe default False
  RLVN-04: ArticleResult carries score field from ES _score

Anti-patterns avoided:
  Direct dict access in from_es_hit — all access via .get() with safe defaults
"""

import pytest

from nitrofind.search.models import ArticleResult


# ---------------------------------------------------------------------------
# ArticleResult construction
# ---------------------------------------------------------------------------


def test_article_result_construction_required_fields():
    """ArticleResult can be constructed with required fields."""
    r = ArticleResult(title="Ferrari 308", url="http://x", source_domain="wikipedia.org", score=1.5)
    assert r.title == "Ferrari 308"
    assert r.url == "http://x"
    assert r.source_domain == "wikipedia.org"
    assert r.score == 1.5


def test_article_result_highlight_fields_default_empty_list():
    """highlight_title and highlight_body default to empty lists."""
    r = ArticleResult(title="T", url="U", source_domain="S", score=0.0)
    assert r.highlight_title == []
    assert r.highlight_body == []


def test_article_result_optional_fields_have_defaults():
    """Optional fields have correct default values."""
    r = ArticleResult(title="T", url="U", source_domain="S", score=0.0)
    assert r.excerpt == ""
    assert r.published_at is None
    assert r.word_count == 0
    assert r.has_infobox is False
    assert r.manufacturer is None
    assert r.era_bucket is None
    assert r.body_style is None


def test_article_result_all_fields():
    """ArticleResult has exactly the expected set of fields."""
    expected_fields = {
        "title", "url", "source_domain", "score",
        "excerpt", "published_at", "word_count", "has_infobox",
        "manufacturer", "era_bucket", "body_style",
        "highlight_title", "highlight_body",
        "body", "body_html",
    }
    import dataclasses
    actual_fields = {f.name for f in dataclasses.fields(ArticleResult)}
    assert actual_fields == expected_fields


# ---------------------------------------------------------------------------
# from_es_hit classmethod
# ---------------------------------------------------------------------------


def test_from_es_hit_extracts_source_fields():
    """from_es_hit extracts title, url, source_domain from _source."""
    hit = {
        "_score": 1.5,
        "_source": {"title": "T", "url": "U", "source_domain": "S"},
        "highlight": {},
    }
    r = ArticleResult.from_es_hit(hit)
    assert r.title == "T"
    assert r.url == "U"
    assert r.source_domain == "S"
    assert r.score == 1.5
    assert r.highlight_title == []
    assert r.highlight_body == []


def test_from_es_hit_extracts_highlight_fragments():
    """from_es_hit extracts body highlight fragments."""
    hit = {
        "_score": 0.9,
        "_source": {},
        "highlight": {"body": ["<b>Ferrari</b> 308 was..."]},
    }
    r = ArticleResult.from_es_hit(hit)
    assert r.highlight_body == ["<b>Ferrari</b> 308 was..."]
    assert r.highlight_title == []


def test_from_es_hit_missing_fields_use_defaults():
    """from_es_hit with empty hit dict returns instance with safe defaults — no KeyError."""
    r = ArticleResult.from_es_hit({})
    assert r.title == ""
    assert r.url == ""
    assert r.source_domain == ""
    assert r.score == 0.0
    assert r.excerpt == ""
    assert r.published_at is None
    assert r.word_count == 0
    assert r.has_infobox is False
    assert r.manufacturer is None
    assert r.era_bucket is None
    assert r.body_style is None
    assert r.highlight_title == []
    assert r.highlight_body == []


def test_from_es_hit_extracts_all_source_fields():
    """from_es_hit correctly maps all _source fields to ArticleResult."""
    hit = {
        "_score": 2.0,
        "_source": {
            "title": "Porsche 911",
            "url": "https://en.wikipedia.org/wiki/Porsche_911",
            "source_domain": "en.wikipedia.org",
            "excerpt": "The Porsche 911 is a sports car.",
            "published_at": "2020-01-01",
            "word_count": 5000,
            "has_infobox": True,
            "manufacturer": "Porsche",
            "era_bucket": "1960s",
            "body_style": "coupe",
        },
        "highlight": {
            "title": ["<b>Porsche</b> 911"],
            "body": ["iconic sports car"],
        },
    }
    r = ArticleResult.from_es_hit(hit)
    assert r.title == "Porsche 911"
    assert r.excerpt == "The Porsche 911 is a sports car."
    assert r.published_at == "2020-01-01"
    assert r.word_count == 5000
    assert r.has_infobox is True
    assert r.manufacturer == "Porsche"
    assert r.era_bucket == "1960s"
    assert r.body_style == "coupe"
    assert r.highlight_title == ["<b>Porsche</b> 911"]
    assert r.highlight_body == ["iconic sports car"]


# ---------------------------------------------------------------------------
# W0-EXT-01: body field tests
# ---------------------------------------------------------------------------


def test_article_result_body_default_empty_string():
    """ArticleResult.body defaults to empty string (W0-EXT-01)."""
    r = ArticleResult(title="x", url="y", source_domain="z", score=1.0)
    assert r.body == ""


def test_body_html_field_default():
    """ArticleResult.body_html defaults to empty string (Phase 9)."""
    r = ArticleResult(title="x", url="y", source_domain="z", score=1.0)
    assert r.body_html == ""


def test_article_result_body_html_from_es_hit():
    """from_es_hit populates body_html from _source and falls back to empty string when missing."""
    hit_with_body_html = {
        "_score": 1.0,
        "_source": {
            "title": "T", "url": "U", "source_domain": "D",
            "body_html": "<div><table><tr><td>Spec</td></tr></table></div>",
        },
    }
    r = ArticleResult.from_es_hit(hit_with_body_html)
    assert r.body_html == "<div><table><tr><td>Spec</td></tr></table></div>"

    hit_no_body_html = {
        "_score": 1.0,
        "_source": {"title": "T", "url": "U", "source_domain": "D"},
    }
    r2 = ArticleResult.from_es_hit(hit_no_body_html)
    assert r2.body_html == ""


def test_article_result_body_from_es_hit():
    """from_es_hit populates body from _source and falls back to empty string when missing."""
    # Case 1: body present in _source
    hit_with_body = {
        "_score": 1.0,
        "_source": {
            "title": "T",
            "url": "U",
            "source_domain": "D",
            "body": "full text here",
        },
    }
    r = ArticleResult.from_es_hit(hit_with_body)
    assert r.body == "full text here"

    # Case 2: body missing from _source — should fall back to empty string
    hit_no_body = {
        "_score": 1.0,
        "_source": {
            "title": "T",
            "url": "U",
            "source_domain": "D",
        },
    }
    r2 = ArticleResult.from_es_hit(hit_no_body)
    assert r2.body == ""
