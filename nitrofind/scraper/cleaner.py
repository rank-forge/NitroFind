"""
nitrofind.scraper.cleaner — Text cleaning and field derivation utilities.

Exports:
  make_excerpt       — truncates body text to ≤300 chars at word boundary (L-06)
  compute_era_bucket — derives decade label from production_start year (L-07)
  parse_year         — extracts 4-digit year from infobox field strings

Requirement coverage:
  L-05: body field contains plain text only (callers must pass pre-stripped text)
  L-06: excerpt capped at 300 characters, no mid-word cut (Pitfall 7)
  L-07: era_bucket formula f"{(year // 10) * 10}s"; "Unknown" when year is None
  SCHEMA-03: enforced by make_excerpt + body passthrough

Anti-patterns avoided:
  Pitfall 7: excerpt never cuts mid-word — uses rsplit(" ", 1)[0] for word-boundary trim
"""

import re
from typing import Optional


def make_excerpt(body_text: str) -> str:
    """Return ≤300-char excerpt ending on a word boundary (L-06, Pitfall 7).

    When len(body_text) <= 300, returns body_text unchanged.
    Otherwise truncates at 300 chars and trims to the last word boundary
    using rsplit(" ", 1)[0]. Handles empty string (returns "").
    When no space exists within the first 300 chars, returns body_text[:300].
    """
    if len(body_text) <= 300:
        return body_text
    return body_text[:300].rsplit(" ", 1)[0]


def compute_era_bucket(production_start: Optional[int]) -> str:
    """Derive decade label from production year (L-07).

    Returns "Unknown" when production_start is None, 0, or outside the
    valid automotive range 1900–2099 (WR-03). Any out-of-range value (including
    negative years) would produce a nonsensical bucket string.
    Otherwise returns f"{(production_start // 10) * 10}s" (L-07 exact formula).

    Examples:
        compute_era_bucket(1965) == "1960s"
        compute_era_bucket(2003) == "2000s"
        compute_era_bucket(None) == "Unknown"
        compute_era_bucket(0)    == "Unknown"
        compute_era_bucket(-500) == "Unknown"
        compute_era_bucket(2100) == "Unknown"
    """
    if not production_start or production_start < 1900 or production_start > 2099:
        return "Unknown"
    return f"{(production_start // 10) * 10}s"


def parse_year(raw: str) -> Optional[int]:
    """Extract first 4-digit year (1900-2099) from an infobox field value string.

    Limits years to 1900-2099 per L-07 reasonable car-era range.
    Returns None if no matching 4-digit sequence is found, or if raw is empty/None.

    Examples:
        parse_year("1965 to 1972")      == 1965
        parse_year("manufactured in 1999") == 1999
        parse_year("")                  is None
        parse_year("no year here")      is None
    """
    if not raw:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", raw)
    return int(match.group()) if match else None
