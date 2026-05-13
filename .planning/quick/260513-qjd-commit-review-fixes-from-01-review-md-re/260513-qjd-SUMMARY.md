---
phase: quick-260513-qjd
plan: 01
type: quick
subsystem: infrastructure
tags: [bugfix, review-remediation, es-manager, ui, tests]
key-files:
  modified:
    - main.py
    - nitrofind/es_manager.py
    - nitrofind/ui/loading_window.py
    - nitrofind/ui/spinner.py
    - scripts/setup_es.py
    - tests/test_es_manager.py
    - tests/test_loading_window.py
    - tests/test_lockfile.py
decisions:
  - "ES_URL constant centralises localhost:9200 — single change point if port changes"
  - "shell=True on Windows only for .bat execution — acceptable security trade-off, required by OS"
  - "_stop_requested flag preferred over QThread.requestInterruption() for clarity"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-13"
  tasks: 1
  commits: 1
---

# Quick Task 260513-qjd: Commit Review Fixes from 01-REVIEW.md Summary

**One-liner:** All 12 Phase 1 code review findings (CR-01..04, WR-01..05, IN-01..03) remediated and committed as a single atomic fix.

## What Was Done

Applied all 8 file edits to resolve the findings from `.planning/phases/01-infrastructure-schema-foundation/01-REVIEW.md` and committed them as one atomic commit (`a5f8dce`).

### Commit

`a5f8dce` — `fix(01): resolve all 12 findings from Phase 1 code review (01-REVIEW.md)`

8 files changed, 108 insertions(+), 23 deletions(-)

## Findings Addressed

| ID | File | Fix |
|----|------|-----|
| CR-01 | `nitrofind/es_manager.py`, `scripts/setup_es.py` | `_es_binary_path()` helper — `elasticsearch.bat` on Windows, `shell=True` for `.bat` |
| CR-02 | `main.py` | `ensure_index()` wrapped in `try/except`; `show_error()` on failure |
| CR-03 | `nitrofind/es_manager.py` | `last_exc` tracked in health-poll loop; surfaced in `es_failed` message |
| CR-04 | `tests/test_lockfile.py` | `pytest.fail()` guard in `_read_requirements()` when file absent |
| WR-01 | `nitrofind/es_manager.py`, `main.py` | `ES_URL = "http://localhost:9200"` constant; imported in `main.py` |
| WR-02 | `nitrofind/ui/spinner.py` | `hideEvent`/`showEvent` stop/start timer to prevent idle 10 Hz wakeups |
| WR-03 | `nitrofind/es_manager.py` | `_stop_requested` flag; set by `shutdown_es()`; checked in polling loop |
| WR-04 | `scripts/setup_es.py` | Back up existing `elasticsearch.yml` to `.bak` before overwriting |
| WR-05 | `tests/test_es_manager.py` | Removed dead `monkeypatch.delenv` from `test_missing_es_home` |
| IN-01 | (comment only) | Intentional major-pin strategy documented inline in `requirements.in` |
| IN-02 | `nitrofind/ui/loading_window.py` | `primaryScreen()` null-checked before `.geometry()` call |
| IN-03 | `tests/test_loading_window.py` | Removed 4 redundant per-function `@pytest.mark.skipif` decorators |

## Verification

```
15 passed, 1 skipped in 1.31s
```

All 15 tests pass. 1 skipped = integration test requiring live Elasticsearch (expected).

## Deviations from Plan

None. Plan executed exactly as written.

## Self-Check: PASSED

- Commit `a5f8dce` exists: confirmed
- 8 files in commit: confirmed (`git show --stat HEAD`)
- 15 tests pass: confirmed
- No unintended deletions: confirmed
