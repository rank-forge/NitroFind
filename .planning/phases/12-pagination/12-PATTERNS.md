# Phase 12: Pagination - Pattern Map

**Mapped:** 2026-07-04
**Files analyzed:** 5
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `nitrofind/server.py` | route/service | request-response | `nitrofind/server.py` itself (in-place modification) | exact |
| `static/js/app.js` | controller (SPA) | event-driven + request-response | `static/js/app.js` itself (in-place modification) | exact |
| `templates/index.html` | template | — | `templates/index.html` itself (add element after `#results-list`) | exact |
| `static/css/style.css` | stylesheet | — | `static/css/style.css` `.sort-btn` block (lines 222–240) | role-match |
| `tests/test_search/test_api_search.py` | test | request-response | `tests/test_search/test_api_search.py` existing fixture pattern | exact |

---

## Pattern Assignments

### `nitrofind/server.py` (route, request-response)

**Analog:** itself — in-place reshape

**Existing module constants pattern** (lines 50–51):
```python
# Existing allowlist constant — PAGE_SIZE follows the same module-level pattern
_VALID_SORTS: frozenset[str] = frozenset({"relevance", "date", "size"})
# ADD after this line:
PAGE_SIZE: int = 10
```

**`_safe_int_param` — reuse for `page` param** (lines 127–144):
```python
def _safe_int_param(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
# This already exists — call it for page: _safe_int_param(request.args.get("page"))
```

**Existing `api_search` route structure to reshape** (lines 147–201):
```python
@app.route("/api/search")
def api_search():
    if not state["ready"]:
        return {"status": "starting"}, 503

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])   # blank q guard — keep unchanged

    filters = build_filter_clauses(...)   # keep unchanged
    sort = request.args.get("sort") or None
    if sort not in _VALID_SORTS:
        sort = None

    # ADD: page param reading — same _safe_int_param pattern as year_from/year_to
    page = max(1, _safe_int_param(request.args.get("page")) or 1)
    from_value = (page - 1) * PAGE_SIZE

    # CHANGE: pass size=PAGE_SIZE, from_=from_value instead of relying on defaults
    body = build_search_body(q, filters=filters, sort=sort, size=PAGE_SIZE, from_=from_value)

    try:
        resp = state["es_client"].search(
            index="car_articles",
            query=body["query"],
            sort=body.get("sort"),
            highlight=body.get("highlight"),
            source=body.get("_source"),
            size=body.get("size", PAGE_SIZE),   # CHANGE: PAGE_SIZE default
            from_=body.get("from", 0),
        )
    except Exception as exc:
        logger.warning("Search error: %s: %s", type(exc).__name__, exc)
        return {"error": "search_failed"}, 500

    # CHANGE: extract total and reshape response
    took_ms = resp.get("took", 0)
    total = resp["hits"]["total"]["value"]
    results = [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]
    return jsonify({
        "results": [_result_to_api_dict(r) for r in results],
        "total": total,
        "took_ms": took_ms,
        "page": page,
    })
```

**`_result_to_api_dict` — remove `took_ms` param** (lines 98–124, current):
```python
# CURRENT signature (to be changed):
def _result_to_api_dict(result: ArticleResult, took_ms: int) -> dict:
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return {
        "title": result.title,
        "url": result.url,
        "source_domain": result.source_domain,
        "excerpt": excerpt,
        "body": result.body,
        "body_html": result.body_html,
        "score": result.score,
        "took_ms": took_ms,   # REMOVE this key + param
    }

# NEW signature:
def _result_to_api_dict(result: ArticleResult) -> dict:
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

---

### `static/js/app.js` (SPA controller, event-driven)

**Analog:** itself — in-place extension

**Module-level state pattern** (lines 25–41) — add `currentPage` following `currentSort`:
```javascript
// Existing pattern (lines 25–38):
let uiState = "home";
let selectedIndex = -1;
let currentQuery = "";
let currentFilters = { ... };
let currentSort = "relevance";
let currentResults = [];
let debounceTimer = null;
let abortController = null;

// ADD after currentSort (same pattern):
let currentPage = 1;
```

**Cached DOM references pattern** (lines 47–62) — add pagination button refs following same pattern:
```javascript
// Existing pattern (add two lines after existing refs):
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
```

**`handleSearchInput` — reset `currentPage`** (lines 77–85, existing):
```javascript
// Existing debounce pattern — insert currentPage = 1 before runSearch:
function handleSearchInput(input) {
  clearTimeout(debounceTimer);
  const q = input.value.trim();
  if (!q) {
    transitionTo("home");
    return;
  }
  debounceTimer = setTimeout(() => {
    currentPage = 1;    // ADD: new query resets page
    runSearch(q);
  }, DEBOUNCE_MS);
}
```

**`onFilterChange` — reset `currentPage`** (lines 202–210, existing):
```javascript
// Existing pattern — insert currentPage = 1 before runSearch:
function onFilterChange() {
  currentFilters.manufacturer = filterMfr.value;
  currentFilters.era_bucket   = filterEra.value;
  currentFilters.body_style   = filterBody.value;
  currentFilters.year_from    = filterYearFrom.value;
  currentFilters.year_to      = filterYearTo.value;
  currentFilters.country      = filterCountry.value;
  currentPage = 1;    // ADD
  if (currentQuery) runSearch(currentQuery);
}
```

**`onSortChange` — reset `currentPage`** (lines 219–223, existing):
```javascript
// Existing pattern — insert currentPage = 1 before runSearch:
function onSortChange(newSort) {
  currentSort = newSort;
  currentPage = 1;    // ADD
  sortBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.sort === newSort));
  if (currentQuery) runSearch(currentQuery);
}
```

**`runSearch` — add page param, update response unwrapping** (lines 94–125, existing):
```javascript
// CURRENT lines 101–121 (to be changed):
const params = new URLSearchParams({ q, ...currentFilters });
// ...strip empties...
const results = await resp.json();
if (!Array.isArray(results)) return;
currentResults = results;
selectedIndex = -1;
renderResults(results);
transitionTo("results");

// NEW (same structural pattern, different values):
const params = new URLSearchParams({ q, ...currentFilters, page: currentPage }); // ADD page
// ...strip empties (unchanged)...
const data = await resp.json();
if (!data || !Array.isArray(data.results)) return;  // CHANGE guard
currentResults = data.results;                       // CHANGE unwrap
selectedIndex = -1;
renderResults(data.results);                         // CHANGE unwrap
renderResultCount(data.total, data.took_ms);         // CHANGE: new signature + move OUT of renderResults
renderPagination(data.total, data.page);             // ADD
transitionTo("results");
```

**`renderResultCount` — new signature** (lines 131–138, existing):
```javascript
// CURRENT (to be replaced):
function renderResultCount(results) {
  if (results.length === 0) {
    statsLine.textContent = "No results";
  } else {
    const took = results[0].took_ms;
    statsLine.textContent = `${results.length} results (${(took / 1000).toFixed(2)}s)`;
  }
}

// NEW (same statsLine.textContent pattern, new params):
function renderResultCount(total, tookMs) {
  if (total === 0) {
    statsLine.textContent = "No results";
  } else {
    statsLine.textContent = `${total} results (${(tookMs / 1000).toFixed(2)}s)`;
  }
}
```

**`renderResults` — remove embedded `renderResultCount` call** (lines 140–170, existing):
```javascript
function renderResults(results) {
  // REMOVE: renderResultCount(results)   ← this line must go; now called from runSearch
  resultsList.innerHTML = "";
  results.forEach((r, i) => {
    // ... all existing item creation unchanged ...
  });
}
```

**`renderPagination` — new function** (add after `renderResults`, following same function declaration style):
```javascript
// NEW function — follows same declaration pattern as renderResults/renderResultCount
function renderPagination(total, page) {
  const pageSize = 10;  // must match PAGE_SIZE in server.py
  prevBtn.disabled = page <= 1;
  nextBtn.disabled = page * pageSize >= total;
}
```

**Pagination button event listeners** (add after `backBtn` event listener at line 193–196, following same `.addEventListener("click", ...)` pattern):
```javascript
// Existing pattern for reference (lines 193–196):
backBtn.addEventListener("click", () => {
  transitionTo("results");
});

// ADD (same pattern):
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

---

### `templates/index.html` (template, add element)

**Analog:** itself — add `.pagination-row` after `#results-list`

**Insertion point** — after `<div id="results-list"></div>` (line 63), inside `.results-view`, before closing `</div>`:
```html
<!-- Existing structure (lines 21–63): -->
<div class="results-view">
  <header class="top-bar">...</header>
  <div class="filter-row">...</div>
  <p id="stats-line"></p>
  <div id="results-list"></div>
  <!-- ADD HERE — follows .filter-row structural pattern, placed after results list -->
  <div class="pagination-row" id="pagination-row">
    <button type="button" id="prev-btn" disabled>&#8592; Previous</button>
    <button type="button" id="next-btn">Next &#8594;</button>
  </div>
</div>
```

**Structural pattern analog** — `.sort-controls` inside `.filter-row` (lines 55–59):
```html
<div class="sort-controls">
  <button type="button" class="sort-btn active" data-sort="relevance">Relevance</button>
  <button type="button" class="sort-btn" data-sort="date">Newest</button>
  <button type="button" class="sort-btn" data-sort="size">Largest</button>
</div>
```
Pagination buttons follow the same `type="button"` convention and class-based styling.

---

### `static/css/style.css` (stylesheet, add rules)

**Analog:** `.sort-btn` block (lines 222–240) — exact token reference pattern to copy

**`.sort-btn` analog to copy** (lines 222–240):
```css
.sort-btn {
  padding: 0.375rem 0.625rem;
  font-size: 0.85rem;
  background-color: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color var(--transition), background-color var(--transition);
}

.sort-btn:hover {
  border-color: var(--text-secondary);
}
```

**New rules to add** (append after `#results-list` block, same token-only pattern — no raw hex):
```css
/* Pagination row */
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

**Token constraint:** All token references (`var(--bg-input)`, `var(--border)`, `var(--radius)`, `var(--transition)`, `var(--text-primary)`, `var(--text-secondary)`) are defined in `:root` at lines 11–29. No raw hex values appear outside that block — this rule applies to pagination CSS too.

---

### `tests/test_search/test_api_search.py` (test, request-response)

**Analog:** itself — update 4 tests, add 6 new tests

**Fixture pattern to reuse** (lines 25–58, `client_with_search`):
```python
@pytest.fixture
def client_with_search(monkeypatch):
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "took": 12,
        "hits": {
            "total": {"value": 1},   # ← already in this shape — confirms path
            "hits": [{ "_score": 2.5, "_source": {...}, "highlight": {...} }],
        },
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    return server.app.test_client()
```

**Inline monkeypatch pattern for pagination tests** (lines 153–168, `test_manufacturer_filter_forwarded`):
```python
# Inline fixture pattern — reuse for pagination tests that inspect call kwargs:
def test_pagination_page_2(monkeypatch):
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "took": 3,
        "hits": {"total": {"value": 25}, "hits": []},
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=ferrari&page=2")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    assert call_kwargs["from_"] == 10   # (2-1) * 10
    assert call_kwargs["size"] == 10
```

**4 existing tests to update** (current lines → new assertions):

| Test | Line | Current assertion | New assertion |
|---|---|---|---|
| `test_search_returns_result_array` | 108 | `isinstance(data, list)` | `isinstance(data["results"], list)` |
| `test_search_returns_result_array` | 109 | `len(data) == 1` | `len(data["results"]) == 1` |
| `test_search_result_shape` | 117 | `item = data[0]` | `item = data["results"][0]` |
| `test_search_result_shape` | 118–122 | keys include `"took_ms"` | keys exclude `"took_ms"`; add `data["took_ms"] == 12`; add `data["total"] == 1`; add `data["page"] == 1` |
| `test_excerpt_uses_highlight` | 134 | `resp.get_json()[0]` | `resp.get_json()["results"][0]` |
| `test_excerpt_fallback` | 143 | `resp.get_json()[0]` | `resp.get_json()["results"][0]` |

**6 new pagination tests to add** (k-labels for pytest `-k` selection):
```
test_pagination_default      — no page param → from_=0, size=10
test_pagination_page_2       — page=2 → from_=10, size=10
test_pagination_page_zero    — page=0 clamped → from_=0
test_pagination_invalid_page — page=abc defaults → from_=0
test_pagination_total        — response includes total key = hits.total.value
test_pagination_wrapper      — took_ms at wrapper level, not per-item
```

**`mock_es.search.call_args.kwargs` inspection pattern** (lines 170–182, existing):
```python
mock_es.search.assert_called_once()
call_kwargs = mock_es.search.call_args.kwargs
# Then assert on call_kwargs["from_"], call_kwargs["size"]
# For wrapper response assertions:
data = resp.get_json()
assert "total" in data
assert "took_ms" in data
assert "page" in data
assert "results" in data
assert isinstance(data["results"], list)
```

---

## Shared Patterns

### `_safe_int_param` — input coercion
**Source:** `nitrofind/server.py` lines 127–144
**Apply to:** `page` param in `api_search` (same pattern already used for `year_from`, `year_to`)
```python
page = max(1, _safe_int_param(request.args.get("page")) or 1)
```
Non-integer values become `None`; `max(1, None or 1)` = 1. ES never sees a raw user string.

### CSS token-only rule
**Source:** `static/css/style.css` lines 1–29 (`:root` block + commentary)
**Apply to:** All new CSS in this phase
No raw hex values outside `:root`. All new `.pagination-row` rules must reference `var(--token)` exclusively.

### `monkeypatch.setitem` fixture pattern
**Source:** `tests/test_search/test_api_search.py` lines 56–58
**Apply to:** All 6 new pagination tests
```python
monkeypatch.setitem(server.state, "ready", True)
monkeypatch.setitem(server.state, "es_client", mock_es)
```

### AbortController + empty-filter strip in `runSearch`
**Source:** `static/js/app.js` lines 97–109
**Apply to:** `runSearch` modification — the abort/strip logic is unchanged; only params construction and response unwrapping change. Do not disturb lines 97–109.

---

## No Analog Found

None. All 5 files have direct analogs in the codebase.

---

## Metadata

**Analog search scope:** `nitrofind/`, `static/`, `templates/`, `tests/`
**Files scanned:** 5 (all files are self-analogs — in-place modifications)
**Pattern extraction date:** 2026-07-04
