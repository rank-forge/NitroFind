# Phase 7: Search REST API - Research

**Researched:** 2026-06-03
**Domain:** Flask route implementation, Elasticsearch client integration, JSON serialization
**Confidence:** HIGH

---

## Summary

Phase 7 adds a single route — `GET /api/search` — to the Flask application established by Phase 6. The entire search stack (query construction, result deserialization) already exists and is Qt-free. The route is a thin synchronous wrapper: read query params, call `build_search_body()`, call `client.search()`, map hits through `ArticleResult.from_es_hit()`, serialize to JSON. No new libraries are required.

The only non-trivial architectural decision is where to store the live `Elasticsearch` client so the route can reach it. The Phase 6 `state` dict is the correct location: `_es_health_poller` is the single writer, Flask routes are readers, and the GIL makes simple assignment atomic — the same rationale that covers `state["ready"]` applies to `state["es_client"]`. Phase 6 code creates a local `client = Elasticsearch(ES_URL, request_timeout=2)` inside `_es_health_poller` and discards it after the poller exits. Phase 7 must store that client in `state["es_client"]` so the route can use it after `state["ready"]` is True.

The test pattern from `tests/test_server.py` extends cleanly: monkeypatch `state["ready"] = True` and `state["es_client"] = MagicMock()` — no live ES, no subprocess. All five existing server tests pass without modification. Phase 7 adds `tests/test_search/test_api_search.py` (new file) following the same fixture pattern.

**Primary recommendation:** Add `state["es_client"]` to `server.py`'s state dict, populate it in `_es_health_poller` alongside `state["ready"] = True`, then implement `api_search()` as a synchronous Flask route that calls the existing query builder and deserializes results.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Query parameter parsing (`q`, `manufacturer`, etc.) | API / Backend (Flask route) | — | Flask `request.args` handles this; no browser logic needed |
| Filter clause construction | API / Backend (`build_filter_clauses`) | — | Already exists Qt-free in `query_builder.py`; route just calls it |
| Elasticsearch query execution | API / Backend (synchronous ES client call) | — | Synchronous call is correct for Flask dev server; no threading needed |
| Result deserialization | API / Backend (`ArticleResult.from_es_hit`) | — | Already exists; route maps hits through it |
| JSON serialization | API / Backend (Flask `jsonify`) | — | Flask handles float/int/str natively |
| 503 warmup guard | API / Backend (state dict check) | — | Pattern already established in `api_status()` |
| ES client lifecycle | API / Backend (state dict, `_es_health_poller`) | — | Single writer; same GIL-safe pattern as Phase 6 |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-01 | `GET /api/search?q={query}` returns JSON array — each item: title, url, source_domain, excerpt (with ES highlight tags), score, took_ms | `build_search_body()` + `ArticleResult.from_es_hit()` + Flask `jsonify` — all verified working end-to-end in this session |
| API-02 | `GET /api/search` accepts optional filter params `manufacturer`, `era_bucket`, `body_style` narrowing results via `build_filter_clauses()` | `request.args.get('manufacturer') or None` pattern verified — empty string coerced to None correctly |
</phase_requirements>

---

## Standard Stack

### Core (no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 [VERIFIED: pip freeze] | Route handler, `request.args`, `jsonify` | Already installed in Phase 6 |
| elasticsearch-py | 8.19.3 [VERIFIED: pip freeze] | `client.search()` flat keyword API | Already installed in Phase 1 |
| nitrofind.search.query_builder | — (local) | `build_search_body()`, `build_filter_clauses()` | Qt-free; verified importable |
| nitrofind.search.models | — (local) | `ArticleResult.from_es_hit()` | Qt-free; verified importable |

**No new packages required.** Phase 7 requires zero additions to `requirements.in` or `requirements.txt`.

### Route Call Signature (verified against elasticsearch-py 8.19.3)

```python
# [VERIFIED: python3 inspect.signature(Elasticsearch.search)]
resp = client.search(
    index="car_articles",
    query=body["query"],
    highlight=body.get("highlight"),
    source=body.get("_source"),   # param name is 'source', dict key is '_source'
    size=body.get("size", 20),
    from_=body.get("from", 0),
)
```

The `source` parameter name (not `_source`) is a known naming difference — `engine.py` already uses this correctly and is the canonical reference.

---

## Package Legitimacy Audit

No new packages are installed in Phase 7. This section is not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser / test client
        |
        | GET /api/search?q=mustang&manufacturer=Ford
        v
nitrofind/server.py  api_search()
        |
        |-- state["ready"] check --(False)--> 503 {"status": "starting"}
        |
        |--(True)-->
        |
        |-- request.args.get('q', '').strip() ----------> q
        |-- request.args.get('manufacturer') or None --> mfr
        |-- request.args.get('era_bucket') or None ----> era
        |-- request.args.get('body_style') or None ----> bstyle
        |
        |-- build_filter_clauses(mfr, era, bstyle) --> filters: list[dict]
        |-- build_search_body(q, filters=filters) --> body: dict
        |
        |-- state["es_client"].search(
        |       index="car_articles",
        |       query=body["query"],
        |       highlight=body["highlight"],
        |       source=body["_source"],
        |       size=body["size"],
        |       from_=body["from"],
        |   ) --> ES resp dict
        |
        |-- [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]
        |-- took_ms = resp.get("took", 0)
        |
        |-- jsonify([result_to_api_dict(r, took_ms) for r in results])
        v
        200 JSON array
```

### Recommended Project Structure

No new directories. Changes are confined to:

```
nitrofind/
└── server.py           # Add state["es_client"], api_search() route

tests/
└── test_search/
    └── test_api_search.py   # NEW: /api/search route tests
```

### Pattern 1: state dict extension for es_client

**What:** Add `"es_client": None` to the existing `state` dict in `server.py`. Populate it inside `_es_health_poller` immediately before setting `state["ready"] = True`.

**When to use:** Any Flask route that needs the ES client after warmup.

```python
# In server.py state dict (D-09 extension)
state: dict = {
    "ready": False,
    "process": None,
    "es_health": None,
    "doc_count": 0,
    "index_size_bytes": 0,
    "es_client": None,     # <-- Phase 7 addition: Elasticsearch instance
}

# In _es_health_poller(), before state["ready"] = True:
#   (client is the local Elasticsearch(ES_URL, request_timeout=2) already in scope)
state["es_client"] = client       # single writer — GIL-safe
state["ready"] = True
```

**Why not create a new client in the route?** Creating a new `Elasticsearch` client per-request opens a new connection pool on every call. The Phase 6 client already has a warm pool; reusing it is correct.

### Pattern 2: /api/search route structure

```python
# Source: verified end-to-end in research session
@app.route("/api/search")
def api_search():
    """GET /api/search — ranked full-text search with optional filters (API-01, API-02)."""
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
            source=body.get("_source"),
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

### Pattern 3: result serialization helper

```python
# Source: verified in research session
def _result_to_api_dict(result: ArticleResult, took_ms: int) -> dict:
    """Serialize one ArticleResult to the API-01 wire format."""
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return {
        "title": result.title,
        "url": result.url,
        "source_domain": result.source_domain,
        "excerpt": excerpt,
        "score": result.score,
        "took_ms": took_ms,
    }
```

**Excerpt selection logic:** `highlight_body[0]` if present (contains `<b>` tags from ES), otherwise fall back to the `excerpt` field from `_source` (plain text). This satisfies API-01's requirement that the excerpt contain "ES highlight tags" when a match exists.

### Pattern 4: test fixture for /api/search

```python
# Source: extends tests/test_server.py established pattern
@pytest.fixture
def client_with_search(monkeypatch):
    """Flask test client with state populated for /api/search tests."""
    from nitrofind import server
    from unittest.mock import MagicMock
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
```

### Anti-Patterns to Avoid

- **Creating Elasticsearch client in the route:** `Elasticsearch(ES_URL)` per request creates a new connection pool on every call — expensive and incorrect. Use `state["es_client"]` set once by `_es_health_poller`.
- **Importing SearchEngine:** `nitrofind/search/engine.py` imports PyQt6 — it is broken on import. The route must call `build_search_body()` directly and call `client.search()` synchronously, mirroring what `_SearchWorker.run()` does minus the signal machinery.
- **Using `body=` keyword in `client.search()`:** The `body=` parameter was deprecated in elasticsearch-py 8.x and removed. Always use flat keyword API (`query=`, `highlight=`, `source=`, etc.). [VERIFIED: elasticsearch-py 8.x source, engine.py existing pattern]
- **Passing `_source` as the keyword param name:** The dict key in `build_search_body()` output is `"_source"` but the `client.search()` parameter is `source` (no leading underscore). Use `body.get("_source")` as the value passed to `source=`. [VERIFIED: inspect.signature in research session]
- **Empty query forwarded to ES:** `multi_match` with an empty string may raise a `BadRequestError` from ES (query parsing error). Guard with `if not q: return jsonify([])` before calling `build_search_body()`.
- **Bare `or None` omitted for filter params:** `request.args.get("manufacturer")` returns `""` for `?manufacturer=` (empty value). `build_filter_clauses(manufacturer="")` would add `{"term": {"manufacturer": ""}}` which matches nothing. Use `request.args.get("manufacturer") or None` to coerce empty string to None. [VERIFIED: Flask test in research session]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Full-text query construction | Custom query dict | `build_search_body()` | Already implements function_score with all RLVN requirements; hand-rolling would duplicate and diverge |
| Filter term clauses | Manual filter dict construction | `build_filter_clauses()` | Handles None-exclusion, supports all three filter params; reuse the existing contract |
| ES hit deserialization | Direct dict access | `ArticleResult.from_es_hit()` | Guards all fields with `.get()` and safe defaults; avoids KeyError on partial hits |
| JSON serialization of floats | Custom float formatting | Flask `jsonify` | Handles float score values and None fields correctly |

**Key insight:** This phase is purely wiring — all hard problems (query scoring, highlight extraction, result deserialization) were solved in Phases 1–3. Do not rebuild any of them.

---

## Common Pitfalls

### Pitfall 1: `_source` vs `source` parameter naming
**What goes wrong:** `client.search(index=..., _source=body["_source"])` raises `TypeError: unexpected keyword argument '_source'`.
**Why it happens:** `build_search_body()` uses `"_source"` as the dict key (ES DSL convention). The elasticsearch-py 8.x flat keyword API parameter is `source` (no underscore).
**How to avoid:** Always `source=body.get("_source")` — use the value from `"_source"` key but pass it to the `source=` param. Confirmed in `engine.py` line 102 which already does this correctly.
**Warning signs:** `TypeError: search() got an unexpected keyword argument '_source'`

### Pitfall 2: `SearchEngine` import breaks at import time
**What goes wrong:** Any file that does `from nitrofind.search.engine import SearchEngine` raises `ImportError: No module named 'PyQt6'`.
**Why it happens:** `engine.py` line 32 has `from PyQt6.QtCore import ...`. PyQt6 was removed in Phase 6 (CLEN-01).
**How to avoid:** The `/api/search` route MUST NOT import `SearchEngine`. Call `build_search_body()` and `client.search()` directly — this is what `_SearchWorker.run()` did, just without the signal machinery.
**Warning signs:** `ModuleNotFoundError: No module named 'PyQt6'` at server startup.

### Pitfall 3: Empty query string forwarded to Elasticsearch
**What goes wrong:** `GET /api/search` (no `q` param) or `GET /api/search?q=` forwards empty string to `build_search_body("")`, which calls `client.search()` with `"multi_match": {"query": ""}` — ES 8.x raises `BadRequestError: failed to parse query`.
**Why it happens:** `multi_match` requires a non-empty query string.
**How to avoid:** `q = request.args.get("q", "").strip(); if not q: return jsonify([])` — return empty array immediately for blank queries.
**Warning signs:** 500 errors on `GET /api/search` with no `q` param.

### Pitfall 4: `state["es_client"]` not populated when `state["ready"]` is True
**What goes wrong:** `/api/search` passes the `state["ready"]` guard but `state["es_client"]` is `None`, causing `AttributeError: 'NoneType' object has no attribute 'search'`.
**Why it happens:** The Phase 6 `_es_health_poller` creates a local `client` variable but never stores it in `state`. If Phase 7 adds the route before updating the poller, the route will NoneError.
**How to avoid:** The poller modification and the route implementation must be in the same task or adjacent tasks. Set `state["es_client"] = client` in the poller before `state["ready"] = True`.
**Warning signs:** `AttributeError: 'NoneType' object has no attribute 'search'` in Flask logs.

### Pitfall 5: `took_ms` placement — per-item vs response-level
**What goes wrong:** Ambiguity in API-01: "returns a JSON array with ... took_ms for each result." The requirement wording implies `took_ms` is a per-item field in the array.
**Why it happens:** ES returns one `took` value per response (not per hit). Phase 8 JS will read `results[0].took_ms` if it expects a per-item field.
**How to avoid:** Include `took_ms` in every item dict with the same value (the single response-level `took` from ES). This satisfies the literal requirement wording without changing the array shape that Phase 8 expects.
**Warning signs:** Phase 8 JS cannot find `took_ms` in results.

---

## Code Examples

### Complete /api/search route (verified pattern)

```python
# Source: verified end-to-end simulation in research session (2026-06-03)
import logging
from flask import request, jsonify
from elasticsearch import ApiError
from nitrofind.search.models import ArticleResult
from nitrofind.search.query_builder import build_search_body, build_filter_clauses

logger = logging.getLogger("nitrofind.server")


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
            source=body.get("_source"),   # 'source' not '_source'
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

### state dict modification for Phase 7

```python
# In server.py — add es_client field (Phase 7 extension of D-09)
state: dict = {
    "ready": False,
    "process": None,
    "es_health": None,
    "doc_count": 0,
    "index_size_bytes": 0,
    "es_client": None,     # Phase 7: Elasticsearch client instance, set by _es_health_poller
}

# In _es_health_poller(), before state["ready"] = True:
state["es_client"] = client        # reuse the already-connected client
state["ready"] = True
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `body=` keyword in `client.search()` | Flat keyword API (`query=`, `highlight=`, etc.) | elasticsearch-py 8.x | `body=` raises TypeError in 8.x — must use flat API |
| `elasticsearch-dsl` standalone package | Merged into `elasticsearch` core at 8.18.0 | elasticsearch-py 8.18 | No separate install; DSL is already available |
| `QThreadPool` + `QRunnable` for async search | Synchronous `client.search()` in Flask route | Phase 7 (PyQt6 removed) | Flask dev server is single-threaded; sync call is correct |

**Deprecated/outdated in this codebase:**
- `SearchEngine` (`engine.py`): PyQt6-dependent, broken on import after CLEN-01. This file is dead code as of Phase 6. Phase 7 does not use it.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `took_ms` belongs as a per-item field in the JSON array (same value for all items) | Pitfall 5 / Code Examples | Phase 8 JS would need to read from a different location if response shape changes |

**All other claims in this research were verified via direct code inspection, import tests, or live Python execution in the project virtualenv.**

---

## Open Questions (RESOLVED)

1. **`took_ms` placement: per-item vs response envelope**
   - What we know: API-01 says "JSON array with ... took_ms for each result" (per-item wording). ES returns one `took` per response.
   - What's unclear: Whether Phase 8 UI would prefer `{took_ms: 12, results: [...]}` (envelope) over per-item repetition.
   - Recommendation: Per-item for now (matches literal requirement wording). Phase 8 planner can migrate to envelope if needed without breaking Phase 7.
   - **RESOLVED: Per-item `took_ms` — matches literal API-01 wording; Phase 8 can migrate to envelope if needed.**

2. **Pagination parameters in Phase 7 scope**
   - What we know: `build_search_body()` accepts `from_` and `size`. API-01/API-02 do not mention pagination params.
   - What's unclear: Whether `?size=N&from=N` should be accepted in Phase 7.
   - Recommendation: Accept them (pass through to `build_search_body` which already clamps size to MAX_RESULT_SIZE). Phase 8 UI may use them for scroll/pagination. Zero cost to wire them now.
   - **RESOLVED: Accept `?size=N&from=N` — pass through to `build_search_body()` which clamps size to MAX_RESULT_SIZE. Zero-cost wire-up; Phase 8 benefits from pagination support.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | All code | ✓ | 3.12 (WSL) | — |
| Flask | Route handler | ✓ | 3.1.3 | — |
| elasticsearch-py | ES client | ✓ | 8.19.3 | — |
| pytest | Test suite | ✓ | (in venv) | — |

All dependencies available. No missing dependencies.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pytest.ini` (project root) |
| Quick run command | `python3 -m pytest tests/test_search/test_api_search.py -q` |
| Full suite command | `python3 -m pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-01 | `GET /api/search?q=mustang` returns 200 JSON array with correct shape | unit | `pytest tests/test_search/test_api_search.py::test_search_returns_result_array -x` | Wave 0 |
| API-01 | Response items have all required fields: title, url, source_domain, excerpt, score, took_ms | unit | `pytest tests/test_search/test_api_search.py::test_search_result_shape -x` | Wave 0 |
| API-01 | excerpt contains `<b>` highlight tag from ES body highlight | unit | `pytest tests/test_search/test_api_search.py::test_excerpt_uses_highlight -x` | Wave 0 |
| API-01 | excerpt falls back to plain `excerpt` field when no highlight returned | unit | `pytest tests/test_search/test_api_search.py::test_excerpt_fallback -x` | Wave 0 |
| API-02 | `?manufacturer=Ford` passes term filter to ES client | unit | `pytest tests/test_search/test_api_search.py::test_manufacturer_filter_forwarded -x` | Wave 0 |
| API-02 | Empty `?manufacturer=` is coerced to None (no filter added) | unit | `pytest tests/test_search/test_api_search.py::test_empty_filter_param_ignored -x` | Wave 0 |
| SRVR-03 | `GET /api/search?q=anything` while `state["ready"] = False` returns 503 | unit | `pytest tests/test_search/test_api_search.py::test_search_503_while_not_ready -x` | Wave 0 |
| API-01 | `GET /api/search` (no q) returns 200 with empty array | unit | `pytest tests/test_search/test_api_search.py::test_search_empty_q_returns_empty -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_search/test_api_search.py -q`
- **Per wave merge:** `python3 -m pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_search/test_api_search.py` — covers all API-01 and API-02 tests above (new file)

*(Existing test infrastructure in `tests/test_server.py` and `tests/test_search/` covers all Phase 6 requirements. No changes to existing test files needed.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (local single-user tool) |
| V3 Session Management | no | — |
| V4 Access Control | no | — (localhost only, per T-06-01) |
| V5 Input Validation | yes | `request.args.get("q", "").strip()` + `or None` coercion for filter params + `build_search_body()` which clamps `size` to `MAX_RESULT_SIZE` |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Query injection via `q` param | Tampering | `q` is placed in `multi_match.query` string value by `build_function_score_query` — never interpolated as raw DSL key. [VERIFIED: query_builder.py] |
| Cross-index access via filter params | Tampering | `index="car_articles"` is a hard-coded string literal in the route — never derived from user input. Pattern carried from `engine.py` T-03-04. |
| Unbounded result size via `size` param | DoS | `build_search_body()` clamps `size` to `MAX_RESULT_SIZE=100`. [VERIFIED: query_builder.py] |
| Filter injection via manufacturer/era/body_style | Tampering | `build_filter_clauses()` places values inside `term` filter value field — never as a key or index name. |

---

## Sources

### Primary (HIGH confidence)
- `nitrofind/server.py` — Phase 6 implementation; state dict pattern, `_es_health_poller` structure
- `nitrofind/search/query_builder.py` — `build_search_body()`, `build_filter_clauses()` signatures and return shapes
- `nitrofind/search/models.py` — `ArticleResult.from_es_hit()` field mapping
- `nitrofind/search/engine.py` — `_SearchWorker.run()` — canonical reference for ES flat keyword API call pattern
- `tests/test_server.py` — established monkeypatch + test_client() fixture pattern
- Direct Python execution in project venv — all route patterns, exception types, serialization behavior verified live

### Secondary (MEDIUM confidence)
- Flask 3.1.3 `request.args.get()` behavior verified via live test in research session
- elasticsearch-py 8.19.3 `search()` signature verified via `inspect.signature`
- `ApiError`, `TransportError` hierarchy verified via direct import

### Tertiary (LOW confidence)
- None — all claims verified via live execution or direct code inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages confirmed present via `pip freeze`; no new installs needed
- Architecture: HIGH — patterns verified end-to-end via live Python execution; route data flow confirmed
- Pitfalls: HIGH — all pitfalls confirmed by inspecting existing code (`engine.py`, `server.py`) and live tests

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (stable ecosystem; Flask 3.x and elasticsearch-py 8.x both stable)
