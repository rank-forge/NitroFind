---
phase: 05-packaging-distribution
plan: "01"
subsystem: packaging
tags:
  - packaging
  - pyinstaller
  - elasticsearch
  - subprocess
  - frozen-mode
dependency_graph:
  requires:
    - 01-infrastructure (ESHealthWorker, validate_es_home — extended in this plan)
  provides:
    - resolve_es_home() — frozen-mode ES path resolver
    - inject_es_config() — idempotent config writer for bundled ES
    - DEVNULL-hardened _start_process() — windowed frozen mode subprocess fix
  affects:
    - main.py (wired with new functions and stdout/stderr guard)
    - tests/test_packaging/ (new test subtree)
tech_stack:
  added:
    - shutil (stdlib, inject_es_config file copies)
    - pathlib.Path (stdlib, resolve_es_home glob)
  patterns:
    - PKG-01: sys.executable parent glob for sibling ES directory detection
    - PKG-01: sys._MEIPASS for config source path in frozen mode
    - subprocess.DEVNULL on all std handles to prevent [WinError 6]
    - close_fds=True to prevent handle lock on binary update
key_files:
  modified:
    - nitrofind/es_manager.py
    - main.py
    - tests/test_packaging/test_subprocess_handles.py
  created:
    - tests/test_packaging/__init__.py
    - tests/test_packaging/test_path_resolution.py
    - tests/test_packaging/test_config_injection.py
    - tests/test_packaging/test_subprocess_handles.py
decisions:
  - resolve_es_home placed in es_manager.py (not main.py) so it is testable as a pure function
  - inject_es_config called before validate_es_home to ensure config is in place before ES starts
  - stdout/stderr None guard placed before logging.basicConfig to prevent crash in windowed frozen mode
  - monkeypatch CREATE_NEW_PROCESS_GROUP sentinel (value=512) in win32 branch test for Linux cross-compatibility
metrics:
  duration: "4 minutes"
  completed: "2026-05-29T13:44:35Z"
  tasks_completed: 3
  files_modified: 2
  files_created: 4
  tests_added: 11
---

# Phase 5 Plan 1: Frozen-Mode Plumbing for PKG-01 Summary

**One-liner:** Frozen-mode runtime side of PKG-01 — resolve_es_home() from sys.executable parent glob, inject_es_config() idempotent config writer, DEVNULL-hardened Popen in _start_process(), and stdout/stderr guard in main().

## What Was Built

Added three new behaviors to `nitrofind/es_manager.py` and two targeted edits to `main.py` to make the application launchable from a PyInstaller bundle on a clean machine with no `ES_HOME` environment variable set.

### New exports in nitrofind/es_manager.py

**`resolve_es_home() -> str | None`**
Pure function. In frozen mode (`getattr(sys, 'frozen', False)` is True) returns the path of the first `elasticsearch-8.*` sibling directory of `sys.executable`. In dev mode returns `os.environ.get('ES_HOME')`. Returns None in both modes if the expected path is absent.

**`inject_es_config(es_home: str, config_src_dir: str) -> None`**
Idempotent. Copies `{config_src_dir}/elasticsearch.yml` to `{es_home}/config/elasticsearch.yml` and `{config_src_dir}/jvm.options` to `{es_home}/config/jvm.options.d/nitrofind.options`, creating `jvm.options.d/` via `os.makedirs(exist_ok=True)` if absent. Called before `validate_es_home()` and before `ESHealthWorker.start()` so ES always sees the NitroFind-controlled config.

**`ESHealthWorker._start_process()` — DEVNULL fix**
All three std handles (`stdin`, `stdout`, `stderr`) now explicitly set to `subprocess.DEVNULL`. `close_fds=True` added. Prevents `[WinError 6] The handle is invalid` in windowed frozen mode (PKG-01 Pitfall 2) and file handle lock on binary update (PKG-01 Pitfall 7).

### main.py changes

1. `sys.stdout/sys.stderr` None guard added before `logging.basicConfig` — PyInstaller `console=False` sets these to None; any logging or `sys.stderr.write` would crash without this guard.
2. `os.environ.get("ES_HOME")` replaced with `resolve_es_home()`.
3. `inject_es_config(es_home_raw, config_src)` inserted between `resolve_es_home()` and `validate_es_home()`, guarded by `if es_home_raw:` and wrapped in `try/except OSError` with `logger.warning`.
4. `resolve_es_home` and `inject_es_config` added to the `from nitrofind.es_manager import ...` line.

### New test files (tests/test_packaging/)

| File | Tests | What They Cover |
|------|-------|-----------------|
| `__init__.py` | — | pytest package marker |
| `test_path_resolution.py` | 4 | resolve_es_home() frozen/dev modes, sibling glob, None return |
| `test_config_injection.py` | 4 | elasticsearch.yml write, jvm.options.d write, dir creation, idempotency |
| `test_subprocess_handles.py` | 3 | DEVNULL kwargs, win32 creationflags+shell, POSIX no-flags |

## Test Results

- `pytest tests/test_packaging/ -x` → **11 passed** (all GREEN)
- `pytest tests/test_es_manager.py -x` → **5 passed** (Phase-1 INFRA-02/03/04 tests unaffected)
- `pytest tests/ -x` → **173 passed, 5 skipped** (full repo suite green)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_start_process_win32_branch cross-platform failure**
- **Found during:** Task 2 verification
- **Issue:** `subprocess.CREATE_NEW_PROCESS_GROUP` does not exist on Linux. The test monkeypatched `sys.platform` to `win32` but didn't provide the constant, causing `AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_PROCESS_GROUP'` when `_start_process()` ran the win32 branch.
- **Fix:** Added `monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", ..., raising=False)` in the test, using `getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 512)` as the sentinel value (512 matches the Windows constant). The test now runs correctly on both Linux and Windows.
- **Files modified:** `tests/test_packaging/test_subprocess_handles.py`
- **Commit:** 80a4090

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The code surface matches the threat model in the plan:

| Mitigation | Status |
|------------|--------|
| T-05-01: DEVNULL + close_fds on Popen | Implemented in _start_process() |
| T-05-02: inject_es_config before validate_es_home | Implemented in main.py (injection precedes validate) |
| T-05-03: sys.executable-relative path resolution | Implemented in resolve_es_home() |
| T-05-04: zip slip (user extraction) | Accepted — no code surface in this plan |

## Known Stubs

None. All functions are fully implemented and tested.

## Self-Check: PASSED

Files exist:
- nitrofind/es_manager.py — contains def resolve_es_home and def inject_es_config
- main.py — contains resolve_es_home(), inject_es_config(), sys.stdout is None guard
- tests/test_packaging/__init__.py
- tests/test_packaging/test_path_resolution.py
- tests/test_packaging/test_config_injection.py
- tests/test_packaging/test_subprocess_handles.py

Commits verified:
- af68508 — test(05-01): add RED-state failing tests for PKG-01 contracts
- 80a4090 — feat(05-01): add resolve_es_home + inject_es_config + DEVNULL Popen kwargs
- b6386e8 — feat(05-01): wire resolve_es_home + inject_es_config into main.py
