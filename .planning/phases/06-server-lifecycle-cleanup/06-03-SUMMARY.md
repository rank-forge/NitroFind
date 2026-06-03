---
phase: 06-server-lifecycle-cleanup
plan: "03"
subsystem: infra
tags: [flask, python, main, lifecycle, cleanup, clen-01, srvr-01, srvr-02, srvr-04]
status: complete

# Dependency graph
requires:
  - phase: 06-server-lifecycle-cleanup/06-01
    provides: es_manager.py Qt-free, Flask in requirements
  - phase: 06-server-lifecycle-cleanup/06-02
    provides: nitrofind/server.py with Flask app, state, start_es_background
provides:
  - main.py rewritten as Flask lifecycle entry point — no PyQt6
  - nitrofind/ui/ deleted (5 files) — CLEN-01 for Phase 6 code paths
  - PyQt6 UI test files deleted (4 tests/test_ui/ + test_loading_window.py)
  - tests/test_search/test_engine.py guarded with PYQT6_AVAILABLE skip guard
  - Manual smoke test checkpoint: user-approved (503→200 transition, placeholder page, clean Ctrl+C shutdown)
affects: [07-search-api, 08-web-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "main.py Flask lifecycle: validate_es_home → inject_es_config → start_es_background → app.run try/finally"
    - "PORT env var: int(os.environ.get('PORT', 5000)) with ValueError → sys.exit(1)"
    - "None-guarded shutdown_es: if state['process'] is not None: shutdown_es(state['process'])"

key-files:
  created: []
  modified:
    - main.py
    - tests/test_search/test_engine.py
  deleted:
    - nitrofind/ui/__init__.py
    - nitrofind/ui/filter_sidebar.py
    - nitrofind/ui/loading_window.py
    - nitrofind/ui/main_window.py
    - nitrofind/ui/result_delegate.py
    - nitrofind/ui/spinner.py
    - tests/test_loading_window.py
    - tests/test_ui/__init__.py
    - tests/test_ui/test_filter_sidebar.py
    - tests/test_ui/test_main_window.py
    - tests/test_ui/test_result_delegate.py
    - tests/integration/test_es_startup.py
    - tests/test_packaging/test_subprocess_handles.py

key-decisions:
  - "main.py now imports app, start_es_background, state from nitrofind.server — no Qt, no PyInstaller frozen-mode branch"
  - "PORT parsing uses try/except ValueError with sys.exit(1) — T-06-03 mitigation"
  - "CLEN-01 scoped to Phase 6 code paths (main.py, server.py, es_manager.py) — engine.py deferred to Phase 7"
  - "PyQt6 skip guard added to test_engine.py so non-integration suite collects when Qt absent"
  - "[Rule 1] Deleted test_es_startup.py and test_subprocess_handles.py — both imported removed ESHealthWorker, blocking collection"

patterns-established:
  - "Flask lifecycle: start_es_background before app.run, finally-block shutdown_es for clean Ctrl+C"

requirements-completed: [SRVR-01, SRVR-02, SRVR-04, CLEN-01]

# Metrics
duration: 10min
completed: 2026-06-03
---

# Phase 06 Plan 03: Flask Lifecycle Entry Point & UI Layer Deletion Summary

**main.py rewritten as Flask lifecycle entry point — PyQt6 UI layer deleted, engine test skip-guarded, CLEN-01 clean for Phase 6 code paths — awaiting manual smoke test checkpoint**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-03T15:00:00Z
- **Completed:** Task 1 complete; Task 2 (manual checkpoint) pending
- **Tasks:** 2/2 complete
- **Files modified/deleted:** 15

## Accomplishments

- Rewrote main.py from 259-line PyQt6 entry point to 70-line Flask lifecycle: ES_HOME validate, inject_es_config, start_es_background, app.run try/finally
- Applied all T-06-01/02/03/08 security mitigations: 127.0.0.1 bind, debug=False + use_reloader=False, PORT ValueError guard, None-guarded shutdown_es in finally
- Deleted nitrofind/ui/ (6 files) and all PyQt6 UI test files (5 files) — CLEN-01 Phase 6 code paths verified clean (0 grep matches)
- Added PYQT6_AVAILABLE skip guard to tests/test_search/test_engine.py — non-integration suite collects with Qt absent (engine.py deferral to Phase 7 preserved)

## Task Commits

1. **Task 1: Rewrite main.py as Flask lifecycle entry point and delete UI layer** - `ba0aebc` (feat)

2. **Task 2: Manual smoke test checkpoint** — approved by user: 503→200 status transition confirmed, placeholder page renders, clean Ctrl+C with no orphaned JVM (SRVR-01, SRVR-02, SRVR-04 verified).

## Files Created/Modified

- `main.py` — Rewritten: Flask lifecycle entry, no Qt, T-06-01/02/03/08 mitigations
- `tests/test_search/test_engine.py` — Added PYQT6_AVAILABLE skip guard (lines 20-34)
- `nitrofind/ui/` (6 files deleted) — CLEN-01
- `tests/test_loading_window.py` (deleted) — PyQt6 UI test
- `tests/test_ui/` (4 files deleted) — PyQt6 UI tests
- `tests/integration/test_es_startup.py` (deleted) — Rule 1 fix: imported removed ESHealthWorker
- `tests/test_packaging/test_subprocess_handles.py` (deleted) — Rule 1 fix: imported removed ESHealthWorker

## Decisions Made

- main.py drops the `if getattr(sys, "frozen", False)` config_src branch — PyInstaller removed in v1.1 per D-08
- `app.run` uses `host="127.0.0.1"` not `"0.0.0.0"` — WSL-only, T-06-01
- `debug=False, use_reloader=False` prevents Flask's reloader from forking a duplicate ES JVM (Pitfall 1, T-06-02)
- CLEN-01 scoped to Phase 6 code paths only: engine.py retains PyQt6 import, deferred to Phase 7 rewrite

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Merged main branch before task execution**
- **Found during:** Pre-execution setup
- **Issue:** Worktree was at commit f33993e (pre-Phase-06 plans), missing es_manager.py/server.py changes from plans 06-01 and 06-02 that are prerequisites for this plan
- **Fix:** `git merge main --no-edit` (fast-forward) to bring in 06-01 and 06-02 changes
- **Files modified:** es_manager.py, server.py, requirements.txt, tests/test_es_manager.py, tests/test_server.py, and .planning/ files
- **Verification:** CLEN-01 grep returns 0 matches after merge
- **Committed in:** Fast-forward merge — no separate merge commit

**2. [Rule 1 - Bug] Deleted tests/integration/test_es_startup.py and tests/test_packaging/test_subprocess_handles.py**
- **Found during:** Task 1 verification (`pytest tests/ -m "not integration" -q`)
- **Issue:** Both files imported `ESHealthWorker` from `nitrofind.es_manager` at module level. ESHealthWorker was removed in Plan 06-01. The import fails at collection time, causing `pytest -m "not integration"` to abort with `Interrupted: 2 errors during collection` — blocking the Task 1 acceptance criterion
- **Fix:** `git rm` both files; they test functionality that no longer exists (ESHealthWorker._start_process, ESHealthWorker.run via QThread)
- **Files modified:** tests/integration/test_es_startup.py (deleted), tests/test_packaging/test_subprocess_handles.py (deleted)
- **Verification:** pytest -m "not integration" now collects and runs 135 tests, 5 skipped (engine tests skip without PyQt6)
- **Committed in:** ba0aebc (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking setup issue, 1 pre-existing bug from Plan 06-01)
**Impact on plan:** Both fixes necessary for correct execution. No scope creep.

## Known Stubs

None — main.py is a complete Flask lifecycle entry point, not a stub.

## Deferred Items

The following pre-existing test failures from Plan 06-01 are out of scope for Plan 06-03:
- `tests/test_lockfile.py::test_required_top_level_packages` — asserts PyQt6 and qt-material are in requirements.txt; both removed in Plan 06-01 but test not updated
- `tests/test_packaging/test_path_resolution.py::test_frozen_mode_finds_sibling_es_dir` — tests frozen-mode resolve_es_home branch removed in Plan 06-01

These were logged to confirm they predate Plan 06-03 changes (verified via `git stash` check). Should be cleaned up in a follow-up quick task or Phase 7.

## Issues Encountered

Worktree was spawned from a commit predating Phase 06 plan 01 and 02 merges — required fast-forward merge from main before task could execute. Standard worktree lifecycle issue when a new agent is spawned from an older base commit.

## User Setup Required

Task 2 (manual smoke test) requires:
1. ES_HOME set to Elasticsearch 8.18 directory
2. `pip install -r requirements.txt` (verify no Qt packages downloaded)
3. `python main.py` in WSL terminal — see checkpoint details below

## Next Phase Readiness

Awaiting Task 2 human verification (manual smoke test). Upon approval:
- `python main.py` is the v1.1 single-command startup
- Phase 7 (search API) can build `/api/search` route on top of the Flask app in server.py
- engine.py PyQt6 import is deferred to Phase 7 which rewrites it for the REST API

---
*Phase: 06-server-lifecycle-cleanup*
*Completed: 2026-06-03 — Task 2 checkpoint approved by user*

## Self-Check: PASSED

- `main.py` exists at `/mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind/.claude/worktrees/agent-a657b3bd2938682c1/main.py` and AST-parses cleanly
- Commit `ba0aebc` exists in git log
- CLEN-01 grep returns 0 matches for nitrofind/server.py, nitrofind/es_manager.py, main.py
- `nitrofind/ui/` directory does not exist
- `tests/test_search/test_engine.py` contains PYQT6_AVAILABLE and pytest.mark.skipif
- 135 tests pass, 5 deselected (engine skip without PyQt6), 2 pre-existing failures out of scope
