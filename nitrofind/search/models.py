"""
nitrofind.search.models — Typed result container for search hits.

Exports:
  ArticleResult  — dataclass wrapping a single ES hit with safe field defaults

Requirement coverage:
  RLVN-01: published_at field exposed for recency decay display; safe None default
  RLVN-02: word_count field exposed for article length signal; safe 0 default
  RLVN-03: has_infobox field exposed for infobox boost signal; safe False default
  RLVN-04: score field carries ES _score value for ranking display

Anti-patterns avoided:
  Direct dict key access in from_es_hit — all access via .get() with safe defaults
  so that an empty or partial ES hit dict never raises KeyError
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
    excerpt: str = ""
    published_at: str | None = None
    word_count: int = 0
    has_infobox: bool = False
    manufacturer: str | None = None
    era_bucket: str | None = None
    body_style: str | None = None

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
        raw_score = hit.get("_score")
        score = float(raw_score) if raw_score is not None else 0.0
        raw_word_count = src.get("word_count")
        word_count = int(raw_word_count) if raw_word_count is not None else 0
        return cls(
            title=src.get("title", ""),
            url=src.get("url", ""),
            source_domain=src.get("source_domain", ""),
            score=score,
            excerpt=src.get("excerpt", ""),
            published_at=src.get("published_at"),
            word_count=word_count,
            has_infobox=src.get("has_infobox", False),
            manufacturer=src.get("manufacturer"),
            era_bucket=src.get("era_bucket"),
            body_style=src.get("body_style"),
            highlight_title=highlights.get("title", []),
            highlight_body=highlights.get("body", []),
        )
