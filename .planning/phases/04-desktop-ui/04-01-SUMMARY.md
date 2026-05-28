---
phase: 04-desktop-ui
plan: "01"
subsystem: search
tags:
  - phase-4
  - desktop-ui
  - wave-0-extensions
  - models
  - engine
  - signals
dependency_graph:
  requires:
    - 03-search-logic-relevance-scoring/03-*
  provides:
    - ArticleResult.body field for SRCH-03 detail pane
    - results_ready(list, int) signal for UIPL-02 query time display
    - tests/test_ui/ package for Phase 4 test files
  affects:
    - nitrofind/search/models.py
    - nitrofind/search/query_builder.py
    - nitrofind/search/engine.py
    - tests/test_search/test_models.py
    - tests/test_search/test_engine.py
    - tests/test_search/test_query_builder.py
    - tests/test_ui/__init__.py
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN per task (test commit before implementation commit)"
    - "pyqtSignal(list, int) — two-arg signal for results+metadata"
    - "resp.get('took', 0) — safe integer extraction from ES response"
key_files:
  created:
    - tests/test_ui/__init__.py
  modified:
    - nitrofind/search/models.py (lines 1-94: docstring, body field at line 41, from_es_hit at line 80)
    - nitrofind/search/query_builder.py (line 242: "body" added to _source list)
    - nitrofind/search/engine.py (lines 1-181: docstring, pyqtSignal(list,int) line 54, run() lines 107-108, callback annotation line 145)
    - tests/test_search/test_models.py (lines 58-66: body in expected_fields; lines 155-191: new body tests)
    - tests/test_search/test_engine.py (lines 293-337: new took_ms tests; all lambda updates)
    - tests/test_search/test_query_builder.py (line 267-272: body in expected _source)
decisions:
  - "body field placed immediately after excerpt in both dataclass definition and from_es_hit return clause — matches plan spec"
  - "took_ms falls back to 0 via resp.get('took', 0) — safe for ES responses that omit the took field"
metrics:
  duration: "7 minutes"
  completed: "2026-05-28"
  tasks_completed: 3
  files_modified: 6
  files_created: 1
---

# Phase 4 Plan 01: Wave 0 Extensions (body field, took_ms, test_ui package) Summary

**One-liner:** Extended Phase 3 contracts with ArticleResult.body field (W0-EXT-01), results_ready(list, int) signal with took_ms (W0-EXT-02), and created tests/test_ui/ package marker to unblock Phase 4 UI plans.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extend ArticleResult with body field + query_builder _source | e47c221 | models.py, query_builder.py, test_models.py |
| 2 | Extend results_ready to (list, int) + update engine + tests | d2d7e6b | engine.py, test_engine.py |
| 3 | Create tests/test_ui/ package marker + full suite verification | 2f9d6b9 | tests/test_ui/__init__.py, test_query_builder.py |

## Extension Confirmations

### W0-EXT-01: ArticleResult.body field

- `ArticleResult` dataclass in `nitrofind/search/models.py` has `body: str = ""` after `excerpt`
- `from_es_hit()` returns `body=src.get("body", "")` — safe default for missing field
- `build_search_body()` `_source` list in `nitrofind/search/query_builder.py` includes `"body"`
- Module docstring updated to reference W0-EXT-01

### W0-EXT-02: results_ready(list, int) signal with took_ms

- `_SearchSignals.results_ready` is now `pyqtSignal(list, int)` (int = took_ms)
- `_SearchWorker.run()` extracts `took_ms = resp.get("took", 0)` and emits `results_ready(results, took_ms)`
- `SearchEngine.search()` callback annotation updated to `Callable[[list, int], None] | None`
- All `results_ready.connect()` lambdas in `test_engine.py` updated to two-arg `(results, took)` form
- Module docstring updated to reference W0-EXT-02

### tests/test_ui/ package marker

- `tests/test_ui/__init__.py` created (1 byte — single newline)
- `python3 -c "import tests.test_ui"` exits 0

## Final Test Suite Status

```
pytest tests/ -x -m "not integration"
130 passed, 6 deselected in 3.21s
```

All Phase 1-3 tests still pass. No regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_build_search_body_source_fields in test_query_builder.py was stale**
- **Found during:** Task 3 full suite run
- **Issue:** `test_build_search_body_source_fields` hardcoded the old `_source` list without `"body"` — failed after W0-EXT-01 added `"body"` to the list
- **Fix:** Added `"body"` to the `expected_source` list in the test at the same position it appears in the production code (after `"excerpt"`)
- **Files modified:** `tests/test_search/test_query_builder.py`
- **Commit:** 2f9d6b9

### Accidental Main Branch Commit (Recovered)

During initial setup, Edit tool used the main repo path (`/mnt/c/Users/Leonardo/.../NitroFind/`) instead of the worktree path. One commit landed on `main` by mistake. The commit was immediately reverted on `main` (`git revert --no-commit`) and correctly re-applied to the worktree branch. No work was lost. The revert commit appears in `main` history.

## Known Stubs

None — this plan only modifies existing data model and signal infrastructure, not UI rendering or data display. No stub values introduced.

## Threat Flags

No new threat surface introduced. The `body` field is consumed as plain text content (T-04-01: mitigated in Plan 03 via QTextBrowser). The `took_ms` integer is read from trusted local ES instance (T-04-02: mitigated by localhost-only ES config from Phase 1).

## Self-Check: PASSED

All created/modified files exist on disk. All task commits present in git log.
Content spot-checks confirmed:
- `body: str = ""` in models.py
- `body=src.get("body", "")` in from_es_hit
- `"body"` in query_builder.py _source list
- `pyqtSignal(list, int)` in engine.py
- `took_ms = resp.get("took", 0)` in _SearchWorker.run()
- `results_ready.emit(results, took_ms)` in _SearchWorker.run()
- `tests/test_ui/__init__.py` exists (1 byte)
