---
phase: 02-data-pipeline-scraper-indexer
plan: "04"
subsystem: scraper-blogs
tags: [scraper, blogs, beautifulsoup4, tdd, wave-1, bs4, requests, pitfall-3, pitfall-4]
dependency_graph:
  requires: [02-01, 02-02]
  provides: [blog-scraper]
  affects: [02-05]
tech_stack:
  added: []
  patterns:
    - bs4-lxml-noise-removal (script/style/nav/footer/aside/.ad decompose before get_text)
    - requests-session-honest-ua (HONEST_USER_AGENT module constant, no Mozilla/)
    - fallback-chain-on-403 (first-winner across enabled targets, Pitfall 3)
    - config-driven-selectors (article_selector/listing_selector from YAML, Pitfall 4)
    - url-slug-article-id (last path segment; SHA-1 fallback for no-segment URLs)
    - caplog-fixture-warning-assertion (pytest caplog at WARNING level)
key_files:
  created:
    - nitrofind/scraper/blogs.py
    - tests/test_scraper/test_blogs.py (replaced Wave 0 stubs)
  modified: []
decisions:
  - "task 1 approved with hagerty, caranddriver, and hemmings all enabled=true and VERIFIED 2026-05-14 selectors in config/scraper.yaml"
  - "blogs.py _fetch_article_urls returns list[str] not Optional[list[str]] internally — None signals listing failure (fallback chain); empty list is valid (no articles found on listing page)"
  - "test mock session injected via scraper._session = mock_session after construction (per plan spec — avoids messy patch.object on instance attribute)"
  - "HONEST_USER_AGENT declared as module-level constant; config/scraper.yaml blogs.headers Mozilla UA is intentionally NOT read by BlogScraper (as specified in checkpoint state)"
metrics:
  duration: "~15m"
  completed: "2026-05-15T16:17:42Z"
  tasks_completed: 2
  tasks_total: 3
  files_created: 1
  files_modified: 1
---

# Phase 02 Plan 04: Blog Scraper Summary

**One-liner:** BlogScraper with BS4/lxml noise removal, graceful HTTP 403 fallback chain across enabled targets, config-driven CSS selectors, honest User-Agent, and 8 unit tests covering Pitfall 3/4/L-05/D-06; 51-test full suite green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Manual blog inspection — APPROVED (developer) | (checkpoint — no commit) | config/scraper.yaml (pre-existing) |
| 2 | Implement BlogScraper | da5b9a7 | nitrofind/scraper/blogs.py |
| 3 | Convert Wave 0 stubs to real unit tests | 3d8aa0b | tests/test_scraper/test_blogs.py |

## Task 1 Checkpoint Outcome

Developer approved with three targets verified:
- **hagerty**: `article_selector: "div.article_body"`, `listing_selector: "a.card_title"` — VERIFIED 2026-05-14, `enabled: true`
- **caranddriver**: `article_selector: "div.article-body-content"`, `listing_selector: "a[data-vars-ga-ux-element='stack_block']"` — VERIFIED 2026-05-14, `enabled: true`
- **hemmings**: `article_selector: "div.entry-content"`, `listing_selector: "article.card a.card__link"` — VERIFIED, `enabled: true`

All three targets accessible with real browser. Honest User-Agent NitroFind/1.0 used at scrape time (NOT the Mozilla UA in config/scraper.yaml headers section — BlogScraper uses HONEST_USER_AGENT module constant exclusively).

## New Module File Paths and Line Counts

| File | Lines | Purpose |
|------|-------|---------|
| `nitrofind/scraper/blogs.py` | 257 | BlogScraper class — article list fetch, article page fetch, BS4 parse, doc dict generation |
| `tests/test_scraper/test_blogs.py` | 384 | 8 unit tests covering Pitfall 3/4, L-05, D-06, doc shape, honest UA |

## Exported Symbols

| Module | Exported Symbols |
|--------|-----------------|
| `nitrofind.scraper.blogs` | `BlogScraper`, `HONEST_USER_AGENT` |

## BlogScraper Methods

| Method | Description |
|--------|-------------|
| `__init__(config, state)` | Filters enabled targets from config; sets rate limit and requests.Session with HONEST_USER_AGENT |
| `yield_documents()` | Generator implementing first-winner fallback chain over enabled targets; D-06 skip; mark_visited after yield |
| `_fetch_article_urls(target)` | GET listing URL, select(listing_selector), return deduplicated absolute URLs; None on HTTP/connection error |
| `_fetch_article(url, target)` | GET article URL, remove noise tags, select_one(article_selector), get_text + whitespace collapse, return doc dict; None on error/missing container/short body |
| `_url_slug(url)` | Last non-empty path segment; SHA-1 prefix fallback for root/no-segment URLs |

## Unit Test Names and Results

| Test | Coverage | Result |
|------|----------|--------|
| `test_fetch_article_returns_none_on_403` | Pitfall 3: 403 on article → None + warning "403" | PASSED |
| `test_fetch_article_returns_none_on_missing_container` | Pitfall 4: missing container → None + "Article container not found" | PASSED |
| `test_fetch_article_returns_none_on_short_body` | Pitfall 4: <100 char body → None + "suspiciously short" | PASSED |
| `test_extract_plain_text_removes_html_tags` | L-05: body has no `<` or `>` characters | PASSED |
| `test_doc_has_correct_shape` | SCRP-02: has_infobox=False, era_bucket="Unknown", source_domain=netloc, article_id=slug | PASSED |
| `test_fallback_chain_advances_on_403` | Pitfall 3: first target 403 listing → second target docs yielded | PASSED |
| `test_state_visited_url_is_skipped` | D-06: is_visited=True skips article fetch entirely | PASSED |
| `test_honest_user_agent_not_mozilla` | Security: UA==HONEST_USER_AGENT, "Mozilla" not in UA | PASSED |

**Total: 8 PASSED**

## Overall Verification Results

```
pytest tests/test_scraper/test_blogs.py -x -m "not integration"
→ 8 passed in 0.97s

pytest tests/ -x -m "not integration"
→ 51 passed, 3 deselected  (exit 0)
```

No regressions in Phase 1 or sibling Phase 2 plan tests.

## Confirmation: HONEST_USER_AGENT and No Mozilla

```
grep -q "NitroFind/1.0" nitrofind/scraper/blogs.py   # ✓ HONEST_USER_AGENT defined
grep -q "Mozilla/" nitrofind/scraper/blogs.py         # ✗ not found — project ethic enforced
```

- `HONEST_USER_AGENT = "NitroFind/1.0 (nullsecurity1337@gmail.com; personal offline research tool)"` present as module-level constant
- No `Mozilla/` substring anywhere in `blogs.py`
- Config `blogs.headers` Mozilla UA intentionally ignored — BlogScraper reads only `config["blogs"]["targets"]` and `rate_limit_seconds`

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria from Task 2 and Task 3 met on first attempt.

## Known Stubs

None. BlogScraper is fully implemented with real HTTP fetching logic, real BS4 parsing, and config-driven selectors. No placeholder return values or TODO markers.

## Threat Flags

No new security surface beyond the plan's threat model:

| Threat ID | Component | Disposition | Applied |
|-----------|-----------|-------------|---------|
| T-02-14 | `_fetch_article` -> body field | mitigate | `get_text(separator=" ", strip=True)` + `re.sub(r"\s+", " ", text).strip()` — body contains no `<` or `>` (verified by test_extract_plain_text_removes_html_tags) |
| T-02-15 | `BlogScraper._session.headers` | accept | `HONEST_USER_AGENT` module constant; no `Mozilla/`; test_honest_user_agent_not_mozilla enforces this |
| T-02-17 | `requests.Session.get` | mitigate | `timeout=15` on every HTTP call; `HTTPError` + `RequestException` both caught and logged |

## Self-Check: PASSED

- [x] `nitrofind/scraper/blogs.py` exists (257 lines)
- [x] `BlogScraper` exports `__init__`, `yield_documents`, `_fetch_article_urls`, `_fetch_article`, `_url_slug`
- [x] `HONEST_USER_AGENT` module constant present
- [x] Module docstring contains `Exports:`, `Requirement coverage:`, `SCRP-02`, `Pitfall 3`, `Pitfall 4`
- [x] No `Mozilla/` substring in `blogs.py`
- [x] No `http://localhost:9200` in `blogs.py`
- [x] No bare `except:` in `blogs.py`
- [x] `tests/test_scraper/test_blogs.py` contains all 8 test functions
- [x] No `pytest.importorskip` in `test_blogs.py`
- [x] No `pytest.skip("Wave 1` in `test_blogs.py`
- [x] `pytest tests/test_scraper/test_blogs.py -x -m "not integration"` exits 0 with 8 PASSED
- [x] `pytest tests/ -x -m "not integration"` exits 0 with 51 PASSED
- [x] Commits da5b9a7 (feat Task 2), 3d8aa0b (feat Task 3) both exist in git log
