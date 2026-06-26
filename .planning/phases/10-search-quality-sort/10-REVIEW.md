---
phase: 10-search-quality-sort
reviewed: 2026-06-26T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - nitrofind/search/query_builder.py
  - nitrofind/server.py
  - static/css/style.css
  - static/js/app.js
  - templates/index.html
  - tests/test_search/test_api_search.py
  - tests/test_search/test_query_builder.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 10 adds fuzzy/phrase query routing (QURY-01/02), sort controls (SORT-02), and associated API plumbing. The `query_builder.py` and Flask `server.py` routes are well-structured and the security mitigations for sort injection (allowlist) and size clamping are sound.

One BLOCKER was found: `_SearchWorker.run()` in `engine.py` (the PyQt desktop path) never passes the `sort` kwarg to the ES client, so sort-by-date and sort-by-size are silently dropped for any caller going through `SearchEngine`. The Flask path (`server.py`) handles sort correctly — the defect is confined to the Qt worker. Phase 10 added the sort infrastructure but the Qt path was not updated.

Four Warnings cover: a `detail` field in the 500 error response that leaks the Python exception class name; a `date` sort that will cause ES query errors for indexes where `published_at` is absent from the mapping or is null on all scraped-pre-Phase-9 docs; incomplete Escape-key state reset in `app.js`; and the `searchInputResults` warmup-disable gap.

## Critical Issues

### CR-01: `_SearchWorker.run()` silently drops the sort parameter — PyQt search path always returns relevance order

**File:** `nitrofind/search/engine.py:98-105`
**Issue:** `_SearchWorker.run()` calls `self._client.search(...)` with `query`, `highlight`, `source`, `size`, and `from_` but never passes `sort`. `build_search_body()` correctly populates `self._body["sort"]` when `sort="date"` or `sort="size"`, but `_SearchWorker.run()` does not read that key. Any sort selection made through `SearchEngine` (the PyQt desktop path) is silently ignored and ES defaults to `_score` descending for every query, making sort controls non-functional on that code path. The Flask path (`server.py:166`) handles this correctly via `sort=body.get("sort")`.

**Fix:**
```python
# engine.py — _SearchWorker.run(), add sort kwarg
resp = self._client.search(
    index="car_articles",
    query=self._body["query"],
    highlight=self._body.get("highlight"),
    source=self._body.get("_source"),
    size=self._body.get("size", 20),
    from_=self._body.get("from", 0),
    sort=self._body.get("sort"),   # add this line — None → ES default _score desc
)
```

## Warnings

### WR-01: `date` sort will cause ES query errors for documents where `published_at` is null or absent

**File:** `nitrofind/search/query_builder.py:203`
**Issue:** `_build_sort_clauses("date")` returns `[{"published_at": {"order": "desc"}}]` with no `unmapped_type` or `missing` handling. When the `car_articles` index contains docs with a null or missing `published_at` field (all Wikipedia articles scraped without a `published_at` value, plus pre-Phase-9 blog articles), Elasticsearch raises a `SearchPhaseExecutionException` if the mapping does not declare the field as optional or `unmapped_type` is absent. In practice, ES 8 will sort nulls to the bottom by default for `date` fields, but if ANY doc has a completely unmapped `published_at` the query fails with a 400-level error that surfaces as a 500 to the user.

**Fix:**
```python
if sort == "date":
    return [{"published_at": {"order": "desc", "missing": "_last", "unmapped_type": "date"}}]
```

### WR-02: 500 error response leaks Python exception class name in `detail` field

**File:** `nitrofind/server.py:174`
**Issue:** The search error handler returns `{"error": "search_failed", "detail": type(exc).__name__}`. While this is a local-only app, the `detail` field exposes internal Python class names (`ConnectionError`, `AuthenticationException`, `SerializationError`, etc.) to the frontend. If the app is ever exposed beyond localhost, this becomes an information-disclosure vector. More concretely, `app.js` does not consume the `detail` field at all (`if (!resp.ok) return;` at line 105 silently swallows non-2xx responses), so the field adds no user value.

**Fix:**
```python
# Remove the detail field or replace with a static string
return {"error": "search_failed"}, 500
```

### WR-03: Escape key handler does not reset `currentQuery`, `currentResults`, or filter/sort state

**File:** `static/js/app.js:236-241`
**Issue:** The Escape key handler (line 236) clears the two input values and transitions to `"home"`, but it does not reset `currentQuery`, `currentResults`, `currentFilters`, or `currentSort`. If the user presses Escape from the article view and then starts typing again, `onFilterChange` and `onSortChange` still fire `runSearch(currentQuery)` using the stale `currentQuery` value (line 196, 206). Additionally, if the user presses Escape then presses ArrowDown, `selectedIndex` increments and `currentResults[selectedIndex]` would open a result item even though the results view is hidden (uiState is "home"). In practice the keyboard guard at line 222 (`if (uiState === "results")`) protects the arrow key path, but the stale `currentQuery` causing an immediate re-search on filter change from "home" state is a real logic error.

**Fix:**
```javascript
if (e.key === "Escape") {
  searchInput.value = "";
  searchInputResults.value = "";
  currentQuery = "";        // add this
  currentResults = [];      // add this
  selectedIndex = -1;
  transitionTo("home");
}
```

### WR-04: `searchInputResults` (results-view search box) is never disabled during warmup polling

**File:** `static/js/app.js:249` and `templates/index.html:24`
**Issue:** `startWarmupPolling()` disables only `searchInput` (the home-view input) but not `searchInputResults`. In `templates/index.html` the results-view input (`#search-input-results`, line 24) has no `disabled` attribute. If the CSS state machine somehow shows the results view before warmup completes (impossible with the current state machine but defensively fragile), the results-view input would be active. More concretely, a user who opens the app, manually navigates to the results view via dev tools, and types in `#search-input-results` would fire `handleSearchInput` → `runSearch` → `fetch(/api/search)` → 503 → `if (!resp.ok) return` (silently fails). This is low risk but inconsistent with the disable-during-warmup design contract expressed in the comments.

**Fix:**
```javascript
function startWarmupPolling() {
  searchInput.disabled = true;
  searchInputResults.disabled = true;   // add this
  // ...
  // on ready:
  searchInput.disabled = false;
  searchInputResults.disabled = false;  // add this
```

## Info

### IN-01: `_build_sort_clauses` is a private function not covered by any direct unit test

**File:** `nitrofind/search/query_builder.py:190-206`
**Issue:** `_build_sort_clauses` is tested only indirectly through `test_build_search_body_sort_date` and `test_build_search_body_sort_size`. The `sort="relevance"` path in `_build_sort_clauses` (the `return None` branch) is exercised by `test_build_search_body_sort_relevance_no_key` in `test_query_builder.py`, but there is no API-level test for `?sort=relevance` in `test_api_search.py`. This means the allowlist coercion path (`sort not in _VALID_SORTS → None`) covers `sort=inject` but does not explicitly verify that a valid `sort=relevance` explicit param is treated the same way.

**Fix:** Add a test case:
```python
def test_sort_relevance_no_sort_kwarg(monkeypatch):
    """GET /api/search?q=test&sort=relevance passes sort=None to es_client.search. [SORT-02]"""
    # ... setup mock_es ...
    resp = client.get("/api/search?q=test&sort=relevance")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    assert call_kwargs.get("sort") is None
```

### IN-02: `took_ms` display shows sub-millisecond ES responses as `0.00s` with no unit fallback

**File:** `static/js/app.js:126`
**Issue:** `statsLine.textContent = \`${results.length} results (${(took / 1000).toFixed(2)}s)\`` divides the ES `took` field (which is already in milliseconds) by 1000 to get seconds. A typical ES response of 5ms displays as `0.01s`; a 1ms response displays as `0.00s`. The `0.00s` display is technically accurate but visually misleading — users may read it as "zero time". Displaying in milliseconds directly (`${took}ms`) would be clearer for the expected sub-100ms response range.

**Fix:**
```javascript
statsLine.textContent = `${results.length} results (${took}ms)`;
```

---

_Reviewed: 2026-06-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
