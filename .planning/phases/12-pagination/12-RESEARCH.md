# Phase 12: Pagination - Research

**Researched:** 2026-07-04
**Domain:** Elasticsearch from/size pagination, Flask API response shape evolution, vanilla JS pagination state management
**Confidence:** HIGH

---

## Summary

Phase 12 adds page navigation to the search results view. The core mechanism — Elasticsearch `from`/`size` pagination — is already wired into `build_search_body` and the `api_search` route. The backend already passes `from_=body.get("from", 0)` and `size=body.get("size", 20)` to `es_client.search`; Phase 12 simply makes these values dynamic (driven by a `page` query param) rather than always defaulting to 0/20.

The critical structural change is the API response shape. Currently `api_search` returns a flat JSON array `[{result}, ...]`. The success criteria require showing the total hit count across all pages (`"248 results (0.08s)"`) — information that exists in `resp["hits"]["total"]["value"]` but is not currently returned. Adding this requires changing the response to a wrapper object: `{"results": [...], "total": 248, "took_ms": 8, "page": 1}`. This is a controlled breaking change — the UI is the only consumer.

The frontend change has three parts: (1) `currentPage` module-level state that resets to 1 on new queries/filters/sorts and increments/decrements on page nav clicks; (2) `renderResultCount` update to read `data.total` and `data.took_ms` from the wrapper rather than `results[0].took_ms` and `results.length`; (3) Previous/Next buttons added below `#results-list` with show/hide/disable logic.

No new packages are required. All changes are in-place modifications to existing files.

**Primary recommendation:** Change `api_search` to a wrapper response, add `PAGE_SIZE = 10` constant, read `page` param with safe coercion, pass `size=PAGE_SIZE, from_=from_` to `build_search_body`. On the frontend, add `currentPage` state and pagination buttons. Update 4 existing `test_api_search.py` assertions for the new response shape.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAGE-01 | Result list shows results in pages (default 10 per page) with Previous / Next navigation buttons | ES `from`/`size` already in `build_search_body`; `api_search` passes these to `es_client.search`; page param → `from_` calculation is straightforward; Previous/Next buttons are new HTML elements wired to `currentPage` state |
| PAGE-02 | Result count below the search box shows total hits across all pages (e.g. "248 results (0.08s)") | `resp["hits"]["total"]["value"]` is the ES total across all pages; currently unused by `api_search`; requires response shape change to expose `total` to the frontend |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Page offset computation (`from_ = (page-1) * PAGE_SIZE`) | API / Backend (`server.py`) | — | The API owns the translation of user-facing `page` number to ES `from`/`size` params — the frontend should not know about ES internals |
| Total hit count extraction | API / Backend (`server.py`) | — | `resp["hits"]["total"]["value"]` is an ES-internal path; isolating it in the server means the JS only sees `data.total`, not the ES response structure |
| `currentPage` state tracking | Browser / Client (`app.js`) | — | Page navigation is UI state — which page the user is on is the browser's concern |
| Previous/Next button visibility/disable | Browser / Client (`app.js`) | — | Depends on `total`, `page`, and `PAGE_SIZE` — computed client-side from API response fields |
| Stats line ("248 results (0.08s)") | Browser / Client (`app.js`) | — | `renderResultCount` reads `data.total` and `data.took_ms` from wrapper response |

---

## Standard Stack

No new packages are introduced by this phase. All changes are additive modifications to existing Python and vanilla JS files.

| File | Change Type | What Changes |
|------|-------------|--------------|
| `nitrofind/server.py` | Extend + reshape | `PAGE_SIZE = 10` constant; `page` param reading; `from_` computation; response changed from flat array to `{"results": [...], "total": N, "took_ms": N, "page": N}` |
| `static/js/app.js` | Extend | `currentPage` state; `runSearch` page param; updated `renderResultCount`; `renderPagination`; pagination button handlers |
| `templates/index.html` | Add elements | `<div class="pagination-row">` with `#prev-btn` and `#next-btn` below `#results-list` |
| `static/css/style.css` | Add rules | `.pagination-row` layout and button styling (mirrors `.sort-btn` style) |
| `tests/test_search/test_api_search.py` | Update + extend | Update 4 existing assertions for new response shape; add 6 new pagination tests |

**No changes needed:**
- `nitrofind/search/query_builder.py` — `build_search_body` already supports `size` and `from_` params; `from_` clamped to non-negative; no modification required
- `tests/test_search/test_query_builder.py` — `test_build_search_body_from_param` already tests the `from_` path; `test_build_search_body_default_size` remains valid (default is still 20 — the route will now explicitly pass 10)

**Version verification:** No new packages.

---

## Package Legitimacy Audit

No new packages are installed in this phase. Not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
User types query OR clicks Next/Prev
    │
    ├── New query / filter / sort change:
    │   currentPage = 1
    │   runSearch(currentQuery)
    │
    └── Page nav click:
        currentPage ± 1
        runSearch(currentQuery)   ← same query, different page
            │
            ↓
runSearch(q)
    │ params = { q, ...currentFilters, page: currentPage }
    │ strip empty values (existing pattern)
    │ append sort (existing pattern)
    ↓
GET /api/search?q=ferrari&page=2
    ↓
Flask api_search
    │ page = max(1, _safe_int_param(request.args.get("page")) or 1)
    │ from_ = (page - 1) * PAGE_SIZE   ← e.g. (2-1)*10 = 10
    │ body = build_search_body(q, filters=filters, sort=sort, size=PAGE_SIZE, from_=from_)
    ↓
Elasticsearch 8.18
    │ resp["hits"]["hits"]          ← up to 10 results for this page
    │ resp["hits"]["total"]["value"] ← e.g. 248 (across ALL pages)
    │ resp["took"]                  ← query time in ms
    ↓
Return {"results": [...], "total": 248, "took_ms": 8, "page": 2}
    ↓
runSearch (client) receives data:
    │ currentResults = data.results
    │ renderResults(data.results)         — renders 10 cards
    │ renderResultCount(data.total, data.took_ms) — "248 results (0.08s)"
    │ renderPagination(data.total, data.page)
    │   ├── prevBtn disabled if page == 1
    │   └── nextBtn disabled if page * PAGE_SIZE >= total
    ↓
DOM updated
```

### Recommended Project Structure

No new directories. Changes are in-place modifications to existing files:

```
nitrofind/
├── server.py              ← PAGE_SIZE constant; page param; wrapper response
templates/
├── index.html             ← .pagination-row with #prev-btn, #next-btn
static/
├── js/app.js              ← currentPage state; updated runSearch/renderResultCount; renderPagination
├── css/style.css          ← .pagination-row and pagination button styles
tests/
├── test_search/
│   └── test_api_search.py ← update 4 tests; add 6 new pagination tests
```

### Pattern 1: Elasticsearch from/size Pagination

**What:** Standard ES pagination for local small indexes. `from` is the zero-based document offset; `size` is the page size. ES returns up to `size` hits starting from offset `from`.

**When to use:** Always for this project — the index is local and well under the 10,000-document `max_result_window` default. Search-after pagination (cursor-based) is only necessary for indexes with tens of thousands of results or for live-export use cases — neither applies here.

**Already in codebase:** `build_search_body` accepts `from_: int = 0` and `size: int = 20`; the route passes `from_=body.get("from", 0)` and `size=body.get("size", 20)` to `es_client.search`. Phase 12 makes these values dynamic.

**Example:**

```python
# Source: nitrofind/search/query_builder.py — existing build_search_body [VERIFIED: codebase]

# Phase 12: caller (api_search) passes explicit size/from_
PAGE_SIZE = 10  # new constant in server.py

page = max(1, _safe_int_param(request.args.get("page")) or 1)
from_value = (page - 1) * PAGE_SIZE

body = build_search_body(q, filters=filters, sort=sort, size=PAGE_SIZE, from_=from_value)
# build_search_body already clamps: max(0, min(size, MAX_RESULT_SIZE)) and max(0, from_)
# PAGE_SIZE=10 is well within MAX_RESULT_SIZE=100; from_ is always >= 0.
```

### Pattern 2: ES Total Hit Count

**What:** `resp["hits"]["total"]["value"]` gives the count of all matching documents across all pages, not just the current page. In ES 8 this is accurate up to `track_total_hits` (default: 10,000). For a 2 GB local index, exact counts are always returned.

**Source:** `[VERIFIED: codebase]` — all existing mock ES responses in `test_api_search.py` already use `{"hits": {"total": {"value": N}, "hits": [...]}}`, confirming the path is correct for ES 8.x.

```python
# Source: server.py existing pattern [VERIFIED: codebase]
took_ms = resp.get("took", 0)
total = resp["hits"]["total"]["value"]   # NEW: extract before building result list
results = [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]
return jsonify({
    "results": [_result_to_api_dict(r) for r in results],   # took_ms removed from per-result
    "total": total,
    "took_ms": took_ms,
    "page": page,
})
```

Note: `_result_to_api_dict` must lose the `took_ms` argument since `took_ms` moves to the wrapper level.

### Pattern 3: API Response Shape Change

**What:** The current flat array response must become a wrapper object to expose `total`. This is a controlled breaking change — the single frontend consumer is updated in the same phase.

**Old shape:**
```python
# Current (before Phase 12)
return jsonify([_result_to_api_dict(r, took_ms) for r in results])
# Frontend: results = await resp.json()   → array
# Frontend: results[0].took_ms           → took_ms per item
# Frontend: results.length               → WRONG for total count
```

**New shape:**
```python
# Phase 12
return jsonify({
    "results": [_result_to_api_dict(r) for r in results],
    "total": total,
    "took_ms": took_ms,
    "page": page,
})
# Frontend: data = await resp.json()     → object
# Frontend: data.results                 → array of items
# Frontend: data.total                   → 248 (across all pages) [PAGE-02]
# Frontend: data.took_ms                 → ms at wrapper level
# Frontend: data.page                    → current page (used for pagination controls)
```

**Impact on `_result_to_api_dict`:** Remove `took_ms` parameter and key. The result item shape becomes: `{title, url, source_domain, excerpt, body, body_html, score}` — no `took_ms`.

### Pattern 4: `currentPage` State and Reset Logic

**What:** Add `currentPage = 1` to module-level state. Reset to 1 when the user starts a new search or changes filters/sort. Do NOT reset when page nav buttons are clicked.

**Example:**

```javascript
// Source: app.js existing state pattern [VERIFIED: codebase]

// Module-level additions:
let currentPage = 1;   // NEW

// handleSearchInput — reset page before new search:
debounceTimer = setTimeout(() => {
  currentPage = 1;    // NEW: new query = start from page 1
  runSearch(q);
}, DEBOUNCE_MS);

// onFilterChange — reset page on filter change:
function onFilterChange() {
  currentFilters.manufacturer = filterMfr.value;
  // ... (existing)
  currentPage = 1;    // NEW: filter change = back to page 1
  if (currentQuery) runSearch(currentQuery);
}

// onSortChange — reset page on sort change:
function onSortChange(newSort) {
  currentSort = newSort;
  currentPage = 1;    // NEW: sort change = back to page 1
  sortBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.sort === newSort));
  if (currentQuery) runSearch(currentQuery);
}

// Page nav handlers — DO NOT reset currentPage:
prevBtn.addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage -= 1;
    runSearch(currentQuery);
  }
});
nextBtn.addEventListener("click", () => {
  currentPage += 1;
  runSearch(currentQuery);
});
```

### Pattern 5: runSearch Update (page param + wrapper response)

**What:** Add `page: currentPage` to `URLSearchParams`, switch from `Array.isArray(results)` guard to object check, and pass `data.results` to `renderResults`.

**Example:**

```javascript
// Source: app.js existing runSearch [VERIFIED: codebase]

async function runSearch(q) {
  currentQuery = q;
  if (abortController) abortController.abort();
  abortController = new AbortController();

  const params = new URLSearchParams({ q, ...currentFilters, page: currentPage }); // NEW: page param
  for (const [k, v] of [...params.entries()]) {
    if (!v) params.delete(k);
  }
  if (currentSort && currentSort !== "relevance") {
    params.set("sort", currentSort);
  }

  try {
    const resp = await fetch(`/api/search?${params}`, { signal: abortController.signal });
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data || !Array.isArray(data.results)) return;  // NEW: guard on wrapper shape
    currentResults = data.results;                       // NEW: unwrap results array
    selectedIndex = -1;
    renderResults(data.results);                         // NEW: pass results array
    renderResultCount(data.total, data.took_ms);         // NEW: total + took from wrapper
    renderPagination(data.total, data.page);             // NEW: show/hide prev/next
    transitionTo("results");
  } catch (err) {
    if (err.name !== "AbortError") console.error("Search failed:", err);
  }
}
```

### Pattern 6: renderResultCount Update (PAGE-02)

**What:** The current implementation reads `results[0].took_ms` and `results.length`. After Phase 12, it reads `total` and `tookMs` directly from the function arguments.

```javascript
// Source: app.js existing renderResultCount [VERIFIED: codebase]

// OLD:
function renderResultCount(results) {
  if (results.length === 0) {
    statsLine.textContent = "No results";
  } else {
    const took = results[0].took_ms;                     // was per-item; now removed
    statsLine.textContent = `${results.length} results (${(took / 1000).toFixed(2)}s)`;
    //                         ^^^^^^^^^^^^^^ was page count, not total
  }
}

// NEW (Phase 12):
function renderResultCount(total, tookMs) {
  if (total === 0) {
    statsLine.textContent = "No results";
  } else {
    statsLine.textContent = `${total} results (${(tookMs / 1000).toFixed(2)}s)`;
    //                        ^^^^^ total across all pages [PAGE-02]
  }
}

// The existing call inside renderResults must be REMOVED:
// renderResultCount(results) ← REMOVE THIS
// renderResultCount is now called only from runSearch with (data.total, data.took_ms)
```

### Pattern 7: renderPagination — Previous/Next Visibility

**What:** Show/hide and disable Previous/Next buttons based on current page and total results.

```javascript
// NEW function in app.js
function renderPagination(total, page) {
  const pageSize = 10;  // must match PAGE_SIZE in server.py
  const hasMore = page * pageSize < total;
  const hasPrev = page > 1;

  prevBtn.disabled = !hasPrev;
  nextBtn.disabled = !hasMore;
  // Visibility: always show the pagination row when in results state
  // The .pagination-row is always rendered in HTML; buttons disabled state handles UX
}
```

Note: Rather than hiding buttons, keep them visible but disabled. Hiding creates layout shift; disabled buttons communicate the boundary state clearly.

### Pattern 8: HTML Pagination Controls

**What:** Add a `<div class="pagination-row">` after `#results-list` in the results view. This follows the same structural pattern as `.filter-row` and `.sort-controls`.

```html
<!-- Source: existing index.html results-view structure [VERIFIED: codebase] -->
<!-- Placed AFTER #results-list, INSIDE .results-view -->
<div class="pagination-row" id="pagination-row">
  <button type="button" id="prev-btn" disabled>&#8592; Previous</button>
  <button type="button" id="next-btn">Next &#8594;</button>
</div>
```

The `disabled` initial state on `prev-btn` is correct — page 1 has no previous page. `next-btn` starts enabled because we only render it after results are shown (when there may be more pages).

### Pattern 9: CSS for Pagination Row

**What:** Style the `.pagination-row` to match the existing filter/sort visual language using CSS custom properties. Follow the `.sort-btn` pattern — same token references, no raw hex.

```css
/* Source: existing style.css sort-btn / filter-row pattern [VERIFIED: codebase] */
.pagination-row {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  justify-content: center;
}

.pagination-row button {
  padding: 0.375rem 0.875rem;
  font-size: 0.85rem;
  background-color: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color var(--transition), background-color var(--transition);
}

.pagination-row button:hover:not(:disabled) {
  border-color: var(--text-secondary);
}

.pagination-row button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

### Anti-Patterns to Avoid

- **`results.length` for total count:** After Phase 12, `results.length` is always 0-10 (one page). Using it for the stats line produces "10 results" when there are 248. Always use `data.total`.
- **Not resetting `currentPage` on new query/filter:** If `currentPage = 5` and the user types a new query with fewer results, `from_ = 40` returns zero results. Reset to 1 in `handleSearchInput`, `onFilterChange`, and `onSortChange`.
- **Client-side result slicing:** Never fetch all results and slice `results.slice(0, 10)` client-side. This defeats ES ranking (scoring is computed per-shard over the full result set) and breaks for large indexes.
- **`search_after` pagination for this phase:** ES `search_after` (cursor-based) is for deep pagination (>10k results) or stateless REST APIs. For a local 2GB index with a few thousand documents, `from`/`size` is correct and simpler.
- **Showing `page` in the stats line:** The success criterion says `"248 results (0.08s)"` — it does NOT include a page number or "Page 2 of 25". Keep the stats line exactly as specified.
- **`Array.isArray(results)` guard after shape change:** The existing guard `if (!Array.isArray(results)) return;` will silently drop all results after the response becomes a wrapper object. Must update to `if (!data || !Array.isArray(data.results)) return;`.
- **Forgetting to remove `renderResultCount(results)` from inside `renderResults`:** If this call remains, it will call `renderResultCount` with the results array (old signature), causing a runtime error or wrong display.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Offset calculation | Custom SQL-style windowing | ES `from`/`size` | Already in `build_search_body` — zero extra code in query layer |
| Total count | Client-side count accumulation across pages | `resp["hits"]["total"]["value"]` | ES computes this in a single query at essentially no extra cost |
| Deep pagination state | Session/cookie-based result caching | Simple `currentPage` integer in module state | The index is small and fast; re-querying ES for each page is instant (< 50ms) |
| Cursor-based pagination | `search_after` with point-in-time | `from`/`size` | `search_after` is for infinite scroll or export tools on large distributed indexes — overkill for a local 2GB node |

**Key insight:** Every component of this feature already exists in the codebase at the ES level. Phase 12 is almost entirely about surfacing existing ES capabilities (`from`, `size`, `total`) through the API and wiring them to new UI elements.

---

## Common Pitfalls

### Pitfall 1: Not Updating the Guard in `runSearch`

**What goes wrong:** The existing guard `if (!Array.isArray(results)) return;` silently returns when the response is the new wrapper object (an object is not an Array). No results are ever rendered after Phase 12.

**Why it happens:** The guard was written for the flat array response and is not noticed during the response shape change.

**How to avoid:** Update the guard to `if (!data || !Array.isArray(data.results)) return;` and change `currentResults = results` to `currentResults = data.results`.

**Warning signs:** No results ever appear in the UI after Phase 12; no console error.

---

### Pitfall 2: `renderResultCount` Called with Wrong Arguments

**What goes wrong:** If the `renderResultCount(results)` call inside `renderResults` is not removed, `renderResultCount` receives a results array (not `total, tookMs`), causing `NaN results (NaN)` or a runtime error.

**Why it happens:** `renderResultCount` is called in two places: inside `renderResults` (old pattern) and from `runSearch` (new pattern). The old call must be removed.

**How to avoid:** Remove `renderResultCount(results)` from inside `renderResults`. Call `renderResultCount(data.total, data.took_ms)` from `runSearch` only.

**Warning signs:** Stats line shows "NaN results (NaN)" or "0 results" even when there are hits.

---

### Pitfall 3: `currentPage` Not Reset on New Query

**What goes wrong:** User searches "Ferrari" (lands on page 1), navigates to page 5, then types "BMW". `runSearch` fires with `page=5`. `from_ = 40`. If BMW has fewer than 41 articles, zero results appear.

**Why it happens:** `currentPage` persists across queries if not explicitly reset.

**How to avoid:** Set `currentPage = 1` in `handleSearchInput` (before calling `runSearch`) and in `onFilterChange` and `onSortChange`.

**Warning signs:** Searching for a broad term after navigating to a high page returns zero results.

---

### Pitfall 4: Previous Button Clickable on Page 1

**What goes wrong:** On page 1, clicking Previous decrements `currentPage` to 0. `from_ = (0 - 1) * 10 = -10`, which is clamped to 0 by `build_search_body`. ES returns page 1 results, but the UI shows `currentPage = 0`, causing the stats or pagination to show incorrect state.

**Why it happens:** `prevBtn.click` handler does not check `currentPage > 1` before decrementing.

**How to avoid:** Guard the decrement: `if (currentPage > 1) { currentPage -= 1; runSearch(currentQuery); }`. Also set `prevBtn.disabled = (page === 1)` in `renderPagination`.

**Warning signs:** Previous button responds on page 1; re-renders the same results but page counter appears as 0.

---

### Pitfall 5: Existing Tests Break on Response Shape Change

**What goes wrong:** `test_search_returns_result_array` does `data = resp.get_json(); assert isinstance(data, list)` and `data[0]`. After the shape change, `data` is a dict, so `isinstance(data, list)` is False and `data[0]` raises a TypeError.

**Why it happens:** The four tests in `test_api_search.py` that inspect the response body were written for the flat array. They must be updated.

**How to avoid:** In Wave 0 (failing test scaffold), update these 4 tests to use `data["results"][0]` and `data["total"]`, `data["took_ms"]`, `data["page"]`. This also captures the new behavior (total count) in the test suite.

**Tests requiring update (4 tests):**
1. `test_search_returns_result_array` — change `isinstance(data, list)` to `isinstance(data["results"], list)`
2. `test_search_result_shape` — change `data[0]` to `data["results"][0]`; remove `took_ms` from item keys; add `data["took_ms"]` assertion
3. `test_excerpt_uses_highlight` — change `resp.get_json()[0]` to `resp.get_json()["results"][0]`
4. `test_excerpt_fallback` — same change as above

**Note:** `test_search_empty_q_returns_empty` checks `resp.get_json() == []` — this remains valid because the early-return for blank `q` still returns `[]` (the API only uses the wrapper for actual searches).

**Warning signs:** Import or assertion errors in the first 4 tests of `test_api_search.py`.

---

### Pitfall 6: Next Button Enables Infinite Pagination

**What goes wrong:** Next button remains enabled even on the last page (where `page * PAGE_SIZE >= total`). Clicking it fires `runSearch` with `from_ = total` (or beyond), returning zero results while `currentPage` increments indefinitely.

**Why it happens:** `renderPagination` does not disable `nextBtn` when there are no more pages.

**How to avoid:** `nextBtn.disabled = (page * PAGE_SIZE >= total)` in `renderPagination`.

**Warning signs:** Clicking Next on the last page renders an empty `#results-list` with the stats line still showing the total.

---

## Code Examples

Verified patterns from codebase and official documentation:

### Complete `api_search` after Phase 12 (backend)

```python
# Source: nitrofind/server.py — Phase 12 extension [VERIFIED: codebase — base pattern]

PAGE_SIZE: int = 10  # new module-level constant

@app.route("/api/search")
def api_search():
    if not state["ready"]:
        return {"status": "starting"}, 503

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])   # blank q guard unchanged

    filters = build_filter_clauses(
        manufacturer=request.args.get("manufacturer") or None,
        era_bucket=request.args.get("era_bucket") or None,
        body_style=request.args.get("body_style") or None,
        year_from=_safe_int_param(request.args.get("year_from")),
        year_to=_safe_int_param(request.args.get("year_to")),
        country=request.args.get("country") or None,
    )
    sort = request.args.get("sort") or None
    if sort not in _VALID_SORTS:
        sort = None

    # PAGE-01: read page param, compute from_ offset
    page = max(1, _safe_int_param(request.args.get("page")) or 1)
    from_value = (page - 1) * PAGE_SIZE

    body = build_search_body(
        q, filters=filters, sort=sort,
        size=PAGE_SIZE, from_=from_value,   # PAGE-01
    )

    try:
        resp = state["es_client"].search(
            index="car_articles",
            query=body["query"],
            sort=body.get("sort"),
            highlight=body.get("highlight"),
            source=body.get("_source"),
            size=body.get("size", PAGE_SIZE),
            from_=body.get("from", 0),
        )
    except Exception as exc:
        logger.warning("Search error: %s: %s", type(exc).__name__, exc)
        return {"error": "search_failed"}, 500

    took_ms = resp.get("took", 0)
    total = resp["hits"]["total"]["value"]   # PAGE-02: total across all pages
    results = [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]
    return jsonify({
        "results": [_result_to_api_dict(r) for r in results],  # took_ms removed from items
        "total": total,    # PAGE-02
        "took_ms": took_ms,
        "page": page,
    })
```

### `_result_to_api_dict` after Phase 12 (remove `took_ms` param)

```python
# Source: nitrofind/server.py [VERIFIED: codebase]
def _result_to_api_dict(result: ArticleResult) -> dict:
    # took_ms argument removed — moved to wrapper response
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return {
        "title": result.title,
        "url": result.url,
        "source_domain": result.source_domain,
        "excerpt": excerpt,
        "body": result.body,
        "body_html": result.body_html,
        "score": result.score,
        # took_ms intentionally omitted — now at wrapper level
    }
```

### `renderResults` after Phase 12 (remove embedded renderResultCount call)

```javascript
// Source: app.js existing renderResults [VERIFIED: codebase]
function renderResults(results) {
  // renderResultCount call REMOVED — now called from runSearch with data.total/tookMs
  resultsList.innerHTML = "";
  results.forEach((r, i) => {
    // ... existing item creation unchanged ...
  });
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed result count (20 per search) | 10 results per page with Previous/Next | Phase 12 | Users can browse beyond first 10 results |
| `results.length` for stats line | `data.total` (ES hits.total.value) | Phase 12 | Stats line shows true total, not page count |
| Flat JSON array response | Wrapper object `{results, total, took_ms, page}` | Phase 12 | API can expose metadata alongside results |
| `took_ms` per result item | `took_ms` at wrapper level | Phase 12 | Eliminates N redundant copies of the same value |

**Not applicable / not deprecated:**

- `build_search_body` `from_`/`size` params — already exist and work correctly; no change
- ES `from`/`size` pagination approach — correct for this use case; no state change needed

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Resetting `currentPage = 1` on sort change is the right UX (show top results in new sort order from page 1) | Pattern 4 | If user expects sort to preserve current page position, this feels disorienting — low risk for typical use case |
| A2 | The "without re-executing the full query from scratch" success criterion means page navigation reuses `currentQuery` (not starting over from page 1), not that results are cached client-side | Summary / Architecture | If interpreted as client-side caching of all results, a different approach would be needed — but this interpretation is inconsistent with the 10-per-page requirement and ES's purpose |
| A3 | Keeping pagination buttons always visible (just disabled on boundaries) is preferable to hiding them | Pattern 7 | If designer wants no layout shift AND no disabled button, hiding would be needed — disabled is the simpler approach |

---

## Open Questions

1. **Keyboard navigation with pagination:** The existing ArrowDown/ArrowUp nav operates on `currentResults` indices 0-9. After Phase 12, this continues to work correctly — `currentResults` holds only the current page's items. No change needed. Not a gap, just a confirmation.

2. **Escape key resets page state:** `currentQuery = ""` and `currentResults = []` are set by the Escape handler. `currentPage` is not reset. This is fine — `currentPage` will be reset the next time `handleSearchInput` fires a new search. Not a gap.

---

## Environment Availability

Step 2.6: SKIPPED — this phase introduces no new external tools, CLIs, runtimes, or services. All changes are to existing Python files and static web assets.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (configured via `pytest.ini`) |
| Config file | `/mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind/pytest.ini` |
| Quick run command | `pytest tests/test_search/ -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PAGE-01 | No `page` param → ES receives `from_=0, size=10` | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_default"` | ❌ Wave 0 |
| PAGE-01 | `page=2` → ES receives `from_=10, size=10` | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_page_2"` | ❌ Wave 0 |
| PAGE-01 | `page=0` clamped to 1 → `from_=0` | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_page_zero"` | ❌ Wave 0 |
| PAGE-01 | Non-integer `page` ("abc") defaults to 1 → `from_=0` | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_invalid_page"` | ❌ Wave 0 |
| PAGE-02 | Response includes `total` key with `hits.total.value` | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_total"` | ❌ Wave 0 |
| PAGE-02 | Response includes `took_ms` at wrapper level (not per-item) | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_wrapper"` | ❌ Wave 0 |
| PAGE-01/02 | Previous/Next buttons visible in results view | manual-only | N/A | N/A |
| PAGE-01/02 | Previous disabled on page 1; Next disabled on last page | manual-only | N/A | Cannot automate DOM interaction without Selenium/Playwright — out of scope |
| PAGE-02 | Stats line shows "248 results (0.08s)" not "10 results" | manual-only | N/A | Requires live ES with indexed data |

**Existing tests requiring update (Wave 0 — update before implementing):**

| Test | Current Assertion | New Assertion |
|------|-------------------|---------------|
| `test_search_returns_result_array` | `isinstance(data, list)` | `isinstance(data["results"], list)` |
| `test_search_result_shape` | `data[0]` keys include `took_ms` | `data["results"][0]` keys exclude `took_ms`; add `data["took_ms"]` check; add `data["total"]` check |
| `test_excerpt_uses_highlight` | `resp.get_json()[0]["excerpt"]` | `resp.get_json()["results"][0]["excerpt"]` |
| `test_excerpt_fallback` | `resp.get_json()[0]["excerpt"]` | `resp.get_json()["results"][0]["excerpt"]` |

### Sampling Rate

- **Per task commit:** `pytest tests/test_search/ -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_search/test_api_search.py` — update 4 existing tests for new response shape (RED first, implement later)
- [ ] `tests/test_search/test_api_search.py` — add 6 new pagination tests (RED first, implement later)

*(No new test files needed — all tests go into the existing `test_api_search.py` file following established patterns.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `_safe_int_param` already used for year params; same function reused for `page` param coercion |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Injection via `page` param | Tampering | `_safe_int_param` coercion — non-integer values become `None`; then `max(1, None or 1) = 1`; ES never sees raw user string in `from_` |
| Unbounded page values (e.g. `page=999999`) | DoS | `from_ = (999999 - 1) * 10 = 9999980`; ES `max_result_window` default is 10,000; a request with `from_ > 10000` will return a 400 from ES. The route catches `Exception` and returns 500. No data leakage; no crash. Consider clamping `page` to `ceil(MAX_RESULT_SIZE / PAGE_SIZE) = 10` to prevent the 400 reaching ES. [ASSUMED — clamping page to 10 is a reasonable defense-in-depth measure] |
| Response shape change exposes internal ES structure | Information Disclosure | `resp["hits"]["total"]["value"]` is a count — not document content; no sensitive data exposed |

---

## Sources

### Primary (HIGH confidence)

- `nitrofind/search/query_builder.py` — `build_search_body` `from_`/`size` params, clamping behavior, `MAX_RESULT_SIZE` constant [VERIFIED: codebase]
- `nitrofind/server.py` — `api_search` route, `_safe_int_param`, current response shape, `resp["hits"]["total"]["value"]` path (all mock responses in tests already use this path) [VERIFIED: codebase]
- `static/js/app.js` — `currentFilters` state pattern, `runSearch` flow, `renderResultCount`, `renderResults`, `onFilterChange`, `onSortChange`, `handleSearchInput`, `transitionTo` [VERIFIED: codebase]
- `templates/index.html` — `.results-view` structure, `.filter-row`, `.sort-controls`, `#results-list` position [VERIFIED: codebase]
- `static/css/style.css` — `.sort-btn`, `.filter-row`, CSS custom-property token system [VERIFIED: codebase]
- `tests/test_search/test_api_search.py` — all 15 existing tests inspected; 4 that check response body shape identified; mock response structure `{"hits": {"total": {"value": N}, "hits": [...]}}` confirmed [VERIFIED: codebase]
- `tests/test_search/test_query_builder.py` — `test_build_search_body_from_param` and `test_build_search_body_default_size` confirmed to cover `from_`/`size` paths [VERIFIED: codebase]
- Elasticsearch 8.x `from`/`size` pagination: `from_` param in `es_client.search` already in use in the codebase [VERIFIED: codebase]

### Secondary (MEDIUM confidence)

- ES `hits.total.value` exact count behavior in ES 8: `track_total_hits` defaults to 10,000; all mock responses in the test suite already reference `{"total": {"value": N}}` confirming the ES 8 object format [VERIFIED: codebase indirectly; ES docs cited in CLAUDE.md]
- ES `max_result_window` default of 10,000: standard ES 8 behavior; not a concern for a 2GB local index [ASSUMED — not explicitly verified against ES 8.18 release notes in this session]

### Tertiary (LOW confidence)

- None.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new packages; all changes are additive modifications to verified existing code
- Architecture (ES from/size): HIGH — already implemented in `build_search_body` and `api_search`; confirmed via direct codebase inspection
- API response shape change: HIGH — the change is straightforward; impact on tests fully catalogued by reading all 15 existing tests
- Frontend pagination patterns: HIGH — `currentPage` state and reset logic follows directly from existing `currentFilters` and `currentSort` patterns in `app.js`
- Pitfalls: HIGH — all pitfalls derived from direct codebase inspection, not training data assumptions

**Research date:** 2026-07-04
**Valid until:** 2026-08-04 (stable stack — ES 8.x `from`/`size` API unchanged across minor versions)
