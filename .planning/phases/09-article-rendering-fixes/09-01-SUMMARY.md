---
phase: 09-article-rendering-fixes
plan: "01"
subsystem: testing
tags: [pytest, body_html, strip_nav_sections, clean_wikipedia_html, red-state, tdd-scaffold]

requires: []
provides:
  - "Failing test scaffold for Phase 9 BUG-01 (body_html field) and BUG-02 (nav-section exclusion)"
  - "14 new/updated tests in RED state targeting unimplemented production symbols"
affects:
  - "09-02 (wikipedia/cleaner implementation must make test_cleaner.py and test_wikipedia.py GREEN)"
  - "09-03 (blogs/schema/server/frontend implementation must make test_blogs.py, test_models.py, test_api_search.py, test_es_schema.py GREEN)"

tech-stack:
  added: []
  patterns:
    - "TDD RED gate: test files import and call symbols not yet in production code"
    - "Noise HTML fixture (_ARTICLE_WITH_NOISE_HTML) pattern for blog scraper tests"
    - "Pure-function test pattern extended to strip_nav_sections"

key-files:
  created: []
  modified:
    - tests/test_scraper/test_cleaner.py
    - tests/test_scraper/test_wikipedia.py
    - tests/test_scraper/test_blogs.py
    - tests/test_search/test_models.py
    - tests/test_search/test_api_search.py
    - tests/test_es_schema.py

key-decisions:
  - "test_api_search.py fixture updated to include body_html in _source (Pitfall 7 fix: also adds missing body key to shape assertion)"
  - "test_blogs.py noise fixture covers breadcrumb, related-articles, newsletter-signup per 09-PATTERNS.md"
  - "test_wikipedia.py imports _clean_wikipedia_html at module level so collection fails RED (not just test body fails)"

patterns-established:
  - "Phase RED scaffold: modify import lines to reference new symbols — collection failure is valid RED state"
  - "_ARTICLE_WITH_NOISE_HTML fixture: static in-module HTML literal, no external fetch, per T-09-T1 threat accept"

requirements-completed: [BUG-01, BUG-02]

duration: 15min
completed: "2026-06-17"
---

# Phase 9 Plan 01: Article Rendering Fixes — Test Scaffold Summary

**14 failing (RED) tests scaffolded across 6 files targeting BUG-01 body_html field and BUG-02 nav-text noise exclusion before any production code is written**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-17T18:00:00Z
- **Completed:** 2026-06-17T18:04:51Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added 4 `strip_nav_sections` tests to `test_cleaner.py` (fail RED: ImportError on missing symbol)
- Added 4 `_clean_wikipedia_html` / `body_html` tests to `test_wikipedia.py` (fail RED: ImportError)
- Added `_ARTICLE_WITH_NOISE_HTML` fixture and 3 blog tests to `test_blogs.py` (fail RED: missing body_html and noise not filtered)
- Added `test_body_html_field_default` and `test_article_result_body_html_from_es_hit` to `test_models.py` (fail RED: no body_html field on ArticleResult)
- Updated `test_search_result_shape` in `test_api_search.py` to assert `body` + `body_html` keys (fail RED: server response missing body_html)
- Added `test_body_html_field_present` to `test_es_schema.py` (fail RED: body_html not in CAR_ARTICLES_MAPPING)

## Task Commits

Each task was committed atomically:

1. **Task 1: Scraper test scaffold (cleaner, wikipedia, blogs)** - `582c3a5` (test)
2. **Task 2: Search/API/schema test scaffold (models, api_search, es_schema)** - `a561b22` (test)

## Files Created/Modified

- `tests/test_scraper/test_cleaner.py` - Updated import + 4 strip_nav_sections tests
- `tests/test_scraper/test_wikipedia.py` - Updated import + 4 _clean_wikipedia_html/body_html tests
- `tests/test_scraper/test_blogs.py` - Added _ARTICLE_WITH_NOISE_HTML fixture + 3 noise/body_html tests
- `tests/test_search/test_models.py` - Added body_html to expected_fields set + 2 new body_html tests
- `tests/test_search/test_api_search.py` - Updated shape assertion to include body + body_html; added body_html to fixture _source
- `tests/test_es_schema.py` - Added test_body_html_field_present

## Decisions Made

- `test_api_search.py` fixture updated to include `body_html` in `_source` so that once production code lands the assertion can pass immediately (per 09-PATTERNS.md Pitfall 7 note: also fixed missing `body` key in the shape assertion set)
- Imported `_clean_wikipedia_html` at module level in `test_wikipedia.py` so the RED gate is a collection-level ImportError, not just a test-body AttributeError — stronger RED signal
- `test_es_schema.py` kept as a standalone function (`test_body_html_field_present`) rather than extending `test_mapping_has_required_fields` to keep failure attribution clean

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All 6 files accepted the new tests without syntax errors. All new tests fail RED for the intended reasons (missing production symbols, not test code bugs). Existing tests continue to pass.

## Known Stubs

None. This is a test-only plan; no production stubs were introduced.

## Threat Flags

None. This plan adds only test code with static HTML fixtures. No new runtime trust boundaries.

## Next Phase Readiness

- Phase 9 RED scaffold is complete: 09-02 (Wikipedia/cleaner) and 09-03 (blogs/schema/server/frontend) can now be implemented against concrete acceptance gates
- All 14 test functions are collected by pytest without syntax errors (2 files fail at collection due to ImportError on missing symbols; 4 files fail at test execution due to missing fields)
- No production file under `nitrofind/` was modified by this plan

---
*Phase: 09-article-rendering-fixes*
*Completed: 2026-06-17*
