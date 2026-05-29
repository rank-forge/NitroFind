---
phase: 03-search-logic-relevance-scoring
fixed_at: 2026-05-27T00:00:00Z
review_path: .planning/phases/03-search-logic-relevance-scoring/03-REVIEW.md
iteration: 2
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-05-27T00:00:00Z
**Source review:** `.planning/phases/03-search-logic-relevance-scoring/03-REVIEW.md`
**Iteration:** 2 (all findings — Critical + Warning in iteration 1; Info in iteration 2)

**Summary:**
- Findings in scope: 10 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04, WR-05, IN-01, IN-02, IN-03)
- Fixed: 10
- Skipped: 0

---

## Fixed Issues — Iteration 1 (Critical + Warning)

### CR-01: `_score=None` silently violates `ArticleResult.score: float` type contract

**Files modified:** `nitrofind/search/models.py`
**Commit:** e66e98c
**Applied fix:** Replaced `hit.get("_score", 0.0)` with a two-step extraction: `raw_score = hit.get("_score")` followed by `score = float(raw_score) if raw_score is not None else 0.0`. Applied the same pattern to `word_count` using `raw_word_count = src.get("word_count")` / `word_count = int(raw_word_count) if raw_word_count is not None else 0`. Both fields now correctly handle the case where ES returns the key present with a `null` value (not just a missing key).

---

### CR-02: `SearchEngine.search()` exposes no `from_` parameter — pagination is impossible

**Files modified:** `nitrofind/search/engine.py`, `tests/test_search/test_engine.py`
**Commit:** c2c736c
**Applied fix:** Added `from_: int = 0` parameter to `SearchEngine.search()` signature and forwarded it to `build_search_body(query_text, filters=filters, size=size, from_=from_)`. Updated two tests (`test_search_calls_build_search_body`, `test_search_passes_filters_to_build_search_body`) that asserted the old call signature without `from_=0` — both now include `from_=0` in the expected call assertion.

---

### WR-01: Callbacks connected without `Qt.ConnectionType.QueuedConnection`

**Files modified:** `nitrofind/search/engine.py`
**Commit:** 43b3e2d
**Applied fix:** Added `Qt` to the `PyQt6.QtCore` import. Changed both `signals.results_ready.connect(callback)` and `signals.search_failed.connect(error_callback)` to pass `Qt.ConnectionType.QueuedConnection` as the second argument. Updated the docstring to correctly state callbacks are delivered via `QueuedConnection` (main thread delivery). This prevents callbacks from executing in the worker thread and violating Qt's single-thread UI rule.

---

### WR-02: `build_search_body` does not forward weight parameters to `build_function_score_query`

**Files modified:** `nitrofind/search/query_builder.py`
**Commit:** 261b440
**Applied fix:** Added four weight parameters to `build_search_body` signature (`recency_weight`, `length_weight`, `infobox_weight`, `missing_published_score`), all defaulting to their corresponding module constants. Changed the `build_function_score_query(query_text)` call to forward all four weight parameters explicitly. Updated the docstring to document the new parameters.

---

### WR-03: Negative `size` and `from_` values pass validation and produce ES 400 errors

**Files modified:** `nitrofind/search/query_builder.py`
**Commit:** caec591
**Applied fix:** Changed `"size": min(size, MAX_RESULT_SIZE)` to `"size": max(0, min(size, MAX_RESULT_SIZE))` to clamp the lower bound to 0. Changed `"from": from_` to `"from": max(0, from_)` to prevent negative offsets. Both values are now clamped to non-negative ranges before being sent to ES.

---

### WR-04: `@pyqtSlot()` applied to `_SearchWorker.run()` is semantically incorrect

**Files modified:** `nitrofind/search/engine.py`
**Commit:** c9d7b6c
**Applied fix:** Removed the `@pyqtSlot()` decorator from `_SearchWorker.run()`. Also removed `pyqtSlot` from the `PyQt6.QtCore` import line since it was no longer used anywhere in the file. `QRunnable.run()` is a C++ virtual override called by QThreadPool, not a slot connected to any signal.

---

### WR-05: `test_search_connects_callback_before_start` does not verify connection order

**Files modified:** `tests/test_search/test_engine.py`
**Commit:** 46f98a7
**Applied fix:** Expanded `tracking_start()` interceptor to capture the receiver count of `worker._signals.results_ready` at the moment `pool.start()` is called, using `worker._signals.receivers(worker._signals.results_ready)`. Added a second assertion: `assert receiver_count_at_start[0] > 0` — this fails if `start()` was called before signals were connected (receiver count would be 0), directly verifying the T-03-06 invariant.

---

## Fixed Issues — Iteration 2 (Info)

### IN-01: `__init__.py` try/except ImportError scaffold removed

**Files modified:** `nitrofind/search/__init__.py`
**Commit:** 780733f
**Applied fix:** Replaced the `try/except ImportError: pass` block (Wave 1 test isolation scaffolding) with a direct, unconditional import of `SearchEngine`. The `__all__` list was already correct. Since `engine.py` now exists, the conditional guard was dead code that also made `__all__` inconsistent when the import failed.

---

### IN-02: Dead `ES_URL` import removed from `engine.py`; test rewritten

**Files modified:** `nitrofind/search/engine.py`, `tests/test_search/test_engine.py`
**Commit:** 69b3910
**Applied fix:** Removed `from nitrofind.es_manager import ES_URL  # noqa: F401` from `engine.py` (the import served no runtime purpose — the ES client is injected by the caller). The corresponding test `test_es_url_imported_from_es_manager` was rewritten as `test_search_engine_accepts_elasticsearch_client`, which verifies the actual construction contract: that `SearchEngine.__init__` accepts an `Elasticsearch` client and stores it as `_client`. The `ES_URL` import in `test_engine.py` was kept because the integration tests use it to construct a live client.

---

### IN-03: `time.sleep(2)` replaced with deterministic pool wait in integration test

**Files modified:** `tests/test_search/test_engine.py`
**Commit:** ad339d2
**Applied fix:** In `test_search_callback_receives_article_results`, replaced the unconditional `time.sleep(2)` with `QThreadPool.globalInstance().waitForDone(10_000)` followed by `QCoreApplication.processEvents()`. The imports of `QCoreApplication` and `QThreadPool` were added inline at the top of the function (consistent with the existing inline-import style). The `import time` / `time.sleep(2)` block was removed entirely.

---

## Test Results (after both iterations)

```
66 passed, 3 skipped in 0.25s
```

All 66 unit tests pass. The 3 skipped tests are integration tests marked `@pytest.mark.integration` that require a live Elasticsearch node (`ES_HOME` env var not set) — expected, unchanged behavior.

---

_Fixed: 2026-05-27T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
