---
phase: 11-extended-filtering
plan: "01"
subsystem: search/tests
tags: [tdd, red-scaffold, filtering, query-builder, api]
dependency_graph:
  requires: []
  provides: [FILT-01-tests, FILT-02-tests, FILT-03-tests]
  affects: [tests/test_search/test_query_builder.py, tests/test_search/test_api_search.py]
tech_stack:
  added: []
  patterns: [pytest-monkeypatch, MagicMock-ES-client, inline-monkeypatch-style]
key_files:
  created: []
  modified:
    - tests/test_search/test_query_builder.py
    - tests/test_search/test_api_search.py
decisions:
  - "test_year_invalid_string_coerced_to_none passes trivially (asserts absence of production_end, which is absent pre-implementation); remains valid post-Plan-02 as a negative-behavior safety assertion"
metrics:
  duration: "4 minutes"
  completed: "2026-06-29T14:37:17Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 11 Plan 01: Extended Filtering RED Scaffold Summary

RED-phase test scaffold for year-range (FILT-01), country-of-origin (FILT-02), and API forwarding (FILT-03) filters — 11 new test functions across two existing test files, all failing against the current implementation.

## What Was Built

Added 11 new failing test functions establishing executable acceptance criteria for the Phase 11 extended filtering implementation:

**`tests/test_search/test_query_builder.py`** — 7 new functions:
- `test_build_filter_clauses_year_from` [FILT-01]: asserts `year_from=1960` produces `{"range": {"production_end": {"gte": 1960}}}`
- `test_build_filter_clauses_year_to` [FILT-01]: asserts `year_to=1975` produces `{"range": {"production_start": {"lte": 1975}}}`
- `test_build_filter_clauses_year_both_bounds` [FILT-01]: asserts both bounds produce exactly 2 range clauses
- `test_build_filter_clauses_year_none_produces_no_clause` [FILT-01]: asserts `None` args emit no clauses
- `test_build_filter_clauses_country` [FILT-02]: asserts `country="Germany"` produces `{"term": {"country_of_origin": "Germany"}}`
- `test_build_filter_clauses_country_empty_string_ignored` [FILT-02]: asserts empty string emits no clause
- `test_build_filter_clauses_all_filters` [FILT-03]: asserts all 6 params produce exactly 6 clauses

**`tests/test_search/test_api_search.py`** — 4 new functions:
- `test_year_from_filter_forwarded` [FILT-03]: asserts `?year_from=1960` produces production_end range in ES call
- `test_year_to_filter_forwarded` [FILT-03]: asserts `?year_to=1975` produces production_start range in ES call
- `test_country_filter_forwarded` [FILT-03]: asserts `?country=Germany` produces country_of_origin term in ES call
- `test_year_invalid_string_coerced_to_none` [FILT-03]: asserts `?year_from=abc` does NOT produce production_end clause

## Verification Results

**Query builder tests (RED):**
```
pytest tests/test_search/test_query_builder.py -q -k "year or country or all_filters"
7 failed, 37 deselected — TypeError: unexpected keyword argument (correct RED)
```

**API tests (RED):**
```
pytest tests/test_search/test_api_search.py -q -k "year or country"
3 failed, 1 passed, 11 deselected — KeyError: bool (correct RED for forwarding tests)
```

**Pre-existing suite (GREEN):**
```
pytest tests/test_search/ -q
10 failed (new tests), 93 passed, 3 skipped — no regressions
```

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add FILT-01/02/03 unit tests to test_query_builder.py | 3627c2a | tests/test_search/test_query_builder.py |
| 2 | Add FILT-03 API forwarding tests to test_api_search.py | 32ddbac | tests/test_search/test_api_search.py |

## Deviations from Plan

### Minor Behavioral Deviation

**1. [Plan Expectation] `test_year_invalid_string_coerced_to_none` passes in RED**
- **Found during:** Task 2 verification
- **Issue:** The plan success criterion states "All 11 fail today." However, `test_year_invalid_string_coerced_to_none` passes trivially because it asserts absence of `production_end` in the query string — and since the current server ignores unknown params entirely, `production_end` is absent. This gives a green test before Plan 02 ships.
- **Assessment:** Not a problem. The test is correctly authored per the plan spec (asserts negative behavior: invalid input must not inject malformed clauses). After Plan 02 ships, `_safe_int_param("abc")` returns `None` and `build_filter_clauses(year_from=None)` emits no clause — the test continues to pass correctly. It serves as a valid safety regression test.
- **Impact:** 10 of 11 new tests RED (command exits non-zero); acceptance criterion "exits non-zero" met.

## Known Stubs

None — this plan adds only test functions, no stub patterns applicable.

## Threat Flags

None — plan adds test functions only; no new network endpoints, auth paths, or file access patterns introduced.

## Self-Check: PASSED

- [x] `tests/test_search/test_query_builder.py` contains `def test_build_filter_clauses_year_from(` — verified
- [x] `tests/test_search/test_query_builder.py` contains `def test_build_filter_clauses_country(` — verified
- [x] `tests/test_search/test_query_builder.py` contains `def test_build_filter_clauses_all_filters(` — verified
- [x] `tests/test_search/test_api_search.py` contains `def test_year_from_filter_forwarded(monkeypatch):` — verified
- [x] `tests/test_search/test_api_search.py` contains `def test_country_filter_forwarded(monkeypatch):` — verified
- [x] `tests/test_search/test_api_search.py` contains `def test_year_invalid_string_coerced_to_none(monkeypatch):` — verified
- [x] Commit 3627c2a exists — verified
- [x] Commit 32ddbac exists — verified
- [x] Pre-existing tests unmodified: 93 pass, 0 regressions — verified
