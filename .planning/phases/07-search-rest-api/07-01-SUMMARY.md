---
phase: 07-search-rest-api
plan: "01"
subsystem: search-rest-api
tags: [flask, elasticsearch, rest-api, search, tdd]

dependency-graph:
  requires:
    - "06-server-lifecycle-cleanup (state dict, _es_health_poller, Flask app)"
    - "nitrofind.search.query_builder (build_search_body, build_filter_clauses)"
    - "nitrofind.search.models (ArticleResult, from_es_hit)"
  provides:
    - "GET /api/search endpoint (API-01, API-02)"
    - "state['es_client'] key wired in _es_health_poller"
    - "_result_to_api_dict() serialization helper"
  affects:
    - "Phase 8 browser UI (consumes /api/search JSON contract)"

tech-stack:
  added: []
  patterns:
    - "MagicMock + monkeypatch.setitem fixture for Flask route testing without live ES"
    - "State dict single-writer pattern extended to es_client (GIL-safe, T-06-06)"
    - "Flat keyword ES client.search() API (source= not _source=, no body=)"
    - "Highlight-or-fallback excerpt: highlight_body[0] if present, else _source.excerpt"
    - "Empty-string coercion for filter params: request.args.get('x') or None"

key-files:
  created:
    - path: tests/test_search/test_api_search.py
      description: "8 unit tests for /api/search covering API-01, API-02, SRVR-03 503 guard"
  modified:
    - path: nitrofind/server.py
      description: "Added state['es_client'] key, _result_to_api_dict(), api_search() route; updated imports and docstring"

decisions:
  - "Reuse the Phase 6 warm ES client from state['es_client'] rather than creating a new client per-request (avoids per-request connection pool overhead)"
  - "took_ms is a per-item field in the JSON array (same value for all items in one response) — satisfies literal API-01 wording; Phase 8 can migrate to envelope if needed"
  - "Accept ?size=N&from=N passthrough to build_search_body() for zero-cost pagination support (Phase 8 benefit)"
  - "No new packages added — Phase 7 is pure wiring over existing stack"

metrics:
  duration: "~15 minutes"
  completed: "2026-06-03T19:49:49Z"
  tasks-completed: 2
  files-created: 1
  files-modified: 1
---

# Phase 07 Plan 01: Search REST API Summary

**One-liner:** GET /api/search route wired over existing Qt-free query builder stack with highlight-or-fallback excerpts, filter forwarding, and 503 warmup guard.

## What Was Built

A single Flask REST endpoint `GET /api/search` added to `nitrofind/server.py` as a thin synchronous wrapper over the existing search stack. The route:

1. Returns HTTP 503 with `{"status": "starting"}` while `state["ready"]` is False (SRVR-03 guard)
2. Returns `[]` immediately for blank/missing `q` (prevents ES `BadRequestError` on empty multi_match)
3. Forwards optional `manufacturer`, `era_bucket`, `body_style` params through `build_filter_clauses()` with empty-string-to-None coercion
4. Calls `build_search_body()` and `state["es_client"].search()` using the flat keyword API
5. Maps hits through `ArticleResult.from_es_hit()` and serializes with `_result_to_api_dict()`
6. Returns a JSON array where each item has: `title`, `url`, `source_domain`, `excerpt`, `score`, `took_ms`

The excerpt uses `highlight_body[0]` (ES `<b>`-tagged fragment) when present, falling back to plain `_source.excerpt`.

The Phase 6 `state` dict was extended with `"es_client": None` and `_es_health_poller` was updated to assign `state["es_client"] = client` immediately before `state["ready"] = True` (single writer, GIL-safe).

## Task Commits

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Add state["es_client"] and populate in _es_health_poller | 5239359 | nitrofind/server.py |
| 2 (RED) | Failing tests for /api/search | 837e19e | tests/test_search/test_api_search.py |
| 2 (GREEN) | Implement /api/search route | 9c170ca | nitrofind/server.py |

## TDD Gate Compliance

- RED gate: `test(07-01)` commit `837e19e` — 8 tests written before implementation, all failing (404 — route not yet registered)
- GREEN gate: `feat(07-01)` commit `9c170ca` — 8 tests pass after implementation
- REFACTOR: Not needed — code was clean on first pass

## Verification Results

1. `python3 -m pytest tests/ -m "not integration" -q` — **143 passed, 5 deselected** (no regression)
2. `python3 -c "from nitrofind import server; assert 'es_client' in server.state; print(server.app.url_map)"` — `/api/search` registered, server imports cleanly
3. `grep -n "SearchEngine|client.search(body=" nitrofind/server.py` — no output (no forbidden patterns)

## Deviations from Plan

None — plan executed exactly as written.

The plan's Task 1 acceptance criteria included a source-order check using string index comparison (`src.index("es_client] = client") < src.index("ready"] = True")`). This check returns False because the docstring contains `state["ready"] = True` as example text, which appears earlier in the string. However, the actual code order is correct (es_client assignment on line 33 of the function, ready on line 34). The check's intent (ordering) is satisfied; only the naive string-index check is misleading.

## Known Stubs

None.

## Threat Surface Scan

No new threat surface beyond what is documented in the plan's `<threat_model>`. All 7 identified threats (T-07-01 through T-07-07) are mitigated in the implementation:

- T-07-01/T-07-02: q and filter params flow through query_builder functions, never interpolated as DSL keys
- T-07-03: `index="car_articles"` hard-coded literal
- T-07-04: `build_search_body()` clamps size to `MAX_RESULT_SIZE=100`
- T-07-05: blank q guard returns `[]` before any ES call
- T-07-06: exception detail in 500 response — accepted (localhost-only, single-user)
- T-07-07: 503 guard runs before any `state["es_client"]` access

## Self-Check: PASSED

- [x] `nitrofind/server.py` exists and modified — FOUND
- [x] `tests/test_search/test_api_search.py` exists — FOUND
- [x] `.planning/phases/07-search-rest-api/07-01-SUMMARY.md` — created now
- [x] Commit 5239359 exists — FOUND (Task 1: state dict extension)
- [x] Commit 837e19e exists — FOUND (Task 2 RED: failing tests)
- [x] Commit 9c170ca exists — FOUND (Task 2 GREEN: implementation)
- [x] All 143 non-integration tests pass
- [x] `/api/search` registered in Flask URL map
- [x] No `SearchEngine` import in server.py
- [x] No `client.search(body=` usage in server.py
