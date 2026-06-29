"""
nitrofind.search.query_builder — Elasticsearch function_score query construction.

Exports:
  build_function_score_query  — four-function function_score dict (RLVN-01..04)
  build_filter_clauses        — term filter list for manufacturer, era, body_style
  build_search_body           — complete ES search request body with highlight and _source

Requirement coverage:
  RLVN-01: Gaussian recency decay on published_at with exists-filter split;
           undated articles receive DEFAULT_MISSING_PUBLISHED_SCORE fallback
  RLVN-02: field_value_factor with log1p modifier on word_count (log1p handles 0 safely)
  RLVN-03: weight function conditioned on has_infobox=True term filter
  RLVN-04: score_mode=sum (missing signal ≠ zero result), boost_mode=multiply
           (BM25 text relevance acts as final multiplier)

Anti-patterns avoided:
  body= parameter — flat keyword API used in engine.py (ES 8.x deprecation)
  log modifier — log1p used instead (log(0) is undefined; log1p(0)=0 is safe)
  "2y" or "24m" in scale — "730d" used (year/month units unsupported in ES decay)
  Unfiltered gauss on published_at — exists-filter split prevents missing-field=1.0 bug
  Unbounded size param — MAX_RESULT_SIZE cap enforced in build_search_body (T-03-02)
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

DEFAULT_RECENCY_WEIGHT: float = 1.5
DEFAULT_LENGTH_WEIGHT: float = 1.0
DEFAULT_INFOBOX_WEIGHT: float = 0.5
DEFAULT_MISSING_PUBLISHED_SCORE: float = 0.3
MAX_RESULT_SIZE: int = 100   # security: cap unbounded size requests (T-03-02)


# ---------------------------------------------------------------------------
# Free functions (RLVN-01..04, Pattern 4)
# ---------------------------------------------------------------------------


def build_function_score_query(
    query_text: str,
    recency_weight: float = DEFAULT_RECENCY_WEIGHT,
    length_weight: float = DEFAULT_LENGTH_WEIGHT,
    infobox_weight: float = DEFAULT_INFOBOX_WEIGHT,
    missing_published_score: float = DEFAULT_MISSING_PUBLISHED_SCORE,
) -> dict:
    """Build the full function_score query dict for a text search.

    Combines four scoring signals:
      0. Gaussian recency decay for dated articles (RLVN-01, exists filter split)
      1. Fixed weight fallback for articles without published_at (RLVN-01)
      2. log1p(word_count) field value factor for article length (RLVN-02)
      3. Boolean weight boost for articles with an infobox (RLVN-03)

    All four combine with score_mode=sum so a missing signal never zeroes a
    result. boost_mode=multiply lets BM25 text relevance act as the final
    multiplier (RLVN-04).

    Args:
        query_text:              User's search text placed in multi_match query.
        recency_weight:          Weight for the Gaussian decay function (fn0).
        length_weight:           Weight for the field_value_factor function (fn2).
        infobox_weight:          Weight for the infobox boolean boost (fn3).
        missing_published_score: Fixed score for articles without published_at (fn1).

    Returns:
        dict with single top-level key "function_score" containing the full
        function_score query structure ready for use as an ES query parameter.
    """
    # Phrase detection: startswith+endswith " and len > 2 (Pitfall 3 guard)
    _is_phrase = (
        query_text.startswith('"')
        and query_text.endswith('"')
        and len(query_text) > 2
    )

    if _is_phrase:
        # Phrase path: strip quotes; NO fuzziness (ES returns 400 if fuzziness
        # is present with type:phrase — Pitfall 1 in RESEARCH.md)
        _phrase_text = query_text[1:-1].strip()
        base_query = {
            "multi_match": {
                "query": _phrase_text,
                "fields": ["title^3", "body"],
                "type": "phrase",
            }
        }
    else:
        # Default path: fuzzy best_fields (QURY-01)
        base_query = {
            "multi_match": {
                "query": query_text,
                "fields": ["title^3", "body"],
                "type": "best_fields",
                "fuzziness": "AUTO",
                "prefix_length": 1,
            }
        }

    return {
        "function_score": {
            "query": base_query,
            "functions": [
                # RLVN-01: Gaussian recency decay — only for dated articles.
                # Filter avoids the missing-field=1.0 bug: without this filter,
                # articles with no published_at receive a perfect recency score of
                # 1.0 instead of the intended fallback value.
                # [CITED: github.com/elastic/elasticsearch/issues/7788]
                {
                    "filter": {"exists": {"field": "published_at"}},
                    "gauss": {
                        "published_at": {
                            "origin": "now",
                            "scale": "730d",    # 2-year scale; "2y" unsupported by ES
                            "offset": "30d",    # no penalty within 30 days of today
                            "decay": 0.5,       # score halves at scale distance (2 years)
                        }
                    },
                    "weight": recency_weight,
                },
                # RLVN-01 (fallback): articles WITHOUT published_at receive a fixed
                # fractional score instead of defaulting to 1.0 (perfect recency).
                # This is the two-function split workaround for the missing-field bug.
                {
                    "filter": {"bool": {"must_not": {"exists": {"field": "published_at"}}}},
                    "weight": missing_published_score,
                },
                # RLVN-02: log1p(word_count) signals article completeness/length.
                # log1p handles word_count=0 safely (log(1+0)=0); missing=1 provides
                # a neutral fallback for articles with no word_count field.
                {
                    "field_value_factor": {
                        "field": "word_count",
                        "modifier": "log1p",
                        "factor": 1.0,
                        "missing": 1,
                    },
                    "weight": length_weight,
                },
                # RLVN-03: boolean boost for articles with structured infobox data.
                # Infobox presence signals a well-structured, spec-rich article.
                {
                    "filter": {"term": {"has_infobox": True}},
                    "weight": infobox_weight,
                },
            ],
            "score_mode": "sum",       # RLVN-04: additive — missing signal ≠ zero result
            "boost_mode": "multiply",  # RLVN-04: BM25 text score acts as final multiplier
        }
    }


def build_filter_clauses(
    manufacturer: str | None = None,
    era_bucket: str | None = None,
    body_style: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    country: str | None = None,
) -> list[dict]:
    """Return a list of term filter dicts for the bool.filter context.

    These go inside the function_score's wrapped bool query as filter clauses,
    NOT as post_filter. This approach means filters gate which documents are
    scored — ES can cache filter results in the filter cache.

    Use post_filter only if aggregations must show unfiltered counts (Phase 4
    decision — deferred).

    Args:
        manufacturer: Exact manufacturer keyword to filter on, or None to skip.
        era_bucket:   Exact era_bucket keyword (e.g. "1960s"), or None to skip.
        body_style:   Exact body_style keyword (e.g. "coupe"), or None to skip.
        year_from:    Lower bound of production year range (inclusive), or None to skip.
        year_to:      Upper bound of production year range (inclusive), or None to skip.
        country:      Exact country_of_origin keyword (e.g. "Germany"), or None to skip.

    Returns:
        List of ES term/range filter dicts. Empty list when all args are None/falsy.
    """
    filters = []
    if manufacturer:
        filters.append({"term": {"manufacturer": manufacturer}})
    if era_bucket:
        filters.append({"term": {"era_bucket": era_bucket}})
    if body_style:
        filters.append({"term": {"body_style": body_style}})
    # FILT-01: interval overlap — article production period intersects [year_from, year_to]
    # Two clauses required: production_end >= year_from AND production_start <= year_to
    # Use `is not None` (not truthiness) so that integer 0 is a valid year.
    if year_from is not None:
        filters.append({"range": {"production_end": {"gte": year_from}}})
    if year_to is not None:
        filters.append({"range": {"production_start": {"lte": year_to}}})
    # FILT-02: exact country of origin match (keyword field — case-sensitive)
    if country:
        filters.append({"term": {"country_of_origin": country}})
    return filters


def _build_sort_clauses(sort: str | None) -> list[dict] | None:
    """Return ES sort array for the given sort mode, or None for relevance.

    None signals the caller to omit the sort kwarg entirely, which lets ES
    default to _score desc (relevance ranking).

    Args:
        sort: "date" | "size" | "relevance" | None

    Returns:
        list with one sort dict for "date" or "size"; None for anything else.
    """
    if sort == "date":
        return [{"published_at": {"order": "desc", "missing": "_last", "unmapped_type": "date"}}]
    if sort == "size":
        return [{"word_count": {"order": "desc"}}]
    return None  # "relevance" or unknown → ES default _score desc


def build_search_body(
    query_text: str,
    filters: list[dict] | None = None,
    size: int = 20,
    from_: int = 0,
    sort: str | None = None,
    recency_weight: float = DEFAULT_RECENCY_WEIGHT,
    length_weight: float = DEFAULT_LENGTH_WEIGHT,
    infobox_weight: float = DEFAULT_INFOBOX_WEIGHT,
    missing_published_score: float = DEFAULT_MISSING_PUBLISHED_SCORE,
) -> dict:
    """Assemble the complete ES search request body dict.

    Filters are applied inside the function_score.query bool.filter context,
    so they gate which documents are scored. Size is clamped to MAX_RESULT_SIZE
    to prevent denial-of-service via unbounded result requests (T-03-02).

    Weight parameters are forwarded to build_function_score_query so callers
    can tune scoring without bypassing this entry point.

    Args:
        query_text:              User's search text forwarded to build_function_score_query.
        filters:                 List of term filter dicts from build_filter_clauses, or None/[].
        size:                    Number of results to return. Clamped to MAX_RESULT_SIZE (100).
        from_:                   Offset for pagination (0-based).
        sort:                    Sort mode: "date" | "size" | "relevance" | None.
                                 "relevance" and None omit the sort key (ES default _score desc).
        recency_weight:          Weight for Gaussian decay function (forwarded to function_score).
        length_weight:           Weight for field_value_factor length signal.
        infobox_weight:          Weight for infobox boolean boost.
        missing_published_score: Fixed score for articles without published_at.

    Returns:
        dict ready to be passed to client.search() as keyword arguments.
        Keys: "query", "highlight", "size", "from", "_source" (+ "sort" when applicable).
    """
    fs_query = build_function_score_query(
        query_text,
        recency_weight=recency_weight,
        length_weight=length_weight,
        infobox_weight=infobox_weight,
        missing_published_score=missing_published_score,
    )

    if filters:
        # Wrap the function_score's base query in a bool with filter context.
        # This ensures filters are applied in ES filter cache context for performance.
        inner_query = fs_query["function_score"]["query"]
        fs_query["function_score"]["query"] = {
            "bool": {
                "must": [inner_query],
                "filter": filters,
            }
        }

    result = {
        "query": fs_query,
        "highlight": {
            "fields": {
                "title": {
                    "fragment_size": 150,
                    "number_of_fragments": 1,
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"],
                },
                "body": {
                    "fragment_size": 300,
                    "number_of_fragments": 2,
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"],
                },
            }
        },
        "size": max(0, min(size, MAX_RESULT_SIZE)),   # T-03-02: clamp to [0, MAX_RESULT_SIZE]
        "from": max(0, from_),                        # clamp to non-negative
        "_source": [
            "title", "url", "source_domain", "excerpt", "body", "body_html",
            "published_at", "word_count", "has_infobox",
            "manufacturer", "era_bucket", "body_style",
        ],
    }
    sort_clauses = _build_sort_clauses(sort)
    if sort_clauses is not None:
        result["sort"] = sort_clauses
    return result
