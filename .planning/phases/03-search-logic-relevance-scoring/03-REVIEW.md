---
phase: 03-search-logic-relevance-scoring
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - nitrofind/search/__init__.py
  - nitrofind/search/engine.py
  - nitrofind/search/models.py
  - nitrofind/search/query_builder.py
  - tests/test_search/test_engine.py
  - tests/test_search/test_models.py
  - tests/test_search/test_query_builder.py
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-27T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

The search package implements a QThreadPool-based search engine, typed result models, and an Elasticsearch `function_score` query builder. The scoring design (Gaussian recency decay, log1p length signal, infobox boost, two-function split for missing `published_at`) is architecturally sound and matches the RLVN requirements. Security mitigations against query injection and unbounded size are correctly applied.

Two blockers were found: (1) `_score=None` (which ES emits in filter-context queries) passes through `hit.get("_score", 0.0)` unchanged and silently breaks the `score: float` type contract; (2) `SearchEngine.search()` omits the `from_` pagination parameter, making offset pagination impossible through the public API. Five warnings cover thread-safety of callback delivery, weight parameter forwarding gaps, negative input validation, a misused decorator, and a test that does not actually verify its stated invariant.

## Critical Issues

### CR-01: `_score=None` silently violates `ArticleResult.score: float` type contract

**File:** `nitrofind/search/models.py:73`

**Issue:** `hit.get("_score", 0.0)` only substitutes the default when the `"_score"` key is **absent** from the dict. When Elasticsearch returns a document in a filter-only context, or when `track_scores` is disabled, it sets `"_score": null` — the key is present with value `None`. Python's `.get()` returns `None` in that case, bypassing the `0.0` fallback. The `ArticleResult` dataclass does not enforce types at runtime, so the `score` field is silently set to `None` instead of `float`. Any downstream code that compares, formats, or arithmetically uses `score` will raise `TypeError` at display time rather than at ingestion time.

**Fix:**
```python
score=hit.get("_score") or 0.0,
```
Or more explicitly to handle both missing key and explicit `None`:
```python
raw_score = hit.get("_score")
score = float(raw_score) if raw_score is not None else 0.0
```
Apply the same pattern to `word_count` (line 76), which could similarly receive `None` if the field is stored as null in the index.

---

### CR-02: `SearchEngine.search()` exposes no `from_` parameter — pagination is impossible via the public API

**File:** `nitrofind/search/engine.py:134-141`

**Issue:** `build_search_body` accepts a `from_` parameter for offset-based pagination, and `_SearchWorker.run()` correctly reads `self._body.get("from", 0)` and passes it to `client.search(from_=...)`. However, `SearchEngine.search()` — the only public entry point for Phase 4 UI — never accepts or forwards a `from_` argument. Every call to `search()` hardwires `build_search_body(..., from_=0)` (because `from_` defaults to `0` in `build_search_body` and is never overridden). Result: all queries start at page 1 with no way to paginate, making the "load more" / "next page" pattern impossible through the exposed API. When Phase 4 adds pagination UI, this will require revisiting the engine's public interface.

**Fix:**
```python
def search(
    self,
    query_text: str,
    filters: list[dict] | None = None,
    size: int = 20,
    from_: int = 0,                          # add pagination offset
    callback: Callable[[list], None] | None = None,
    error_callback: Callable[[str], None] | None = None,
) -> None:
    body = build_search_body(query_text, filters=filters, size=size, from_=from_)
```

---

## Warnings

### WR-01: Callbacks connected without `Qt.ConnectionType.QueuedConnection` — thread-safety of UI updates not guaranteed

**File:** `nitrofind/search/engine.py:167-169`

**Issue:** The docstring on `SearchEngine.search()` (line 145) states "Results are delivered via callback **in the Qt main thread** via signal/slot." This is incorrect as written. `results_ready` is connected to a plain Python callable (lambda or function). When PyQt6 resolves `AutoConnection` for a non-`QObject` receiver, it cannot determine the receiver's thread affinity and defaults to `DirectConnection`. The callback therefore executes in the **worker thread** that emits the signal, not the main thread. If the Phase 4 callback updates any `QWidget`, it will violate Qt's single-thread UI rule and cause crashes or data corruption.

**Fix:** Specify `Qt.ConnectionType.QueuedConnection` explicitly:
```python
from PyQt6.QtCore import Qt

if callback:
    signals.results_ready.connect(callback, Qt.ConnectionType.QueuedConnection)
if error_callback:
    signals.search_failed.connect(error_callback, Qt.ConnectionType.QueuedConnection)
```
Also update the docstring to accurately describe the delivery thread — or link to the connection type used.

---

### WR-02: `build_search_body` does not forward weight parameters to `build_function_score_query`

**File:** `nitrofind/search/query_builder.py:191`

**Issue:** `build_function_score_query` accepts four weight parameters (`recency_weight`, `length_weight`, `infobox_weight`, `missing_published_score`), all documented and tested. `build_search_body` calls `build_function_score_query(query_text)` without forwarding any weights. There is no way to tune scoring weights through the main entry point without bypassing `build_search_body` entirely. Phase 4 settings UI (if weight sliders are added) would have to either duplicate the `build_function_score_query` call or add new parameters to `build_search_body`. The gap is not a current crash, but it is a design dead-end that will require an API break to fix.

**Fix:**
```python
def build_search_body(
    query_text: str,
    filters: list[dict] | None = None,
    size: int = 20,
    from_: int = 0,
    recency_weight: float = DEFAULT_RECENCY_WEIGHT,
    length_weight: float = DEFAULT_LENGTH_WEIGHT,
    infobox_weight: float = DEFAULT_INFOBOX_WEIGHT,
    missing_published_score: float = DEFAULT_MISSING_PUBLISHED_SCORE,
) -> dict:
    fs_query = build_function_score_query(
        query_text,
        recency_weight=recency_weight,
        length_weight=length_weight,
        infobox_weight=infobox_weight,
        missing_published_score=missing_published_score,
    )
```

---

### WR-03: Negative `size` and `from_` values pass validation and produce ES 400 errors at runtime

**File:** `nitrofind/search/query_builder.py:222-223`

**Issue:** `size` is clamped with `min(size, MAX_RESULT_SIZE)`, which only caps the upper bound. `min(-5, 100)` returns `-5`, which ES rejects with a 400 error surfacing as a `search_failed` signal. `from_` has no validation at all; a negative value also causes ES 400. Both are docstring-declared as "0-based" and "number of results", implying non-negative values only. The errors are contained (they surface as `search_failed` signals, not crashes), but they produce unhelpful error messages with no indication that invalid input was the cause.

**Fix:**
```python
"size": max(0, min(size, MAX_RESULT_SIZE)),   # clamp [0, MAX_RESULT_SIZE]
"from": max(0, from_),                         # clamp to non-negative
```

---

### WR-04: `@pyqtSlot()` applied to `_SearchWorker.run()` is semantically incorrect

**File:** `nitrofind/search/engine.py:84`

**Issue:** `@pyqtSlot()` marks a Python method as a Qt slot — a method intended to receive Qt signals. `QRunnable.run()` is a C++ virtual method override that QThreadPool calls directly via the threading machinery; it is not connected to any signal and is never invoked through the signal/slot system. Applying `@pyqtSlot()` here is misleading and adds unnecessary metaclass overhead. It could also cause confusion for future maintainers who might expect `run()` to be callable as a slot.

**Fix:** Remove the decorator:
```python
def run(self) -> None:
    """Execute the ES search query and emit results via signals."""
```

---

### WR-05: `test_search_connects_callback_before_start` does not verify its stated invariant

**File:** `tests/test_search/test_engine.py:372-397`

**Issue:** The test is documented as verifying that signal connections are established **before** `pool.start(worker)` is called (the T-03-06 race condition mitigation). The `tracking_start` interceptor appends `"start_called"` to a list, and the assertion checks `len(connection_count_at_start) == 1`. This only proves `pool.start()` was called once. A buggy implementation that calls `pool.start(worker)` **before** `signals.results_ready.connect(callback)` would still pass this test. The connection-order invariant is entirely untested.

**Fix:** Capture whether signals are already connected at the moment `start()` is intercepted:
```python
def tracking_start(worker):
    # Verify signals are already connected at start() time
    assert worker._signals.receivers(worker._signals.results_ready) > 0 or \
           worker._signals.results_ready.receivers(0) > 0
    connection_count_at_start.append("start_called")
```
Or use PyQt6's `signalsBlocked()` / receiver count introspection to assert connection state.

---

## Info

### IN-01: `__init__.py` declares `SearchEngine` in `__all__` even when the import silently fails

**File:** `nitrofind/search/__init__.py:3-9`

**Issue:** The `try/except ImportError: pass` block is a deliberate Wave 1 isolation mechanism. However, `__all__ = ["SearchEngine", "ArticleResult"]` is unconditional. If the import fails (e.g., PyQt6 not installed), `SearchEngine` is absent from the module namespace but still present in `__all__`. A consumer using `from nitrofind.search import *` or `from nitrofind.search import SearchEngine` will receive a `NameError` with no hint about the root cause. The comment says "Wave 1 test isolation" — if this is temporary scaffolding, it should be removed now that engine.py exists.

**Fix:** Remove the try/except wrapper since `engine.py` now exists, or conditionally exclude `SearchEngine` from `__all__`:
```python
from nitrofind.search.engine import SearchEngine  # noqa: F401
from nitrofind.search.models import ArticleResult  # noqa: F401

__all__ = ["SearchEngine", "ArticleResult"]
```

---

### IN-02: `ES_URL` imported in `engine.py` but never functionally used

**File:** `nitrofind/search/engine.py:30`

**Issue:** `ES_URL` is imported from `nitrofind.es_manager` with a `# noqa: F401` comment suppressing the "imported but unused" warning. The ES client is injected into `SearchEngine.__init__` by the caller; `engine.py` never constructs an `Elasticsearch` instance, so `ES_URL` serves no runtime purpose here. The `noqa` comment is a code smell: it silences a linter warning that is correctly diagnosing dead code. The only reason the import exists is to satisfy `test_es_url_imported_from_es_manager`, which tests that `engine_module.ES_URL` is accessible — a test that validates the import rather than any actual behaviour.

**Fix:** Remove the import and remove or rewrite `test_es_url_imported_from_es_manager` to test the actual contract (that `SearchEngine` uses a properly constructed ES client at `localhost:9200`).

---

### IN-03: Integration test uses bare `time.sleep(2)` to wait for QThreadPool worker

**File:** `tests/test_search/test_engine.py:510`

**Issue:** `test_search_callback_receives_article_results` calls `engine.search(...)` which submits a worker to `QThreadPool.globalInstance()`, then immediately calls `time.sleep(2)` to wait for results. This is a flaky test pattern — on slow CI machines, a 2-second timeout may be insufficient (ES cold start + JVM GC pause). It also sleeps unconditionally even when the worker finishes in 50ms.

**Fix:** Use `QThreadPool.globalInstance().waitForDone(timeout_ms)` after submitting, then process events:
```python
from PyQt6.QtCore import QCoreApplication
engine.search("Ferrari", callback=..., error_callback=...)
QThreadPool.globalInstance().waitForDone(10_000)  # 10s max
QCoreApplication.processEvents()
```

---

_Reviewed: 2026-05-27T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
