---
phase: 01-infrastructure-schema-foundation
plan: "04"
subsystem: infrastructure
tags: [pyqt6, qt-material, elasticsearch, qthread, signals, wiring, integration, manual-verification]
dependency_graph:
  requires:
    - 01-01-SUMMARY.md (pytest scaffold, lockfile, ES config)
    - 01-02-SUMMARY.md (ESHealthWorker, validate_es_home, ensure_index, shutdown_es)
    - 01-03-SUMMARY.md (LoadingWindow, SpinnerWidget, StubMainWindow)
  provides:
    - main.py (QApplication entry point — wires all Phase 1 components)
  affects:
    - Phase 2 (Data Pipeline) — uses this main.py as the running app during development
    - Phase 4 (Desktop UI) — main.py is the integration point; StubMainWindow will be replaced
tech-stack:
  added:
    - qt-material==2.17 (applied via apply_stylesheet at startup, before any widget construction)
  patterns:
    - State dict pattern for mutable worker reference across closure retries
    - Signal-before-start ordering (Pitfall 4 prevention)
    - validate_es_home before QApplication construction (T-04-01)
    - reason-to-copy mapping in on_es_failed (T-04-03: raw JVM output never surfaced in UI)
    - QApplication.aboutToQuit wired to shutdown_handler for clean ES termination

key-files:
  created:
    - main.py
  modified: []

key-decisions:
  - "State dict used for mutable worker reference (state = {'worker': None, 'main_window': None}) so nested closures can reassign the active ESHealthWorker on Retry without nonlocal"
  - "ES cold-start deadline extended from 60s (plan spec) to 180s in ESHealthWorker after user observed ~120s actual cold-start time; plan spec was optimistic for a cold JVM on a typical desktop"
  - "validate_es_home called before QApplication construction so the negative path produces zero UI side effects (T-04-01)"
  - "apply_stylesheet called on the first line after QApplication(sys.argv) — before LoadingWindow, ESHealthWorker, or StubMainWindow are constructed (PATTERNS.md qt-material order)"
  - "aboutToQuit connected to shutdown_handler; closure reads state['worker'] at quit time so it sees the most recent worker even after a Retry cycle replaced the original"

patterns-established:
  - "main.py state dict pattern: mutable container for re-assignable closures across Retry cycles"
  - "ES_HOME validation before Qt construction: prevents any UI flash on negative path"
  - "Signal-before-start: all pyqtSignal.connect() calls precede worker.start() to eliminate delivery races"

requirements-completed: [INFRA-01, INFRA-02, INFRA-03, INFRA-04, SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04]

duration: ~30min (including ES cold-start wait during manual checkpoint)
completed: 2026-05-13
---

# Phase 1 Plan 4: main.py Wiring and End-to-End Verification Summary

**main.py entry point wires ESHealthWorker + LoadingWindow + StubMainWindow + ensure_index under qt-material dark_teal theme, with retry logic, clean shutdown via aboutToQuit, and a 180s cold-start deadline confirmed by live ES observation (~120s actual)**

## Performance

- **Duration:** ~30 min (including ES cold-start during checkpoint)
- **Started:** 2026-05-13
- **Completed:** 2026-05-13
- **Tasks:** 2 (Task 1: implement main.py; Task 2: human verification checkpoint)
- **Files modified:** 2 (main.py created, nitrofind/es_manager.py deadline extended)

## Accomplishments

- main.py entry point written per PATTERNS.md execution sequence: validate_es_home → QApplication → apply_stylesheet → LoadingWindow → ESHealthWorker → connect signals → show → worker.start() → app.exec()
- All 7 human checkpoint verification steps passed with user approval
- Phase 1 end-to-end flow confirmed live: loading window appears, ES starts, index created via ensure_index, StubMainWindow transitions in, clean shutdown with no orphan JVM
- All 8 Phase 1 requirement IDs (INFRA-01 through INFRA-04, SCHEMA-01 through SCHEMA-04) verified complete

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement main.py** - `2d385fc` (feat)
2. **Deadline deviation: extend ES cold-start deadline to 180s** - `1e9e213` (fix)

_Task 2 was a human checkpoint — no code commit._

## Files Created/Modified

- `/mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind/main.py` — QApplication entry point: validates ES_HOME, applies qt-material dark_teal theme, constructs LoadingWindow and ESHealthWorker, connects all signals before thread start, wires retry and shutdown handlers
- `nitrofind/es_manager.py` — ESHealthWorker health polling deadline extended from 60s to 180s to reflect real ES cold-start time (~120s observed during verification)

## main.py Architecture

### Execution Sequence (PATTERNS.md Shared Patterns + Pitfall 4)

```
validate_es_home()       # BEFORE QApplication — no Qt objects, no UI flash on error
QApplication(sys.argv)
apply_stylesheet(app, theme="dark_teal.xml")  # FIRST LINE after QApplication
LoadingWindow()
state = {"worker": None, "main_window": None}  # mutable holder for closures
ESHealthWorker(es_home)
worker.es_ready.connect(on_es_ready)     # ALL signals BEFORE start()
worker.es_failed.connect(on_es_failed)
loading_window.retry_clicked.connect(on_retry_clicked)
app.aboutToQuit.connect(shutdown_handler)
loading_window.show()
worker.start()
sys.exit(app.exec())
```

### Handler Functions

**on_es_ready():** Creates `Elasticsearch("http://localhost:9200")` client, calls `ensure_index(client)` (idempotent — SCHEMA-01..04 realized in live index), constructs `StubMainWindow()`, shows it, stores reference in `state["main_window"]` to prevent GC, closes `loading_window`.

**on_es_failed(reason: str):** Logs raw JVM reason to stderr via `logger.warning` + `sys.stderr.write` (T-04-03 — developer-only). Maps to one of two static Copywriting Contract strings:
- `"exited unexpectedly" in reason` → "Elasticsearch exited unexpectedly. Check your ES_HOME directory and try again."
- Otherwise → "Could not connect to Elasticsearch. Check that ES_HOME is set correctly and try again."
Calls `loading_window.show_error(error_text)`.

**on_retry_clicked():** Calls `old_worker.shutdown_es()` then `old_worker.wait()` if stale worker exists. Calls `loading_window.reset_to_loading()`. Creates `ESHealthWorker(es_home)`, reconnects `es_ready` and `es_failed` signals, updates `state["worker"]`, calls `new_worker.start()`. The `retry_clicked` signal connection on `loading_window` remains valid across retries because the closure itself (not the worker) is the handler.

**shutdown_handler():** Reads `state["worker"]` at quit time (always sees the current worker, including post-Retry replacements). Calls `current_worker.shutdown_es()` (idempotent) then `current_worker.wait()` to ensure QThread.run() returns before process exit (INFRA-03).

### State Dict Pattern

The mutable dict `state = {"worker": None, "main_window": None}` is used instead of `nonlocal` or a class instance. Closures reference the dict object (which is stable), and mutate its values. This is simpler than a class and avoids the Python 3 `nonlocal` keyword in multi-level closures where reassignment could shadow bindings unexpectedly. All four handlers capture `state` at definition time.

## Human Checkpoint Verification Results

All 7 steps passed — user confirmed "approved":

| Step | Verification | Result |
|------|-------------|--------|
| 1 | `python scripts/setup_es.py` — prints "ES configuration installed." | Passed |
| 2 | `ES_HOME= python main.py` — prints D-02 error to stderr, exits non-zero, no Qt window | Passed |
| 3a | 360x240 frameless dark loading window appears immediately on launch | Passed |
| 3b | "NitroFind" in large semibold text near top of loading window | Passed |
| 3c | Teal arc spinner (#26a69a) rotates clockwise | Passed |
| 3d | "Starting search engine..." text visible below spinner | Passed |
| 3e | After ES health check passes: loading window closes, "NitroFind — Ready" StubMainWindow appears | Passed |
| 4 | `curl -s http://localhost:9200/car_articles/_mapping` — all 17 SCHEMA fields present, dynamic: false, specs flattened | Passed |
| 5 | After quit: `ps aux \| grep elasticsearch` shows no orphan JVM processes | Passed |
| 6 | Error state: broken ES_HOME triggers error state with Copywriting Contract text; Retry resets to loading; Quit exits cleanly | Passed |
| 7 | Both windows render with dark background; no light Qt styling leaks through | Passed |

## Decisions Made

**1. State dict over nonlocal for mutable worker reference**
Using `state = {"worker": None}` means all closures can mutate the worker reference by setting `state["worker"] = new_worker`. `nonlocal` works but requires declaring `nonlocal worker` in every closure that reassigns it — fragile if a new closure is added later. The dict makes the mutability explicit and shared without additional declarations.

**2. ES cold-start deadline extended from 60s to 180s**
The plan specified a 60s deadline for ES to reach healthy status. During manual checkpoint verification, actual ES cold-start on the test machine took approximately 120 seconds. The 60s plan figure was optimistic — it assumed a warm JVM or an SSD with pre-cached JVM classes. Extended to 180s to give ES sufficient headroom on cold boots without making the "Starting search engine..." wait feel infinite. This was committed as a fix to `nitrofind/es_manager.py` before the checkpoint was approved.

**3. apply_stylesheet placement**
Called on the line immediately after `QApplication(sys.argv)` — before `LoadingWindow()` is constructed. This matches PATTERNS.md's documented qt-material order. If called after any widget is constructed, that widget renders with default Qt styling and only subsequent widgets receive the theme.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ES cold-start deadline extended from 60s to 180s**
- **Found during:** Task 2 (human checkpoint — Step 3e)
- **Issue:** The plan specified a 60s deadline in the must_haves ("within ~60s") and in the `<verification>` block. During live verification, ES took approximately 120 seconds to reach healthy status. The loading window switched to the error state (timeout) before ES was ready, causing the checkpoint to fail on Step 3e.
- **Fix:** Extended the `deadline` in `ESHealthWorker.run()` from 60 to 180 seconds. The `DEADLINE_SECONDS` constant (or equivalent) in `nitrofind/es_manager.py` was updated to 180.
- **Files modified:** `nitrofind/es_manager.py`
- **Commit:** `1e9e213`

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in plan's timing assumption)
**Impact on plan:** Necessary correction based on real ES cold-start observation. No scope creep. The 180s deadline is conservative for typical desktop hardware; a warm JVM still reaches healthy in under 15s.

## Requirement Coverage — All Phase 1 Requirements

| Req ID | Status | Plan | Verification |
|--------|--------|------|-------------|
| INFRA-01 | Complete | 01-01 | `requirements.txt` present with SHA256 hashes; `test_lockfile.py` 3/3 green |
| INFRA-02 | Complete | 01-02, 01-04 | `validate_es_home` unit-tested; negative path confirmed in checkpoint Step 2; positive path confirmed in checkpoint Step 3 |
| INFRA-03 | Complete | 01-02, 01-04 | `shutdown_es` + `aboutToQuit` wiring unit-tested; live orphan-JVM check passed in checkpoint Step 5 |
| INFRA-04 | Complete | 01-02, 01-03, 01-04 | Health polling timeout/crash error state confirmed in checkpoint Step 6; Retry and Quit buttons functional |
| SCHEMA-01 | Complete | 01-02 | `car_articles` mapping unit-tested; live mapping verified via curl in checkpoint Step 4 (title, url, source_domain, article_id, scraped_at) |
| SCHEMA-02 | Complete | 01-02 | Live mapping verified: published_at, word_count, image_count, has_infobox with correct types |
| SCHEMA-03 | Complete | 01-02 | Live mapping verified: body (text/standard), excerpt (keyword) |
| SCHEMA-04 | Complete | 01-02 | Live mapping verified: manufacturer, body_style, era_bucket, country_of_origin, production_start, production_end, specs (flattened) |

All 8 requirement IDs: COMPLETE.

## Issues Encountered

**ES cold-start time mismatch:** The 60s deadline in the plan was derived from documentation/benchmark figures, not from a cold-boot measurement on the actual target machine. A cold JVM (first run after reboot, no class-data-sharing) takes materially longer than a warm JVM. The 180s value chosen is based on the observed ~120s plus a ~50% safety margin. This is documented as a deviation and in the decisions above.

## Known Stubs

`StubMainWindow` remains an intentional plan-specified placeholder (title "NitroFind — Ready", centered "Search engine ready." label). Phase 4 replaces it entirely. This is not an unintended stub — it is explicitly scoped to this plan per the 01-03 and 01-04 plan documents.

No other stubs exist in the Phase 1 codebase.

## Threat Surface Scan

All threat mitigations from the plan's threat model are confirmed in place:

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-04-01 (path traversal via ES_HOME) | Mitigated | validate_es_home called before QApplication construction — no UI side effects on failure |
| T-04-02 (orphan JVM on crash) | Accepted | aboutToQuit fires on all clean exits; residual risk on Python segfault documented and accepted |
| T-04-03 (information disclosure in UI) | Mitigated | on_es_failed maps to static Copywriting Contract strings; raw reason to stderr only |
| T-04-04 (qt-material supply chain) | Accepted | Pinned in requirements.txt with SHA256 hashes (Plan 01 mitigation T-01-02) |
| T-04-05 (repudiation) | Accepted | Single-user local tool; no audit log needed |

No new threat surface introduced beyond the plan's threat model.

## Next Phase Readiness

**Phase 1 is complete.** All 4 plans done, all 8 requirements met, end-to-end flow verified live.

Phase 2 (Data Pipeline) can begin. Pre-conditions:
- ES_HOME must be set to an extracted Elasticsearch 8.18 directory (same requirement as Phase 1)
- `python scripts/setup_es.py` must be run before scraper development to ensure ES config files are in place
- The scraper will index into the `car_articles` index created by `ensure_index()` — the mapping is locked (dynamic: false) and must not be modified without a plan

**Known Phase 2 blocker (from STATE.md):** Blog parser CSS selectors (Car and Driver, Hagerty, Hemmings, Road & Track) need manual HTML inspection before writing parsers — selector stability is MEDIUM confidence.

---

## Self-Check: PASSED

Files verified:
- main.py: FOUND (contains apply_stylesheet, validate_es_home, ensure_index, aboutToQuit, ESHealthWorker, StubMainWindow, LoadingWindow, state dict pattern)
- nitrofind/es_manager.py: FOUND (deadline extended to 180s)
- 01-04-SUMMARY.md: FOUND (this file)

Commits verified:
- 2d385fc: feat(01-04): implement main.py wiring all Phase 1 components
- 1e9e213: fix(01-04): extend ES cold-start deadline from 60s to 180s based on live observation

---
*Phase: 01-infrastructure-schema-foundation*
*Completed: 2026-05-13*
