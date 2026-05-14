"""
nitrofind.scraper.cleaner — Text cleaning and field derivation utilities.

Exports:
  make_excerpt       — truncates body text to <=300 chars at word boundary (L-06)
  compute_era_bucket — derives decade label from production_start year (L-07)
  parse_year         — extracts 4-digit year from infobox field strings

Requirement coverage:
  L-05: body field contains plain text only (callers must pass pre-stripped text)
  L-06: excerpt capped at 300 characters, no mid-word cut (Pitfall 7)
  L-07: era_bucket formula f"{(year // 10) * 10}s"; "Unknown" when year is None
  SCHEMA-03: enforced by make_excerpt + body passthrough

Anti-patterns avoided:
  Pitfall 7: excerpt ends at word boundary — body_text[:300].rsplit(" ", 1)[0]
"""

import re
from typing import Optional


def make_excerpt(body_text: str) -> str:
    """Return <=300-char excerpt ending on a word boundary (L-06, Pitfall 7)."""
    if len(body_text) <= 300:
        return body_text
    return body_text[:300].rsplit(" ", 1)[0]


def compute_era_bucket(production_start: Optional[int]) -> str:
    """Derive decade label from production year (L-07).

    Returns "Unknown" when production_start is None or 0.
    """
    if not production_start:
        return "Unknown"
    return f"{(production_start // 10) * 10}s"


def parse_year(raw: str) -> Optional[int]:
    """Extract first 4-digit year from an infobox field value string.

    Returns None if no 4-digit sequence in range 1900-2099 is found.
    """
    if not raw:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", raw)
    return int(match.group()) if match else None
