# Phase 10: Search Quality & Sort - Research

**Researched:** 2026-06-25
**Domain:** Elasticsearch 8.x query DSL (fuzzy/phrase routing), Flask API extension, vanilla JS UI controls
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QURY-01 | User searches with typos ("Ferari", "Lamborgini") and gets correct results — fuzziness: "AUTO" applied to multi_match query | Add `fuzziness="AUTO"`, `prefix_length=1` to existing `multi_match` in `build_function_score_query` |
| QURY-02 | User wraps a phrase in quotes ("V8 engine") and gets phrase-match results — query routed automatically to match_phrase | Detect leading+trailing `"` in Python, emit `multi_match` with `type: "phrase"` instead of `best_fields` |
| SORT-01 | User can sort results by relevance (default), newest-first (date), or largest-first (size) via toggle buttons in the search UI | Three `<button>` elements in `filter-row`, JS stores `currentSort`, appends `sort=` to URLSearchParams |
| SORT-02 | `GET /api/search` accepts optional `sort` param (`relevance` | `date` | `size`) and applies the corresponding ES sort order | `build_search_body` gains a `sort` param; server.py reads `request.args.get("sort")`; ES `sort=` keyword arg added to `client.search()` call |
</phase_requirements>

---

## Summary

Phase 10 adds three capabilities to the existing search stack: (1) typo-tolerance via `fuzziness: "AUTO"` in the `multi_match` base query, (2) phrase search via automatic routing to `multi_match` with `type: "phrase"` when the user wraps input in double quotes, and (3) sort controls so users and the API can reorder results by relevance, publication date, or article length.

All three touch the same narrow layer — `query_builder.py` — plus a thin extension to the Flask `api_search` route and the browser UI. No schema changes are needed: `published_at` is already a `date` field and `word_count` is already an `integer` field; both are stored and sortable. The ES Python client (8.19.3) exposes `sort` as a first-class flat keyword argument to `client.search()` with type `Optional[Sequence[Union[str, Mapping[str, Any]]]]`.

**Primary recommendation:** All logic change is in `build_function_score_query` (add `fuzziness`/`prefix_length`), a new `is_phrase_query` helper + routing branch in `build_search_body`, and a `sort` parameter threaded from `build_search_body` down to `_SearchWorker` and `api_search`. The UI adds three sort toggle buttons with a `currentSort` state variable.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fuzzy matching (QURY-01) | API / Backend (`query_builder.py`) | — | ES DSL parameter; no UI or API route change needed |
| Phrase detection + routing (QURY-02) | API / Backend (`query_builder.py`) | Browser (strip quotes before display) | String parsing is pure Python; ES query type is backend decision |
| Sort toggle buttons (SORT-01) | Browser / Client (`app.js`, `index.html`) | — | User interaction; sends `sort=` param via URLSearchParams |
| Sort API param + ES sort (SORT-02) | API / Backend (`server.py`, `query_builder.py`) | — | Flask reads param; ES `sort` kwarg applied server-side |

---

## Standard Stack

No new packages required. This phase extends existing code only.

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| elasticsearch | 8.19.3 | `fuzziness`, `sort`, `multi_match` DSL params | Already installed; `sort` is a verified flat kwarg [VERIFIED: elasticsearch-py readthedocs.io v8.0.0] |
| Flask | 3.1.3 | `request.args.get("sort")` | Already installed |
| Python | 3.12.3 (env) | Phrase detection regex | Already installed |

### No New Packages

No packages are added in this phase. The `## Package Legitimacy Audit` section is omitted — no external packages to audit.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (app.js)
  └─ URLSearchParams: { q, sort, ...filters }
        │  GET /api/search?q=...&sort=date
        ▼
Flask api_search (server.py)
  ├─ read sort= param  (SORT-02)
  ├─ build_filter_clauses(...)
  └─ build_search_body(q, filters, sort="date")  ← new sort arg
        │
        ▼
query_builder.py
  ├─ is_phrase_query(q)  →  True when q starts+ends with "
  │     ├─ True  → multi_match type:"phrase"  (no fuzziness)
  │     └─ False → multi_match best_fields + fuzziness:"AUTO"
  └─ _build_sort_clauses(sort)
        ├─ "date"      → [{"published_at": {"order": "desc"}}]
        ├─ "size"      → [{"word_count": {"order": "desc"}}]
        └─ "relevance" → None  (ES default _score desc)
        │
        ▼
ES client.search(
  index="car_articles",
  query=body["query"],
  sort=body.get("sort"),   ← new
  highlight=..., source=..., size=..., from_=...
)
```

### Recommended Project Structure

No new files. Modifications are localized to:

```
nitrofind/
├── search/
│   └── query_builder.py  — add fuzziness, phrase routing, sort helpers
└── server.py             — read sort= param, pass to build_search_body

static/
└── js/app.js             — add sort toggle buttons + currentSort state

templates/
└── index.html            — add sort toggle button markup in filter-row

tests/
└── test_search/
    ├── test_query_builder.py  — add tests for fuzz, phrase, sort
    └── test_api_search.py     — add tests for sort= param routing
```

---

### Pattern 1: Fuzzy Multi-Match (QURY-01)

**What:** Add `fuzziness="AUTO"` and `prefix_length=1` to the existing `multi_match` base query inside `build_function_score_query`.

**When to use:** Default path — any query that is NOT a quoted phrase.

**Why `prefix_length=1`:** Prevents fuzz from matching completely unrelated terms. The first character of a manufacturer name (e.g., "F" in "Ferrari") is always correct for typos like "Ferari". Without `prefix_length`, fuzz can expand into irrelevant terms on short queries.

**Why `fuzziness="AUTO"` not a fixed integer:** AUTO applies 0 edits for 1-2 char terms, 1 edit for 3-5 chars, 2 edits for 6+ chars. "Ferari" (6 chars) gets 2 edits → matches "Ferrari". "Lamborgini" (10 chars) gets 2 edits → matches "Lamborghini". Fixed `fuzziness=2` would also work but AUTO is the documented standard. [CITED: elastic.co/docs/reference/query-languages/query-dsl/query-dsl-multi-match-query]

**Confirmed:** `fuzziness` works with `best_fields` type. It does NOT work with `phrase`, `phrase_prefix`, or `cross_fields` types. [CITED: elastic.co/docs/reference/query-languages/query-dsl/query-dsl-multi-match-query]

```python
# Source: ES 8.x multi_match docs — fuzziness on best_fields
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

### Pattern 2: Phrase Detection and Routing (QURY-02)

**What:** Detect `"quoted input"` in the raw query string, strip quotes, emit `multi_match` with `type: "phrase"`.

**When to use:** When the user wraps input in double quotes.

**Detection rule:** `q.startswith('"') and q.endswith('"') and len(q) > 2`

**Phrase query on multiple fields:** `multi_match` with `type: "phrase"` creates a `match_phrase` per field and combines with dis_max. Fields can still carry boost (`title^3`). [CITED: elastic.co/guide/en/elasticsearch/reference/current/query-dsl-multi-match-query.html]

**Key constraint:** `fuzziness` MUST NOT be present when `type: "phrase"`. The ES docs explicitly state this is unsupported. The implementation must branch before setting `fuzziness`. [CITED: elastic.co/docs/reference/query-languages/query-dsl/query-dsl-multi-match-query]

```python
# Source: ES 8.x docs — multi_match type phrase
def is_phrase_query(raw_q: str) -> bool:
    """True when user wrapped input in double quotes."""
    return (
        raw_q.startswith('"')
        and raw_q.endswith('"')
        and len(raw_q) > 2
    )

def extract_phrase(raw_q: str) -> str:
    """Strip surrounding double quotes."""
    return raw_q[1:-1].strip()

# Phrase path (no fuzziness — ES rejects it on type:phrase)
phrase_query = {
    "multi_match": {
        "query": phrase_text,
        "fields": ["title^3", "body"],
        "type": "phrase",
    }
}
```

### Pattern 3: Sort Clauses (SORT-01, SORT-02)

**What:** Translate `sort` string parameter into an ES `sort` array, then pass it as a keyword argument to `client.search()`.

**Confirmed:** `client.search(sort=...)` is a first-class flat keyword argument in elasticsearch-py 8.x with type `Optional[Sequence[Union[str, Mapping[str, Any]]]]`. [VERIFIED: elasticsearch-py readthedocs.io v8.0.0 — confirmed via `inspect.signature(Elasticsearch.search)` against installed 8.19.3]

**Sort interactions with function_score:** The `sort` parameter overrides the default `_score desc` ordering when present. Passing a field-based sort returns documents sorted by that field; the function_score still runs (it determines which docs pass) but does not determine final ordering. For `sort=relevance`, passing `sort=None` (omitting the kwarg) restores default `_score desc`. [ASSUMED — based on Elastic community discussion; verified via official sort docs]

**"Size" sort field:** The `word_count` integer field is the correct proxy for "article size" — it is already indexed as `integer` in the ES schema (confirmed in `es_schema.py`). There is no `_size` meta-field stored by default; using `word_count` is the correct approach for this codebase.

```python
# Source: ES 8.x sort-search-results docs + inspect.signature verification
def _build_sort_clauses(sort: str | None) -> list[dict] | None:
    """Return ES sort array for the given sort mode, or None for relevance."""
    if sort == "date":
        return [{"published_at": {"order": "desc"}}]
    if sort == "size":
        return [{"word_count": {"order": "desc"}}]
    return None  # relevance = ES default _score desc

# In client.search() call:
resp = client.search(
    index="car_articles",
    query=body["query"],
    sort=body.get("sort"),          # None → ES default; list → field sort
    highlight=body.get("highlight"),
    source=body.get("_source"),
    size=body.get("size", 20),
    from_=body.get("from", 0),
)
```

### Pattern 4: Sort Toggle Buttons (SORT-01)

**What:** Three `<button>` elements in the filter row. JS tracks `currentSort`, appends `sort=` param in URLSearchParams. Active button gets `.active` CSS class.

**Integration with existing runSearch:** `currentSort` is added to the `params` URLSearchParams alongside existing filters. On sort button click: update `currentSort`, re-run `runSearch(currentQuery)`.

```javascript
// Vanilla JS — no framework; mirrors existing filter pattern
let currentSort = "relevance";  // "relevance" | "date" | "size"

function onSortChange(newSort) {
  currentSort = newSort;
  document.querySelectorAll(".sort-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.sort === newSort);
  });
  if (currentQuery) runSearch(currentQuery);
}

// In runSearch — add sort param
const params = new URLSearchParams({ q, ...currentFilters });
if (currentSort && currentSort !== "relevance") {
  params.set("sort", currentSort);
}
```

### Anti-Patterns to Avoid

- **Adding `fuzziness` to the phrase branch:** ES will reject the query with a 400 error. The `is_phrase_query` check must branch before adding fuzziness.
- **Using `fuzziness=2` (fixed integer) instead of `"AUTO"`:** AUTO adapts to query length. Fixed 2 is over-permissive for short terms.
- **Sorting by `excerpt` or `body` text fields:** Text fields are not sortable without fielddata enabled (expensive). Use `word_count` (integer) for size sort.
- **Passing `sort=None` to `client.search()` as an explicit kwarg instead of omitting it:** ES 8 Python client treats `None` as "omit this parameter" — this is safe, but confirm behavior. [ASSUMED — standard Python client convention]
- **Forgetting `prefix_length` on fuzz:** Without it, single-char edits on very short terms produce noisy unrelated matches.
- **Using `body=` API:** The existing codebase correctly uses the flat keyword API for `client.search()`; the sort extension must follow the same pattern (no `body=`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy edit-distance matching | Custom Levenshtein in Python | `fuzziness: "AUTO"` in multi_match | ES implements BK-tree fuzzy at the Lucene level — order-of-magnitude faster, handles Unicode |
| Phrase proximity scoring | Score-boosting after word-by-word match | `type: "phrase"` in multi_match | Lucene positional indexes make this zero-cost at query time |
| Sort by date | Python sort after retrieving all hits | ES `sort` array with `published_at` | ES can sort at shard level before transferring — never pull all docs to Python to sort |

---

## Common Pitfalls

### Pitfall 1: fuzziness on phrase type → 400 Bad Request
**What goes wrong:** Adding `fuzziness: "AUTO"` to a `multi_match` with `type: "phrase"` causes ES to return a 400 error.
**Why it happens:** ES Lucene implementation: phrase matching operates on positional indexes which do not support edit-distance expansion.
**How to avoid:** Branch in `build_function_score_query` (or its caller) before setting `fuzziness`. The phrase path must have no `fuzziness` key at all.
**Warning signs:** `elasticsearch.BadRequestError: [400]` with "fuzziness" in the message text.

### Pitfall 2: Sorting on `published_at` when field is absent
**What goes wrong:** Articles without a `published_at` value appear at the end (or top, depending on sort mode) when sorting by date. This is expected ES behavior (`_last` for missing values by default).
**Why it happens:** ES default `missing` behavior for date sort is `_last`. This is actually the correct UX for "newest first" — undated articles sink to the bottom.
**How to avoid:** No action needed; the default is correct. Document it so the plan doesn't add unnecessary `missing` handling.
**Warning signs:** If the spec later requires undated articles to sort in the middle, add `"missing": "_last"` explicitly.

### Pitfall 3: Phrase detection swallows the entire input as one phrase
**What goes wrong:** User types `"V8 engine` (opens quote, forgets to close) — `endswith('"')` is False, so it falls through to the fuzzy path correctly. But `q = '"V8 engine"` with trailing space inside quotes — the `strip()` inside `extract_phrase` removes it.
**Why it happens:** String edge cases.
**How to avoid:** `extract_phrase` must call `.strip()` on the inner text. The detection must require BOTH start and end quotes with `len(q) > 2` (rejects empty `""` case).

### Pitfall 4: `sort=None` vs omitting sort in build_search_body
**What goes wrong:** `build_search_body` stores `sort=None` in the body dict; later `body.get("sort")` returns `None`; `client.search(sort=None)` is passed — this is safe in elasticsearch-py 8 (None is treated as "omit").
**Why it happens:** Dictionary `get` returns None for missing keys. Passing None to a keyword arg is the correct omission pattern for this client.
**How to avoid:** Consistently use `body.get("sort")` pattern. Do NOT use `body.get("sort", [])` — an empty list `[]` might behave differently than None.

### Pitfall 5: Sort toggle state not reset on new query
**What goes wrong:** User sorts by date, navigates away, types a new query — results come back sorted by date unexpectedly.
**Why it happens:** `currentSort` is module-level state in JS.
**How to avoid:** Per the requirements, sort controls are persistent (the user chose that sort mode). Don't reset on new query. The UX is: sort stays active until the user explicitly clicks a different sort button. This is the correct behavior per SORT-01 ("reorders visible results").

### Pitfall 6: Phrase detection in the UI vs the API
**What goes wrong:** The JS `runSearch` function passes the raw query including the double quotes to the API. The Python `is_phrase_query` function then strips the quotes. If the UI strips quotes before sending, the API loses the phrase signal.
**Why it happens:** Confusion about where detection happens.
**How to avoid:** Detection and stripping happen ONLY in `query_builder.py` (Python). The browser sends the raw query including quotes to `/api/search?q=`. The Python layer detects and strips.

---

## Code Examples

### Complete fuzz + phrase routing in build_function_score_query

```python
# Source: ES 8.x multi_match docs (confirmed via official Elastic reference)
def build_function_score_query(
    query_text: str,
    ...
) -> dict:
    stripped = query_text[1:-1].strip() if (
        query_text.startswith('"') and query_text.endswith('"') and len(query_text) > 2
    ) else None

    if stripped is not None:
        # Phrase path: no fuzziness (ES rejects it for type:phrase)
        base_query = {
            "multi_match": {
                "query": stripped,
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
    # ... rest of function_score structure unchanged
```

### sort parameter in build_search_body and client.search

```python
# Source: elasticsearch-py 8.x API reference (flat keyword API)
# inspect.signature confirms: sort: Optional[Sequence[Union[str, Mapping[str, Any]]]] = None

def _build_sort_clauses(sort: str | None) -> list | None:
    if sort == "date":
        return [{"published_at": {"order": "desc"}}]
    if sort == "size":
        return [{"word_count": {"order": "desc"}}]
    return None

# In build_search_body, add to returned dict:
result = {
    "query": fs_query,
    "highlight": {...},
    "size": ...,
    "from": ...,
    "_source": [...],
}
sort_clauses = _build_sort_clauses(sort)
if sort_clauses is not None:
    result["sort"] = sort_clauses
return result

# In _SearchWorker.run() and api_search:
resp = client.search(
    index="car_articles",
    query=body["query"],
    sort=body.get("sort"),      # None → ES default; list → field sort
    highlight=body.get("highlight"),
    source=body.get("_source"),
    size=body.get("size", 20),
    from_=body.get("from", 0),
)
```

### Flask sort param extraction

```python
# In server.py api_search route
sort = request.args.get("sort") or None
# Allowlist: only accept known values
VALID_SORTS = {"relevance", "date", "size"}
if sort not in VALID_SORTS:
    sort = None
body = build_search_body(q, filters=filters, sort=sort)
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| multi_match without fuzziness | multi_match + `fuzziness: "AUTO"` | Typos like "Ferari" now match "Ferrari" |
| All queries use best_fields | Phrase-detected queries use `type: "phrase"` | `"V8 engine"` returns articles with exact phrase ranked above scattered-word matches |
| Results always sorted by function_score | Optional `sort` array overrides ordering | User controls by date/size/relevance |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Passing `sort=None` to `client.search()` is equivalent to omitting the sort kwarg (ES default _score desc) | Pattern 3 | Minimal: would need to conditionally pass sort kwarg; easy fix |
| A2 | `function_score` still computes correctly when a field-based `sort` array is present; sort overrides result ordering only | Pattern 3 Anti-pattern | Low: ES sort/score separation is well-documented; sort determines ordering, function_score still gates/scores docs |
| A3 | UX design: sort button state persists across new queries (not reset on each search) | Pitfall 5 | Low: requirement says "clicking X reorders" — implies sort is persistent user choice |

---

## Open Questions (RESOLVED)

1. **Should phrase search also apply function_score boosts?**
   - What we know: The current function_score functions (recency, length, infobox) are independent of query type.
   - What's unclear: Whether phrase-matched articles should still be ranked by recency/infobox etc. or ordered purely by phrase proximity score.
   - Recommendation: Keep function_score wrapping the phrase query — recency and infobox boosts improve phrase results the same way they improve fuzzy results. No change needed.

2. **"By size" sort: what if word_count is 0 for many articles?**
   - What we know: The schema defaults `word_count` to `integer`; missing=1 is used only in the function_score factor, not in sort.
   - What's unclear: Articles with `word_count=0` would sort to the bottom with `desc` order. This may be acceptable.
   - Recommendation: Accept default behavior. Articles with no word_count sort last on size — correct semantics.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| elasticsearch-py | query DSL, sort kwarg | Yes | 8.19.3 | — |
| Flask | API route | Yes | 3.1.3 | — |
| pytest | test suite | Yes | (in venv) | — |

No missing dependencies.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini at project root) |
| Config file | `pytest.ini` |
| Quick run command | `python3 -m pytest tests/test_search/ -q` |
| Full suite command | `python3 -m pytest tests/ -q --ignore=tests/integration` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QURY-01 | `build_function_score_query("Ferari")` contains `fuzziness:"AUTO"` and `prefix_length:1` in multi_match | unit | `python3 -m pytest tests/test_search/test_query_builder.py -q` | Existing file — new tests needed |
| QURY-01 | Phrase query path does NOT contain fuzziness key | unit | same | same |
| QURY-02 | `build_function_score_query('"V8 engine"')` emits `type:phrase` with stripped text | unit | `python3 -m pytest tests/test_search/test_query_builder.py -q` | Existing file — new tests needed |
| QURY-02 | Non-quoted query does NOT emit `type:phrase` | unit | same | same |
| SORT-01 | Sort buttons present in rendered HTML | manual UI | n/a | n/a — UI check |
| SORT-02 | `build_search_body(q, sort="date")` returns sort array `[{"published_at": {"order":"desc"}}]` | unit | `python3 -m pytest tests/test_search/test_query_builder.py -q` | Existing file — new tests needed |
| SORT-02 | `build_search_body(q, sort="size")` returns sort array `[{"word_count": {"order":"desc"}}]` | unit | same | same |
| SORT-02 | `build_search_body(q, sort="relevance")` returns no sort key | unit | same | same |
| SORT-02 | `GET /api/search?q=test&sort=date` passes sort array to `es_client.search()` | unit (mock) | `python3 -m pytest tests/test_search/test_api_search.py -q` | Existing file — new tests needed |
| SORT-02 | Unknown sort value (e.g. `sort=inject`) is ignored (treated as relevance) | unit (mock) | same | same |

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_search/ -q`
- **Per wave merge:** `python3 -m pytest tests/ -q --ignore=tests/integration`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

All new test functions are additions to existing files — no new test files need to be created. The existing `test_query_builder.py` and `test_api_search.py` are the correct locations.

*(No new test infrastructure needed — existing pytest setup covers all requirements)*

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `sort` param allowlisted to `{"relevance","date","size"}` in server.py; unknown values silently treated as `relevance` |
| V5 Input Validation | yes | Phrase detection operates on the raw query string — the stripped phrase text is placed in `multi_match.query` value only (never interpolated as DSL key) — inherits existing T-07-01 mitigation |
| V4 Access Control | no | Single-user local tool; no auth scope change |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Sort param injection (e.g., `sort={"script":"..."})` | Tampering | Allowlist: only string values `"relevance"`, `"date"`, `"size"` reach query_builder |
| Phrase detection bypass (e.g., `q="` alone) | Tampering | `len(q) > 2` guard in `is_phrase_query` prevents empty-phrase 400 error |
| Fuzz expansion DoS (high max_expansions) | DoS | Default `max_expansions=50` (ES default) is acceptable; no override needed |

---

## Sources

### Primary (HIGH confidence)
- [ES 8.x multi_match query docs](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-multi-match-query) — fuzziness support on best_fields, prohibition on phrase type
- [elasticsearch-py 8.0.0 API reference](https://elasticsearch-py.readthedocs.io/en/v8.0.0/api.html) — `sort` as flat keyword arg
- `inspect.signature(Elasticsearch.search)` on installed 8.19.3 — `sort: Optional[Sequence[Union[str, Mapping[str, Any]]]] = None` confirmed
- [ES 8.19 sort-search-results](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/sort-search-results.html) — sort array syntax
- [ES match_phrase query](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-query-phrase.html) — phrase syntax, slop, zero_terms_query

### Secondary (MEDIUM confidence)
- [Opster multi_match guide](https://opster.com/guides/elasticsearch/search-apis/elasticsearch-multi-match/) — `type:phrase` on multiple fields creates match_phrase per field with dis_max
- [Elastic community: function_score with sort](https://discuss.elastic.co/t/function-score-with-order/164049) — sort overrides ordering, function_score still scores

### Tertiary (LOW confidence)
- None — all critical claims verified above.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing packages verified
- Architecture: HIGH — code structure verified against installed source
- ES fuzzy/phrase DSL: HIGH — verified against official Elastic reference docs
- Sort kwarg: HIGH — verified via `inspect.signature` on installed elasticsearch-py 8.19.3
- Pitfalls: HIGH — pitfall 1 (fuzz+phrase) is an explicit ES doc warning; others are codebase-derived

**Research date:** 2026-06-25
**Valid until:** 2026-09-25 (stable ES 8.x DSL; 90 days)
