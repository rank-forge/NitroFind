---
phase: 03-search-logic-relevance-scoring
plan: 02
subsystem: search
tags: [search, engine, qrunnable, qthreadpool, threading, signals]
dependency_graph:
  requires:
    - nitrofind.search.query_builder.build_search_body (Plan 03-01)
    - nitrofind.search.models.ArticleResult (Plan 03-01)
    - nitrofind.es_manager.ES_URL
  provides:
    - nitrofind.search.engine.SearchEngine
    - nitrofind.search.engine._SearchSignals
    - nitrofind.search.engine._SearchWorker
  affects:
    - nitrofind.search.__init__ (SearchEngine now importable without try/except fallback)
    - tests/test_search/test_engine.py (Plan 03-03 integration tests will extend this)
    - Phase 4 UI (SearchEngine consumer)
tech_stack:
  added: []
  patterns:
    - QObject sidecar (_SearchSignals) for pyqtSignal on QRunnable — signals cannot live on QRunnable directly
    - QThreadPool.globalInstance() for thread reuse — no per-search pool construction
    - Signal connections BEFORE pool.start(worker) — race condition prevention (T-03-06)
    - Flat keyword API for client.search() — no deprecated body= parameter (elasticsearch-py 8.x)
    - Constructor injection of Elasticsearch client — thread-safe sharing across workers
    - TDD: RED (failing tests) then GREEN (implementation) commit pattern
key_files:
  created:
    - nitrofind/search/engine.py
    - tests/test_search/test_engine.py
  modified: []
decisions:
  - "_SearchSignals is a QObject sidecar (not on QRunnable) — pyqtSignal requires QObject ancestry"
  - "QThreadPool.globalInstance() used — single global pool for thread reuse across searches"
  - "ES_URL imported from es_manager — never hard-coded as string in engine.py (WR-01)"
  - "index='car_articles' hard-coded in _SearchWorker.run() — never from user input (T-03-04)"
  - "Signal connections before pool.start(worker) — code structure enforces T-03-06 mitigation"
  - "run() suppresses and emits exceptions via search_failed — never raises to pool (correct QRunnable behavior)"
metrics:
  duration: 3m
  completed: 2026-05-28
  tasks_completed: 1
  files_created: 2
---

# Phase 3 Plan 2: SearchEngine with QRunnable Worker (engine.py) Summary

**One-liner:** SearchEngine wrapping ES function_score queries in a _SearchWorker(QRunnable) with _SearchSignals(QObject) sidecar, delivering ArticleResult lists to callers via Qt signals with all connections established before pool.start() to prevent race conditions.

## What Was Built

Created `nitrofind/search/engine.py` — the thread-safe ES search driver that sits between the query builder (Plan 03-01) and the Phase 4 UI. All ES I/O executes on a background thread via QThreadPool, satisfying Phase 3 success criterion 5 (all ES calls off the main thread).

### `nitrofind/search/engine.py`

Three classes implementing the QRunnable worker pattern:

**`_SearchSignals(QObject)`** — signals sidecar. QRunnable cannot hold `pyqtSignal` attributes because it does not inherit `QObject`. The sidecar pattern keeps signals on a separate `QObject` instance that is passed by reference into the worker at construction time. Two signals: `results_ready = pyqtSignal(list)` and `search_failed = pyqtSignal(str)`.

**`_SearchWorker(QRunnable)`** — one ES search per submission. `run()` calls `self._client.search()` using the flat keyword API (no deprecated `body=` parameter): `index="car_articles"` is hard-coded as a string literal (T-03-04 cross-index prevention); `query=`, `highlight=`, `source=`, `size=`, `from_=` are passed from the pre-built body dict. On success emits `results_ready` with `[ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]`. On exception: logs via `logger.warning("Search failed: %s: %s", ...)` with `%` lazy formatting, then emits `search_failed` — exception is never re-raised so the pool is not contaminated.

**`SearchEngine`** — public API for Phase 4. `__init__` stores the injected client and captures `QThreadPool.globalInstance()` — no per-engine or per-search pool construction. `search()` calls `build_search_body()`, creates a `_SearchSignals` sidecar, connects callback and error_callback BEFORE `pool.start(worker)` (T-03-06 race condition prevention), then submits the worker. Returns `None` immediately.

### `tests/test_search/test_engine.py`

30 unit tests covering:
- `_SearchSignals` structure (QObject, both signals present)
- `_SearchWorker` construction (stores client, body, signals as instance attributes)
- `_SearchWorker.run()` behavior (flat API, no body= kwarg, index hard-coded, results deserialization, empty hits, exception handling, no re-raise)
- `SearchEngine` construction (stores client, uses globalInstance, has search method)
- `SearchEngine.search()` API (returns None, calls build_search_body with correct args, forwards filters, no callback acceptable, pool.start called)
- Module contracts (ES_URL imported, no body= kwarg in source, QThreadPool.globalInstance used, logger % formatting)
- 1 integration test stub (skipped if ES_HOME not set)

## Task Commits

| Task | Phase | Type | Commit | Description |
|------|-------|------|--------|-------------|
| 1 | RED | test | `085d075` | Failing tests for SearchEngine with QRunnable worker |
| 1 | GREEN | feat | `9e54ef9` | SearchEngine with _SearchSignals and _SearchWorker |

## TDD Gate Compliance

- RED gate (test commit): `085d075` — tests fail with `ModuleNotFoundError: No module named 'nitrofind.search.engine'` before implementation
- GREEN gate (feat commit): `9e54ef9` — 30/30 tests passing after implementation
- No REFACTOR phase needed — implementation was clean on first pass

## Deviations from Plan

None — plan executed exactly as written.

The implementation follows Pattern 4 from RESEARCH.md precisely. All must_have truths are satisfied:
- SearchEngine.search() returns None immediately (verified by test_search_returns_none)
- Signal connections established BEFORE pool.start() (code order enforced, verified by structural grep)
- WorkerSignals sidecar pattern used (_SearchSignals is QObject, not on QRunnable)
- ES_URL imported from nitrofind.es_manager (not hard-coded as string)
- ES client shared via constructor injection (never constructed inside run())
- index="car_articles" hard-coded in _SearchWorker.run()

## Verification Results

```
python3 -m pytest tests/test_search/test_engine.py -m "not integration" -x -q
30 passed, 1 deselected in 1.32s

python3 -m pytest tests/test_search/ -m "not integration" -x -q
66 passed, 1 deselected in 1.61s

python3 -c "from nitrofind.search.engine import SearchEngine, _SearchSignals, _SearchWorker; print('engine.py structure OK')"
engine.py structure OK

python3 -c "from nitrofind.search import SearchEngine, ArticleResult; print('package __init__.py imports OK')"
package __init__.py imports OK
```

Structural smoke checks:
```
grep -n "body=" nitrofind/search/engine.py | grep -v "self._body"
# (empty — no deprecated body= kwarg)

grep -n "QThreadPool()" nitrofind/search/engine.py
# (empty — only globalInstance() used)

grep -n "results_ready.connect\|search_failed.connect\|_pool.start" engine.py
# lines 167, 169 (connections) before line 172 (pool.start) — correct order
```

## Known Stubs

None — engine.py is fully wired. `SearchEngine.search()` calls `build_search_body()` (which builds the real function_score query), passes it to `_SearchWorker.run()` (which calls `client.search()` with real ES flat kwargs), and emits `ArticleResult.from_es_hit()` results via signal. No hardcoded placeholder values or mock data flow paths.

## Threat Flags

No new threat surface beyond the plan's threat model. All threats mitigated as designed:
- T-03-01 (query injection): query_text reaches ES only via `build_search_body()` which places it inside `multi_match.query` string field — never interpolated as DSL keys
- T-03-04 (cross-index): `index="car_articles"` hard-coded on line 91 of engine.py — no user-derived index name path exists
- T-03-05 (unbounded size): `build_search_body` clamps size before body reaches _SearchWorker — engine layer never sees unclamped size
- T-03-06 (signal race): Signal connections on lines 167/169 precede `pool.start()` on line 172 by code structure

## Self-Check: PASSED

Files exist:
- [x] `nitrofind/search/engine.py`
- [x] `tests/test_search/test_engine.py`

Commits exist:
- [x] `085d075` — test(03-02): add failing tests for SearchEngine with QRunnable worker
- [x] `9e54ef9` — feat(03-02): implement SearchEngine with QRunnable worker (engine.py)
