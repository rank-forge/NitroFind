# Phase 10: Search Quality & Sort - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 4 modified files (no new files)
**Analogs found:** 4 / 4 (all files are self-analogs — modifications to existing files)

---

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `nitrofind/search/query_builder.py` | service / query builder | request-response | Self — existing `build_function_score_query` / `build_search_body` | exact |
| `nitrofind/server.py` | controller / API route | request-response | Self — existing `api_search` route, `build_filter_clauses` pattern | exact |
| `static/js/app.js` | UI controller | event-driven | Self — existing `onFilterChange` / `runSearch` / module-level state pattern | exact |
| `templates/index.html` | UI template | — | Self — existing `.filter-row` `<select>` elements | exact |
| `tests/test_search/test_query_builder.py` | test | — | Self — existing `test_base_query_is_multi_match`, `test_build_search_body_*` pattern | exact |
| `tests/test_search/test_api_search.py` | test | — | Self — existing `test_manufacturer_filter_forwarded` + `monkeypatch` fixture pattern | exact |

---

## Pattern Assignments

### `nitrofind/search/query_builder.py` (service, request-response)

**Analog:** Self — read the file in full above.

**Imports / module header** (lines 1-27):
```python
"""
nitrofind.search.query_builder — Elasticsearch function_score query construction.
...
"""
import logging
logger = logging.getLogger(__name__)
```
New helpers (`is_phrase_query`, `extract_phrase`, `_build_sort_clauses`) follow the same module pattern — free functions, no class, `logger = logging.getLogger(__name__)` at module level.

**Existing base query to modify** (lines 75-82):
```python
# Current — to be replaced with phrase-branching version
base_query = {
    "multi_match": {
        "query": query_text,
        "fields": ["title^3", "body"],
        "type": "best_fields",
    }
}
```
Replace with the branching block below (phrase path first, fuzzy path as else).

**Core pattern to insert — phrase detection + fuzzy routing** (new code, replaces lines 75-82):
```python
# Phrase detection: startswith+endswith " and len > 2 (Pitfall 3 guard)
_is_phrase = (
    query_text.startswith('"')
    and query_text.endswith('"')
    and len(query_text) > 2
)

if _is_phrase:
    # Phrase path: strip quotes; NO fuzziness (ES 400 if present on type:phrase)
    _phrase_text = query_text[1:-1].strip()
    base_query = {
        "multi_match": {
            "query": _phrase_text,
            "fields": ["title^3", "body"],
            "type": "phrase",
        }
    }
else:
    # Default path: fuzzy best_fields
    base_query = {
        "multi_match": {
            "query": query_text,
            "fields": ["title^3", "body"],
            "type": "best_fields",
            "fuzziness": "AUTO",
            "prefix_length": 1,
        }
    }
```

**Sort helper — new free function** (add after `build_filter_clauses`, before `build_search_body`):
```python
def _build_sort_clauses(sort: str | None) -> list[dict] | None:
    """Return ES sort array for the given sort mode, or None for relevance.

    None → caller omits sort kwarg entirely → ES default _score desc.
    "date" → newest-first by published_at (missing values sink to bottom — correct UX).
    "size" → largest-first by word_count (integer field, already indexed).
    """
    if sort == "date":
        return [{"published_at": {"order": "desc"}}]
    if sort == "size":
        return [{"word_count": {"order": "desc"}}]
    return None  # "relevance" or unknown → ES default
```

**`build_search_body` signature extension** — add `sort: str | None = None` parameter (mirrors existing pattern at lines 169-177 where all params have defaults):
```python
def build_search_body(
    query_text: str,
    filters: list[dict] | None = None,
    size: int = 20,
    from_: int = 0,
    sort: str | None = None,          # NEW — "relevance" | "date" | "size" | None
    recency_weight: float = DEFAULT_RECENCY_WEIGHT,
    ...
) -> dict:
```

**`build_search_body` return dict extension** — conditionally add `"sort"` key (mirrors the existing conditional `if filters:` pattern at lines 210-219):
```python
result = {
    "query": fs_query,
    "highlight": {...},
    "size": max(0, min(size, MAX_RESULT_SIZE)),
    "from": max(0, from_),
    "_source": [...],
}
sort_clauses = _build_sort_clauses(sort)
if sort_clauses is not None:
    result["sort"] = sort_clauses
return result
```

---

### `nitrofind/server.py` (controller, request-response)

**Analog:** Self — existing `api_search` route.

**Existing filter param extraction pattern** (lines 148-152) — copy exactly for sort:
```python
filters = build_filter_clauses(
    manufacturer=request.args.get("manufacturer") or None,
    era_bucket=request.args.get("era_bucket") or None,
    body_style=request.args.get("body_style") or None,
)
```

**Sort param extraction — new lines to add after filters block**:
```python
# SORT-02: read sort param with allowlist (T-sort-inject mitigation)
_VALID_SORTS = {"relevance", "date", "size"}
sort = request.args.get("sort") or None
if sort not in _VALID_SORTS:
    sort = None  # unknown value → treat as relevance (silently ignored)
```
Note: `_VALID_SORTS` can be a module-level constant (following `MAX_RESULT_SIZE` pattern at line 37) or defined inline in `api_search`. Module-level is preferred to match existing style.

**`build_search_body` call extension** (line 153 currently):
```python
# Current:
body = build_search_body(q, filters=filters)

# New:
body = build_search_body(q, filters=filters, sort=sort)
```

**`client.search()` call extension** (lines 156-163) — add `sort=body.get("sort")` kwarg:
```python
resp = state["es_client"].search(
    index="car_articles",
    query=body["query"],
    sort=body.get("sort"),           # NEW — None → ES default; list → field sort
    highlight=body.get("highlight"),
    source=body.get("_source"),
    size=body.get("size", 20),
    from_=body.get("from", 0),
)
```
`sort=None` is safe per elasticsearch-py 8.x convention (None omits the parameter). Follow the flat keyword API pattern already established — never use `body=`.

---

### `static/js/app.js` (UI controller, event-driven)

**Analog:** Self — existing module-level state block and `onFilterChange` pattern.

**Module-level state extension** (lines 25-32) — add `currentSort` alongside existing state vars:
```javascript
// Existing:
let currentFilters = { manufacturer: "", era_bucket: "", body_style: "" };

// Add after (same pattern as other module-level state):
let currentSort = "relevance";  // "relevance" | "date" | "size"
```

**`runSearch` URLSearchParams extension** (lines 89-93) — mirrors the existing empty-filter-strip pattern:
```javascript
// Existing params construction:
const params = new URLSearchParams({ q, ...currentFilters });
for (const [k, v] of [...params.entries()]) {
  if (!v) params.delete(k);
}

// Add after the strip loop:
if (currentSort && currentSort !== "relevance") {
  params.set("sort", currentSort);
}
```
`"relevance"` is omitted from params (ES default) — same as how empty filter values are stripped.

**Sort button handler — new function** (add in the Filter handlers section after `onFilterChange`, following same structure):
```javascript
function onSortChange(newSort) {
  currentSort = newSort;
  // Toggle .active class on all sort buttons — mirrors updateSelection() classList.toggle pattern
  document.querySelectorAll(".sort-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.sort === newSort);
  });
  if (currentQuery) runSearch(currentQuery);
}
```
`classList.toggle(class, condition)` is the existing pattern from `updateSelection()` at lines 202-205.

**DOM reference addition** — add sort button refs in the cached DOM block (lines 39-50), following the `filterMfr` / `filterEra` / `filterBody` pattern:
```javascript
const sortBtns = document.querySelectorAll(".sort-btn");
```
Then wire up in the event listener block:
```javascript
sortBtns.forEach(btn => {
  btn.addEventListener("click", () => onSortChange(btn.dataset.sort));
});
```

---

### `templates/index.html` (UI template)

**Analog:** Self — existing `.filter-row` block (lines 26-50).

**Filter row pattern to follow** (lines 26-50):
```html
<div class="filter-row">
  <select id="filter-manufacturer">...</select>
  <select id="filter-era">...</select>
  <select id="filter-body">...</select>
</div>
```

**Sort buttons to add inside `.filter-row`** — after the three `<select>` elements:
```html
<div class="sort-controls">
  <button type="button" class="sort-btn active" data-sort="relevance">Relevance</button>
  <button type="button" class="sort-btn" data-sort="date">Newest</button>
  <button type="button" class="sort-btn" data-sort="size">Largest</button>
</div>
```
`data-sort` attribute is read by `btn.dataset.sort` in `onSortChange`. `type="button"` follows the `back-btn` pattern (line 57) to prevent form submission. `active` class on "Relevance" matches `currentSort = "relevance"` default.

---

### `tests/test_search/test_query_builder.py` (test)

**Analog:** Self — existing test structure.

**Import extension** — add new exports to existing import block (lines 24-33):
```python
from nitrofind.search.query_builder import (
    build_filter_clauses,
    build_function_score_query,
    build_search_body,
    MAX_RESULT_SIZE,
    DEFAULT_RECENCY_WEIGHT,
    DEFAULT_LENGTH_WEIGHT,
    DEFAULT_INFOBOX_WEIGHT,
    DEFAULT_MISSING_PUBLISHED_SCORE,
    # Phase 10 additions (if exported; otherwise test via build_function_score_query):
    # _build_sort_clauses,
)
```
`_build_sort_clauses` is a private helper — test it indirectly via `build_search_body` return value (same approach as existing tests that verify inner query dict structure).

**Test function pattern** (copy from `test_base_query_is_multi_match` at lines 75-83):
```python
def test_base_query_is_multi_match():
    """Base query inside function_score uses multi_match."""
    q = build_function_score_query("Ferrari")
    base = q["function_score"]["query"]
    assert "multi_match" in base
    assert base["multi_match"]["query"] == "Ferrari"
    assert base["multi_match"]["type"] == "best_fields"
```
New Phase 10 tests follow the identical pattern — call builder, navigate dict, assert leaf value.

**Tests to add for QURY-01 (fuzzy):**
```python
def test_fuzzy_path_has_fuzziness():
    """Non-quoted query multi_match contains fuzziness:AUTO and prefix_length:1. [QURY-01]"""
    q = build_function_score_query("Ferari")
    base = q["function_score"]["query"]
    mm = base["multi_match"]
    assert mm["type"] == "best_fields"
    assert mm["fuzziness"] == "AUTO"
    assert mm["prefix_length"] == 1


def test_phrase_path_no_fuzziness():
    """Quoted query phrase path does NOT contain fuzziness key. [QURY-01 anti-pattern]"""
    q = build_function_score_query('"V8 engine"')
    base = q["function_score"]["query"]
    mm = base["multi_match"]
    assert "fuzziness" not in mm
```

**Tests to add for QURY-02 (phrase routing):**
```python
def test_phrase_query_routing():
    """Quoted input emits multi_match type:phrase with stripped text. [QURY-02]"""
    q = build_function_score_query('"V8 engine"')
    base = q["function_score"]["query"]
    mm = base["multi_match"]
    assert mm["type"] == "phrase"
    assert mm["query"] == "V8 engine"   # quotes stripped


def test_non_quoted_not_phrase():
    """Non-quoted input does NOT emit type:phrase. [QURY-02]"""
    q = build_function_score_query("V8 engine")
    base = q["function_score"]["query"]
    assert base["multi_match"]["type"] == "best_fields"


def test_empty_quotes_not_phrase():
    """'\"\"' (two chars) does not trigger phrase path — len > 2 guard. [QURY-02]"""
    q = build_function_score_query('""')
    base = q["function_score"]["query"]
    assert base["multi_match"]["type"] == "best_fields"
```

**Tests to add for SORT-02 (sort parameter):**
```python
def test_build_search_body_sort_date():
    """build_search_body(sort='date') includes published_at desc sort. [SORT-02]"""
    body = build_search_body("Ferrari", sort="date")
    assert "sort" in body
    assert body["sort"] == [{"published_at": {"order": "desc"}}]


def test_build_search_body_sort_size():
    """build_search_body(sort='size') includes word_count desc sort. [SORT-02]"""
    body = build_search_body("Ferrari", sort="size")
    assert "sort" in body
    assert body["sort"] == [{"word_count": {"order": "desc"}}]


def test_build_search_body_sort_relevance_no_key():
    """build_search_body(sort='relevance') omits 'sort' key entirely. [SORT-02]"""
    body = build_search_body("Ferrari", sort="relevance")
    assert "sort" not in body


def test_build_search_body_no_sort_no_key():
    """build_search_body() without sort param omits 'sort' key. [SORT-02]"""
    body = build_search_body("Ferrari")
    assert "sort" not in body
```

---

### `tests/test_search/test_api_search.py` (test)

**Analog:** Self — existing fixture and `test_manufacturer_filter_forwarded` pattern.

**Fixture pattern to copy** (lines 25-58) — the `client_with_search` fixture:
```python
@pytest.fixture
def client_with_search(monkeypatch):
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = { "took": 12, "hits": { ... } }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    return server.app.test_client()
```
New sort tests reuse `client_with_search`. For sort-forwarding assertions, use inline `monkeypatch` (same as `test_manufacturer_filter_forwarded` at lines 153-182) to inspect `mock_es.search.call_args.kwargs`.

**Call-kwarg assertion pattern** (lines 169-182):
```python
mock_es.search.assert_called_once()
call_kwargs = mock_es.search.call_args.kwargs
# assert on call_kwargs["query"], call_kwargs["sort"], etc.
```

**Tests to add for SORT-02 (API sort param routing):**
```python
def test_sort_date_passed_to_es(monkeypatch):
    """GET /api/search?q=mustang&sort=date passes date sort array to es_client.search. [SORT-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=mustang&sort=date")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    assert call_kwargs["sort"] == [{"published_at": {"order": "desc"}}]


def test_sort_size_passed_to_es(monkeypatch):
    """GET /api/search?q=mustang&sort=size passes size sort array to es_client.search. [SORT-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=mustang&sort=size")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    assert call_kwargs["sort"] == [{"word_count": {"order": "desc"}}]


def test_sort_unknown_value_ignored(monkeypatch):
    """GET /api/search?q=test&sort=inject treats unknown sort as relevance (sort=None). [SORT-02]"""
    from nitrofind import server
    mock_es = MagicMock()
    mock_es.search.return_value = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/search?q=test&sort=inject")
    assert resp.status_code == 200
    call_kwargs = mock_es.search.call_args.kwargs
    # sort kwarg should be None (no sort array) when value is not in allowlist
    assert call_kwargs.get("sort") is None
```

---

## Shared Patterns

### Flat keyword API for `client.search()`
**Source:** `nitrofind/server.py` lines 156-163
**Apply to:** The `sort` kwarg extension in `api_search`.
```python
resp = state["es_client"].search(
    index="car_articles",
    query=body["query"],
    highlight=body.get("highlight"),
    source=body.get("_source"),
    size=body.get("size", 20),
    from_=body.get("from", 0),
)
```
Never use `body=` (deprecated in ES 8.x). `sort=body.get("sort")` passes `None` for relevance, which elasticsearch-py 8.x treats as "omit the parameter."

### Module-level state in JS
**Source:** `static/js/app.js` lines 25-32
**Apply to:** `currentSort` addition.
```javascript
let currentFilters = { manufacturer: "", era_bucket: "", body_style: "" };
```
All persistent UI state is module-level `let` — no class, no closure pattern.

### `classList.toggle(class, condition)` for active state
**Source:** `static/js/app.js` lines 202-205 (`updateSelection`)
**Apply to:** `onSortChange` button active-state management.
```javascript
document.querySelectorAll(".result-item").forEach((el, i) => {
  el.classList.toggle("selected", i === selectedIndex);
});
```

### Allowlist validation for request params
**Source:** `nitrofind/server.py` lines 148-152 (coercion via `or None`)
**Apply to:** `sort` param extraction.
The `or None` idiom coerces empty string to `None`. For `sort`, additionally check membership in `_VALID_SORTS` set before passing to `build_search_body`.

### `monkeypatch.setitem` fixture for server state
**Source:** `tests/test_search/test_api_search.py` lines 56-58
**Apply to:** All new sort API tests.
```python
monkeypatch.setitem(server.state, "ready", True)
monkeypatch.setitem(server.state, "es_client", mock_es)
```

---

## No Analog Found

None. All files are pre-existing; Phase 10 is purely additive modification.

---

## Metadata

**Analog search scope:** `nitrofind/`, `static/js/`, `templates/`, `tests/test_search/`
**Files read:** 6 (query_builder.py, server.py, app.js, index.html, test_query_builder.py, test_api_search.py)
**Pattern extraction date:** 2026-06-25
