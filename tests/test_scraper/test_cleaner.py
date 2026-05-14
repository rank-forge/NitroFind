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

# ---------------------------------------------------------------------------
# L-06, Pitfall 7: excerpt capping and word-boundary cut
# ---------------------------------------------------------------------------


def test_excerpt_max_300_chars():
    """L-06: make_excerpt always returns ≤300 characters."""
    pytest.importorskip("nitrofind.scraper.cleaner", reason="Wave 1 — cleaner utilities not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_excerpt_no_mid_word_cut():
    """Pitfall 7: make_excerpt ends on a word boundary, never mid-word."""
    pytest.importorskip("nitrofind.scraper.cleaner", reason="Wave 1 — cleaner utilities not yet implemented")
    pytest.skip("Wave 1 implementation")


# ---------------------------------------------------------------------------
# L-07: era_bucket derivation
# ---------------------------------------------------------------------------


def test_era_bucket_from_year():
    """L-07: compute_era_bucket returns correct decade label for a valid year."""
    pytest.importorskip("nitrofind.scraper.cleaner", reason="Wave 1 — cleaner utilities not yet implemented")
    pytest.skip("Wave 1 implementation")


def test_era_bucket_unknown_when_year_none():
    """L-07: compute_era_bucket returns 'Unknown' when production_start is None or 0."""
    pytest.importorskip("nitrofind.scraper.cleaner", reason="Wave 1 — cleaner utilities not yet implemented")
    pytest.skip("Wave 1 implementation")


# ---------------------------------------------------------------------------
# parse_year utility
# ---------------------------------------------------------------------------


def test_parse_year_extracts_4_digit_year():
    """parse_year extracts first 4-digit year (1900-2099) from an infobox field string."""
    pytest.importorskip("nitrofind.scraper.cleaner", reason="Wave 1 — cleaner utilities not yet implemented")
    pytest.skip("Wave 1 implementation")
