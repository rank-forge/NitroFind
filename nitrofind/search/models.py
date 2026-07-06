"""
nitrofind.search.models — Typed result container for search hits.

Exports:
  ArticleResult  — dataclass wrapping a single ES hit with safe field defaults

Requirement coverage:
  RLVN-01: published_at field exposed for recency decay display; safe None default
  RLVN-02: word_count field exposed for article length signal; safe 0 default
  RLVN-03: has_infobox field exposed for infobox boost signal; safe False default
  RLVN-04: score field carries ES _score value for ranking display

W0-EXT-01 (Phase 4):
  body field added for SRCH-03 full-article detail pane. Populated from ES
  _source["body"] via from_es_hit; defaults to empty string when not present.

Anti-patterns avoided:
  Direct dict key access in from_es_hit — all access via .get() with safe defaults
  so that an empty or partial ES hit dict never raises KeyError
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Safe type-conversion helpers (WR-04)
# ---------------------------------------------------------------------------

def _safe_float(value: object, default: float = 0.0) -> float:
    """Convert value to float, returning default on TypeError/ValueError.

    Guards from_es_hit against malformed ES data (e.g. _score="unknown")
    that would otherwise propagate as ValueError through the list comprehension
    in _SearchWorker.run() and cause the entire search to fail.
    """
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    """Convert value to int via float, returning default on TypeError/ValueError.

    Uses int(float(value)) so string-encoded floats like "3.5" are handled
    gracefully (truncated to 3) rather than raising ValueError as int("3.5")
    would. Guards from_es_hit against malformed word_count values.
    """
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


@dataclass
class ArticleResult:
    """Single search result returned by SearchEngine.

    highlight_title: list of HTML-tagged title fragments from ES highlighter.
    highlight_body:  list of HTML-tagged body fragments from ES highlighter.
    Empty lists when ES returns no highlights for a field.
    """

    # Required fields (no default — must be supplied at construction time)
    title: str
    url: str
    source_domain: str
    score: float

    # Optional fields with safe defaults matching ES mapping types
    article_id: str = ""
    excerpt: str = ""
    body: str = ""          # W0-EXT-01: full article text for SRCH-03 detail pane
    body_html: str = ""     # Phase 9: rendered HTML with <table> for article view
    hero_image_url: str = ""
    published_at: str | None = None
    word_count: int = 0
    has_infobox: bool = False
    manufacturer: str | None = None
    era_bucket: str | None = None
    body_style: str | None = None
    production_start: int | None = None
    production_end: int | None = None
    country_of_origin: str | None = None
    specs: dict = field(default_factory=dict)

    # Highlight fragments — must use field(default_factory=list) to avoid shared mutable default
    highlight_title: list[str] = field(default_factory=list)
    highlight_body: list[str] = field(default_factory=list)

    @classmethod
    def from_es_hit(cls, hit: dict) -> "ArticleResult":
        """Construct from a raw ES response hit dict.

        All field access uses .get() with safe defaults so an empty or partial
        hit dict never raises KeyError. This matches the RLVN-01..04 requirement
        that missing fields receive neutral values rather than scoring errors.

        Args:
            hit: A single dict from resp["hits"]["hits"]. May be partially
                 populated or empty — all cases handled safely.

        Returns:
            ArticleResult instance with fields populated from hit, or safe
            defaults for any missing fields.
        """
        src = hit.get("_source", {})
        highlights = hit.get("highlight", {})
        # WR-04: use safe helpers so non-numeric strings (e.g. "unknown", "")
        # or mixed types from schema evolution/index corruption never raise
        # ValueError and propagate as a full search failure.
        score = _safe_float(hit.get("_score"), 0.0)
        word_count = _safe_int(src.get("word_count"), 0)
        return cls(
            title=src.get("title", ""),
            url=src.get("url", ""),
            source_domain=src.get("source_domain", ""),
            score=score,
            article_id=src.get("article_id", ""),
            excerpt=src.get("excerpt", ""),
            body=src.get("body", ""),  # W0-EXT-01
            body_html=src.get("body_html", ""),
            hero_image_url=src.get("hero_image_url", ""),
            published_at=src.get("published_at"),
            word_count=word_count,
            has_infobox=src.get("has_infobox", False),
            manufacturer=src.get("manufacturer"),
            era_bucket=src.get("era_bucket"),
            body_style=src.get("body_style"),
            production_start=src.get("production_start"),
            production_end=src.get("production_end"),
            country_of_origin=src.get("country_of_origin"),
            specs=src.get("specs") if isinstance(src.get("specs"), dict) else {},
            highlight_title=highlights.get("title", []),
            highlight_body=highlights.get("body", []),
        )
