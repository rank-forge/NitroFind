---
phase: 10-search-quality-sort
fixed_at: 2026-06-26T00:00:00Z
review_path: .planning/phases/10-search-quality-sort/10-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-06-26T00:00:00Z
**Source review:** .planning/phases/10-search-quality-sort/10-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `_SearchWorker.run()` silently drops the sort parameter

**Files modified:** `nitrofind/search/engine.py`
**Commit:** 602b30b
**Applied fix:** Added `sort=self._body.get("sort")` kwarg to the `self._client.search()` call in `_SearchWorker.run()`. The `build_search_body()` function correctly populates `self._body["sort"]` when sort mode is "date" or "size", but the PyQt worker was not forwarding it to the ES client. `None` value lets ES default to `_score` descending (relevance). The Flask path in `server.py` already handled this correctly; this brings the PyQt path to parity.

### WR-01: `date` sort causes ES query errors for documents with null or absent `published_at`

**Files modified:** `nitrofind/search/query_builder.py`
**Commit:** 825c185
**Applied fix:** Added `"missing": "_last"` and `"unmapped_type": "date"` to the `published_at` date sort clause in `_build_sort_clauses()`. This prevents `SearchPhaseExecutionException` for documents where `published_at` is null or absent from the mapping (Wikipedia articles and pre-Phase-9 blog articles), causing ES to sort those documents to the bottom instead of raising a 400-level error.

### WR-02: 500 error response leaks Python exception class name in `detail` field

**Files modified:** `nitrofind/server.py`
**Commit:** 63178f3
**Applied fix:** Removed the `"detail": type(exc).__name__` field from the 500 error response in `api_search()`. The exception class name is retained in the `logger.warning()` call for debugging but no longer sent to the frontend. The `detail` field had no user value since `app.js` silently discards non-2xx responses.

### WR-03: Escape key handler does not reset `currentQuery`, `currentResults`, or `selectedIndex`

**Files modified:** `static/js/app.js`
**Commit:** e4daf8a
**Applied fix:** Added `currentQuery = ""` and `currentResults = []` resets to the Escape key handler, before `transitionTo("home")`. Also moved `selectedIndex = -1` before the transition call for consistency. This prevents `onFilterChange`/`onSortChange` from firing `runSearch(currentQuery)` with a stale query when the user changes a filter after pressing Escape from the results or article view.

### WR-04: `searchInputResults` not disabled during ES warmup polling

**Files modified:** `static/js/app.js`
**Commit:** 22be193
**Applied fix:** Added `searchInputResults.disabled = true` at the start of `startWarmupPolling()` and `searchInputResults.disabled = false` inside the `data.status === "ok"` branch alongside the existing `searchInput` enable. This enforces the warmup design contract symmetrically on both search inputs — the home-view input and the results-view input are now both disabled during ES startup and re-enabled together when ES reports ready.

---

_Fixed: 2026-06-26T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
