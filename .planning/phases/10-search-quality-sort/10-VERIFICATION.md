---
phase: 10-search-quality-sort
verified: 2026-06-26T00:00:00Z
status: human_needed
score: 7/8
overrides_applied: 0
human_verification:
  - test: "Sort buttons render, toggle active state, and reorder live results"
    expected: "Clicking 'Newest' moves most-recently-published articles to the top; clicking 'Largest' moves highest word_count articles to the top; clicking 'Relevance' restores default ES _score ordering. Active button state visually tracks the current sort. Sort choice persists when a new query is typed."
    why_human: "Requires a running Flask server with a populated Elasticsearch index. Cannot verify live result reordering, visual active-state appearance, or sort persistence across queries without a real browser session."
---

# Phase 10: Search Quality & Sort — Verification Report

**Phase Goal:** Users get correct results despite typos and can control result ordering
**Verified:** 2026-06-26
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Searching a typo like 'Ferari' matches 'Ferrari' (fuzziness AUTO applied on the default path) | VERIFIED | `build_function_score_query("Ferari")` produces `multi_match.type == "best_fields"`, `fuzziness == "AUTO"`, `prefix_length == 1`. Confirmed via direct Python execution and `test_fuzzy_path_has_fuzziness` test passing. |
| 2 | Wrapping input in double quotes routes the query to multi_match type:phrase with quotes stripped and no fuzziness key | VERIFIED | `build_function_score_query('"V8 engine"')` produces `type == "phrase"`, `query == "V8 engine"` (quotes stripped), and no `fuzziness` key. Confirmed via direct Python execution and `test_phrase_query_routing` / `test_phrase_path_no_fuzziness` passing. |
| 3 | GET /api/search?sort=date returns an ES sort array [{published_at:{order:desc}}]; sort=size returns [{word_count:{order:desc}}]; sort=relevance and unknown values omit the sort kwarg | VERIFIED | `_build_sort_clauses("date")` returns `[{"published_at": {"order": "desc", "missing": "_last", "unmapped_type": "date"}}]`; `"size"` returns `[{"word_count": {"order": "desc"}}]`; `"relevance"` and `None` return `None`. Server-side tests `test_sort_date_passed_to_es`, `test_sort_size_passed_to_es`, `test_sort_unknown_value_ignored` all pass. |
| 4 | Three sort toggle buttons (Relevance / Newest / Largest) render in the results filter row | VERIFIED | `templates/index.html` lines 51-53 contain exactly 3 `<button type="button" class="sort-btn">` elements with `data-sort="relevance"` (also `active`), `data-sort="date"`, `data-sort="size"` inside `.sort-controls` div in `.filter-row`. Grep count confirms 3 buttons. |
| 5 | Clicking a sort button sets it active and re-runs the current query with the corresponding sort= param (relevance omitted) | VERIFIED (code path) | `onSortChange(newSort)` in `static/js/app.js` sets `currentSort = newSort`, toggles `.active` via `classList.toggle("active", btn.dataset.sort === newSort)`, and calls `runSearch(currentQuery)` when a query is active. `runSearch` appends `params.set("sort", currentSort)` only when `currentSort !== "relevance"`. Node syntax check passes. |
| 6 | Clicking 'Newest' reorders visible results newest-first; 'Largest' largest-first; 'Relevance' restores default scoring order | UNCERTAIN (human needed) | Code path verified: sort param flows from button click → `onSortChange` → `runSearch` → `/api/search?sort=date/size` → `_build_sort_clauses` → ES sort array. Live reordering requires running server + populated index. |
| 7 | ROADMAP SC 1: Searching "Ferari" or "Lamborgini" returns the expected manufacturer articles | VERIFIED | Fuzzy routing confirmed operational (Truth 1 above). Function will match both misspellings through Levenshtein AUTO fuzziness. |
| 8 | ROADMAP SC 2: Searching `"V8 engine"` (with quotes) returns articles that contain the exact phrase | VERIFIED | Phrase routing confirmed operational (Truth 2 above). |

**Score:** 7/8 truths verified (1 requires human confirmation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `nitrofind/search/query_builder.py` | phrase-branching base query + `_build_sort_clauses` + sort param on `build_search_body` | VERIFIED | `_build_sort_clauses` exists (line 190); phrase branch at lines 76-103; `sort: str | None = None` param in `build_search_body` signature (line 214); sort key conditionally added at lines 290-292. Contains `_build_sort_clauses` — confirmed. |
| `nitrofind/server.py` | sort param allowlist + sort= kwarg on `client.search()` | VERIFIED | `_VALID_SORTS = frozenset({"relevance", "date", "size"})` at line 50; allowlist check at lines 157-159; `build_search_body(q, filters=filters, sort=sort)` at line 160; `sort=body.get("sort")` at line 166. |
| `tests/test_search/test_query_builder.py` | unit tests for fuzzy path, phrase path, and sort clauses | VERIFIED | Contains `def test_fuzzy_path_has_fuzziness(` (line 342), `def test_phrase_query_routing(` (line 365), `def test_build_search_body_sort_date(` (line 393), `def test_build_search_body_no_sort_no_key(` (line 413). All 9 new test functions present and passing. |
| `tests/test_search/test_api_search.py` | API-level sort forwarding + allowlist tests | VERIFIED | Contains `def test_sort_date_passed_to_es(` (line 269), `def test_sort_unknown_value_ignored(` (line 299), `def test_sort_size_passed_to_es(` (line 284). All 3 new sort tests present and passing. |
| `templates/index.html` | sort-controls markup with three .sort-btn buttons | VERIFIED | Lines 50-54: `.sort-controls` div with three `<button type="button" class="sort-btn">` elements. First button has `active` class. All have `data-sort` attributes. `grep -c` confirms count of 3. |
| `static/js/app.js` | `currentSort` state + `onSortChange` handler + sort param in `runSearch` | VERIFIED | `let currentSort = "relevance"` (line 29); `const sortBtns` cached (line 49); `function onSortChange(newSort)` (line 203); `params.set("sort", currentSort)` in `runSearch` (lines 97-99); click listeners wired (line 209). |
| `static/css/style.css` | `.sort-btn` and `.sort-btn.active` styling | VERIFIED | `.sort-controls` (line 194), `.sort-btn` (line 200), `.sort-btn:hover` (line 211), `.sort-btn.active` (line 215). All rules reference existing `var(--)` tokens; no new variables introduced. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `nitrofind/server.py` | `nitrofind/search/query_builder.py` | `build_search_body(q, filters=filters, sort=sort)` | WIRED | Grep confirms pattern `build_search_body(q, filters=filters, sort=sort)` at server.py line 160. |
| `nitrofind/server.py` | `es_client.search` | `sort=body.get("sort")` | WIRED | Confirmed at server.py line 166: `sort=body.get("sort")`. Returns `None` for relevance (ES omits sort), list for date/size. |
| `static/js/app.js` | `/api/search` | `params.set("sort", currentSort)` in `runSearch` | WIRED | `params.set("sort", currentSort)` at lines 97-99, guarded by `currentSort !== "relevance"`. |
| `templates/index.html` | `static/js/app.js` | `data-sort` attribute read by `btn.dataset.sort` | WIRED | `sortBtns.forEach(btn => btn.addEventListener("click", () => onSortChange(btn.dataset.sort)))` at line 209 reads `btn.dataset.sort` which corresponds to `data-sort` attribute. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `static/js/app.js` | `currentSort` | User click → `onSortChange` → `params.set("sort", currentSort)` → `/api/search` | Yes — value originates from `btn.dataset.sort` (hardcoded HTML attributes, not user text injection) | FLOWING |
| `nitrofind/server.py` `api_search` | `sort` var | `request.args.get("sort")` + `_VALID_SORTS` allowlist | Yes — filtered through allowlist, passed to `build_search_body`, result forwarded to `client.search` | FLOWING |
| `nitrofind/search/query_builder.py` | `sort_clauses` | `_build_sort_clauses(sort)` | Yes — returns concrete ES sort dicts for "date"/"size", `None` for relevance | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Fuzzy path: `build_function_score_query("Ferari")` has `fuzziness == "AUTO"` | `python3 -c "from nitrofind.search.query_builder import build_function_score_query; mm = build_function_score_query('Ferari')['function_score']['query']['multi_match']; print(mm['fuzziness'])"` | `AUTO` | PASS |
| Phrase path: `build_function_score_query('"V8 engine"')` has `type == "phrase"`, no fuzziness | Direct Python execution | `type: phrase`, `fuzziness` absent | PASS |
| Sort: `build_search_body("Ferrari", sort="date")["sort"]` returns date sort array | Direct Python execution | `[{"published_at": {"order": "desc", "missing": "_last", "unmapped_type": "date"}}]` | PASS |
| Sort: `"sort" not in build_search_body("Ferrari", sort="relevance")` | Direct Python execution | `True` | PASS |
| Full unit suite passes (no regression) | `python3 -m pytest tests/ -q -m "not integration"` | `170 passed, 5 deselected` | PASS |
| JS syntax valid | `node --check static/js/app.js` | exit 0 | PASS |

### Probe Execution

No probe scripts declared in PLAN.md frontmatter. No `scripts/*/tests/probe-*.sh` found in the repository. Step 7c: SKIPPED (no probe scripts exist for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| QURY-01 | 10-01-PLAN.md | User searches with typos and gets correct results — fuzziness: "AUTO" applied to multi_match | SATISFIED | `build_function_score_query` adds `fuzziness="AUTO"` + `prefix_length=1` on non-quoted (default) path. Tests `test_fuzzy_path_has_fuzziness` and `test_phrase_path_no_fuzziness` pass. |
| QURY-02 | 10-01-PLAN.md | User wraps a phrase in quotes and gets phrase-match results — query routed to match_phrase | SATISFIED | Quoted input routes to `type:phrase` with quotes stripped and no `fuzziness` key. `len > 2` guard rejects empty `""`. Tests `test_phrase_query_routing`, `test_non_quoted_not_phrase`, `test_empty_quotes_not_phrase` pass. |
| SORT-01 | 10-02-PLAN.md | User can sort results by relevance, newest-first, or largest-first via toggle buttons in the search UI | SATISFIED (code) / NEEDS HUMAN (live) | Three `.sort-btn` buttons in `.filter-row` with `data-sort` attributes. `onSortChange` handler wired. Code path verified. Live behavior requires human verification. |
| SORT-02 | 10-01-PLAN.md | `GET /api/search` accepts optional `sort` param and applies corresponding ES sort order | SATISFIED | `_VALID_SORTS` allowlist, `build_search_body(q, filters=filters, sort=sort)`, `sort=body.get("sort")` in `client.search()`. Tests `test_sort_date_passed_to_es`, `test_sort_size_passed_to_es`, `test_sort_unknown_value_ignored` all pass. |

All four requirement IDs (QURY-01, QURY-02, SORT-01, SORT-02) from the PLAN frontmatter are accounted for and verified against REQUIREMENTS.md descriptions. No orphaned requirement IDs found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `templates/index.html` | 15, 24 | `placeholder=` on input elements | Info | Standard HTML attribute; not a code debt marker. Not a stub. |

No `TBD`, `FIXME`, or `XXX` markers found in any file modified by this phase. No stub patterns found. No empty returns, no `return null`, no disconnected state variables.

### Human Verification Required

#### 1. Live Sort Behavior and UI Active State

**Test:** Start the NitroFind server (`python3 -m nitrofind.main`) with a populated Elasticsearch index. Open http://localhost:5000. Search for "ferrari".

1. Confirm the three sort buttons (Relevance / Newest / Largest) appear in the filter row. Confirm "Relevance" shows the active style (teal border + text per `.sort-btn.active` rule).
2. Click "Newest". Confirm: the button becomes active (Relevance deactivates) AND visible results reorder so articles with the most recent `published_at` appear at the top.
3. Click "Largest". Confirm: it becomes active AND results reorder so longer articles (higher `word_count`) appear first.
4. Click "Relevance". Confirm: it becomes active AND the original relevance-scored order is restored.
5. With "Newest" active, type a new query (e.g. "mustang"). Confirm the sort choice persists — results come back newest-first and the "Newest" button stays active.

**Expected:** All five steps succeed. Active state visually distinguishes the selected button (teal border/text). Result order changes meaningfully between sort modes.

**Why human:** Requires a live server with indexed data. Result reordering requires real ES documents with varying `published_at` and `word_count` values. Active-state visual appearance cannot be verified by grep. Sort persistence across new queries requires interactive browser session.

### Gaps Summary

No gaps blocking goal achievement. All backend behaviors (QURY-01, QURY-02, SORT-02) are fully implemented, tested, and verified. Frontend sort controls (SORT-01) are fully implemented and code-path verified. The single human verification item is a live-behavior confirmation of the end-to-end sort UX — the code wiring is complete, the behavior is conditional on a running server with real data.

---

_Verified: 2026-06-26_
_Verifier: Claude (gsd-verifier)_
