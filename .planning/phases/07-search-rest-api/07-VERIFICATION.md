---
phase: 07-search-rest-api
verified: 2026-06-03T20:30:00Z
status: human_needed
score: 6/6
overrides_applied: 0
human_verification:
  - test: "Start the full app with `python main.py` and send `curl -s 'http://localhost:5000/api/search?q=mustang'` once ES becomes healthy"
    expected: "HTTP 200, JSON array with at least one object containing title, url, source_domain, excerpt (with <b> tags if matches exist), score, took_ms"
    why_human: "Live ES node required; mock-only tests cannot prove real highlight tags emerge from actual ES hits stored in the car_articles index"
  - test: "With the app running and ready, send `curl -s 'http://localhost:5000/api/search?q=mustang&manufacturer=Ford'` and compare result count to `curl -s 'http://localhost:5000/api/search?q=mustang'`"
    expected: "Filter-narrow response has fewer or equal results, all manufacturer fields match Ford (or result count is visibly reduced)"
    why_human: "Requires a populated index; cannot be verified without a live ES cluster with real documents"
  - test: "Before ES becomes healthy (immediately after `python main.py`), send `curl -s -o /dev/null -w '%{http_code}' 'http://localhost:5000/api/search?q=anything'`"
    expected: "Returns 503"
    why_human: "Timing-dependent; needs a real startup race to observe the warmup guard in production; mocked in tests but not observable live without human"
---

# Phase 7: Search REST API Verification Report

**Phase Goal:** The app exposes a stable JSON search endpoint that browsers (and any HTTP client) can query, returning ranked results with highlights and optional facet filters
**Verified:** 2026-06-03T20:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /api/search?q=mustang` returns 200 JSON array; each item has title, url, source_domain, excerpt, score, took_ms | VERIFIED | `test_search_returns_result_array` + `test_search_result_shape` both pass; shape assertion uses `set(item.keys()) == {"title","url","source_domain","excerpt","score","took_ms"}` |
| 2 | When ES returns a body highlight, excerpt contains the `<b>`-tagged fragment; otherwise falls back to plain `_source` excerpt | VERIFIED | `test_excerpt_uses_highlight` asserts `"<b>" in item["excerpt"]`; `test_excerpt_fallback` asserts `"<b>" not in item["excerpt"]`; both pass |
| 3 | `GET /api/search?q=mustang&manufacturer=Ford` forwards a manufacturer term filter via `build_filter_clauses()` | VERIFIED | `test_manufacturer_filter_forwarded` inspects `call_args.kwargs["query"]` and asserts `{"term": {"manufacturer": "Ford"}}` in `bool.filter`; passes |
| 4 | Empty filter param (e.g. `?manufacturer=`) adds no filter clause (coerced to None) | VERIFIED | `test_empty_filter_param_ignored` verifies no manufacturer key in `bool.filter` when empty string is passed; passes |
| 5 | `GET /api/search?q=anything` while `state["ready"]` is False returns HTTP 503 with `{"status": "starting"}` | VERIFIED | `test_search_503_while_not_ready` asserts `resp.status_code == 503` and `resp.get_json() == {"status": "starting"}`; also asserts `mock_es.search.assert_not_called()`; passes |
| 6 | `GET /api/search` with no q (or blank q) returns 200 empty JSON array with no ES call | VERIFIED | `test_search_empty_q_returns_empty` covers both no-q and whitespace-only q; asserts `resp.get_json() == []` and `mock_es.search.assert_not_called()`; passes |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `nitrofind/server.py` | api_search() route, _result_to_api_dict() helper, state['es_client'] key, es_client assignment in _es_health_poller | VERIFIED | All four symbols present; `@app.route("/api/search")` registered in Flask URL map; `_result_to_api_dict` at line 90; `state["es_client"]` key at line 59; assignment at line 244 |
| `tests/test_search/test_api_search.py` | 8 unit tests covering API-01, API-02, SRVR-03 503 guard | VERIFIED | 8 tests collected and all pass in 0.93s; file contains all required test function names including `test_search_returns_result_array` and `test_excerpt_fallback` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `api_search()` in server.py | `build_search_body` / `build_filter_clauses` in query_builder.py | direct import + function call | VERIFIED | `from nitrofind.search.query_builder import build_search_body, build_filter_clauses` at line 39; both called at lines 141-146 |
| `api_search()` in server.py | `state["es_client"].search` | warm-pool client from poller | VERIFIED | `resp = state["es_client"].search(...)` at line 149; flat keyword API used (`source=`, `from_=`, no `body=`) |
| `_es_health_poller()` | `state["es_client"]` | single-writer assignment before `state["ready"] = True` | VERIFIED | Line 244: `state["es_client"] = client`; line 245: `state["ready"] = True`; correct ordering confirmed programmatically |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `api_search()` | `resp` / `results` | `state["es_client"].search(...)` — warm Elasticsearch client populated by `_es_health_poller` | Yes (live ES node in production; mocked in tests) | VERIFIED (wired to live ES; mock tests confirm response mapping is non-hollow) |

Note: The `state["es_client"]` is set to a real `Elasticsearch(ES_URL, ...)` instance before `state["ready"]` becomes True. The `api_search` route cannot be called before that assignment because the 503 guard fires first (T-07-07). Data flow from ES to JSON response is complete.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 8 api_search tests pass | `python3 -m pytest tests/test_search/test_api_search.py -v` | 8 passed in 0.93s | PASS |
| Full non-integration suite no regression | `python3 -m pytest tests/ -m "not integration" -q` | 143 passed, 5 deselected | PASS |
| server imports cleanly; /api/search registered | `python3 -c "from nitrofind import server; print(server.app.url_map)"` | URL map contains `/api/search` rule | PASS |
| state has es_client key; poller assigns it | `python3 -c "from nitrofind import server; assert 'es_client' in server.state..."` | OK | PASS |
| No forbidden patterns | `grep -n "SearchEngine|client.search(body=" nitrofind/server.py` | No output | PASS |

### Probe Execution

No probe scripts declared in PLAN.md or found at `scripts/*/tests/probe-*.sh`. Step 7c: SKIPPED (no probes for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| API-01 | 07-01-PLAN.md | `GET /api/search?q={query}` returns JSON array with title, url, source_domain, excerpt (ES highlight), score, took_ms | VERIFIED | `test_search_result_shape` asserts exact key set; `test_excerpt_uses_highlight` asserts `<b>` tags present |
| API-02 | 07-01-PLAN.md | `GET /api/search` accepts optional filter params manufacturer, era_bucket, body_style | VERIFIED | `test_manufacturer_filter_forwarded` and `test_empty_filter_param_ignored` pass; route calls `build_filter_clauses()` for all three params |
| API-03 | NOT claimed by this plan | `GET /api/status` returns ES health JSON | N/A — delivered by Phase 6 (06-02-PLAN.md) | `/api/status` implemented in server.py at line 73; Phase 6 VERIFICATION.md marks this VERIFIED |
| API-04 | NOT claimed by this plan | `GET /` serves HTML search page (placeholder) | N/A — delivered by Phase 6 (06-02-PLAN.md) | `index()` route at line 67; Phase 6 VERIFICATION.md marks this VERIFIED |

Note on REQUIREMENTS.md traceability table: The table maps API-03 and API-04 to "Phase 7 / Pending" — this is stale. ROADMAP.md Phase Details (the authoritative source) lists them under Phase 6, and Phase 6 VERIFICATION.md confirms both as VERIFIED. No gap here; the traceability table needs a documentation update (not a code gap).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `nitrofind/server.py` | 9, 20, 69 | "placeholder" in docstrings | Info | These describe the intentional D-13 GET / placeholder for Phase 8; not a stub — the route returns real HTML. No TBD/FIXME/XXX markers found. |

No blockers. No TBD/FIXME/XXX markers. No `return null` / `return {}` / `return []` stubs in the implementation path. The "placeholder" word appears only in docstrings describing an intentional Phase 8 deferral.

### Human Verification Required

The automated suite passes completely (6/6 truths, 8/8 tests, 143/143 non-integration tests). The three items below require a live running stack to confirm end-to-end behavior with a real Elasticsearch node and real indexed documents.

#### 1. Live Search Returns Real Results With Highlights

**Test:** Start the app with `python main.py`, wait for ES to become healthy (check `curl http://localhost:5000/api/status` for `"status":"ok"`), then run `curl -s 'http://localhost:5000/api/search?q=mustang' | python3 -m json.tool`
**Expected:** HTTP 200; JSON array of one or more objects each with `title`, `url`, `source_domain`, `excerpt` (containing `<b>` tags if the index has documents), `score`, `took_ms`
**Why human:** Requires a live Elasticsearch node with the `car_articles` index populated. Mock tests confirm the serialization path but cannot prove ES is running, the index exists, or that real highlights are returned.

#### 2. Filter Param Narrows Live Results

**Test:** With the app running and ready, compare `curl 'http://localhost:5000/api/search?q=ford'` vs `curl 'http://localhost:5000/api/search?q=ford&manufacturer=Ford'`
**Expected:** The filtered response contains only articles with manufacturer=Ford; result count is equal or smaller
**Why human:** Filter correctness in a populated index cannot be asserted without real indexed documents with a `manufacturer` field.

#### 3. 503 Guard During Real Startup Race

**Test:** Immediately after `python main.py` (before ES becomes healthy), run `curl -s -o /dev/null -w '%{http_code}' 'http://localhost:5000/api/search?q=anything'`
**Expected:** HTTP 503
**Why human:** The timing-dependent warmup window is real-environment behavior; mocked deterministically in tests but requires human observation in the live startup sequence.

### Gaps Summary

No gaps. All six must-have truths are VERIFIED, all required artifacts exist and are substantive, all key links are wired, and no anti-pattern blockers were found. The phase goal — a stable JSON search endpoint returning ranked results with highlights and optional facet filters — is achieved in the codebase.

The three human verification items are standard integration/smoke-test checks that require a live Elasticsearch node. They do not indicate incomplete implementation — they are runtime environment checks that automated grep-based verification cannot substitute for.

---

_Verified: 2026-06-03T20:30:00Z_
_Verifier: Claude (gsd-verifier)_
