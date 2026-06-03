---
phase: 06-server-lifecycle-cleanup
plan: "01"
subsystem: infra
tags: [flask, elasticsearch, requirements, pip-compile, es_manager, linux]

# Dependency graph
requires:
  - phase: 05-packaging
    provides: requirements.in, requirements.txt, nitrofind/es_manager.py with ESHealthWorker
provides:
  - Flask added to requirements.in and requirements.txt (locked with hashes)
  - PyQt6 and qt-material removed from requirements.in and requirements.txt
  - es_manager.py simplified to Qt-free Linux-only subprocess/path utilities
  - ESHealthWorker class removed from es_manager.py
  - tests/test_es_manager.py updated: worker tests removed, graceful shutdown test simplified
affects: [06-02, 06-03, 07-search-api]

# Tech tracking
tech-stack:
  added: [flask>=3.1]
  patterns:
    - shutdown_es: POSIX SIGTERM then kill fallback (Linux-only, no win32 branches)
    - resolve_es_home: reads only from ES_HOME env var (no PyInstaller frozen-mode branch)

key-files:
  created: []
  modified:
    - requirements.in
    - requirements.txt
    - nitrofind/es_manager.py
    - tests/test_es_manager.py

key-decisions:
  - "PyQt6 and qt-material removed from requirements.in; flask>=3.1 added as the only new dependency"
  - "es_manager.py is now Linux/WSL only — all sys.platform win32 branches removed per D-01"
  - "ESHealthWorker QThread class removed; health polling moved to server.py threading.Thread in Plan 02"
  - "resolve_es_home simplified to os.environ.get('ES_HOME') only — no frozen/PyInstaller branch (v1.1 removes PyInstaller)"

patterns-established:
  - "shutdown_es (Linux-only): terminate() + wait(timeout=10) + kill fallback — no signal import needed"
  - "resolve_es_home: single-line env var read (no frozen-mode complexity)"

requirements-completed: [CLEN-01, SRVR-04]

# Metrics
duration: 5min
completed: 2026-06-03
---

# Phase 06 Plan 01: Dependencies & ES Manager Cleanup Summary

**Flask added and PyQt6 removed from lockfile; es_manager.py stripped to Linux-only subprocess utilities with ESHealthWorker deleted**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-03T14:32:31Z
- **Completed:** 2026-06-03T14:37:00Z
- **Tasks:** 2 (Task 1 + TDD Task 2)
- **Files modified:** 4

## Accomplishments

- Removed PyQt6==6.11.0 and qt-material==2.17 from requirements.in; added flask>=3.1; regenerated requirements.txt with pip-compile --generate-hashes
- Deleted ESHealthWorker QThread class and all PyQt6 imports from es_manager.py (179 lines removed, 20 added)
- Simplified resolve_es_home, _es_binary_path, and shutdown_es to Linux-only single-path implementations
- Updated test_es_manager.py: removed test_worker_emits_ready and test_worker_emits_failed; simplified test_shutdown_graceful to assert terminate() unconditionally (no win32 branch)

## Task Commits

Each task was committed atomically:

1. **Task 1: Swap Qt dependencies for Flask** - `fb4386e` (chore)
2. **Task 2 RED: Update test_es_manager.py (TDD test commit)** - `d6b64d7` (test)
3. **Task 2 GREEN: Strip es_manager.py to Qt-free utilities** - `164cbe9` (feat)

_Task 2 followed TDD RED/GREEN pattern. Tests already passed before implementation (Linux path already correct); GREEN commit removed dead code and dead imports._

## Files Created/Modified

- `requirements.in` - Removed PyQt6==6.11.0 and qt-material==2.17; added flask>=3.1
- `requirements.txt` - Regenerated lockfile: flask pinned with hashes, no Qt packages
- `nitrofind/es_manager.py` - ESHealthWorker removed; Windows branches removed; PyQt6 import removed; dead imports (signal, time, sys, Path) removed
- `tests/test_es_manager.py` - Import simplified to shutdown_es + validate_es_home; ESHealthWorker tests deleted; test_shutdown_graceful simplified to Linux-only assertions

## Decisions Made

- Followed plan exactly: Linux-only simplification per D-01/D-07; no deviations needed
- TDD RED phase: tests passed before implementation because Linux behavior was already correct (else branch); proceeded directly to GREEN to remove dead code

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — pip-compile, imports, and pytest all ran cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (server.py creation) can import ES_URL and shutdown_es from es_manager.py cleanly
- requirements.txt has Flask pinned with hashes — ready for pip install
- ESHealthWorker is gone; health polling logic for Plan 02 threading.Thread approach is unblocked

---
*Phase: 06-server-lifecycle-cleanup*
*Completed: 2026-06-03*
