---
phase: 11-extended-filtering
reviewed: 2026-07-03T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - tests/test_search/test_query_builder.py
  - tests/test_search/test_api_search.py
  - nitrofind/search/query_builder.py
  - nitrofind/server.py
  - templates/index.html
  - static/js/app.js
  - static/css/style.css
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-07-03
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 11 adds extended filtering (year range, country of origin, sort controls), phrase detection, and fuzzy routing to the query builder. The backend query logic and server routes are solid — `build_filter_clauses`, `build_function_score_query`, and the SORT-02 allowlist are all correctly implemented and well-tested. Two blockers prevent the feature from shipping as-is: the manufacturer dropdown is permanently non-functional (no code populates it), and `excerpt.innerHTML` introduces an XSS vector that the developer's own comment mischaracterizes. Six additional warnings cover a stale docstring, missing `_source` fields for the new filter dimensions, a CSS pre-wrap collision with HTML article rendering, an under-specified sort clause, an infinite warmup poller, and a query-sync gap between the two search inputs.

---

## Critical Issues

### CR-01: Manufacturer filter dropdown is permanently non-functional

**File:** `templates/index.html:27-30`, `static/js/app.js` (no population code anywhere)

**Issue:** The `#filter-manufacturer` `<select>` element is hardcoded with exactly one option — "All manufacturers" (value `""`). No JavaScript code ever adds manufacturer options to this element. `filterMfr.value` is read in `onFilterChange` and forwarded to the API, but it can only ever produce value `""`, which the server correctly ignores. The backend supports manufacturer filtering (`build_filter_clauses` accepts `manufacturer`, the route reads it, and the tests verify it is forwarded), but the UI makes it permanently unreachable. This is a Phase 11 deliverable that does not work.

**Fix:** Either populate the manufacturer select statically (if the set of manufacturers is known at build time):

```html
<select id="filter-manufacturer">
  <option value="">All manufacturers</option>
  <option value="Ford">Ford</option>
  <option value="BMW">BMW</option>
  <!-- ... etc. -->
</select>
```

Or populate it dynamically from an aggregations API call on startup (correct long-term solution — requires a `/api/aggregations` endpoint that returns `terms` aggregation on the `manufacturer` field):

```javascript
async function populateManufacturers() {
  try {
    const resp = await fetch("/api/aggregations?field=manufacturer");
    if (!resp.ok) return;
    const { buckets } = await resp.json();
    buckets.forEach(({ key }) => {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = key;
      filterMfr.appendChild(opt);
    });
  } catch (_) { /* non-fatal */ }
}
```

At minimum, a static list unblocks the feature for the current phase.

---

### CR-02: `excerpt.innerHTML` with unsanitized content — ES does not HTML-encode highlight output

**File:** `static/js/app.js:162`

**Issue:** The code sets:

```javascript
excerpt.innerHTML = r.excerpt || "";      // innerHTML ONLY — ES highlight <b> tags (D-10)
```

The comment claims only ES-generated `<b>` tags will be present. This is incorrect. Elasticsearch does **not** HTML-encode field content before inserting highlight markers. When building a highlight fragment, ES extracts text from the `body` field and wraps matched terms with the configured `pre_tags`/`post_tags`. If the `body` field contains raw HTML characters (e.g., `<img src=x onerror=alert(1)>` or `<a href="javascript:...">`) from imperfect scraper text extraction, those characters appear verbatim in the highlighted fragment. In the no-highlight fallback path, `result.excerpt` from `_source` is used directly — whatever the scraper stored there goes straight to `innerHTML`.

The comment documents `articleBody.innerHTML = htmlContent` (line 185) with an explicit risk acknowledgment ("Scraper strips `<script>`, `<style>`, and on* event handler attributes before storing. Local single-user offline app — XSS attack surface is near-zero."). No such acknowledgment exists for `excerpt.innerHTML`, and the assumption that the excerpt contains only `<b>` tags is not verified in the reviewed code.

**Fix:** Sanitize before setting innerHTML. The minimal correct approach for excerpt display:

```javascript
// Option A: sanitize with DOMPurify (add to project if not already present)
excerpt.innerHTML = DOMPurify.sanitize(r.excerpt || "", {
  ALLOWED_TAGS: ["b"],   // only ES highlight tags are valid here
  ALLOWED_ATTR: []
});

// Option B: no dependency — decode ES highlights manually and use textContent
const raw = r.excerpt || "";
const safe = raw
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/&lt;b&gt;/g, "<b>")       // restore only the ES highlight tags
  .replace(/&lt;\/b&gt;/g, "</b>");
excerpt.innerHTML = safe;
```

Option B is zero-dependency and matches the project's "no npm, no CDN" constraint stated in `app.js`.

---

## Warnings

### WR-01: Stale docstring in `_result_to_api_dict` — 6 keys documented, 8 returned

**File:** `nitrofind/server.py:112`

**Issue:** The docstring reads: "Returns: dict with keys: title, url, source_domain, excerpt, score, took_ms." The actual return dict at lines 115-124 has 8 keys: `title`, `url`, `source_domain`, `excerpt`, **`body`**, **`body_html`**, `score`, `took_ms`. `body` and `body_html` were added in Phase 9 but the docstring was not updated. The test at `test_api_search.py:119` correctly checks for all 8 keys, so the implementation is right and the docstring is wrong.

**Fix:**

```python
Returns:
    dict with keys: title, url, source_domain, excerpt, body, body_html, score, took_ms.
```

---

### WR-02: Phase 11 filter fields missing from `_source` list

**File:** `nitrofind/search/query_builder.py:300-304`

**Issue:** `build_search_body` sets `_source` to:

```python
"_source": [
    "title", "url", "source_domain", "excerpt", "body", "body_html",
    "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
],
```

Phase 11 adds three new filter dimensions — `country_of_origin`, `production_start`, and `production_end` — that are used in `build_filter_clauses` range/term clauses. None of these fields is included in `_source`. The filters execute correctly against indexed data, but the field values are never returned with search results. If the UI (or a future caller) needs to display or validate these values per result (e.g., show "Germany · 1963-1973" on a result card), the data will not be available without a second fetch.

**Fix:** Add the three fields to the `_source` list:

```python
"_source": [
    "title", "url", "source_domain", "excerpt", "body", "body_html",
    "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
    "country_of_origin", "production_start", "production_end",   # Phase 11
],
```

---

### WR-03: `white-space: pre-wrap` on `#article-body` renders HTML whitespace literally

**File:** `static/css/style.css:355`

**Issue:**

```css
#article-body {
  ...
  white-space: pre-wrap;
}
```

`pre-wrap` is inherited by all descendants. When `openArticle` sets `articleBody.innerHTML = htmlContent` (app.js:185), any whitespace in the HTML source — newlines between `<p>` tags, indentation inside `<ul>` items, blank lines between `<h2>` and `<p>` blocks — renders as visible whitespace in the browser. The partial workaround at line 362 (`#article-body table { white-space: normal; }`) covers table cells only; `<p>`, `<h2>`, `<h3>`, `<ul>`, `<li>`, and all other elements remain under `pre-wrap`. Wikipedia-sourced `body_html` is not minified and will produce extra blank lines throughout rendered articles.

The `pre-wrap` value is correct for the plain-text fallback path (`articleBody.textContent = result.body`) but incorrect for the HTML path.

**Fix:** Add a class toggle in `openArticle` so CSS can distinguish the two rendering modes:

```javascript
// in openArticle:
if (htmlContent) {
  articleBody.classList.add("html-mode");
  articleBody.innerHTML = htmlContent;
} else {
  articleBody.classList.remove("html-mode");
  articleBody.textContent = result.body || "No content available.";
}
```

```css
#article-body          { white-space: pre-wrap; }  /* plain-text fallback */
#article-body.html-mode { white-space: normal;   }  /* HTML rendering path */
```

---

### WR-04: `word_count` sort clause has no `missing` parameter

**File:** `nitrofind/search/query_builder.py:221`

**Issue:** The `date` sort clause explicitly handles missing values:

```python
{"published_at": {"order": "desc", "missing": "_last", "unmapped_type": "date"}}
```

The `size` sort on `word_count` does not:

```python
{"word_count": {"order": "desc"}}
```

Documents that lack a `word_count` field sort in an undefined position (ES default for numeric fields is `_last` for `desc`, but this is not guaranteed across all ES versions and is not explicit in the code). If documents scraped before `word_count` was added to the schema reach the sort path, their ordering is unspecified.

**Fix:**

```python
if sort == "size":
    return [{"word_count": {"order": "desc", "missing": "_last", "unmapped_type": "long"}}]
```

---

### WR-05: Warmup polling `setInterval` never terminates if ES stays unhealthy

**File:** `static/js/app.js:272-286`

**Issue:** `startWarmupPolling` creates an interval that polls `/api/status` every 2 seconds with no maximum iteration count or timeout. If ES never becomes healthy (disk full, JVM OOM, corrupted index), the interval runs forever — one loopback fetch every 2 seconds for the lifetime of the browser tab. The Python-side `_es_health_poller` has a hard 180-second deadline (server.py:269), after which it logs a warning and exits without ever setting `state["ready"] = True`. The JS poller has no corresponding deadline and will continue polling a permanently-503 endpoint indefinitely.

**Fix:** Add a bounded poll count:

```javascript
function startWarmupPolling() {
  const MAX_POLLS = 120;          // 120 × 2 s = 4 minutes
  let pollCount = 0;
  ...
  const pollId = setInterval(async () => {
    if (++pollCount > MAX_POLLS) {
      clearInterval(pollId);
      statusLine.textContent = "ES failed to start. Restart the application.";
      statusLine.style.opacity = "1";
      return;
    }
    ...
  }, 2000);
}
```

---

### WR-06: `search-input` and `search-input-results` never synchronized

**File:** `static/js/app.js:47-48, 87-88`

**Issue:** The two search inputs are independent. When a user types "Ferrari" in the home `search-input`, transitions to the results view, and sees the results, `search-input-results` is empty. If the user then types a different query in `search-input-results` and presses Escape, the home view shows `search-input` still containing "Ferrari" while `currentQuery` is now the new term. Conversely, if the user clears `search-input-results` (clearing triggers `handleSearchInput` which calls `transitionTo("home")`), the home input still shows the old query.

**Fix:** Keep the two inputs synchronized in `handleSearchInput`:

```javascript
function handleSearchInput(input) {
  clearTimeout(debounceTimer);
  const q = input.value.trim();
  // Sync the other input
  const other = input === searchInput ? searchInputResults : searchInput;
  other.value = input.value;
  if (!q) {
    transitionTo("home");
    return;
  }
  debounceTimer = setTimeout(() => runSearch(q), DEBOUNCE_MS);
}
```

And in the Escape handler, both inputs are already cleared (lines 254-255), so the handler is correct.

---

## Info

### IN-01: `filterCountry` uses `change` event — requires blur to apply filter

**File:** `static/js/app.js:217`

**Issue:** `filterCountry.addEventListener("change", onFilterChange)` fires only when focus leaves the input, not on each keystroke. The comment on the year inputs says this is "Pitfall 4: change not input" to avoid triggering search on a partial year like "196". The rationale applies correctly to number inputs but not to a text field: a user typing "Germany" and expecting the filter to apply must click away from the field. The era and body selects use `change` correctly since they are dropdowns. A text filter input expecting a complete country name is more usable with a debounced `input` handler.

**Fix:** Replace `change` with a debounced `input` listener on `filterCountry`:

```javascript
filterCountry.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    currentFilters.country = filterCountry.value;
    if (currentQuery) runSearch(currentQuery);
  }, DEBOUNCE_MS);
});
```

---

### IN-02: `api_status` returns plain dict; `api_search` uses `jsonify()` — inconsistent serialization

**File:** `nitrofind/server.py:89`, `nitrofind/server.py:201`

**Issue:** `api_status` returns `{"status": "starting"}, 503` and `{"status": "ok", ...}, 200` as plain Python dicts. Flask auto-serializes these in Flask 2+. `api_search` explicitly calls `jsonify(...)`. Both work, but using two different styles in the same module is inconsistent and makes the auto-serialization behavior non-obvious to a reader of `api_status`.

**Fix:** Use `jsonify` consistently:

```python
return jsonify({"status": "starting"}), 503
```

---

### IN-03: Server-side year params accept out-of-range values

**File:** `nitrofind/server.py:127-144`

**Issue:** `_safe_int_param` validates that the raw string is a valid integer but does not check range. Values like `-5`, `0`, or `99999` pass through and generate range clauses against `production_start` / `production_end`. `year_from=0` emits `production_end >= 0`, which matches every document. While the HTML inputs have `min="1900" max="2099"` attributes (client-side only), a direct API call bypasses them entirely.

**Fix:** Clamp to a reasonable range in `_safe_int_param` or in `build_filter_clauses`:

```python
def _safe_int_param(raw: str | None, min_val: int = 1885, max_val: int = 2099) -> int | None:
    if not raw:
        return None
    try:
        v = int(raw)
        if not (min_val <= v <= max_val):
            return None
        return v
    except ValueError:
        return None
```

(1885 chosen as the year of the Benz Patent-Motorwagen — before that, no production cars exist in the corpus.)

---

_Reviewed: 2026-07-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
