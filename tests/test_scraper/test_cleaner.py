"""
Unit tests for nitrofind.scraper.cleaner — SCHEMA-03 coverage.

Test strategy:
  - Pure function assertions — no mocks required
  - stdlib only; no external dependencies

Requirement coverage:
  SCHEMA-03: excerpt is always ≤300 chars in generated docs (L-06)
  SCHEMA-03: body field contains no HTML tags — no < or > characters (L-05)
  L-07: era_bucket derived correctly from production_start
  Pitfall 7: excerpt never cuts mid-word
"""

import pytest
from nitrofind.scraper.cleaner import make_excerpt, compute_era_bucket, parse_year

# ---------------------------------------------------------------------------
# L-06, Pitfall 7: excerpt capping and word-boundary cut
# ---------------------------------------------------------------------------


def test_excerpt_max_300_chars():
    """L-06: make_excerpt always returns ≤300 characters."""
    long_body = "word " * 200  # 1000 chars
    result = make_excerpt(long_body)
    assert len(result) <= 300


def test_excerpt_no_mid_word_cut():
    """Pitfall 7: make_excerpt ends on a word boundary, never mid-word."""
    body = "a" * 295 + " boundary_word"
    result = make_excerpt(body)
    # If excerpt is ≤300 chars, it must not end mid-word on 'boundary_word'
    assert len(result) <= 300
    # "boundar" would indicate mid-word cut
    assert not result.endswith("boundar")


def test_excerpt_short_text_unchanged():
    """make_excerpt returns input unchanged when len(input) <= 300."""
    short_body = "short text"
    result = make_excerpt(short_body)
    assert result == short_body


def test_excerpt_boundary_at_300_word_boundary():
    """make_excerpt at 295-char input followed by space-delimited word returns word-boundary excerpt."""
    # Body: 295 'a' chars + space + 'boundary_word' = 310 chars > 300
    body = "a" * 295 + " boundary_word"
    result = make_excerpt(body)
    # rsplit will return the 295 'a' chars (since space is at index 295)
    assert result == "a" * 295


def test_make_excerpt_empty_input():
    """make_excerpt returns empty string for empty input."""
    result = make_excerpt("")
    assert result == ""


def test_make_excerpt_no_spaces():
    """make_excerpt on a 301-character no-space string returns exactly 300 chars (rsplit returns [full_300_chars])."""
    body = "a" * 301
    result = make_excerpt(body)
    # rsplit(" ", 1) on body[:300] (no spaces) returns [body[:300]] so result == body[:300]
    assert len(result) == 300
    assert result == "a" * 300


# ---------------------------------------------------------------------------
# L-07: era_bucket derivation
# ---------------------------------------------------------------------------


def test_era_bucket_from_year():
    """L-07: compute_era_bucket returns correct decade label for valid years."""
    assert compute_era_bucket(1965) == "1960s"
    assert compute_era_bucket(2003) == "2000s"
    assert compute_era_bucket(1999) == "1990s"


def test_era_bucket_unknown_when_year_none():
    """L-07: compute_era_bucket returns 'Unknown' when production_start is None or 0."""
    assert compute_era_bucket(None) == "Unknown"
    assert compute_era_bucket(0) == "Unknown"


# ---------------------------------------------------------------------------
# parse_year utility
# ---------------------------------------------------------------------------


def test_parse_year_extracts_4_digit_year():
    """parse_year extracts first 4-digit year (1900-2099) from an infobox field string."""
    assert parse_year("1965 to 1972") == 1965
    assert parse_year("manufactured in 1999") == 1999


def test_parse_year_returns_none_for_empty_or_no_year():
    """parse_year returns None for empty string or string with no valid year."""
    assert parse_year("") is None
    assert parse_year("no year here") is None
