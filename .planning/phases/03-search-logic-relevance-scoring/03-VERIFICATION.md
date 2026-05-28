---
phase: 03-search-logic-relevance-scoring
verified: 2026-05-27T12:00:00Z
status: human_needed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Search 'Ferrari 308' against live indexed data and confirm Wikipedia article appears in top 3 results"
    expected: "At least one of the top 3 results has '308' in the title, coming from the Wikipedia source"
    why_human: "Requires live Elasticsearch with indexed data; ES_HOME not set in this environment so integration tests skip"
  - test: "Index two articles — one published 2 years ago, one published 10 years ago — search and confirm the recent article scores measurably higher on the recency signal"
    expected: "The 2-year-old article's function_score recency component (fn0) produces a higher weight contribution than the 10-year-old article"
    why_human: "Requires live indexed data with known published_at values to compare scores; not provable from static DSL structure alone"
  - test: "Index a long article (high word_count, has_infobox=True) and a short article (low word_count, has_infobox=False) for the same query term; confirm the long/infobox article consistently scores higher"
    expected: "The log1p(word_count) signal and has_infobox weight boost visibly separate the two articles in the ranked result list"
    why_human: "Requires live indexed data with controlled word_count and has_infobox variation; cannot be verified by DSL inspection alone"
---

# Phase 3: Search Logic & Relevance Scoring Verification Report

**Phase Goal:** A tested Python search layer translates a query string and optional filter set into an Elasticsearch function_score query, returns ranked ArticleResult objects with highlighted excerpts, and produces results whose ranking reflects source quality signals on real indexed data.
**Verified:** 2026-05-27
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ArticleResult can be constructed from any ES hit dict with safe defaults for missing fields | VERIFIED | `from_es_hit({})` returns instance with `title=""`, `score=0.0`, `highlight_body=[]`; all 8 unit tests in `test_models.py` pass; `.get()` used on every field access |
| 2 | `build_function_score_query()` returns a dict with all four function_score functions present | VERIFIED | `len(fs["functions"]) == 4` confirmed via inline Python assertion and `test_function_score_has_four_functions` test |
| 3 | Gaussian decay function is gated by exists filter so missing published_at cannot receive score 1.0 | VERIFIED | fn0 has `{"exists": {"field": "published_at"}}`; fn1 has `{"bool": {"must_not": {"exists": {"field": "published_at"}}}}` with `weight=0.3`; `test_missing_published_fallback` passes |
| 4 | field_value_factor uses log1p modifier and missing=1 fallback so word_count=0 is safe | VERIFIED | `fn2["field_value_factor"]["modifier"] == "log1p"` and `fn2["field_value_factor"]["missing"] == 1`; `test_length_signal_in_query` and `test_log1p_not_log_modifier` pass |
| 5 | score_mode is sum and boost_mode is multiply per RLVN-04 | VERIFIED | `fs["score_mode"] == "sum"` and `fs["boost_mode"] == "multiply"`; `test_score_and_boost_modes` passes |
| 6 | build_filter_clauses() and build_search_body() produce correct bool filter wrapping | VERIFIED | `build_filter_clauses()` returns `[]`; `build_filter_clauses(manufacturer="BMW")` returns `[{"term": {"manufacturer": "BMW"}}]`; `build_search_body` with filters wraps inner query in bool.must; 8 filter/body tests pass |
| 7 | SearchEngine.search() delivers results via callback using QRunnable worker pattern | VERIFIED | 30 unit tests pass; `test_run_emits_results_ready_on_success` confirms callback delivery via `_SearchWorker.run()` called synchronously with mock client; `test_search_returns_none` confirms non-blocking API |
| 8 | Signal connections are established before pool.start(worker); ES_URL imported from es_manager; index hard-coded as "car_articles" | VERIFIED | Lines 167/169 (signal connect) precede line 172 (`pool.start`) in `engine.py`; `from nitrofind.es_manager import ES_URL` present; `index="car_articles"` hard-coded as string literal; structural tests in `TestEngineModuleContracts` all pass |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `nitrofind/search/__init__.py` | Package init re-exporting SearchEngine and ArticleResult; `__all__` defined | VERIFIED | Exists, 9 lines; `try/except` guard on engine import for Wave 1 isolation; `__all__ = ["SearchEngine", "ArticleResult"]` present; importable |
| `nitrofind/search/models.py` | ArticleResult dataclass with from_es_hit classmethod | VERIFIED | Exists, 84 lines; all 13 fields declared; `from_es_hit` uses `.get()` on every field; no direct `hit["key"]` access |
| `nitrofind/search/query_builder.py` | build_function_score_query, build_filter_clauses, build_search_body | VERIFIED | Exists, 230 lines; all three functions exported; 5 module constants declared; no `2y`/`24m` scale; no `modifier="log"` |
| `nitrofind/search/engine.py` | SearchEngine class with _SearchSignals, _SearchWorker, and search() method | VERIFIED | Exists, 173 lines; `_SearchSignals(QObject)` with `results_ready` and `search_failed`; `_SearchWorker(QRunnable)` with `@pyqtSlot() run()`; `SearchEngine` with `search()` returning None; flat keyword API; no `body=` kwarg |
| `tests/test_search/__init__.py` | Empty package init | VERIFIED | Exists, 0 bytes |
| `tests/test_search/test_models.py` | ArticleResult unit tests | VERIFIED | Exists; 8 tests collected; all 8 pass |
| `tests/test_search/test_query_builder.py` | Unit tests for all four RLVN requirements | VERIFIED | Exists; 28 tests collected; all 28 pass |
| `tests/test_search/test_engine.py` | Unit + integration tests for engine | VERIFIED | Exists; 33 tests collected (30 unit + 3 integration); 30 unit tests pass; 3 integration tests skip cleanly with "ES_HOME not set" message |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `nitrofind/search/query_builder.py` | Elasticsearch function_score DSL | `function_score` dict with four functions, `score_mode="sum"` | WIRED | Inline Python assertions confirm structure; `score_mode.*sum` pattern present at line 131 |
| `nitrofind/search/models.py` | ES hit dict | `from_es_hit` classmethod using `.get()` with safe defaults | WIRED | `def from_es_hit` at line 52; `src = hit.get("_source", {})` pattern confirmed |
| `nitrofind/search/engine.py` | `nitrofind/search/query_builder.py` | `from nitrofind.search.query_builder import build_search_body` | WIRED | Import present at module level; `build_search_body` called in `SearchEngine.search()` at line 161 |
| `nitrofind/search/engine.py` | `nitrofind/es_manager.py` | `from nitrofind.es_manager import ES_URL` | WIRED | Import present at line 30; `ES_URL` accessible in engine module namespace; `test_es_url_imported_from_es_manager` passes |
| `_SearchWorker.run()` | `client.search()` | Flat keyword API (`index=`, `query=`, `highlight=`, `source=`, `size=`, `from_=`) | WIRED | `client.search(index="car_articles", query=..., ...)` at lines 95–102; no `body=` kwarg; `test_run_uses_flat_keyword_api_not_body` passes |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_SearchWorker.run()` | `results` list | `resp["hits"]["hits"]` from `self._client.search(...)` | Yes — live ES query with real function_score DSL built by `build_search_body` | FLOWING |
| `SearchEngine.search()` | callback receives `list[ArticleResult]` | `signals.results_ready.emit(results)` from `_SearchWorker.run()` | Yes — wired through real QRunnable/QThreadPool pipeline | FLOWING |
| `ArticleResult.from_es_hit` | All 13 fields | ES `_source` dict and `highlight` dict via `.get()` | Yes — maps real ES response structure to typed Python object | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `build_function_score_query("Ferrari")` returns four-function structure with correct modes | `python3 -c "...all assertions..."` | All assertions pass | PASS |
| `build_search_body("Ferrari", size=999)["size"] == 100` | `python3 -c "..."` | `100` | PASS |
| `ArticleResult.from_es_hit({})` returns safe defaults without KeyError | `python3 -c "..."` | `title=""`, `score=0.0`, `highlight_body=[]` | PASS |
| 66 unit tests pass without live ES | `python3 -m pytest tests/test_search/ -m "not integration" -x -q` | `66 passed, 3 deselected in 1.27s` | PASS |
| Full project test suite — no regressions | `python3 -m pytest tests/ -m "not integration" -x -q` | `126 passed, 6 deselected in 3.63s` | PASS |
| Integration tests skip cleanly without ES_HOME | `python3 -m pytest tests/test_search/test_engine.py -m "integration" -v` | `3 skipped (ES_HOME not set)` | PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes exist for this phase. Behavioral spot-checks above served as the executable verification layer.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RLVN-01 | 03-01, 03-02, 03-03 | Gaussian recency decay with ~2-year half-life | SATISFIED (unit: structure; integration: deferred to human) | fn0: `gauss.published_at.scale="730d"`, `decay=0.5`, `origin="now"`, `filter={"exists":{"field":"published_at"}}`; fn1: missing-field fallback `weight=0.3`; `test_recency_decay_in_query` and `test_missing_published_fallback` pass |
| RLVN-02 | 03-01, 03-03 | Logarithmic word_count signal | SATISFIED | fn2: `field_value_factor.modifier="log1p"`, `field="word_count"`, `missing=1`; `test_length_signal_in_query` and `test_log1p_not_log_modifier` pass |
| RLVN-03 | 03-01, 03-03 | Boolean boost for has_infobox=True | SATISFIED | fn3: `filter={"term":{"has_infobox":True}}`, `weight=0.5`; `test_infobox_boost_in_query` passes |
| RLVN-04 | 03-01, 03-03 | score_mode=sum; boost_mode=multiply | SATISFIED | `fs["score_mode"]=="sum"` and `fs["boost_mode"]=="multiply"` confirmed; `test_score_and_boost_modes` passes |

Note: REQUIREMENTS.md traceability table still shows RLVN-01..04 as "Pending" (unchecked). The implementation satisfies all four requirements per code evidence, but the tracking file was not updated during this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | No TBD/FIXME/XXX markers; no unguarded `return []`/`return {}`; no f-strings in logger calls; no `body=` kwarg; no `QThreadPool()` direct constructor |

### Human Verification Required

The three roadmap Success Criteria that require live indexed Elasticsearch data cannot be verified programmatically in this environment (ES_HOME is not set). Integration tests for all three are present in `tests/test_search/test_engine.py`, correctly marked `@pytest.mark.integration`, and skip with "ES_HOME not set". Human verification must confirm the ranking behavior against real data.

#### 1. Ferrari 308 Top-3 Result (SC1)

**Test:** With the car_articles index populated from Phase 2, run: `pytest tests/test_search/test_engine.py::test_ferrari_308_top3 -v` (with ES_HOME set)
**Expected:** At least one of the top 3 results has "308" in the title, confirming text relevance and recency decay work together on real indexed data
**Why human:** Requires live Elasticsearch with real Phase 2 indexed data; ES_HOME unavailable in this environment

#### 2. Recency Decay Active on Real Data (SC2)

**Test:** With the car_articles index populated, run: `pytest tests/test_search/test_engine.py::test_recency_decay_active -v` (with ES_HOME set)
**Expected:** The `_explanation` field appears in the first hit when `explain=True` is passed, confirming the function_score scoring tree (including Gaussian decay) is computing scores; then manually compare scores of a recently published vs. decade-old article for the same query
**Why human:** The `explain=True` test only proves the scoring tree is active — confirming that recent articles measurably outscore older ones requires inspecting actual `_score` values from indexed documents with known `published_at` dates

#### 3. Length Signal + Infobox Boost Active on Real Data (SC3)

**Test:** Query the car_articles index for a term that returns both a long Wikipedia article (with infobox) and a shorter blog article (without infobox). Compare `_score` values.
**Expected:** The long infobox-equipped article outscores the shorter infobox-free article for the same query, confirming both RLVN-02 and RLVN-03 signals are active and additive
**Why human:** Requires controlled comparison of real indexed documents; cannot be proven by DSL inspection or mock data

### Gaps Summary

No gaps. All code artifacts exist and are substantive (not stubs), all key wiring links are present, all 66 unit tests pass, no regressions in the broader test suite, and no unresolved debt markers were found.

The three human verification items are not code gaps — they are behavioral validations of the scoring system on real data that are only observable with a live Elasticsearch index populated by Phase 2.

---

_Verified: 2026-05-27_
_Verifier: Claude (gsd-verifier)_
