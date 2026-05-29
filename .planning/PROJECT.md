# NitroFind

## What This Is

NitroFind is an offline desktop application for automotive enthusiasts that provides instant, full-text search over a locally stored encyclopedia of car specifications, history, and articles. It scrapes Wikipedia and reputable automotive blogs, indexes everything into a local Elasticsearch node, and presents results through a native PyQt interface — no internet connection required at search time, no ads, no SEO clutter.

## Core Value

Instant, noise-free access to deep automotive knowledge — the entire database on your machine, searchable in milliseconds.

## Requirements

### Validated

- [x] Scraper collects car articles and specs from Wikipedia and automotive blogs, outputs structured JSON — Validated in Phase 2: data-pipeline-scraper-indexer
- [x] Local Elasticsearch node indexes all scraped data and stays under 2 GB total — Validated in Phase 2: data-pipeline-scraper-indexer
- [x] Relevance scoring based on source quality signals: publication date, domain reputation, article completeness — Validated in Phase 3: search-logic-relevance-scoring
- [x] As-you-type (instant) search that queries Elasticsearch with each keystroke — Validated in Phase 4: desktop-ui
- [x] Filter panel alongside search for narrowing by manufacturer, era, body style, and other car attributes — Validated in Phase 4: desktop-ui
- [x] Result detail view renders the full scraped article text inline, within the app — Validated in Phase 4: desktop-ui
- [x] PyQt native desktop UI with a fluid, modern feel comparable to a browser search experience — Validated in Phase 4: desktop-ui

### Validated

- [x] Application packaged as standalone executable — PyInstaller onedir bundle + Elasticsearch alongside, distributable zip, no Python/Java required on end-user machine — Validated in Phase 5: packaging-distribution

### Out of Scope

- Motorcycles, trucks, and non-car vehicles — cars only to keep database under 2 GB and scope focused
- AI/ML-based relevance — deliberate choice; scoring uses only explicit math via Elasticsearch function_score
- Online/cloud mode — the product promise is offline-first; no external calls at search time
- Periodic auto-update — scraper is a one-shot tool; re-running it refreshes the database manually
- User accounts or saved searches — single-user local tool, no auth complexity needed

## Context

- Tech stack is fixed: Python for the scraper and backend logic, Elasticsearch (local node) as the search engine, PyQt for the native desktop UI.
- Elasticsearch is not yet configured — initial setup and schema design is part of the first milestone.
- Database size hard cap of 2 GB: the scraper must be selective (curate sources, limit article count, compress stored content) to stay under this limit.
- Relevance is modeled as a "PageRank-like" composite of source quality signals — no ML weights, no embeddings. Signals include: article publish date (fresher = higher), source domain authority (well-known automotive sites rank higher), article length/completeness, and citation density. These are combined via Elasticsearch `function_score`.
- The search UI combines Google-style instant search (results update as you type) with a sidebar filter panel (manufacturer, era, body style, etc.). Clicking a result shows the full article text rendered inside the app.
- Scraper targets: Wikipedia automotive pages as the primary source; specific automotive enthusiast blogs (e.g., Car and Driver, Road & Track, Hagerty, Hemmings) as supplementary sources. Final list confirmed during research phase.

## Constraints

- **Database size**: Must stay under 2 GB — drives scraper selectivity and data compression decisions
- **Tech stack**: Python + Elasticsearch + PyQt — fixed; no substitutions
- **No AI/ML**: Relevance is pure mathematical function_score — no models, no embeddings, no API calls
- **Offline at search time**: All data must be local; Elasticsearch node runs on localhost

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Cars only (all eras) | Keeps DB under 2 GB; aligns with enthusiast focus | — Pending |
| Relevance = source quality signals, not car specs | User wants "PageRank-like" article authority, not a performance leaderboard | — Pending |
| Full article text in detail view | Enthusiasts want to read the actual content, not just a snippet | — Pending |
| Instant search + filter panel combined | Best of both: fluid discovery + precise narrowing | — Pending |
| function_score with explicit math only | No AI dependency; deterministic, inspectable, reproducible results | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-29 — Phase 5 complete, NitroFind packaged as standalone distributable Windows executable*
