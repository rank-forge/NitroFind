# Phase 2: Data Pipeline (Scraper + Indexer) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 02-data-pipeline-scraper-indexer
**Areas discussed:** Wikipedia article selection scope, Scraper CLI design

---

## Wikipedia article selection scope

### Q1: Which Wikipedia content should the scraper target?

| Option | Description | Selected |
|--------|-------------|----------|
| Walk category trees | Start from root categories and recursively fetch member pages | ✓ |
| Curated seed list of categories | Manually specify 20-50 high-signal categories upfront | |
| Wikipedia 'automobile' category only (flat) | Fetch all direct and 1-level-deep members of 'Automobile' | |

**User's choice:** Walk category trees
**Notes:** Broad coverage; size cap enforced by 1.8 GB scraper halt (SCRP-04).

---

### Q2: How deep should the category walk go, and should we filter articles before indexing?

| Option | Description | Selected |
|--------|-------------|----------|
| Depth 2 + infobox filter | Walk 2 levels deep; only index articles with an infobox | ✓ |
| Depth 3, no filter | Deeper walk, no article-level filter | |
| Depth 2, minimum word count filter | Walk 2 levels; only index articles with word_count >= 300 | |

**User's choice:** Depth 2 + infobox filter
**Notes:** Infobox presence distinguishes structured car articles from disambiguation pages, list articles, and stubs.

---

### Q3: Which root categories should the walk start from?

| Option | Description | Selected |
|--------|-------------|----------|
| Predefined list in config file | Store root categories in config/scraper.yaml or similar | ✓ |
| Hardcoded in scraper source | Categories baked directly into the scraper script | |
| Passed as CLI argument | User specifies root categories at run time | |

**User's choice:** Predefined list in config file
**Notes:** Researcher selects the best starting Wikipedia categories; user can adjust without touching source code.

---

## Scraper CLI design

### Q1: How should the scraper be invoked?

| Option | Description | Selected |
|--------|-------------|----------|
| Single entrypoint, flags for source | `python scraper.py` with `--wikipedia`, `--blogs`, `--all` flags | ✓ |
| Separate scripts per source | `scrape_wikipedia.py` and `scrape_blogs.py` run independently | |
| Module entrypoint via python -m | `python -m nitrofind.scraper` | |

**User's choice:** Single entrypoint, flags for source
**Notes:** Simple and discoverable; `--all` is the default for a full database rebuild.

---

### Q2: How should the scraper report progress during a run?

| Option | Description | Selected |
|--------|-------------|----------|
| Live logging with article counts | Print category being walked, article count, index size to stdout | ✓ |
| tqdm progress bar | Visual progress bar showing articles processed / estimated total | |
| Silent with summary at end | No output during run; prints final summary when done | |

**User's choice:** Live logging with article counts
**Notes:** Works well in terminals and when output is redirected to a log file.

---

### Q3: Should the scraper support resuming an interrupted run?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — track scraped URLs in SQLite | Store scraped page IDs/URLs; re-runs skip already-indexed articles | ✓ |
| No — idempotent re-index only | Re-fetches everything on each run; ES _id prevents duplicates | |
| Yes — track in a plain text file | Write scraped IDs to a .txt file | |

**User's choice:** Yes — track scraped URLs in SQLite
**Notes:** CLAUDE.md already prescribes SQLite for scraper state tracking. Safe to interrupt anytime.

---

## Claude's Discretion

None — user made explicit choices for all questions.

## Deferred Ideas

None — discussion stayed within phase scope.
