# Phase 11: Extended Filtering - Research

**Researched:** 2026-06-27
**Domain:** Elasticsearch range/term filters, Flask query param parsing, vanilla JS filter state, SPA filter row extension
**Confidence:** HIGH

---

## Summary

Phase 11 adds two new filter dimensions to the NitroFind search flow: a year-range filter (production era overlap) and a free-text country-of-origin filter. Both ES fields (`production_start`, `production_end` as integer; `country_of_origin` as keyword) are already in the schema and populated by the scraper. No index schema change is required — this phase is purely additive to the query-building layer, the Flask API, and the browser UI.

The year-range filter requires range overlap semantics: an article with `production_start=1958, production_end=1968` must appear in a search for years 1960–1975 because the production period overlaps the requested window. The correct Elasticsearch pattern for this is two `range` filter clauses combined with `bool.filter`: `production_end >= year_from` AND `production_start <= year_to`. This is the canonical interval overlap test.

The country filter uses a `term` query on the `country_of_origin` keyword field. Because the scraper stores raw infobox strings (e.g., "Germany", "United Kingdom"), the filter must match exactly on the indexed value — a full-text `match` query would be appropriate here only if the mapping were changed to `text`, which it is not and should not be. User input case-sensitivity is therefore a UX concern (documented in pitfalls below).

All three new filter parameters (`year_from`, `year_to`, `country`) follow the existing `build_filter_clauses` + `api_search` pattern established in earlier phases. The extension is additive: the existing `build_filter_clauses` function gains three new optional keyword arguments, and `api_search` reads three additional query params.

**Primary recommendation:** Extend `build_filter_clauses` with `year_from`, `year_to`, and `country` params; add range clauses and a term clause following the existing pattern; wire three new form controls in the filter row; mirror the existing empty-param strip pattern in `runSearch()`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FILT-01 | User can filter results by year range (from / to) using `production_start` / `production_end` — fields already mapped in the ES index schema | ES range query with interval overlap semantics covers this; both fields are `integer` type in CAR_ARTICLES_MAPPING |
| FILT-02 | User can filter results by country of origin via a free-text input in the filter sidebar | `country_of_origin` is `keyword` type; term filter is the correct approach; UX note: case-sensitive exact match |
| FILT-03 | `GET /api/search` accepts `year_from`, `year_to`, and `country` params and applies them as ES filter clauses alongside the existing `manufacturer`, `era_bucket`, and `body_style` filters | Additive extension of `build_filter_clauses` signature and `api_search` param extraction |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Year-range filter clause construction | API / Backend (`query_builder.py`) | — | Filter logic belongs in the query-builder; the JS layer only collects user input and appends params |
| Country filter clause construction | API / Backend (`query_builder.py`) | — | Same as above; `term` on keyword field is server-side ES DSL |
| API param parsing for new filters | API / Backend (`server.py`) | — | Flask route reads `request.args`; validation and coercion happen here |
| Year range inputs + country input in UI | Browser / Client (`index.html`, `app.js`, `style.css`) | — | Three new form controls in `.filter-row`; wired to `currentFilters` state dict |

---

## Standard Stack

No new packages are introduced by this phase. All changes are additive modifications to existing Python and vanilla JS files.

| File | Change Type | Purpose |
|------|-------------|---------|
| `nitrofind/search/query_builder.py` | Extend function signature | Add `year_from`, `year_to`, `country` params to `build_filter_clauses`; emit `range` and `term` filter dicts |
| `nitrofind/server.py` | Extend route | Read `year_from`, `year_to`, `country` from `request.args`; coerce year params to `int`; pass to `build_filter_clauses` |
| `templates/index.html` | Add form controls | Year From input, Year To input, Country input in `.filter-row` |
| `static/js/app.js` | Extend filter state | Add `year_from`, `year_to`, `country` to `currentFilters`; wire new inputs to `onFilterChange` |
| `static/css/style.css` | Style new inputs | Consistent styling with existing `.filter-row` controls |
| `tests/test_search/test_query_builder.py` | New tests | FILT-01/02/03 unit test coverage |
| `tests/test_search/test_api_search.py` | New tests | API param forwarding coverage |

**Version verification:** No new packages — not applicable.

---

## Package Legitimacy Audit

No new packages are installed in this phase. Not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (user types year range or country)
    │ input event → onFilterChange()
    │ currentFilters = { ..., year_from, year_to, country }
    ↓
runSearch() builds URLSearchParams
    │ strips empty values
    ↓
GET /api/search?q=...&year_from=1960&year_to=1975&country=Germany
    ↓
Flask api_search route
    │ coerce year_from/year_to to int (or None on ValueError)
    │ country: string or None
    ↓
build_filter_clauses(year_from=1960, year_to=1975, country="Germany")
    │ emits: range(production_end ≥ 1960)
    │        range(production_start ≤ 1975)
    │        term(country_of_origin="Germany")
    ↓
build_search_body wraps filters into bool.filter context (existing pattern)
    ↓
Elasticsearch 8.18 — filters applied in filter cache context
    ↓
JSON results array → rendered to DOM (existing renderResults)
```

### Recommended Project Structure

No new directories required. All changes are in-place modifications to existing files:

```
nitrofind/
├── search/
│   ├── query_builder.py   ← extend build_filter_clauses signature
│   └── ...
├── server.py              ← extend api_search param extraction
templates/
├── index.html             ← add 3 filter controls to .filter-row
static/
├── js/app.js              ← extend currentFilters + wire new inputs
├── css/style.css          ← style number inputs consistently
tests/
├── test_search/
│   ├── test_query_builder.py   ← FILT-01/02/03 unit tests
│   └── test_api_search.py      ← FILT-03 API forwarding tests
```

### Pattern 1: ES Range Overlap Filter (FILT-01)

**What:** To find articles whose production period overlaps a requested year window, use two range clauses in `bool.filter`:
- `production_end >= year_from` — article's end year is at or after the window start
- `production_start <= year_to` — article's start year is at or before the window end

**Why two clauses (not one):** A single range on `production_start` alone would miss articles whose run began before `year_from` but extended into the window. A single range on `production_end` alone would miss articles that started after the window start but before `year_to`. The interval overlap condition is: `start <= window_end AND end >= window_start`.

**When to use:** Always use this pair together when implementing year range filters on articles with a start and an end year.

**Example:**
```python
# Source: ES range query docs (elastic.co/docs/reference/query-languages/query-dsl/query-dsl-range-query)
# [VERIFIED: elastic.co/docs]

# User requests 1960–1975 production window:
if year_from is not None:
    filters.append({"range": {"production_end": {"gte": year_from}}})
if year_to is not None:
    filters.append({"range": {"production_start": {"lte": year_to}}})

# Result: only articles whose production period overlaps [year_from, year_to]
# Articles with missing production_end or production_start are excluded by
# ES range semantics — null/missing fields are NOT matched by range queries.
# [VERIFIED: elastic.co/docs] missing values excluded from range results
```

**Handling missing production_end:** When `production_end` is `None` (still-produced or unknown end), the ES range filter `production_end >= year_from` will **exclude** those articles because null fields are not matched by range queries in ES. This is acceptable behavior for the current scope — FILT-01 says "production period overlaps that range", and articles with no end date cannot definitively be said to fall within or outside the window. If the project later wants to include still-produced cars in all year-to filters, a `bool.should` with `must_not exists` can be added, but that is out of scope for this phase. [ASSUMED — behavior accepted without explicit user confirmation]

**Handling single bound:** Year from alone (no year to) or year to alone (no year from) each emit one range clause independently. The other clause is simply omitted. Both bounds are optional.

### Pattern 2: ES Term Filter on Keyword Field (FILT-02)

**What:** `country_of_origin` is mapped as `keyword` (exact match, no analysis). The correct ES filter is a `term` query.

**When to use:** For all exact-match keyword field filters — same pattern already used for `manufacturer`, `era_bucket`, and `body_style`.

**Example:**
```python
# Source: existing build_filter_clauses pattern in query_builder.py [VERIFIED: codebase]
if country:
    filters.append({"term": {"country_of_origin": country}})
```

**Case sensitivity:** `keyword` fields are stored as-is. The scraper populates `country_of_origin` from Wikipedia infobox `origin` or `country` fields — values like "Germany", "United Kingdom", "Japan" (capitalized). A user typing "germany" (lowercase) will not match. The UI should use a `<datalist>` or note in placeholder text that the field is case-sensitive, OR the placeholder text should communicate the expected format. Recommend: placeholder text `e.g. Germany` to signal casing convention.

### Pattern 3: Extending build_filter_clauses (FILT-03)

**What:** Add three optional keyword arguments to the existing `build_filter_clauses` function, following the same None-guard pattern as `manufacturer`, `era_bucket`, and `body_style`.

**Example:**
```python
# Source: existing build_filter_clauses in nitrofind/search/query_builder.py [VERIFIED: codebase]

def build_filter_clauses(
    manufacturer: str | None = None,
    era_bucket: str | None = None,
    body_style: str | None = None,
    year_from: int | None = None,   # NEW
    year_to: int | None = None,     # NEW
    country: str | None = None,     # NEW
) -> list[dict]:
    filters = []
    if manufacturer:
        filters.append({"term": {"manufacturer": manufacturer}})
    if era_bucket:
        filters.append({"term": {"era_bucket": era_bucket}})
    if body_style:
        filters.append({"term": {"body_style": body_style}})
    # FILT-01: year range overlap (interval intersection semantics)
    if year_from is not None:
        filters.append({"range": {"production_end": {"gte": year_from}}})
    if year_to is not None:
        filters.append({"range": {"production_start": {"lte": year_to}}})
    # FILT-02: country of origin exact match (keyword field)
    if country:
        filters.append({"term": {"country_of_origin": country}})
    return filters
```

**Year param coercion in server.py:** The Flask route must coerce `year_from` and `year_to` from string (all query params are strings) to `int` before passing to `build_filter_clauses`. Use a safe coercion helper to handle non-integer input gracefully:

```python
# Source: existing server.py pattern (or_ None coercion) extended [VERIFIED: codebase]
def _safe_int_param(value: str | None) -> int | None:
    """Coerce string query param to int, returning None on error."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
```

### Pattern 4: JS Filter State Extension

**What:** Extend `currentFilters` object in `app.js` with three new keys, and cache three new DOM element references. Wire them to `onFilterChange`.

**Example:**
```javascript
// Source: existing app.js filter pattern [VERIFIED: codebase]

// Module-level state extension:
let currentFilters = {
  manufacturer: "",
  era_bucket: "",
  body_style: "",
  year_from: "",   // NEW
  year_to: "",     // NEW
  country: "",     // NEW
};

// DOM cache additions:
const filterYearFrom = document.getElementById("filter-year-from");
const filterYearTo   = document.getElementById("filter-year-to");
const filterCountry  = document.getElementById("filter-country");

// onFilterChange extension:
function onFilterChange() {
  currentFilters.manufacturer = filterMfr.value;
  currentFilters.era_bucket   = filterEra.value;
  currentFilters.body_style   = filterBody.value;
  currentFilters.year_from    = filterYearFrom.value;  // NEW
  currentFilters.year_to      = filterYearTo.value;    // NEW
  currentFilters.country      = filterCountry.value;   // NEW
  if (currentQuery) runSearch(currentQuery);
}

filterYearFrom.addEventListener("change", onFilterChange);
filterYearTo.addEventListener("change", onFilterChange);
filterCountry.addEventListener("change", onFilterChange);
```

The existing `runSearch()` empty-param strip logic (`params.delete(k)` for falsy values) already handles empty year_from/year_to/country strings without any modification. [VERIFIED: codebase — the for-loop over URLSearchParams entries strips all falsy values]

### Pattern 5: HTML Form Controls for Filter Row

**What:** Three new controls in `.filter-row`: two `<input type="number">` (year from / to) and one `<input type="text">` (country). Use `<input>` not `<select>` because year ranges and country names are free-form, unlike the fixed vocabulary of era_bucket and body_style.

**Example:**
```html
<!-- Source: existing filter-row pattern in index.html [VERIFIED: codebase] -->
<input id="filter-year-from" type="number" placeholder="Year from"
       min="1900" max="2099" step="1">
<input id="filter-year-to"   type="number" placeholder="Year to"
       min="1900" max="2099" step="1">
<input id="filter-country"   type="text"   placeholder="e.g. Germany">
```

`min`/`max` on the number inputs enforce reasonable bounds client-side without blocking legitimate values — the server also validates via `int()` conversion which will reject letters.

### Pattern 6: CSS Styling for New Inputs

The existing `.filter-row select` rule already establishes the correct styling for filter row controls. The number and text inputs need a separate rule (or shared rule). Extend to cover `input` elements in `.filter-row`:

```css
/* Source: existing style.css filter-row pattern [VERIFIED: codebase] */
.filter-row input[type="number"],
.filter-row input[type="text"] {
  padding: 0.375rem 0.625rem;
  font-size: 0.85rem;
  background-color: var(--bg-input);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  outline: none;
  transition: border-color var(--transition);
  width: 7rem;        /* constrain number inputs; text input can be wider */
}

.filter-row input[type="text"] {
  width: 9rem;
}

.filter-row input[type="number"]:focus,
.filter-row input[type="text"]:focus {
  border-color: var(--accent);
}
```

The width values keep the filter row from overflowing on typical desktop widths. The existing `flex-wrap: wrap` on `.filter-row` handles narrower viewports gracefully — no change needed to the row container.

### Anti-Patterns to Avoid

- **`match` query on `country_of_origin`:** The field is `keyword` type — no text analysis is applied. Using `match` instead of `term` will raise an ES mapping exception or return wrong results. Use `term`.
- **Range on `published_at` instead of `production_start`/`production_end`:** `published_at` is the article's publication date, not the car's production year. FILT-01 explicitly specifies `production_start` / `production_end`.
- **Passing raw string year param to ES range query:** ES will accept a string `"1960"` in a range filter on an `integer` field but the Python elasticsearch-py client may type-check it. Always coerce to `int` in `server.py` before passing to `build_filter_clauses`.
- **Single range clause for year overlap:** Using only `production_start >= year_from AND production_start <= year_to` would exclude articles that started before `year_from` but ran into the window (e.g., a 1958–1968 car is excluded from a 1960–1975 search). Must use the two-clause overlap pattern.
- **Resetting `currentSort` in `runSearch`:** The Phase 10 decision (STATE.md) is that sort persists across filter changes. Do not add sort-reset logic.
- **`input` event on year fields:** Firing a search on every keystroke of a year number (typing "1", "19", "196", "1960") produces 4 unnecessary ES calls. Use `change` event (fires on blur or Enter) instead of `input` for the year inputs. The country text input can also use `change` for consistency.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Year range overlap detection | Custom Python overlap logic | ES `range` filter on `production_end ≥ year_from` + `production_start ≤ year_to` | ES executes this inside filter cache — faster than post-processing results in Python |
| Country normalization / synonyms | Custom synonym table or fuzzy match logic | Direct `term` filter with placeholder text hinting at format | Out of scope; the indexed data is raw infobox text; normalization belongs in the scraper, not the filter layer |
| Input validation beyond type coercion | Custom year bounds checks, regex patterns | `min`/`max` on `<input type="number">` + `int()` coercion in server.py | Sufficient for a single-user local tool; ES rejects structurally invalid queries anyway |

**Key insight:** The ES filter cache makes properly formed `range` and `term` filters extremely cheap for a small local index. There is no performance argument for custom Python filtering of results.

---

## Common Pitfalls

### Pitfall 1: Using a Single Range Clause and Missing Overlap Cases

**What goes wrong:** Filtering `production_start >= year_from AND production_start <= year_to` misses cars whose production started before the window but ran into it (e.g., a 1955–1970 car is excluded from a 1960–1975 search).

**Why it happens:** Developers think "year range" means "the car started production within the window" rather than "the car's production period overlaps the window."

**How to avoid:** Use the two-clause overlap pattern: `production_end >= year_from AND production_start <= year_to`.

**Warning signs:** A search for 1960–1975 fails to return well-known cars like the Ford Mustang (1964–present) or Porsche 911 (1963–present).

---

### Pitfall 2: Range Queries Exclude Documents with Missing/Null Fields

**What goes wrong:** Articles where `production_start` or `production_end` is `None` (not indexed) are excluded from range filter results. For `year_from` filter (`production_end >= year_from`), any car with no recorded end date (still in production) is excluded.

**Why it happens:** ES range queries only match indexed values — null/missing fields produce no entry in the inverted index for integer fields, so the range clause returns no match.

**How to avoid:** Accept this behavior as correct for this phase — a car with no end date cannot be definitively placed within or outside a year window. Document this in comments. If future requirements need "include cars still in production", add a `bool.should` clause with `must_not: exists(production_end)`.

**Warning signs:** Searching for "Ferrari" with year range 1960–2025 omits modern Ferrari models that have no `production_end` indexed.

---

### Pitfall 3: Country Filter Case Sensitivity

**What goes wrong:** User types "germany" and gets zero results because `country_of_origin` is stored as "Germany" (capitalized) from the Wikipedia infobox `origin` field.

**Why it happens:** `keyword` fields are stored and queried with exact-case matching. No `normalizer` is applied to the field in the current schema.

**How to avoid:** Placeholder text `e.g. Germany` signals the expected casing. This is sufficient for the current scope. Do NOT add a `normalizer` to the field mapping — that would require a destructive `PUT` mapping update or full index rebuild. A `normalizer` is a v1.3+ improvement. [ASSUMED — decision to accept case-sensitive behavior accepted based on project constraints]

**Warning signs:** Zero results from country filter when user uses lowercase.

---

### Pitfall 4: `input` Event on Number Fields Firing Mid-Keystroke

**What goes wrong:** Attaching `input` event listeners to `filter-year-from` and `filter-year-to` fires `runSearch` on partial year values: `"1"`, `"19"`, `"196"`, `"1960"`. The intermediate values produce spurious ES calls and wrong results.

**Why it happens:** The existing search box uses `input` event for debounced live search, which is correct for the query text. But year filters are not "live search" inputs — they are boundary values that only make sense when fully entered.

**How to avoid:** Use `change` event (fires on blur or Enter key) for the year inputs and country text input. This matches the behavior of `<select>` elements (which also fire `change` on selection), keeping filter behavior consistent.

**Warning signs:** Search triggers on "1" when user is typing "1960".

---

### Pitfall 5: Not Stripping Empty Year Params in URLSearchParams

**What goes wrong:** `currentFilters.year_from = ""` and `currentFilters.year_to = ""` are added to URLSearchParams as `year_from=&year_to=`, causing Flask to receive empty string params that must be coerced to `None`.

**Why it doesn't cause a bug (but why it matters):** The server already uses `_safe_int_param` (or equivalent) which returns `None` on empty string. However, the existing `runSearch` loop that strips empty params from URLSearchParams already handles this correctly — no change needed. Verify the strip loop covers the new keys.

**Warning signs:** URL looks like `/api/search?q=ferrari&year_from=&year_to=&country=` when filters are empty.

---

## Code Examples

### Complete `build_filter_clauses` after Phase 11

```python
# Source: nitrofind/search/query_builder.py [VERIFIED: codebase — current implementation shown]
# Phase 11 adds year_from, year_to, country parameters.

def build_filter_clauses(
    manufacturer: str | None = None,
    era_bucket: str | None = None,
    body_style: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    country: str | None = None,
) -> list[dict]:
    filters = []
    if manufacturer:
        filters.append({"term": {"manufacturer": manufacturer}})
    if era_bucket:
        filters.append({"term": {"era_bucket": era_bucket}})
    if body_style:
        filters.append({"term": {"body_style": body_style}})
    # FILT-01: interval overlap — article production period intersects [year_from, year_to]
    if year_from is not None:
        filters.append({"range": {"production_end": {"gte": year_from}}})
    if year_to is not None:
        filters.append({"range": {"production_start": {"lte": year_to}}})
    # FILT-02: exact country of origin match (keyword field — case-sensitive)
    if country:
        filters.append({"term": {"country_of_origin": country}})
    return filters
```

### Flask `api_search` year param coercion

```python
# Source: nitrofind/server.py existing pattern [VERIFIED: codebase]
# Add to api_search, following existing filter param pattern.

def _safe_int_param(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None

# Inside api_search():
filters = build_filter_clauses(
    manufacturer=request.args.get("manufacturer") or None,
    era_bucket=request.args.get("era_bucket") or None,
    body_style=request.args.get("body_style") or None,
    year_from=_safe_int_param(request.args.get("year_from")),
    year_to=_safe_int_param(request.args.get("year_to")),
    country=request.args.get("country") or None,
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `<select>` dropdowns only for filters | Mix of `<select>` for fixed vocab, `<input>` for free-form fields | Phase 11 | Year inputs use `type="number"`; country uses `type="text"` |
| No year range filtering | ES range overlap via two `range` filter clauses | Phase 11 | `production_start`/`production_end` fields now addressable by user |
| No country filter | ES `term` filter on `country_of_origin` keyword field | Phase 11 | Direct match on infobox-extracted country string |

**Deprecated/outdated:**

- None for this phase — all patterns are additive to the current stack.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Excluding articles with null `production_end` from year-from range filter is acceptable behavior for this phase | Pattern 1 (Pitfall 2) | Missing modern cars (still-in-production) from year-ranged results — user may notice and request fix |
| A2 | Case-sensitive exact match on `country_of_origin` is acceptable; placeholder hint is sufficient UX mitigation | Pattern 2 (Pitfall 3) | Zero results when user types lowercase country name — low severity for a power-user tool |
| A3 | `change` event (blur/Enter) is the right trigger for year inputs instead of `input` | Pattern 4 / Pitfall 4 | If user expects live-search on year typing, this feels less responsive — but avoiding spurious mid-keystroke queries is the right tradeoff |

---

## Open Questions

1. **Country normalization UX**
   - What we know: `country_of_origin` stores raw Wikipedia infobox strings. Values are inconsistent ("Germany", "West Germany", "British", "United Kingdom").
   - What's unclear: Should the UI hint at available countries (datalist), or accept any input and silently return zero?
   - Recommendation: Keep as free-text `<input>` with placeholder for this phase; a `<datalist>` populated from live ES aggregations is a v1.3 improvement. Out of scope for FILT-02.

2. **Year bounds for number inputs**
   - What we know: Scraper validates `production_start` in range 1900–2099. ES schema has no constraint.
   - What's unclear: Should the UI enforce `min="1900"` on inputs to prevent users typing 4-digit years outside this range?
   - Recommendation: Use `min="1900" max="2099"` on both number inputs as soft client-side validation. Server coerces to `int` regardless.

---

## Environment Availability

Step 2.6: SKIPPED — this phase introduces no new external tools, CLIs, runtimes, or services. All changes are to existing Python files and static web assets that are already operational.

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
| FILT-01 | `build_filter_clauses(year_from=1960)` emits `range production_end >=1960` | unit | `pytest tests/test_search/test_query_builder.py -q -k "year"` | ❌ Wave 0 |
| FILT-01 | `build_filter_clauses(year_to=1975)` emits `range production_start <=1975` | unit | `pytest tests/test_search/test_query_builder.py -q -k "year"` | ❌ Wave 0 |
| FILT-01 | Both year bounds together produce two range clauses | unit | `pytest tests/test_search/test_query_builder.py -q -k "year"` | ❌ Wave 0 |
| FILT-01 | `year_from` and `year_to` both `None` produce no extra clauses | unit | `pytest tests/test_search/test_query_builder.py -q -k "year"` | ❌ Wave 0 |
| FILT-02 | `build_filter_clauses(country="Germany")` emits `term country_of_origin=Germany` | unit | `pytest tests/test_search/test_query_builder.py -q -k "country"` | ❌ Wave 0 |
| FILT-02 | Empty string country produces no filter clause | unit | `pytest tests/test_search/test_query_builder.py -q -k "country"` | ❌ Wave 0 |
| FILT-03 | `GET /api/search?q=test&year_from=1960&year_to=1975&country=Germany` forwards all three filter clauses to ES | unit | `pytest tests/test_search/test_api_search.py -q -k "year or country"` | ❌ Wave 0 |
| FILT-03 | Non-integer `year_from` (e.g. "abc") is coerced to `None`, no clause emitted | unit | `pytest tests/test_search/test_api_search.py -q -k "year_invalid"` | ❌ Wave 0 |
| FILT-03 | All six filter params combine correctly (manufacturer + era + body_style + year_from + year_to + country) | unit | `pytest tests/test_search/test_query_builder.py -q -k "all_filters"` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_search/ -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_search/test_query_builder.py` — add FILT-01/02/03 test functions (existing file, add to it)
- [ ] `tests/test_search/test_api_search.py` — add FILT-03 API forwarding tests (existing file, add to it)

*(No new test files needed — all tests go into existing test files following the established pattern.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `_safe_int_param` coercion for year params; `or None` guard for country string |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Injection via `year_from` / `year_to` params | Tampering | `int()` coercion in `_safe_int_param` — non-integer values become `None`, no clause emitted; ES never sees raw user string in a range clause |
| Injection via `country` param | Tampering | Country value placed in `term` filter value field (same as existing `manufacturer`); never interpolated as DSL key (T-07-02 precedent) |
| Unbounded year values (e.g. year_from=9999999) | DoS | `int()` coercion succeeds but ES range on an integer field with an extreme value is a no-op returning zero results — no performance risk on a 2 GB local index |

**Security note:** The existing `T-07-01` through `T-07-07` mitigations in `server.py` and `query_builder.py` cover the new params by extension — user input is never placed in a DSL key position, always in a value position.

---

## Sources

### Primary (HIGH confidence)

- Elasticsearch 8 Range Query docs (`elastic.co/docs/reference/query-languages/query-dsl/query-dsl-range-query`) — range syntax verified
- `nitrofind/es_schema.py` — `production_start` (integer), `production_end` (integer), `country_of_origin` (keyword) field types confirmed by direct file read
- `nitrofind/search/query_builder.py` — existing `build_filter_clauses` pattern and `bool.filter` wrapping confirmed by direct file read
- `nitrofind/server.py` — existing `api_search` param extraction pattern confirmed by direct file read
- `static/js/app.js` — `currentFilters` state dict structure, `onFilterChange`, URLSearchParams empty-strip loop confirmed by direct file read
- `templates/index.html` — `.filter-row` structure confirmed by direct file read
- `static/css/style.css` — `.filter-row select` styling pattern confirmed by direct file read
- `tests/test_search/test_query_builder.py` — existing test pattern for `build_filter_clauses` confirmed by direct file read
- `tests/test_search/test_api_search.py` — existing API test pattern with monkeypatched `state` confirmed by direct file read

### Secondary (MEDIUM confidence)

- ES null-field behavior in range queries — confirmed via GitHub elastic/elasticsearch issue #46977 and official ES docs: missing values are excluded from range results
- Year range overlap semantics (two-clause `AND`) — established SQL/ES pattern; confirmed by range query docs

### Tertiary (LOW confidence)

- None.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new packages; all changes are additive to verified existing code
- Architecture: HIGH — ES schema already has the required fields; filter pattern is identical to existing manufacturer/era/body_style filters
- Pitfalls: HIGH — null-field exclusion is documented ES behavior; case-sensitivity on keyword fields is deterministic; pitfalls derived from direct codebase inspection
- UI patterns: HIGH — existing `.filter-row` structure is simple and well-understood

**Research date:** 2026-06-27
**Valid until:** 2026-07-27 (stable stack — ES 8.x filter DSL does not change between minor versions)
