# Phase 7: Search REST API - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 2 (1 modified, 1 new)
**Analogs found:** 2 / 2

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `nitrofind/server.py` | route + state | request-response | `nitrofind/server.py` (existing) | exact — extend in-place |
| `tests/test_search/test_api_search.py` | test | request-response | `tests/test_server.py` | exact — same fixture pattern |

---

## Pattern Assignments

### `nitrofind/server.py` — state dict extension + `api_search()` route

**Analog:** `nitrofind/server.py` (self — extend in-place)

**Imports pattern** (lines 29–32 + new additions):
```python
# Existing imports (keep as-is)
from flask import Flask
from elasticsearch import Elasticsearch
from nitrofind.es_manager import ES_URL, shutdown_es

# Add to existing imports block (Phase 7 additions)
from flask import jsonify, request
from nitrofind.search.models import ArticleResult
from nitrofind.search.query_builder import build_search_body, build_filter_clauses
```

**state dict extension** (lines 46–52 — add one key):
```python
# Current state dict — add es_client field
state: dict = {
    "ready": False,
    "process": None,        # subprocess.Popen | None
    "es_health": None,      # str | None: "green" | "yellow" | "red"
    "doc_count": 0,
    "index_size_bytes": 0,
    "es_client": None,      # Phase 7: Elasticsearch instance, set by _es_health_poller
}
```

**_es_health_poller modification** (lines 157–161 — add one assignment before ready=True):
```python
# In _es_health_poller(), inside the green/yellow branch, BEFORE state["ready"] = True:
state["es_health"] = resp["status"]
state["doc_count"], state["index_size_bytes"] = _fetch_index_stats(client)
state["es_client"] = client       # Phase 7: single writer — GIL-safe (same rationale as ready flag)
state["ready"] = True
return
```

**503 warmup guard pattern** (lines 72–73 — copy exactly for api_search):
```python
# Established pattern from api_status() — copy verbatim for api_search()
if not state["ready"]:
    return {"status": "starting"}, 503
```

**Core route pattern** (new function after api_status):
```python
def _result_to_api_dict(result: ArticleResult, took_ms: int) -> dict:
    """Serialize ArticleResult to API-01 wire format."""
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return {
        "title": result.title,
        "url": result.url,
        "source_domain": result.source_domain,
        "excerpt": excerpt,
        "score": result.score,
        "took_ms": took_ms,
    }


@app.route("/api/search")
def api_search():
    """GET /api/search — ranked full-text search with optional filters.

    Requirement coverage:
      API-01: returns JSON array with title, url, source_domain, excerpt, score, took_ms
      API-02: accepts manufacturer, era_bucket, body_style filter params
      SRVR-03: returns 503 while state["ready"] is False
    """
    if not state["ready"]:
        return {"status": "starting"}, 503

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    filters = build_filter_clauses(
        manufacturer=request.args.get("manufacturer") or None,
        era_bucket=request.args.get("era_bucket") or None,
        body_style=request.args.get("body_style") or None,
    )
    body = build_search_body(q, filters=filters)

    try:
        resp = state["es_client"].search(
            index="car_articles",
            query=body["query"],
            highlight=body.get("highlight"),
            source=body.get("_source"),   # 'source' not '_source' — known param name difference
            size=body.get("size", 20),
            from_=body.get("from", 0),
        )
    except Exception as exc:
        logger.warning("Search error: %s: %s", type(exc).__name__, exc)
        return {"error": "search_failed", "detail": str(exc)}, 500

    took_ms = resp.get("took", 0)
    results = [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]
    return jsonify([_result_to_api_dict(r, took_ms) for r in results])
```

---

### `tests/test_search/test_api_search.py` — new test file

**Analog:** `tests/test_server.py` (exact same fixture + test_client pattern)

**File header pattern** (lines 1–19 of test_server.py — adapt docstring, keep structure):
```python
"""
Unit tests for nitrofind.server api_search — API-01, API-02 coverage.

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
```

**Fixture pattern** (lines 27–43 of test_server.py — adapt for es_client mock):
```python
# Copy the monkeypatch.setitem pattern from test_server.py client_ready fixture.
# Add es_client mock to the fixture alongside ready=True.

@pytest.fixture
def client_with_search(monkeypatch):
    """Flask test client with state populated for /api/search tests."""
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
def client_not_ready(monkeypatch):
    """Flask test client with state["ready"] = False — reuse from test_server.py pattern."""
    from nitrofind import server
    monkeypatch.setitem(server.state, "ready", False)
    return server.app.test_client()
```

**Test assertion pattern** (lines 71–119 of test_server.py — copy structure):
```python
# Follow the same assert pattern: resp.status_code, resp.get_json()
def test_search_returns_result_array(client_with_search):
    resp = client_with_search.get("/api/search?q=mustang")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 1

def test_search_503_while_not_ready(client_not_ready):
    resp = client_not_ready.get("/api/search?q=anything")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "starting"}
```

---

## Shared Patterns

### 503 warmup guard
**Source:** `nitrofind/server.py` lines 72–73
**Apply to:** `api_search()` — identical two-line guard at top of every route function
```python
if not state["ready"]:
    return {"status": "starting"}, 503
```

### monkeypatch state fixture
**Source:** `tests/test_server.py` lines 27–43
**Apply to:** `tests/test_search/test_api_search.py` fixtures
```python
monkeypatch.setitem(server.state, "ready", True)
monkeypatch.setitem(server.state, "es_client", mock_es)
return server.app.test_client()
```

### Flask test assertion style
**Source:** `tests/test_server.py` lines 71–119
**Apply to:** All test functions in `test_api_search.py`
```python
resp = client.get("/api/search?q=mustang")
assert resp.status_code == 200
data = resp.get_json()
assert isinstance(data, list)
```

### Logger usage
**Source:** `nitrofind/server.py` line 38
**Apply to:** Any exception handler in `api_search()`
```python
logger = logging.getLogger("nitrofind.server")
# In exception handler:
logger.warning("Search error: %s: %s", type(exc).__name__, exc)
```

---

## No Analog Found

None — both files have direct analogs in the codebase.

---

## Critical Anti-Patterns (from RESEARCH.md)

| Anti-Pattern | What Breaks | Correct Pattern |
|---|---|---|
| `client.search(_source=...)` | `TypeError: unexpected keyword argument '_source'` | `source=body.get("_source")` |
| `from nitrofind.search.engine import SearchEngine` | `ModuleNotFoundError: No module named 'PyQt6'` | Import `build_search_body`, `build_filter_clauses`, `ArticleResult` directly |
| `client.search(body=...)` | `TypeError` in elasticsearch-py 8.x | Flat keyword API: `query=`, `highlight=`, `source=`, `size=`, `from_=` |
| `request.args.get("manufacturer")` without `or None` | Passes `""` to `build_filter_clauses`, adds `{"term": {"manufacturer": ""}}` | `request.args.get("manufacturer") or None` |
| Forwarding empty `q` to `build_search_body("")` | `BadRequestError` from ES `multi_match` | `if not q: return jsonify([])` guard before any ES call |

---

## Metadata

**Analog search scope:** `nitrofind/`, `tests/`
**Files scanned:** `nitrofind/server.py`, `tests/test_server.py`, `nitrofind/search/models.py`, `tests/test_search/test_models.py`
**Pattern extraction date:** 2026-06-03
