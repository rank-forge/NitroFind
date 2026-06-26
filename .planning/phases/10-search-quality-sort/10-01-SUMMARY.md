---
phase: 10-search-quality-sort
plan: "01"
subsystem: search-backend
tags: [fuzzy-search, phrase-routing, sort, query-builder, flask-api, tdd]
dependency_graph:
  requires: []
  provides: [fuzzy-routing, phrase-routing, sort-api]
  affects: [nitrofind/search/query_builder.py, nitrofind/server.py]
tech_stack:
  added: []
  patterns: [phrase-branch-query, sort-clauses-helper, request-param-allowlist]
key_files:
  created: []
  modified:
    - nitrofind/search/query_builder.py
    - nitrofind/server.py
    - tests/test_search/test_query_builder.py
    - tests/test_search/test_api_search.py
decisions:
  - Frozenset for _VALID_SORTS to signal immutability intent at module level
  - sort param placed between from_ and recency_weight in build_search_body signature to maintain weight params as trailing defaults
metrics:
  duration_minutes: 3
  completed_date: "2026-06-26"
  tasks_completed: 3
  files_modified: 4
---

# Phase 10 Plan 01: Search Backend — Fuzzy Routing, Phrase Routing, Sort Summary

**One-liner:** Phrase-branching multi_match with fuzziness:AUTO on non-quoted path, type:phrase on quoted path, plus `_build_sort_clauses` helper and Flask sort allowlist wiring `_VALID_SORTS={"relevance","date","size"}`.

## What Was Built

Three backend changes to enable typo tolerance, exact-phrase matching, and sortable results:

1. **Fuzzy routing (QURY-01):** `build_function_score_query` now branches on phrase detection. Non-quoted input gets `type:best_fields` with `fuzziness:"AUTO"` and `prefix_length:1`, enabling typo tolerance ("Ferari" matches "Ferrari"). Quoted input skips fuzziness entirely to avoid ES 400 errors.

2. **Phrase routing (QURY-02):** Quoted input (e.g. `"V8 engine"`) is detected via `startswith('"') and endswith('"') and len > 2`, routes to `type:phrase` with quotes stripped. The `len > 2` guard rejects empty `""` input. No `fuzziness` key is emitted on the phrase path.

3. **Sort param API (SORT-02):** New `_build_sort_clauses(sort)` free function returns `[{"published_at": {"order": "desc"}}]` for `"date"`, `[{"word_count": {"order": "desc"}}]` for `"size"`, and `None` for anything else. `build_search_body` gains a `sort:str|None=None` parameter; the `"sort"` key is conditionally added to the result dict. `server.py` defines `_VALID_SORTS` frozenset, extracts the sort param with allowlist guard, and passes `sort=body.get("sort")` to `client.search()` using the existing flat-keyword API.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED tests — fuzzy, phrase, sort | 813366f | tests/test_search/test_query_builder.py, tests/test_search/test_api_search.py |
| 2 | GREEN — query_builder.py implementation | 37aeaf2 | nitrofind/search/query_builder.py |
| 3 | GREEN — server.py sort allowlist + wiring | 94ce46a | nitrofind/server.py |

## TDD Gate Compliance

- RED gate: `test(10-01)` commit `813366f` — 12 new tests added (7 failing before implementation)
- GREEN gate: `feat(10-01)` commit `37aeaf2` + `94ce46a` — all 12 tests pass after implementation
- REFACTOR gate: Not needed — implementation was clean on first pass

## Verification Results

```
python3 -m pytest tests/ -q -m "not integration"
170 passed, 5 deselected
```

All pre-existing RLVN tests (function_score structure, filter forwarding, API shape) still pass.

## Key Decisions

1. **frozenset for `_VALID_SORTS`** — signals immutability intent at module level; matches `MAX_RESULT_SIZE` constant pattern nearby.
2. **`sort` param placed between `from_` and weight params** — keeps all weight parameters together as trailing defaults; `sort` is a routing concern, not a weight concern.
3. **`sort=None` passed to `client.search()`** — elasticsearch-py 8.x treats `None` kwargs as "omit the parameter", matching Pitfall 4 guidance from RESEARCH.md. No conditional logic needed in the route.
4. **`_build_sort_clauses` returns `None` for relevance** — absence of `"sort"` key in the body dict is the signal for ES default `_score desc`; a caller checking `body.get("sort")` naturally gets `None`.

## Deviations from Plan

None — plan executed exactly as written. All patterns from PATTERNS.md followed verbatim.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The `_VALID_SORTS` allowlist is the only security-relevant surface (T-10-SORT mitigation from the plan's threat model). All threats from the plan's STRIDE register were addressed:
- T-10-SORT: allowlist implemented in `server.py`
- T-10-PHRASE: `len > 2` guard implemented in `query_builder.py`
- T-10-FUZZ: accepted via `prefix_length=1` (no override needed)
- T-10-01: test fixtures use synthetic mock data only

## Self-Check: PASSED

Files created/modified:
- FOUND: nitrofind/search/query_builder.py (modified)
- FOUND: nitrofind/server.py (modified)
- FOUND: tests/test_search/test_query_builder.py (modified)
- FOUND: tests/test_search/test_api_search.py (modified)

Commits:
- FOUND: 813366f (test(10-01): add failing tests...)
- FOUND: 37aeaf2 (feat(10-01): add fuzzy routing, phrase routing...)
- FOUND: 94ce46a (feat(10-01): add sort param allowlist...)
