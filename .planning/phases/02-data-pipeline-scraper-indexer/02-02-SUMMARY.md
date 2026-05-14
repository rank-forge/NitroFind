---
phase: 02-data-pipeline-scraper-indexer
plan: "02"
subsystem: scraper-core
tags: [scraper, text-cleaner, sqlite-state, bulk-indexer, tdd, wave-1]
dependency_graph:
  requires: [02-01]
  provides: [scraper-cleaner, scraper-state, scraper-indexer]
  affects: [02-03, 02-04, 02-05]
tech_stack:
  added: []
  patterns:
    - tdd-red-green per task (test commit then impl commit)
    - rsplit-word-boundary-excerpt (L-06, Pitfall 7)
    - sqlite3-in-memory-tests
    - monkeypatch-chdir for path guard testing
    - streaming_bulk with raise_on_error=False
    - caplog-fixture for warning assertion
key_files:
  created:
    - nitrofind/scraper/__init__.py
    - nitrofind/scraper/cleaner.py
    - nitrofind/scraper/state.py
    - nitrofind/scraper/indexer.py
    - tests/test_scraper/test_cleaner.py (replaced Wave 0 stubs)
    - tests/test_scraper/test_state.py (replaced Wave 0 stubs)
    - tests/test_scraper/test_indexer.py (replaced Wave 0 stubs)
  modified: []
decisions:
  - "test_visited_persists_across_close_reopen uses monkeypatch.chdir(tmp_path) so the T-02-05 path guard accepts the temp file path (pytest tmp_path resolves to /tmp/... which is outside project cwd)"
  - "path traversal guard uses str(resolved).startswith(str(cwd_resolved) + os.sep) with explicit os.sep suffix to prevent siblings of the project dir from being accepted (e.g. /project-sibling would not pass)"
  - "size guard warning uses literal substrings 'Halting scraper' and 'SCRP-04' in one log.warning call so caplog assertion finds both in a single message"
metrics:
  duration: "8m 12s"
  completed: "2026-05-14T13:58:29Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 0
---

# Phase 02 Plan 02: Scraper Core Modules Summary

**One-liner:** Wave 1 scraper core — pure text cleaner (make_excerpt/compute_era_bucket/parse_year), SQLiteStateManager with T-02-05 path traversal guard and parameterized SQL, BulkIndexer with 1.8 GB size guard logging 'Halting scraper'+'SCRP-04'; 22 unit tests green via TDD RED/GREEN cycle per task.

## Tasks Completed

| Task | Name | Commit (RED) | Commit (GREEN) | Files |
|------|------|------|------|-------|
| 1 | Implement nitrofind/scraper/cleaner.py | 41ec142 | 15ddbbf | scraper/__init__.py, cleaner.py, test_cleaner.py |
| 2 | Implement nitrofind/scraper/state.py | ec8a2dc | 4d0a6fa | state.py, test_state.py |
| 3 | Implement nitrofind/scraper/indexer.py | 684ad9d | fca8894 | indexer.py, test_indexer.py |

## New Module File Paths and Line Counts

| File | Lines | Purpose |
|------|-------|---------|
| `nitrofind/scraper/__init__.py` | 1 | Package marker |
| `nitrofind/scraper/cleaner.py` | 68 | make_excerpt, compute_era_bucket, parse_year |
| `nitrofind/scraper/state.py` | 109 | SQLiteStateManager class |
| `nitrofind/scraper/indexer.py` | 161 | BulkIndexer class, build_action, SIZE_HALT_BYTES |

## Exported Symbols per Module

| Module | Exported Symbols |
|--------|-----------------|
| `nitrofind.scraper.cleaner` | `make_excerpt`, `compute_era_bucket`, `parse_year` |
| `nitrofind.scraper.state` | `SQLiteStateManager` |
| `nitrofind.scraper.indexer` | `BulkIndexer`, `build_action`, `SIZE_HALT_BYTES`, `CHECK_EVERY_N_DOCS` |

## Test Counts

| Test File | Unit Tests Passed | Notes |
|-----------|------------------|-------|
| `tests/test_scraper/test_cleaner.py` | 10 | All pass; includes empty input + no-space edge cases |
| `tests/test_scraper/test_state.py` | 6 | All pass; context manager, path traversal, persistence |
| `tests/test_scraper/test_indexer.py` | 6 (unit) + 1 collected (integration) | Unit: build_action, constants, primaries, size guard, counts; Integration: @pytest.mark.integration collected, skips without ES_HOME |
| **Total** | **22 unit** | All pass; 1 integration deselected by `-m "not integration"` |

## Overall Verification Results

```
pytest tests/test_scraper/test_cleaner.py tests/test_scraper/test_state.py tests/test_scraper/test_indexer.py -x -m "not integration"
→ 22 passed, 1 deselected

pytest tests/ -x -m "not integration"
→ 37 passed, 6 skipped, 2 deselected  (exit 0)
```

- 37 total unit tests pass (Phase 1 tests unaffected)
- 6 skipped = Wave 0 stubs for test_wikipedia.py and test_blogs.py (Plan 03/04 work)

## Confirmation: No Hardcoded localhost

```
grep -n "http://localhost:9200" nitrofind/scraper/*.py
```

Result: Only appears in a docstring comment in `indexer.py` (Anti-patterns avoided section).
No actual code reference — `ES_URL` is imported from `nitrofind.es_manager` throughout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_visited_persists_across_close_reopen used pytest tmp_path outside cwd**

- **Found during:** Task 2, GREEN phase (test failed after implementing path traversal guard)
- **Issue:** pytest's `tmp_path` fixture resolves to `/tmp/pytest-of-.../...` which is outside the project working directory. The T-02-05 path traversal guard (correctly) rejects it with `ValueError`, causing the persistence test to fail.
- **Fix:** Added `monkeypatch` fixture alongside `tmp_path` and called `monkeypatch.chdir(tmp_path)` to set cwd to the temp directory before constructing the `SQLiteStateManager`. The guard then accepts the path since it resolves within the (now-set) cwd. This mirrors real usage where `db_path` is always inside the project directory.
- **Files modified:** `tests/test_scraper/test_state.py`
- **Commit:** 4d0a6fa (included in GREEN commit)

## Known Stubs

None. All three modules are fully implemented with no placeholders, hardcoded empty collections, or "TODO" markers.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced beyond those already in the plan's threat model:

| Threat ID | Component | Disposition | Applied |
|-----------|-----------|-------------|---------|
| T-02-05 | `SQLiteStateManager.__init__(db_path)` | mitigate | Path traversal guard: `Path(db_path).resolve()` starts-with check + `:memory:` exception |
| T-02-06 | SQLiteStateManager queries | mitigate | All SQL uses `?` parameterized placeholders; no f-string SQL (grep confirmed) |
| T-02-07 | `BulkIndexer.index_all` | mitigate | `SIZE_HALT_BYTES = 1_800_000_000` halt at 1.8 GB; warning logs 'SCRP-04' tag |
| T-02-08 | `build_action` -> ES | accept | `dynamic: "false"` on index mapping drops extra fields (Phase 1) |

## Self-Check: PASSED

- [x] `nitrofind/scraper/__init__.py` exists (1 line: `# NitroFind scraper package`)
- [x] `nitrofind/scraper/cleaner.py` exports make_excerpt, compute_era_bucket, parse_year
- [x] `nitrofind/scraper/state.py` exports SQLiteStateManager with all required methods
- [x] `nitrofind/scraper/indexer.py` exports BulkIndexer, build_action, SIZE_HALT_BYTES, CHECK_EVERY_N_DOCS
- [x] `cleaner.py` docstring contains `Exports:`, `Requirement coverage:`, `L-06`, `L-07`
- [x] `state.py` docstring contains `Exports:`, `Requirement coverage:`, `D-06`
- [x] `indexer.py` imports `from nitrofind.es_manager import ES_URL`
- [x] `indexer.py` contains no `"http://localhost:9200"` in executable code
- [x] `indexer.py` uses `["primaries"]["store"]["size_in_bytes"]` (not `["total"]`)
- [x] `state.py` has zero f-string SQL (grep confirms)
- [x] `pytest tests/test_scraper/test_cleaner.py tests/test_scraper/test_state.py tests/test_scraper/test_indexer.py -x -m "not integration"` exits 0 with 22 PASSED
- [x] `pytest tests/ -x -m "not integration"` exits 0 with 37 PASSED
- [x] Commits 41ec142 (test RED cleaner), 15ddbbf (feat GREEN cleaner), ec8a2dc (test RED state), 4d0a6fa (feat GREEN state), 684ad9d (test RED indexer), fca8894 (feat GREEN indexer) all exist in git log
- [x] Integration test `test_deduplication_no_duplicate_docs` collected by pytest with `@pytest.mark.integration`
