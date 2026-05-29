---
phase: 05-packaging-distribution
fixed_at: 2026-05-29T21:45:00Z
review_path: .planning/phases/05-packaging-distribution/05-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 05: Code Review Fix Report

**Fixed at:** 2026-05-29T21:45:00Z
**Source review:** .planning/phases/05-packaging-distribution/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, CR-02, WR-01, WR-02)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-02: inject_es_config calls shutil.copy before os.makedirs

**Files modified:** `nitrofind/es_manager.py`
**Commit:** 9509e6c
**Applied fix:** Moved `jvm_dir = os.path.join(es_config, "jvm.options.d")` and `os.makedirs(jvm_dir, exist_ok=True)` to the top of the function body, before either `shutil.copy` call. Since `os.makedirs` creates all missing intermediate directories, this single call now guarantees both `config/` and `jvm.options.d/` exist before any write attempt, fixing the `FileNotFoundError` that occurred when `es_home/config/` did not pre-exist.

### CR-01: ESHealthWorker.run() has no exception handler around _start_process()

**Files modified:** `nitrofind/es_manager.py`
**Commit:** 85b23b1
**Applied fix:** Wrapped `self.process = self._start_process()` in a `try/except OSError as exc` block. On `OSError` (e.g. binary not executable, filesystem error, OS resource exhaustion), the handler calls `self.es_failed.emit(f"Failed to start Elasticsearch: {exc}")` and returns. This restores the INFRA-04 invariant — `run()` now emits exactly one signal per invocation regardless of `Popen` outcome.

### WR-01: build_dist.py does not validate es_src.name — name collision with _internal destroys PyInstaller output

**Files modified:** `scripts/build_dist.py`
**Commit:** d3f3944
**Applied fix:** Added `import re` and a `re.match(r"^elasticsearch-8\.\d+", es_src.name)` guard after `es_src = Path(es_bundle)`. If the name does not match, the script prints an informative error message and calls `sys.exit(1)` before `shutil.rmtree` or `shutil.copytree` are reached. This prevents a misnamed ES_BUNDLE (e.g. one ending in `_internal`) from silently destroying the PyInstaller bundle.

### WR-02: CTRL_BREAK_EVENT targets cmd.exe, not the JVM

**Files modified:** `nitrofind/es_manager.py`
**Commit:** b9c84d7
**Applied fix:** Replaced the misleading "gives ES a chance to flush translog" comment with an accurate explanation of the known limitation: `shell=True` spawns `cmd.exe /c elasticsearch.bat`; `CTRL_BREAK_EVENT` reaches the `cmd.exe` process group but delivery to the Java child is not guaranteed. The comment now explicitly states that `process.kill()` after the 10-second timeout is the actual termination mechanism and defers a proper fix (`shell=False` or `taskkill /F /T`) to a future hardening pass. The signal call itself is retained since it may help on some Windows configurations; the comment corrects the false expectation of reliable graceful shutdown.

---

_Fixed: 2026-05-29T21:45:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
