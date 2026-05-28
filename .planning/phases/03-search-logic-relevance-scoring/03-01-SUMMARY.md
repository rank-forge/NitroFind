---
phase: 03-search-logic-relevance-scoring
plan: 01
subsystem: search
tags: [search, query-builder, dataclass, function-score, relevance]
dependency_graph:
  requires: []
  provides:
    - nitrofind.search.models.ArticleResult
    - nitrofind.search.query_builder.build_function_score_query
    - nitrofind.search.query_builder.build_filter_clauses
    - nitrofind.search.query_builder.build_search_body
  affects:
    - nitrofind.search.engine (Plan 03-02 imports from both modules)
    - tests/test_search/ (Plan 03-03 tests depend on these modules)
tech_stack:
  added: []
  patterns:
    - Gaussian decay with exists-filter split (avoids missing-field=1.0 ES bug)
    - field_value_factor with log1p modifier (safe for word_count=0)
    - MAX_RESULT_SIZE clamp in build_search_body (T-03-02 DoS mitigation)
    - TDD: RED (failing tests) then GREEN (implementation) commit pattern
key_files:
  created:
    - nitrofind/search/__init__.py
    - nitrofind/search/models.py
    - nitrofind/search/query_builder.py
    - tests/test_search/__init__.py
    - tests/test_search/test_models.py
    - tests/test_search/test_query_builder.py
  modified: []
decisions:
  - "ArticleResult.from_es_hit uses .get() for every field — no direct dict key access"
  - "Gauss scale is 730d (not 2y/24m) — year/month units unsupported in ES decay functions"
  - "Two-function split for published_at: fn0 gated by exists filter, fn1 by must_not exists"
  - "log1p modifier (not log) for field_value_factor — log(0) undefined, log1p(0)=0 safe"
  - "MAX_RESULT_SIZE=100 hard cap enforced via min(size, MAX_RESULT_SIZE) in build_search_body"
  - "__init__.py uses try/except on engine import for Wave 1 test isolation before engine.py exists"
metrics:
  duration: 4m
  completed: 2026-05-28
  tasks_completed: 2
  files_created: 6
---

# Phase 3 Plan 1: Search Package Foundation (models.py + query_builder.py) Summary

**One-liner:** ArticleResult dataclass with from_es_hit safe defaults and four-function Elasticsearch function_score query builder implementing RLVN-01..04 with Gaussian decay (730d scale), log1p length signal, has_infobox boost, and MAX_RESULT_SIZE=100 DoS cap.

## What Was Built

Created the `nitrofind/search/` package foundation: two pure-Python modules with no ES connection dependency, making them fully unit-testable in Wave 1. This establishes the typed contracts that `engine.py` (Plan 03-02) imports and that Wave 2 tests assert against.

### `nitrofind/search/__init__.py`
Package init with try/except guard on SearchEngine import (engine.py not yet created) and unconditional ArticleResult re-export. `__all__ = ["SearchEngine", "ArticleResult"]`.

### `nitrofind/search/models.py`
`ArticleResult` dataclass with 13 typed fields matching the ES index mapping (`CAR_ARTICLES_MAPPING.properties`). The `from_es_hit(hit: dict)` classmethod uses `.get()` for every field access — no direct key access — so an empty or partially populated ES hit dict never raises `KeyError`. Highlight fields use `field(default_factory=list)` to avoid shared mutable default.

### `nitrofind/search/query_builder.py`
Three functions implementing the ES query DSL layer:

- **`build_function_score_query()`** — Returns the complete four-function `function_score` dict:
  - fn0: Gaussian recency decay gated by `{"exists": {"field": "published_at"}}` filter — prevents missing-field=1.0 ES bug
  - fn1: Fixed weight fallback (`{"bool": {"must_not": {"exists": ...}}}`) for undated articles
  - fn2: `field_value_factor` with `modifier="log1p"` and `missing=1` on `word_count`
  - fn3: Weight boost filtered to `{"term": {"has_infobox": True}}`
  - `score_mode="sum"`, `boost_mode="multiply"` (RLVN-04)
- **`build_filter_clauses()`** — Returns term filter list for manufacturer, era_bucket, body_style facets
- **`build_search_body()`** — Assembles complete search body with highlight config and `size` clamped to `MAX_RESULT_SIZE=100` (T-03-02)

### Tests Created
- `tests/test_search/test_models.py` — 8 tests covering ArticleResult construction and from_es_hit behavior
- `tests/test_search/test_query_builder.py` — 28 tests covering all function_score structure assertions, filter clauses, and search body construction

## Task Commits

| Task | Phase | Type | Commit | Description |
|------|-------|------|--------|-------------|
| 1 | RED | test | `7b1d06b` | Failing tests for ArticleResult dataclass |
| 1 | GREEN | feat | `2b8a412` | ArticleResult dataclass with from_es_hit |
| 2 | RED | test | `827afa1` | Failing tests for query_builder functions |
| 2 | GREEN | feat | `204efc8` | query_builder with function_score DSL |

## TDD Gate Compliance

- RED gate (test commit): `7b1d06b` (task 1), `827afa1` (task 2) — both confirmed failing before implementation
- GREEN gate (feat commit): `2b8a412` (task 1), `204efc8` (task 2) — all tests passing after implementation

## Deviations from Plan

None — plan executed exactly as written.

Both tasks followed the TDD RED/GREEN cycle. All acceptance criteria verified via `python3 -c` inline assertions and `pytest` runs. No architectural decisions required. No new packages installed.

## Verification Results

```
python3 -m pytest tests/test_search/ -m "not integration" -x -q
36 passed in 1.11s
```

```
python3 -c "from nitrofind.search.models import ArticleResult; from nitrofind.search.query_builder import build_function_score_query, build_search_body, build_filter_clauses; print('imports OK')"
imports OK
```

## Known Stubs

None — all fields wired from ES hit dict; no hardcoded empty values that flow to UI rendering. `build_function_score_query` weights use literature-derived starting values (recency=1.5, length=1.0, infobox=0.5) noted in STATE.md as needing empirical tuning after Phase 4 integration — this is a tuning concern, not a stub.

## Threat Flags

No new threat surface introduced beyond what is documented in the plan's threat model:
- T-03-01 (mitigated): `query_text` placed inside `multi_match.query` string field only — never interpolated into DSL keys
- T-03-02 (mitigated): `min(size, MAX_RESULT_SIZE)` enforced in `build_search_body`
- T-03-03 (accepted): `ArticleResult` exposes only public ES `_source` fields — no PII or system paths

## Self-Check: PASSED

Files exist:
- [x] `nitrofind/search/__init__.py`
- [x] `nitrofind/search/models.py`
- [x] `nitrofind/search/query_builder.py`
- [x] `tests/test_search/__init__.py`
- [x] `tests/test_search/test_models.py`
- [x] `tests/test_search/test_query_builder.py`

Commits exist:
- [x] `7b1d06b` — test(03-01): add failing tests for ArticleResult dataclass
- [x] `2b8a412` — feat(03-01): implement ArticleResult dataclass with from_es_hit
- [x] `827afa1` — test(03-01): add failing tests for query_builder functions
- [x] `204efc8` — feat(03-01): implement query_builder with function_score DSL
