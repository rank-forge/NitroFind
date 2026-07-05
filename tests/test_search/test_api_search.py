"""
Unit tests for nitrofind.server api_search — API-01, API-02, SRVR-03 coverage.

Test strategy:
  - Monkeypatch state["ready"] and state["es_client"] to control ready/not-ready branches
  - Use Flask test_client() — no live ES, no subprocess
  - MagicMock for es_client.search() return value

Requirement coverage:
  API-01: /api/search?q=mustang returns 200 JSON array with correct shape
  API-02: optional filter params forwarded to build_filter_clauses
  SRVR-03: 503 while state["ready"] is False
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures: Flask test clients with monkeypatched state
# ---------------------------------------------------------------------------


@pytest.fixture
def client_with_search(monkeypatch):
    """Flask test client with state populated for /api/search tests.

    Mock ES client returns one hit WITH a body highlight so highlight-path
    tests can exercise the <b>-tagged excerpt logic.
    """
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "took": 12,
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_score": 2.5,
                    "_source": {
                        "title": "Ford Mustang",
                        "url": "https://en.wikipedia.org/wiki/Ford_Mustang",
                        "source_domain": "en.wikipedia.org",
                        "excerpt": "The Ford Mustang is a pony car.",
                        "body": "Full text.",
                        "body_html": "<p>Full text.</p>",
                    },
                    "highlight": {
                        "body": ["The <b>Mustang</b> is a pony car."]
                    },
                }
            ],
        },
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    return server.app.test_client()


@pytest.fixture
def client_no_highlight(monkeypatch):
    """Flask test client whose mock hit has NO highlight key — tests fallback path."""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "took": 5,
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_score": 1.8,
                    "_source": {
                        "title": "Ford Mustang",
                        "url": "https://en.wikipedia.org/wiki/Ford_Mustang",
                        "source_domain": "en.wikipedia.org",
                        "excerpt": "The Ford Mustang is a pony car.",
                        "body": "Full text.",
                    },
                    # No "highlight" key — ArticleResult.from_es_hit returns empty lists
                }
            ],
        },
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    return server.app.test_client()


@pytest.fixture
def client_not_ready(monkeypatch):
    """Flask test client with state["ready"] = False — warmup / not-yet-healthy."""
    from nitrofind import server
    monkeypatch.setitem(server.state, "ready", False)
    return server.app.test_client()


# ---------------------------------------------------------------------------
# API-01: Basic result shape
# ---------------------------------------------------------------------------


def test_search_returns_result_array(client_with_search):
    """GET /api/search?q=mustang returns 200 with a JSON wrapper containing a 'results' list of length 1. [API-01]"""
    resp = client_with_search.get("/api/search?q=mustang")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["results"], list)
    assert len(data["results"]) == 1


def test_search_result_shape(client_with_search):
    """Each result item has exactly the seven expected keys (no took_ms per-item); took_ms/total/page are at wrapper level. [API-01]"""
    resp = client_with_search.get("/api/search?q=mustang")
    assert resp.status_code == 200
    data = resp.get_json()
    item = data["results"][0]
    assert set(item.keys()) == {
        "title", "url", "source_domain", "excerpt", "body", "body_html", "score"
    }
    assert item["title"] == "Ford Mustang"
    assert data["took_ms"] == 12  # from mock took=12, at wrapper level
    assert data["total"] == 1
    assert data["page"] == 1


# ---------------------------------------------------------------------------
# API-01: Highlight vs fallback excerpt
# ---------------------------------------------------------------------------


def test_excerpt_uses_highlight(client_with_search):
    """When ES returns a body highlight, excerpt contains the <b>-tagged fragment. [API-01]"""
    resp = client_with_search.get("/api/search?q=mustang")
    assert resp.status_code == 200
    item = resp.get_json()["results"][0]
    assert "<b>" in item["excerpt"]
    assert item["excerpt"] == "The <b>Mustang</b> is a pony car."


def test_excerpt_fallback(client_no_highlight):
    """When ES returns no highlight, excerpt falls back to plain _source excerpt. [API-01]"""
    resp = client_no_highlight.get("/api/search?q=mustang")
    assert resp.status_code == 200
    item = resp.get_json()["results"][0]
    assert "<b>" not in item["excerpt"]
    assert item["excerpt"] == "The Ford Mustang is a pony car."


# ---------------------------------------------------------------------------
# API-02: Filter forwarding
# ---------------------------------------------------------------------------


def test_manufacturer_filter_forwarded(monkeypatch):
    """GET /api/search?q=mustang&manufacturer=Ford forwards manufacturer term filter to ES. [API-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "took": 3,
        "hits": {"total": {"value": 0}, "hits": []},
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=mustang&manufacturer=Ford")
    assert resp.status_code == 200

    # Assert es_client.search was called once
    mock_es.search.assert_called_once()
    call_kwargs = mock_es.search.call_args.kwargs

    # The query arg passed to search() should contain a term filter for manufacturer=Ford
    # This goes through build_filter_clauses -> build_search_body -> bool.filter
    query = call_kwargs["query"]
    query_str = str(query)
    assert "Ford" in query_str
    # Verify the term filter for manufacturer is present in the bool filter structure
    inner_query = query["function_score"]["query"]
    assert "bool" in inner_query
    assert "filter" in inner_query["bool"]
    filters = inner_query["bool"]["filter"]
    assert {"term": {"manufacturer": "Ford"}} in filters


def test_empty_filter_param_ignored(monkeypatch):
    """GET /api/search?q=mustang&manufacturer= coerces empty manufacturer to None. [API-02]

    No manufacturer term filter should appear in the query sent to ES.
    """
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "took": 2,
        "hits": {"total": {"value": 0}, "hits": []},
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=mustang&manufacturer=")
    assert resp.status_code == 200

    mock_es.search.assert_called_once()
    call_kwargs = mock_es.search.call_args.kwargs
    query = call_kwargs["query"]

    # When manufacturer is empty string (coerced to None), no bool.filter wrapping occurs
    # The function_score query goes directly without a surrounding bool.filter
    fs_inner = query["function_score"]["query"]
    # No bool.filter with manufacturer term clause should be present
    # The inner query should be a plain multi_match (no bool filter wrapper)
    assert "bool" not in fs_inner or (
        "filter" not in fs_inner.get("bool", {})
        or not any(
            "manufacturer" in str(f) for f in fs_inner["bool"].get("filter", [])
        )
    )


# ---------------------------------------------------------------------------
# SRVR-03: 503 warmup guard
# ---------------------------------------------------------------------------


def test_search_503_while_not_ready(client_not_ready, monkeypatch):
    """GET /api/search?q=anything while not ready returns 503 and does not call ES. [SRVR-03]"""
    from nitrofind import server
    mock_es = MagicMock()
    monkeypatch.setitem(server.state, "es_client", mock_es)

    resp = client_not_ready.get("/api/search?q=anything")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "starting"}
    mock_es.search.assert_not_called()


# ---------------------------------------------------------------------------
# API-01 / Pitfall 3: blank/missing q guard
# ---------------------------------------------------------------------------


def test_search_empty_q_returns_empty(monkeypatch):
    """GET /api/search (no q) and GET /api/search?q=   return 200 [] without calling ES. [API-01]"""
    from nitrofind import server
    mock_es = MagicMock()
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    # No q param
    resp = client.get("/api/search")
    assert resp.status_code == 200
    assert resp.get_json() == []

    # Blank q (whitespace only)
    resp = client.get("/api/search?q=%20")
    assert resp.status_code == 200
    assert resp.get_json() == []

    # ES was never called for either request
    mock_es.search.assert_not_called()


# ---------------------------------------------------------------------------
# SORT-02: sort param forwarding and allowlist
# ---------------------------------------------------------------------------


def test_sort_date_passed_to_es(monkeypatch):
    """GET /api/search?q=mustang&sort=date passes date sort array to es_client.search. [SORT-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=mustang&sort=date")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    assert call_kwargs["sort"] == [{"published_at": {"order": "desc", "missing": "_last", "unmapped_type": "date"}}]


def test_sort_size_passed_to_es(monkeypatch):
    """GET /api/search?q=mustang&sort=size passes size sort array to es_client.search. [SORT-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=mustang&sort=size")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    assert call_kwargs["sort"] == [{"word_count": {"order": "desc"}}]


def test_sort_unknown_value_ignored(monkeypatch):
    """GET /api/search?q=test&sort=inject treats unknown sort as relevance (sort=None). [SORT-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=test&sort=inject")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    # sort kwarg should be None (no sort array) when value is not in allowlist
    assert call_kwargs.get("sort") is None


# ---------------------------------------------------------------------------
# FILT-03: year/country API param forwarding
# ---------------------------------------------------------------------------


def test_year_from_filter_forwarded(monkeypatch):
    """GET /api/search?year_from=1960 forwards production_end range clause to ES. [FILT-03]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=test&year_from=1960")
    assert resp.status_code == 200

    call_kwargs = mock_es.search.call_args.kwargs
    filters = call_kwargs["query"]["function_score"]["query"]["bool"]["filter"]
    assert {"range": {"production_end": {"gte": 1960}}} in filters


def test_year_to_filter_forwarded(monkeypatch):
    """GET /api/search?year_to=1975 forwards production_start range clause to ES. [FILT-03]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=test&year_to=1975")
    assert resp.status_code == 200

    call_kwargs = mock_es.search.call_args.kwargs
    filters = call_kwargs["query"]["function_score"]["query"]["bool"]["filter"]
    assert {"range": {"production_start": {"lte": 1975}}} in filters


def test_country_filter_forwarded(monkeypatch):
    """GET /api/search?country=Germany forwards country_of_origin term clause to ES. [FILT-03]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=test&country=Germany")
    assert resp.status_code == 200

    call_kwargs = mock_es.search.call_args.kwargs
    filters = call_kwargs["query"]["function_score"]["query"]["bool"]["filter"]
    assert {"term": {"country_of_origin": "Germany"}} in filters


def test_year_invalid_string_coerced_to_none(monkeypatch):
    """Non-integer year_from (e.g. 'abc') is coerced to None — no range clause emitted. [FILT-03]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=test&year_from=abc")
    assert resp.status_code == 200

    call_kwargs = mock_es.search.call_args.kwargs
    query = call_kwargs["query"]
    # No bool.filter wrapping — inner query is plain multi_match with no production_end clause
    fs_inner = query["function_score"]["query"]
    assert "production_end" not in str(fs_inner)
