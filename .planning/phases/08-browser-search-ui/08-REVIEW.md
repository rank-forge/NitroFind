---
phase: 08-browser-search-ui
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - nitrofind/server.py
  - static/css/style.css
  - static/js/app.js
  - templates/index.html
  - tests/test_server.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-06-03
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the five files comprising the Phase 8 browser-search-UI implementation: the Flask server, HTML template, CSS SPA stylesheet, vanilla-JS SPA controller, and server unit tests.

The security constraints are mostly met: no external CDN links are present in `index.html`, Flask's `template_folder`/`static_folder` use explicit `os.path` relative to `server.py`, `innerHTML` is used in exactly two places in `app.js` (lines 122 and 141), and article body uses `textContent`. The ES highlight pre/post tags are hardcoded to `<b>`/`</b>` which limits injection scope.

However, two blockers were found:

1. The API wire format (`_result_to_api_dict`) omits the `body` field, so the article detail view (`openArticle`) always displays "No content available." - the SRCH-03 feature is non-functional as shipped.
2. `runSearch` calls `resp.json()` and `results.forEach()` without checking `resp.ok`. A 500 or 503 response returns a JSON object (not an array), causing `results.forEach` to throw `TypeError`, crashing the search flow silently inside the catch block rather than showing an error to the user.

Four additional warnings cover: a dead DOM reference, the Escape key failing to clear the results-view search input, internal ES error detail leaking in the 500 response, and a 1px content-shift layout jitter on keyboard selection.

---

## Critical Issues

### CR-01: `body` field missing from API wire format - article view always shows fallback

**File:** `nitrofind/server.py:112-119`

**Issue:** `_result_to_api_dict` serializes six fields (`title`, `url`, `source_domain`, `excerpt`, `score`, `took_ms`) but omits `body`. `ArticleResult` carries a `body` field populated by `from_es_hit` (models.py line 115) and `build_search_body` includes `"body"` in the `_source` projection (query_builder.py line 242). The JS `openArticle` function reads `result.body` (app.js line 158), which will always be `undefined` since the field is never sent. The `|| "No content available."` fallback fires unconditionally, making the entire article detail view (SRCH-03) non-functional.

**Fix:** Add `"body"` to the return dict in `_result_to_api_dict`:

```python
def _result_to_api_dict(result: ArticleResult, took_ms: int) -> dict:
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return {
        "title": result.title,
        "url": result.url,
        "source_domain": result.source_domain,
        "excerpt": excerpt,
        "body": result.body,        # add this line
        "score": result.score,
        "took_ms": took_ms,
    }
```

Note: `body` may be a large string (full article text). If payload size becomes a concern, consider a separate `/api/article?url=...` endpoint to fetch body on demand, but the immediate fix is to include it here.

---

### CR-02: `runSearch` does not guard against non-array responses - crashes on server errors

**File:** `static/js/app.js:92-103`

**Issue:** After `await fetch(...)`, the code unconditionally calls `await resp.json()` and then assigns the parsed value to `currentResults` and passes it to `renderResults(results)`. When the server is still warming up or encounters an error it returns JSON objects (`{"status": "starting"}` or `{"error": "search_failed", "detail": "..."}`) rather than an array. `renderResults` then calls `results.forEach(...)` (line 123), which throws `TypeError: results.forEach is not a function`. The catch block at line 101 only silences `AbortError`, so this TypeError is swallowed by `console.error` but the UI is left in an indeterminate state (no transition to "results", no user-visible error).

The user would see a blank, unresponsive UI after a server error with no indication of what happened.

**Fix:** Check `resp.ok` before parsing and handle the error case explicitly:

```js
async function runSearch(q) {
  currentQuery = q;
  if (abortController) abortController.abort();
  abortController = new AbortController();

  const params = new URLSearchParams({ q, ...currentFilters });
  for (const [k, v] of [...params.entries()]) {
    if (!v) params.delete(k);
  }

  try {
    const resp = await fetch(`/api/search?${params}`, {
      signal: abortController.signal,
    });
    if (!resp.ok) {
      // Server error (500) or warmup 503 — do not parse as results array
      console.warn("Search returned non-ok status:", resp.status);
      return;
    }
    const results = await resp.json();
    if (!Array.isArray(results)) {
      console.warn("Unexpected search response shape:", results);
      return;
    }
    currentResults = results;
    selectedIndex = -1;
    renderResults(results);
    transitionTo("results");
  } catch (err) {
    if (err.name !== "AbortError") console.error("Search failed:", err);
  }
}
```

---

## Warnings

### WR-01: `searchInputResults` DOM reference is declared but never used

**File:** `static/js/app.js:41`

**Issue:** `const searchInputResults = document.getElementById("search-input-results")` is assigned at module level but no `addEventListener` is ever attached to it. The results-view search input (`#search-input-results`) is visually present and focusable in the HTML, but typing into it has no effect. Users who naturally try to refine their search from the results view will get no response. This is a dead variable paired with a dead UI element.

**Fix:** Wire the results-view input to the same debounced search handler and keep both inputs in sync:

```js
searchInputResults.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const q = searchInputResults.value.trim();
  // Sync the home-view input so Escape→home shows the same query
  searchInput.value = q;
  if (!q) {
    transitionTo("home");
    return;
  }
  debounceTimer = setTimeout(() => runSearch(q), DEBOUNCE_MS);
});
```

Also update `transitionTo("results")` to sync `searchInputResults.value = currentQuery` so the results-view input reflects the active query when the state changes.

---

### WR-02: Escape key does not clear the results-view search input

**File:** `static/js/app.js:207-211`

**Issue:** The Escape handler clears `searchInput.value` (the home-view input) but not `searchInputResults.value`. If a user is in the results state and presses Escape, they are taken to the home view with the home input cleared - but if they press a key that brings them back to results, the results-view input still shows the previous query text while `currentQuery` may have been reset. This state desynchronization will become more visible once WR-01 is fixed and the results-view input is wired.

**Fix:**
```js
if (e.key === "Escape") {
  searchInput.value = "";
  searchInputResults.value = "";   // add this line
  transitionTo("home");
  selectedIndex = -1;
}
```

---

### WR-03: Internal Elasticsearch error detail leaked in 500 response

**File:** `nitrofind/server.py:164`

**Issue:** When an ES search call fails, the server returns:
```json
{"error": "search_failed", "detail": "<str(exc)>"}
```
`str(exc)` on an `elasticsearch.exceptions` object can include the full query body, ES endpoint URL (including port), index name, ES cluster error message, and transport-level details. While this is a local-only app, the Flask development server is accessible to any process on the machine and potentially to local network peers depending on binding. Exposing raw exception strings also makes debugging harder (they are already logged at WARNING level with `logger.warning`).

**Fix:** Return a generic detail string to the client and rely on the server-side log for diagnostics:

```python
except Exception as exc:
    logger.warning("Search error: %s: %s", type(exc).__name__, exc)
    return {"error": "search_failed", "detail": type(exc).__name__}, 500
```

---

### WR-04: `border-left: 2px` on `.result-item.selected` causes 1px content shift

**File:** `static/css/style.css:226-229`

**Issue:** `.result-item` has `border: 1px solid var(--border)` (all four sides). `.result-item.selected` overrides only `border-left: 2px solid var(--accent)`. With `box-sizing: border-box`, the total element width stays the same but the left border now occupies 2px instead of 1px, pushing the content 1px to the right on selection. When navigating with arrow keys, each selection change produces a 1px horizontal jitter in the card content.

**Fix:** Either compensate with padding or use `outline` instead of a border mutation for the selection indicator:

```css
/* Option A: compensate left padding so content stays in place */
.result-item.selected {
  background-color: var(--bg-surface);
  border-left: 2px solid var(--accent);
  padding-left: calc(1rem - 1px);   /* 1rem base padding minus the extra 1px border */
}

/* Option B: use outline (doesn't affect layout) */
.result-item.selected {
  background-color: var(--bg-surface);
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
```

Option B is cleaner since it avoids touching the box model.

---

## Info

### IN-01: `MagicMock` and `patch` imported but never used in tests

**File:** `tests/test_server.py:17`

**Issue:** `from unittest.mock import MagicMock, patch` - neither `MagicMock` nor `patch` is referenced anywhere in the test file. These were likely imported in anticipation of `api_search` tests that were not written.

**Fix:** Remove the unused imports. If `api_search` tests are planned, add them at the same time.

```python
# Remove this line entirely until mock-based tests are added:
from unittest.mock import MagicMock, patch
```

---

### IN-02: `api_search` endpoint has zero test coverage

**File:** `tests/test_server.py`

**Issue:** The test file covers `GET /` (2 tests), `GET /api/status` (3 tests), and PORT resolution (1 test), but has no test for `GET /api/search`. The search route is the primary feature of the phase and contains non-trivial logic: the 503 warmup guard, the blank-query early return, filter parameter parsing, and error handling. The unused `MagicMock`/`patch` imports suggest this was intended but not completed.

**Fix:** Add at minimum:
- A test asserting `GET /api/search?q=ford` returns 503 when not ready (mirrors the status guard pattern already tested).
- A test with a mocked `state["es_client"]` asserting a blank `q` returns HTTP 200 with `[]`.
- A test asserting the error branch returns HTTP 500 with `{"error": "search_failed"}`.

---

_Reviewed: 2026-06-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
