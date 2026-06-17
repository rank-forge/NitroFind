---
phase: 09-article-rendering-fixes
plan: "04"
subsystem: scraper
tags: [elasticsearch, scraper, integration, re-index, human-verify]

requires:
  - phase: 09-02
    provides: --recreate flag, body_html scraper pipeline
  - phase: 09-03
    provides: display path (ArticleResult, API, frontend) wired for body_html

provides:
  - Full non-integration test suite verified green (158 passed)
  - Operator instructions for ES re-index (ES unavailable in CI/executor environment)
  - Human checkpoint pending: BUG-01 and BUG-02 visual verification in running UI

affects: [car_articles-index, body_html-field, re-scrape]

tech-stack:
  added: []
  patterns:
    - "ES-unavailable path: scraper exits cleanly with log message when localhost:9200 unreachable"

key-files:
  created:
    - .planning/phases/09-article-rendering-fixes/09-04-SUMMARY.md
  modified: []

key-decisions:
  - "ES re-index is an operator step — requires running Elasticsearch on localhost:9200 before scraper can drop/rebuild index"
  - "Test suite (158/158 non-integration) confirms Phase 9 pipeline code is correct; live verification gated on human-verify checkpoint"

requirements-completed: []

duration: 2min
completed: 2026-06-17
---

# Phase 09 Plan 04: Article Rendering Fixes — Index Recreation and Human Verification Summary

**Full non-integration test suite is green (158 passed). Elasticsearch was not running in the executor environment; re-index and re-scrape are documented as operator steps. Human checkpoint required for BUG-01 and BUG-02 visual sign-off.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-17T18:19:23Z
- **Completed:** 2026-06-17T18:20:46Z
- **Tasks:** 1 of 2 complete (Task 2 pending human-verify)
- **Files modified:** 0

## Accomplishments

### Task 1: Full suite green + re-create index + re-scrape corpus

**Test suite:** `python3 -m pytest tests/ -m "not integration" -q` — **158 passed, 5 deselected** (integration-only tests excluded). Exit code 0.

**Phase 9 tests passing (key coverage):**
- `test_es_schema.py::test_body_html_field_present` — body_html field in CAR_ARTICLES_MAPPING
- `test_scraper/test_cleaner.py::test_strip_nav_sections_removes_references` — BUG-02 Wikipedia nav stripping
- `test_scraper/test_cleaner.py::test_strip_nav_sections_removes_external_links` — BUG-02 Wikipedia nav stripping
- `test_scraper/test_cleaner.py::test_strip_nav_sections_preserves_content_headings` — prose headings retained
- `test_scraper/test_wikipedia.py::test_clean_wikipedia_html_preserves_tables` — BUG-01 Wikipedia table preservation
- `test_scraper/test_wikipedia.py::test_clean_wikipedia_html_removes_navboxes` — navbox removal
- `test_scraper/test_wikipedia.py::test_fetch_and_build_doc_returns_body_html` — body_html key in scraper output
- `test_scraper/test_blogs.py::test_doc_has_body_html_field` — BUG-01 blog body_html
- `test_scraper/test_blogs.py::test_breadcrumb_excluded_from_body` — BUG-02 blog noise removal
- `test_scraper/test_blogs.py::test_related_articles_excluded_from_body` — BUG-02 blog noise removal
- `test_search/test_models.py::test_body_html_field_default` — ArticleResult.body_html field
- `test_search/test_models.py::test_article_result_body_html_from_es_hit` — from_es_hit mapping

**ES re-index (ES-unavailable path):**

Elasticsearch was not running on localhost:9200 in this execution environment. `PYTHONPATH=. python3 scripts/scraper.py --recreate --all` attempted to connect and exited with:

```
Cannot reach Elasticsearch at http://localhost:9200: ConnectionError: Connection error caused by: ConnectionError(...)
```

Exit code: 1. The scraper handles ES unavailability gracefully — it logs the error and exits without an unhandled Python exception. This is the documented ES-unavailable path per the plan's acceptance criteria.

**Operator steps (manual, requires live Elasticsearch):**

To complete the re-index and re-scrape:
1. Ensure Elasticsearch 8.x is running on localhost:9200 (start via `ES_HOME/bin/elasticsearch` or `python3 main.py`)
2. Run: `PYTHONPATH=. python3 scripts/scraper.py --recreate --all`
3. Verify body_html landed: `curl -s 'localhost:9200/car_articles/_search?size=1&_source=title,body_html' | python3 -c "import sys,json; d=json.load(sys.stdin); src=d['hits']['hits'][0]['_source']; print('HAS_BODY_HTML' if src.get('body_html') else 'MISSING'); print(src.get('title'))"`
4. Verify mapping: `curl -s 'localhost:9200/car_articles/_mapping' | grep -q body_html && echo MAPPING_OK`

## Task Commits

1. **Task 1: Full suite green + ES-unavailable path documented** — `pending` (committed with SUMMARY)

## Files Created/Modified

None — this plan exercises existing code from 09-02 and 09-03. No source files modified.

## Decisions Made

- ES re-index is an operator step: Elasticsearch is not available in the CI/executor environment. The scraper gracefully handles this case. The re-index must be run by the operator with a live ES node.
- All Phase 9 code changes (09-01 through 09-03) are verified correct via the 158-test non-integration suite. The gap is purely operational (live ES required for index recreation and live UI verification).

## Deviations from Plan

None — plan anticipated the ES-unavailable path explicitly in the acceptance criteria and action block ("If ES cannot be started in this environment, report that and convert this task to operator instructions in the SUMMARY"). This is followed exactly.

## Task 2: PENDING (checkpoint:human-verify)

Task 2 requires visual inspection of the running UI after the operator has:
1. Started Elasticsearch
2. Run `python3 scripts/scraper.py --recreate --all`
3. Started the app (`python3 main.py`)

The human must verify:
- BUG-01 (tables render) for both a Wikipedia article (Ferrari 308) and a Hagerty article
- BUG-02 (no nav text) for both sources
- Fallback: pre-Phase-9 articles without body_html still show plain-text body (not empty pane)

## Known Stubs

None — the code pipeline is complete. `body_html` will be populated after the operator runs the re-scrape. Until then, the fallback to plain `body` is active for all existing articles.

## Threat Flags

No new threat surface. T-09-04-T1 (stored XSS via body_html) is mitigated by scraper-side stripping implemented in 09-02 (confirmed passing via test suite).

## Self-Check

- [x] `python3 -m pytest tests/ -m "not integration" -q` → 158 passed, 5 deselected (exit 0)
- [x] All Phase 9-specific tests passing (strip_nav_sections, clean_wikipedia_html, body_html fields, breadcrumb/related exclusion, API shape)
- [x] Scraper --recreate attempt documented (ES-unavailable path, exit code 1, graceful error log)
- [x] Operator instructions included for live ES re-index
- [x] Task 2 checkpoint details documented

## Self-Check: PASSED

---
*Phase: 09-article-rendering-fixes*
*Completed (partial — Task 2 pending human-verify): 2026-06-17*
