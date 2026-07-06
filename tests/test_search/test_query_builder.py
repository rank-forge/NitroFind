"""
Unit tests for nitrofind.search.query_builder — RLVN-01..04 coverage.

Test strategy:
  - Unit: assert dict structure of build_function_score_query output
  - Unit: assert filter clause list from build_filter_clauses
  - Unit: assert search body structure from build_search_body
  - No ES connection or Qt event loop required

Requirement coverage:
  RLVN-01: Gaussian decay function present with correct params; missing-field fallback
  RLVN-02: field_value_factor with log1p modifier on word_count
  RLVN-03: has_infobox weight function with term filter
  RLVN-04: score_mode=sum, boost_mode=multiply

Anti-patterns avoided:
  Pitfall 1: missing published_at must NOT score 1.0 — two-function split verified
  Pitfall 3: log modifier NOT used — log1p only
  Pitfall 4: year/month units NOT used — 730d only
"""

import pytest

from nitrofind.search.query_builder import (
    build_filter_clauses,
    build_function_score_query,
    build_search_body,
    DETAIL_SOURCE_FIELDS,
    MAX_RESULT_SIZE,
    DEFAULT_RECENCY_WEIGHT,
    DEFAULT_LENGTH_WEIGHT,
    DEFAULT_INFOBOX_WEIGHT,
    DEFAULT_MISSING_PUBLISHED_SCORE,
)


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_module_constants():
    """Module constants have expected values."""
    assert DEFAULT_RECENCY_WEIGHT == 1.5
    assert DEFAULT_LENGTH_WEIGHT == 1.0
    assert DEFAULT_INFOBOX_WEIGHT == 0.5
    assert DEFAULT_MISSING_PUBLISHED_SCORE == 0.3
    assert MAX_RESULT_SIZE == 100


# ---------------------------------------------------------------------------
# RLVN-04: score_mode and boost_mode
# ---------------------------------------------------------------------------


def test_score_and_boost_modes():
    """function_score uses score_mode=sum and boost_mode=multiply."""
    q = build_function_score_query("Ferrari")
    fs = q["function_score"]
    assert fs["score_mode"] == "sum"
    assert fs["boost_mode"] == "multiply"


def test_function_score_key_present():
    """build_function_score_query returns dict with 'function_score' key."""
    q = build_function_score_query("Ferrari")
    assert "function_score" in q


def test_function_score_has_four_functions():
    """function_score.functions has exactly 4 entries."""
    q = build_function_score_query("Ferrari")
    assert len(q["function_score"]["functions"]) == 4


def test_base_query_is_multi_match():
    """Base query inside function_score uses multi_match."""
    q = build_function_score_query("Ferrari")
    base = q["function_score"]["query"]
    assert "multi_match" in base
    assert base["multi_match"]["query"] == "Ferrari"
    assert "title^3" in base["multi_match"]["fields"]
    assert "body" in base["multi_match"]["fields"]
    assert base["multi_match"]["type"] == "best_fields"


# ---------------------------------------------------------------------------
# RLVN-01: Gaussian recency decay signal
# ---------------------------------------------------------------------------


def test_recency_decay_in_query():
    """Function 0 is the gauss decay for dated articles (published_at exists)."""
    q = build_function_score_query("Ferrari")
    fn0 = q["function_score"]["functions"][0]

    # Must have exists filter to avoid missing-field=1.0 bug
    assert "filter" in fn0
    assert fn0["filter"] == {"exists": {"field": "published_at"}}

    # Must have gauss key
    assert "gauss" in fn0
    gauss_params = fn0["gauss"]["published_at"]
    assert gauss_params["origin"] == "now"
    assert gauss_params["scale"] == "730d"   # MUST be 730d, not "2y" or "24m"
    assert gauss_params["offset"] == "30d"
    assert gauss_params["decay"] == 0.5

    # Weight must be recency_weight default
    assert fn0["weight"] == DEFAULT_RECENCY_WEIGHT


def test_missing_published_fallback():
    """Function 1 handles missing published_at with negated exists filter."""
    q = build_function_score_query("Ferrari")
    fn1 = q["function_score"]["functions"][1]

    # Must have bool.must_not.exists filter for missing field
    assert "filter" in fn1
    assert fn1["filter"] == {
        "bool": {"must_not": {"exists": {"field": "published_at"}}}
    }

    # Must NOT have gauss key — this is a weight-only fallback
    assert "gauss" not in fn1

    # Weight must be missing_published_score default
    assert fn1["weight"] == DEFAULT_MISSING_PUBLISHED_SCORE


def test_gauss_scale_not_2y():
    """Gauss scale uses '730d', not '2y' or '24m' (year units unsupported in ES)."""
    q = build_function_score_query("Ferrari")
    gauss_params = q["function_score"]["functions"][0]["gauss"]["published_at"]
    assert "2y" not in str(gauss_params)
    assert "24m" not in str(gauss_params)
    assert gauss_params["scale"] == "730d"


# ---------------------------------------------------------------------------
# RLVN-02: field_value_factor length signal
# ---------------------------------------------------------------------------


def test_length_signal_in_query():
    """Function 2 is field_value_factor with log1p modifier on word_count."""
    q = build_function_score_query("Ferrari")
    fn2 = q["function_score"]["functions"][2]

    assert "field_value_factor" in fn2
    fvf = fn2["field_value_factor"]
    assert fvf["field"] == "word_count"
    assert fvf["modifier"] == "log1p"   # MUST be log1p, not "log"
    assert fvf["factor"] == 1.0
    assert fvf["missing"] == 1          # safe fallback for missing word_count

    assert fn2["weight"] == DEFAULT_LENGTH_WEIGHT


def test_log1p_not_log_modifier():
    """field_value_factor uses 'log1p' modifier, never 'log'."""
    q = build_function_score_query("Ferrari")
    fn2 = q["function_score"]["functions"][2]
    assert fn2["field_value_factor"]["modifier"] == "log1p"
    # Explicitly check "log" alone is not used
    assert fn2["field_value_factor"]["modifier"] != "log"


# ---------------------------------------------------------------------------
# RLVN-03: has_infobox weight boost
# ---------------------------------------------------------------------------


def test_infobox_boost_in_query():
    """Function 3 is a weight function filtered to has_infobox=True articles."""
    q = build_function_score_query("Ferrari")
    fn3 = q["function_score"]["functions"][3]

    assert "filter" in fn3
    assert fn3["filter"] == {"term": {"has_infobox": True}}

    # Must NOT have gauss or field_value_factor — this is a weight-only boost
    assert "gauss" not in fn3
    assert "field_value_factor" not in fn3

    assert fn3["weight"] == DEFAULT_INFOBOX_WEIGHT


# ---------------------------------------------------------------------------
# build_filter_clauses
# ---------------------------------------------------------------------------


def test_build_filter_clauses_no_args_returns_empty():
    """build_filter_clauses() with no args returns empty list."""
    result = build_filter_clauses()
    assert result == []


def test_build_filter_clauses_manufacturer():
    """build_filter_clauses(manufacturer='BMW') returns term filter."""
    result = build_filter_clauses(manufacturer="BMW")
    assert result == [{"term": {"manufacturer": "BMW"}}]


def test_build_filter_clauses_era_bucket():
    """build_filter_clauses(era_bucket='1960s') returns term filter."""
    result = build_filter_clauses(era_bucket="1960s")
    assert result == [{"term": {"era_bucket": "1960s"}}]


def test_build_filter_clauses_body_style():
    """build_filter_clauses(body_style='coupe') returns term filter."""
    result = build_filter_clauses(body_style="coupe")
    assert result == [{"term": {"body_style": "coupe"}}]


def test_build_filter_clauses_multiple_args():
    """build_filter_clauses with multiple args returns multiple filters."""
    result = build_filter_clauses(manufacturer="BMW", era_bucket="1960s")
    assert len(result) == 2
    assert {"term": {"manufacturer": "BMW"}} in result
    assert {"term": {"era_bucket": "1960s"}} in result


# ---------------------------------------------------------------------------
# build_search_body
# ---------------------------------------------------------------------------


def test_build_search_body_keys():
    """build_search_body returns dict with required top-level keys."""
    body = build_search_body("Ferrari")
    assert "query" in body
    assert "highlight" in body
    assert "size" in body
    assert "from" in body
    assert "_source" in body


def test_build_search_body_size_clamped():
    """build_search_body clamps size to MAX_RESULT_SIZE (100)."""
    body = build_search_body("Ferrari", size=999)
    assert body["size"] == 100


def test_build_search_body_size_clamped_200():
    """build_search_body clamps size=200 to MAX_RESULT_SIZE."""
    body = build_search_body("Ferrari", size=200)
    assert body["size"] == 100


def test_build_search_body_default_size():
    """build_search_body default size is 20."""
    body = build_search_body("Ferrari")
    assert body["size"] == 20


def test_build_search_body_from_param():
    """build_search_body sets 'from' key from from_ parameter."""
    body = build_search_body("Ferrari", from_=10)
    assert body["from"] == 10


def test_build_search_body_source_fields():
    """build_search_body returns lightweight list fields only."""
    body = build_search_body("Ferrari")
    expected_source = [
        "article_id",
        "title",
        "url",
        "source_domain",
        "excerpt",
        "manufacturer",
        "era_bucket",
        "body_style",
    ]
    assert body["_source"] == expected_source
    assert "body" not in body["_source"]
    assert "body_html" not in body["_source"]
    assert "hero_image_url" not in body["_source"]


def test_build_search_body_source_fields_are_isolated_between_calls():
    """Mutating one result's _source does not contaminate later calls."""
    body1 = build_search_body("Ferrari")
    body1["_source"].append("mutated_field")

    body2 = build_search_body("Ferrari")
    assert "mutated_field" not in body2["_source"]


def test_detail_source_fields_include_article_payload():
    """DETAIL_SOURCE_FIELDS contains full article fields for the click-through endpoint."""
    assert DETAIL_SOURCE_FIELDS == [
        "article_id",
        "title",
        "url",
        "source_domain",
        "excerpt",
        "body",
        "body_html",
        "hero_image_url",
        "published_at",
        "word_count",
        "has_infobox",
        "image_count",
        "manufacturer",
        "production_start",
        "production_end",
        "era_bucket",
        "body_style",
        "country_of_origin",
        "specs",
    ]


def test_build_search_body_highlight_title():
    """build_search_body includes highlight config for title field."""
    body = build_search_body("Ferrari")
    title_hl = body["highlight"]["fields"]["title"]
    assert title_hl["fragment_size"] == 150
    assert title_hl["number_of_fragments"] == 1
    assert title_hl["pre_tags"] == ["<b>"]
    assert title_hl["post_tags"] == ["</b>"]


def test_build_search_body_highlight_body():
    """build_search_body includes highlight config for body field."""
    body = build_search_body("Ferrari")
    body_hl = body["highlight"]["fields"]["body"]
    assert body_hl["fragment_size"] == 300
    assert body_hl["number_of_fragments"] == 2
    assert body_hl["pre_tags"] == ["<b>"]
    assert body_hl["post_tags"] == ["</b>"]


def test_build_search_body_with_filters_wraps_query():
    """build_search_body wraps base query in bool.must when filters given."""
    filters = [{"term": {"manufacturer": "BMW"}}]
    body = build_search_body("Ferrari", filters=filters)
    inner = body["query"]["function_score"]["query"]
    assert "bool" in inner
    assert "must" in inner["bool"]
    assert "filter" in inner["bool"]
    assert inner["bool"]["filter"] == filters


def test_build_search_body_no_filters_no_bool_wrap():
    """build_search_body without filters keeps base query as multi_match."""
    body = build_search_body("Ferrari")
    inner = body["query"]["function_score"]["query"]
    # Without filters the inner query should be multi_match (not wrapped in bool)
    assert "multi_match" in inner


def test_build_search_body_empty_filters_no_bool_wrap():
    """build_search_body with empty filters list keeps base query as multi_match."""
    body = build_search_body("Ferrari", filters=[])
    inner = body["query"]["function_score"]["query"]
    assert "multi_match" in inner


def test_custom_weights_propagate():
    """Custom weight parameters propagate correctly to function dict."""
    q = build_function_score_query(
        "Ferrari",
        recency_weight=2.0,
        length_weight=0.5,
        infobox_weight=1.0,
        missing_published_score=0.1,
    )
    fns = q["function_score"]["functions"]
    assert fns[0]["weight"] == 2.0
    assert fns[1]["weight"] == 0.1
    assert fns[2]["weight"] == 0.5
    assert fns[3]["weight"] == 1.0
