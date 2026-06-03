---
phase: 07-search-rest-api
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - nitrofind/server.py
  - tests/test_search/test_api_search.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-06-03
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

This phase adds the `GET /api/search` REST endpoint to the existing Flask application, wires the Elasticsearch client into `state["es_client"]` via `_es_health_poller`, and delivers a companion unit test suite. The overall approach is sound: the 503 warmup guard, blank-q guard, and filter coercion are all correctly implemented. However, one critical defect exists — the response-parsing code after the ES call is outside the error-handling try/except block, causing a raw unhandled 500 on any malformed ES response. Three additional warnings are also present: pagination parameters advertised in the research document are silently ignored at the route level, `era_bucket` and `body_style` filter forwarding is entirely untested, and the exception-path 500 response shape is never exercised by the test suite.

---

## Critical Issues

### CR-01: Response parsing outside try/except — unhandled KeyError on malformed ES response

**File:** `nitrofind/server.py:161-163`
**Issue:** Lines 161-163 execute *outside* the `try` block that catches `Exception` from `client.search()`. Specifically, `resp["hits"]["hits"]` uses direct key access on the ES response dict. If the Elasticsearch cluster returns a response missing the `"hits"` key (e.g., during a shard failure, after a partial timeout, or under unusual cluster state), a `KeyError` is raised outside the error handler. Flask will emit a raw 500 HTML traceback rather than the structured `{"error": "search_failed", "detail": ...}` JSON that the route promises. The issue is that the `try` closes after line 156 and the except at line 157-159 returns early — lines 161-163 are entirely unprotected.

Current code:
```python
    try:
        resp = state["es_client"].search(
            index="car_articles",
            query=body["query"],
            ...
        )
    except Exception as exc:
        logger.warning("Search error: %s: %s", type(exc).__name__, exc)
        return {"error": "search_failed", "detail": str(exc)}, 500

    took_ms = resp.get("took", 0)
    results = [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]  # <-- unprotected
    return jsonify([_result_to_api_dict(r, took_ms) for r in results])
```

**Fix:** Expand the try/except block to include response parsing, or use safe `.get()` access for the `"hits"` traversal:

```python
    try:
        resp = state["es_client"].search(
            index="car_articles",
            query=body["query"],
            highlight=body.get("highlight"),
            source=body.get("_source"),
            size=body.get("size", 20),
            from_=body.get("from", 0),
        )
        took_ms = resp.get("took", 0)
        results = [
            ArticleResult.from_es_hit(hit)
            for hit in resp.get("hits", {}).get("hits", [])
        ]
        return jsonify([_result_to_api_dict(r, took_ms) for r in results])
    except Exception as exc:
        logger.warning("Search error: %s: %s", type(exc).__name__, exc)
        return {"error": "search_failed", "detail": str(exc)}, 500
```

---

## Warnings

### WR-01: `size` and `from_` pagination parameters from query string are silently ignored

**File:** `nitrofind/server.py:146`
**Issue:** `build_search_body()` is called at line 146 as `build_search_body(q, filters=filters)` — neither `size` nor `from_` are read from `request.args` and forwarded. The RESEARCH.md Open Questions section explicitly resolves this as "Accept them (pass through to `build_search_body` which clamps size to `MAX_RESULT_SIZE`)" and the `build_search_body` signature accepts both parameters. The docstring security comment at line 130 even references `T-07-04: size clamped to MAX_RESULT_SIZE by build_search_body()`, implying the parameters reach `build_search_body` — but they never arrive there. A caller sending `?size=50&from=20` silently receives the default 20 results starting from 0. This is a broken contract between the documented API and the actual behavior.

**Fix:**
```python
    try:
        size = int(request.args.get("size", 20))
    except (TypeError, ValueError):
        size = 20
    try:
        from_ = int(request.args.get("from", 0))
    except (TypeError, ValueError):
        from_ = 0

    body = build_search_body(q, filters=filters, size=size, from_=from_)
```
`build_search_body` already enforces the `MAX_RESULT_SIZE=100` cap and clamps `from_` to non-negative, so no additional bounds checking is needed at the route level.

---

### WR-02: `era_bucket` and `body_style` filter parameters have no test coverage

**File:** `tests/test_search/test_api_search.py`
**Issue:** The test suite covers `manufacturer` filter forwarding (`test_manufacturer_filter_forwarded`) and the empty-manufacturer coercion (`test_empty_filter_param_ignored`), but the two other API-02 filter parameters — `era_bucket` and `body_style` — have zero test coverage. A typo or regression in the corresponding `request.args.get("era_bucket")` or `build_filter_clauses` path would go undetected. The requirement coverage claim in the module docstring ("API-02: optional filter params forwarded to build_filter_clauses") is only partially fulfilled by the tests.

**Fix:** Add at least one parameterized test or two targeted tests mirroring `test_manufacturer_filter_forwarded`:

```python
@pytest.mark.parametrize("param,field,value", [
    ("era_bucket", "era_bucket", "1960s"),
    ("body_style", "body_style", "coupe"),
])
def test_filter_param_forwarded(param, field, value, monkeypatch):
    """era_bucket and body_style params produce correct term filters. [API-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "took": 1,
        "hits": {"total": {"value": 0}, "hits": []},
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get(f"/api/search?q=car&{param}={value}")
    assert resp.status_code == 200
    query = mock_es.search.call_args.kwargs["query"]
    filters = query["function_score"]["query"]["bool"]["filter"]
    assert {"term": {field: value}} in filters
```

---

### WR-03: ES exception path (HTTP 500) has no test coverage

**File:** `tests/test_search/test_api_search.py`
**Issue:** The `except Exception` branch at `server.py:157-159` that returns `{"error": "search_failed", "detail": str(exc)}, 500` is completely untested. There is no test that injects a `side_effect` exception into `mock_es.search` and asserts the 500 status code plus the `{"error": "search_failed"}` JSON body shape. If this path were accidentally removed or its return value changed, no test would catch it.

**Fix:**
```python
def test_search_es_error_returns_500(monkeypatch):
    """When ES raises an exception, /api/search returns 500 with search_failed error body. [API-01]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.side_effect = ConnectionError("ES unreachable")
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=mustang")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["error"] == "search_failed"
    assert "detail" in data
```

---

## Info

### IN-01: `patch` imported but never used in test file

**File:** `tests/test_search/test_api_search.py:15`
**Issue:** `from unittest.mock import MagicMock, patch` — `patch` is imported but never referenced anywhere in the test file. All patching uses pytest's `monkeypatch` fixture instead. The unused import adds noise and would be flagged by linters (`F401` in flake8/ruff).

**Fix:**
```python
from unittest.mock import MagicMock
```

---

_Reviewed: 2026-06-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
