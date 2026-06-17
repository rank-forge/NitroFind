---
phase: 09-article-rendering-fixes
plan: "03"
subsystem: search
tags: [elasticsearch, flask, javascript, css, pyqt6]

requires:
  - phase: 09-01
    provides: RED-state tests for body_html field in models, api_search shape, and query _source

provides:
  - ArticleResult.body_html dataclass field + from_es_hit mapping
  - body_html in build_search_body() _source list
  - body_html key in _result_to_api_dict() API response
  - openArticle() renders body_html via innerHTML with plain-text body fallback
  - "#article-body table" CSS rules for legible Wikipedia/blog table rendering

affects: [09-04, search-read-path, article-view-rendering]

tech-stack:
  added: []
  patterns:
    - "body_html preference with body fallback in openArticle() — same pattern as excerpt.innerHTML (D-10)"
    - "ES _source field added alongside body; body remains the searchable field, body_html is index:false display-only"

key-files:
  created: []
  modified:
    - nitrofind/search/models.py
    - nitrofind/search/query_builder.py
    - nitrofind/server.py
    - static/js/app.js
    - static/css/style.css
    - tests/test_search/test_query_builder.py

key-decisions:
  - "Use innerHTML for body_html rendering — intentional, matches excerpt.innerHTML precedent; scraper strips script/style/on* before storing; local offline single-user app (near-zero XSS surface)"
  - "white-space: normal override inside #article-body table to prevent pre-wrap from breaking table cell text"
  - "Table CSS uses existing --border and --bg-surface tokens — no new color values"

patterns-established:
  - "Pattern: body_html field threaded from ES _source through ArticleResult → API → browser via same .get() default-empty-string pattern as body field"

requirements-completed: [BUG-01]

duration: 11min
completed: 2026-06-17
---

# Phase 09 Plan 03: Article Rendering Fixes — Display Path Summary

**body_html threaded from Elasticsearch _source through ArticleResult, Flask API, and into the browser article view via innerHTML, with #article-body table CSS for legible Wikipedia table rendering**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-17T18:00:00Z
- **Completed:** 2026-06-17T18:11:23Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `body_html: str = ""` field to `ArticleResult` dataclass and `from_es_hit()` mapping, making the scraper's stored HTML available throughout the read path
- Added `"body_html"` to the `_source` list in `build_search_body()` so ES returns the field in search hits
- Added `"body_html": result.body_html` to `_result_to_api_dict()` so GET /api/search includes the field for every result
- Switched `openArticle()` in app.js from `articleBody.textContent` to conditional `innerHTML`/`textContent` — prefers `body_html`, falls back to plain `body` for pre-Phase-9 articles
- Added `#article-body table`, `#article-body th`, `#article-body td` CSS rules with `border-collapse`, `border`, `padding`, and header background using existing CSS tokens

## Task Commits

Each task was committed atomically:

1. **Task 1: body_html through model + query _source + API response** - `bcc885d` (feat)
2. **Task 2: article view innerHTML rendering + table CSS** - `93833fc` (feat)

## Files Created/Modified

- `nitrofind/search/models.py` — Added `body_html: str = ""` field and `body_html=src.get("body_html", "")` in `from_es_hit()`
- `nitrofind/search/query_builder.py` — Added `"body_html"` to `_source` list in `build_search_body()`
- `nitrofind/server.py` — Added `"body_html": result.body_html` to `_result_to_api_dict()` return dict
- `static/js/app.js` — Replaced `articleBody.textContent` assignment with conditional `innerHTML`/`textContent` in `openArticle()`
- `static/css/style.css` — Added `#article-body table`, `th`, `td` rules for legible table rendering
- `tests/test_search/test_query_builder.py` — Updated `test_build_search_body_source_fields` to expect `body_html` in `_source` list (auto-fix, Rule 1)

## Decisions Made

- `innerHTML` is used intentionally for `body_html` rendering. This matches the existing `excerpt.innerHTML` precedent (D-10). The scraper (09-02) strips `<script>`, `<style>`, and `on*` event handler attributes before storing. NitroFind is a local single-user offline application — no remote submitter, no server-side execution — making the XSS risk near-zero per the threat model in 09-RESEARCH.md.
- Added `white-space: normal` override scoped to `#article-body table` to prevent the outer `pre-wrap` setting from breaking table cell text layout.
- Table CSS uses existing design token `--border` and `--bg-surface` only — no new raw hex values, matching project CSS convention.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale test_build_search_body_source_fields assertion**
- **Found during:** Task 2 (overall verification run)
- **Issue:** `tests/test_search/test_query_builder.py::test_build_search_body_source_fields` asserted the old `_source` list without `"body_html"`. After Task 1 added `"body_html"` to the list, this test failed with an AssertionList mismatch.
- **Fix:** Updated the `expected_source` list in the test to include `"body_html"` after `"body"`, matching the new production code.
- **Files modified:** `tests/test_search/test_query_builder.py`
- **Verification:** Full test_search suite passed (80/80 tests, 3 deselected for integration marker)
- **Committed in:** `93833fc` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — stale test assertion)
**Impact on plan:** Auto-fix essential for test correctness. No scope creep — the test was simply stale relative to the new `_source` field added by this plan.

## Issues Encountered

None — all changes were straightforward additive modifications following patterns documented in 09-PATTERNS.md.

## Known Stubs

None — body_html is fully wired from ES _source through ArticleResult to the API and browser. The field will be empty for articles scraped before Phase 9 (before 09-02 runs), but the fallback to plain `body` handles that gracefully.

## Threat Flags

No new threat surface introduced beyond what the plan's threat model already covers. The `body_html` field in the API response is the same article content already exposed via `body` (T-09-03-I1: accept). The `innerHTML` assignment is mitigated by scraper-side stripping (T-09-03-T1: mitigate — matching D-10 decision).

## Next Phase Readiness

- The read path (models, query builder, server, frontend) is fully wired for body_html
- Phase 09-02 (scraper changes to produce body_html) and 09-04 (ES schema + index recreation) will complete the pipeline
- Until 09-02 and 09-04 run and data is re-scraped, body_html will be empty for all existing articles and the plain-text fallback will engage

## Self-Check

- [x] `nitrofind/search/models.py` — body_html field present
- [x] `nitrofind/search/query_builder.py` — body_html in _source list
- [x] `nitrofind/server.py` — body_html in _result_to_api_dict
- [x] `static/js/app.js` — innerHTML assignment present
- [x] `static/css/style.css` — #article-body table rule present
- [x] Task 1 commit `bcc885d` exists in git log
- [x] Task 2 commit `93833fc` exists in git log

## Self-Check: PASSED

---
*Phase: 09-article-rendering-fixes*
*Completed: 2026-06-17*
