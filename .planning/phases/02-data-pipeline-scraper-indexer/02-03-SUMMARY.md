---
phase: 02-data-pipeline-scraper-indexer
plan: "03"
subsystem: wikipedia-scraper
tags: [wikipedia, mediawikiapi, scraper, tdd, category-walk, infobox-filter]
dependency_graph:
  requires: [02-01, nitrofind.scraper.cleaner, nitrofind.scraper.state]
  provides: [WikipediaScraper, nitrofind.scraper.wikipedia]
  affects: [02-05]
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle for Wikipedia scraper implementation
    - raw MediaWiki Action API with cmcontinue pagination for large categories
    - generator-based document yielding (composable with BulkIndexer in Plan 05)
    - visited_categories set for cycle-proof recursive category walk
key_files:
  created:
    - nitrofind/scraper/wikipedia.py
    - nitrofind/scraper/__init__.py
    - nitrofind/scraper/cleaner.py
    - nitrofind/scraper/state.py
  modified:
    - tests/test_scraper/test_wikipedia.py
decisions:
  - "test_yield_documents_skips_already_visited uses side_effect not return_value for _get_category_members_raw — flat return_value causes uncontrolled recursion because subcat calls also return page IDs"
  - "Package stubs for cleaner.py and state.py created in this worktree since Plan 02-02 runs in parallel; these match the interface specified in PATTERNS.md and will merge cleanly"
metrics:
  duration: "7m 22s"
  completed: "2026-05-14T13:58:29Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 1
---

# Phase 02 Plan 03: Wikipedia Scraper Summary

**One-liner:** WikipediaScraper class — category walk with cmcontinue pagination, pageid+auto_suggest=False fetch, falsy infobox filter, visited_categories cycle guard, and generator-based document yield conforming to CAR_ARTICLES_MAPPING.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| TDD RED | Failing tests for WikipediaScraper | dddc59a | tests/test_scraper/test_wikipedia.py, nitrofind/scraper/__init__.py, cleaner.py, state.py |
| TDD GREEN (Task 1+2) | WikipediaScraper implementation + test conversion | e7347e4 | nitrofind/scraper/wikipedia.py, tests/test_scraper/test_wikipedia.py |

## nitrofind/scraper/wikipedia.py

**Line count:** 304 lines

**Exported symbols:** `WikipediaScraper`

**Module constant:** `MEDIAWIKI_API_URL = "https://en.wikipedia.org/w/api.php"`

### WikipediaScraper Methods

| Method | What it does |
|--------|-------------|
| `__init__(config, state)` | Initialise MediaWikiAPI client + requests.Session with honest User-Agent from config; set rate limit and max_depth |
| `yield_documents()` | Generator: walk all root categories (D-03), collect pageids, skip visited (D-06), fetch each, yield document dict; log progress every 50 yields (D-05) |
| `_walk_category(category_title, depth, visited_categories)` | Recursive category walk with Pitfall 6 cycle guard; fetches page IDs + subcategory titles via raw API; respects max_depth (D-01) |
| `_get_category_members_raw(category_title, cmtype, return_titles)` | Paginated raw MediaWiki Action API call using cmcontinue loop; returns int pageids or str titles; returns [] on API error |
| `_fetch_and_build_doc(pageid)` | Fetch page with pageid+auto_suggest=False (Pitfall 1); apply falsy infobox filter (Pitfall 2); build doc dict conforming to CAR_ARTICLES_MAPPING |

## Pitfall Mitigations Verified

| Pitfall | Literal Present | Behavior |
|---------|----------------|---------|
| Pitfall 1 (auto-suggest redirect) | `auto_suggest=False` | Page fetched by pageid, not title |
| Pitfall 2 (infobox None vs empty) | `if not page.infobox:` | Falsy check handles {} and None |
| Pitfall 6 (cyclic categories) | `visited_categories` | Set guards recursion; already-visited returns [] |
| cmcontinue (large categories) | `cmcontinue` | While-loop exhausts all pages regardless of category size |

## Dependency Stubs Created

Since Plan 02-02 (cleaner/state/indexer) runs in parallel in a separate worktree, this plan creates minimal implementations of the two modules that `wikipedia.py` imports:

| Module | Line count | Functions/Classes |
|--------|-----------|-------------------|
| nitrofind/scraper/__init__.py | 1 | package marker only |
| nitrofind/scraper/cleaner.py | 48 | make_excerpt, compute_era_bucket, parse_year |
| nitrofind/scraper/state.py | 68 | SQLiteStateManager (is_visited, mark_visited, close, context manager) |

These implementations match the interface specified in PATTERNS.md verbatim. Merge conflict risk is low since 02-02 will produce identical code.

## Unit Tests

| Test Name | What it Verifies |
|-----------|-----------------|
| test_walk_category_avoids_cycles | Pitfall 6: already-visited category returns [] without recursion |
| test_fetch_and_filter_skips_empty_infobox | D-02 + Pitfall 2: falsy infobox check returns None |
| test_fetch_and_build_doc_returns_full_doc_for_infobox_page | Full doc dict: article_id, source_domain, has_infobox, manufacturer, production_start, era_bucket, image_count, excerpt |
| test_pageid_used_with_auto_suggest_false | Pitfall 1: page call uses pageid kwarg + auto_suggest=False |
| test_yield_documents_skips_already_visited | D-06: wiki.page never called for already-visited pageid |
| test_user_agent_set_from_config | UA set on both wiki.config.user_agent AND session headers |
| test_real_wikipedia_page_fetch | @pytest.mark.integration — live Ferrari 308 page fetch |

**Unit test result:** 6 passed, 1 deselected (integration), 1 deselected (integration) — exit 0

## pytest Verification

```
pytest tests/test_scraper/test_wikipedia.py -x -m "not integration"
→ 6 passed, 1 deselected  (exit 0)

pytest tests/ -x -m "not integration"
→ 21 passed, 13 skipped, 3 deselected  (exit 0)

pytest tests/test_scraper/test_wikipedia.py -m integration --collect-only
→ <Function test_real_wikipedia_page_fetch>  (1 collected)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_yield_documents_skips_already_visited used flat return_value causing 4 docs yielded instead of 1**

- **Found during:** Task 2 GREEN verification
- **Issue:** `patch.object(WikipediaScraper, "_get_category_members_raw", return_value=[99, 100])` returns `[99, 100]` for ALL calls including subcat queries. This causes `_walk_category` to recurse into pageids 99 and 100 as subcategory titles, collecting 4 copies of the pageid list.
- **Fix:** Changed to `side_effect=fake_get_members` with a function that returns `[99, 100]` for `cmtype="page"` and `[]` for `cmtype="subcat"`, preventing uncontrolled recursion.
- **Files modified:** tests/test_scraper/test_wikipedia.py
- **Commit:** e7347e4

**2. [Rule 3 - Blocking] Plan 02-02 (cleaner/state) runs in parallel — needed stubs to satisfy wikipedia.py imports**

- **Found during:** TDD RED setup
- **Issue:** `from nitrofind.scraper.cleaner import ...` and `from nitrofind.scraper.state import SQLiteStateManager` would fail with ModuleNotFoundError since 02-02 hasn't run yet.
- **Fix:** Created `nitrofind/scraper/__init__.py`, `nitrofind/scraper/cleaner.py`, and `nitrofind/scraper/state.py` with complete implementations matching the PATTERNS.md interface spec.
- **Files modified:** 3 new files created
- **Commit:** dddc59a

**3. [Deviation] Commit to wrong repo branch (CORRECTED)**

- **Found during:** First RED commit attempt
- **Issue:** bash `cd /mnt/c/Users/Leonardo/.../NitroFind` navigated to main repo instead of worktree; commit `e338917` accidentally landed on `main` branch of main repo.
- **Fix:** Ran `git reset --hard HEAD~1` on main repo to remove the bad commit. All subsequent work done using the worktree path exclusively.
- **Impact:** No data loss; bad commit fully reversed; all work properly committed on worktree-agent-af7853237aeb59201 branch.

## TDD Gate Compliance

| Gate | Commit | Description |
|------|--------|-------------|
| RED | dddc59a | test(02-03): failing tests — ModuleNotFoundError on collection |
| GREEN | e7347e4 | feat(02-03): implementation + test refinement — 6 passed |

Both RED and GREEN gates present. No REFACTOR phase needed (code is clean on first pass).

## Known Stubs

None — all implementations are complete. The cleaner.py and state.py stubs are full implementations, not placeholders.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-02-09 (mitigated) | wikipedia.py L255 | `specs` field uses ES `flattened` type; `dynamic: false` blocks root-level field injection — per existing threat register |
| T-02-10 (accepted) | wikipedia.py L71-74 | Honest NitroFind User-Agent on both clients — no browser impersonation |
| T-02-11 (mitigated) | wikipedia.py L154-156 | `visited_categories` cycle guard at `_walk_category` entry — Pitfall 6 |
| T-02-13 (mitigated) | wikipedia.py L247 | `auto_suggest=False` + `pageid=<int>` — Pitfall 1 |

No new threat surface introduced beyond what is documented in the plan's threat register.

## Self-Check: PASSED
