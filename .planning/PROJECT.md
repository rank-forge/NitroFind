# NitroFind

## What This Is

NitroFind is an offline automotive search tool. It provides instant full-text search over a locally stored encyclopedia of car specifications, history, and articles — accessible at `http://localhost:5000` in any browser. A single `python main.py` starts Elasticsearch and the web server together. No internet connection required at search time, no ads, no SEO clutter.

## Core Value

Instant, noise-free access to deep automotive knowledge — the entire database on your machine, searchable in milliseconds.

## Requirements

### Validated

- ✓ Developer can run the app from a Python venv with a pinned lockfile (reproducible environment) — v1.0
- ✓ App starts a local Elasticsearch 8.18 node as a subprocess on launch (localhost:9200, TLS disabled) — v1.0
- ✓ App terminates the Elasticsearch process cleanly when the user quits — v1.0
- ✓ App shows a loading state while Elasticsearch warms up and becomes healthy — v1.0
- ✓ car_articles index with 17 explicitly mapped fields (identity, scoring signals, facets, body/excerpt) — v1.0
- ✓ Scraper fetches car articles from Wikipedia using the MediaWiki API — v1.0
- ✓ Scraper fetches articles from at least one automotive blog (Hagerty) using BeautifulSoup4 — v1.0
- ✓ MediaWiki page ID used as ES document _id to prevent duplicates — v1.0
- ✓ Scraper halts with warning when index approaches 1.8 GB — v1.0
- ✓ function_score with Gaussian recency decay (~2-year half-life) — v1.0
- ✓ Article length signal via log1p modifier on word_count — v1.0
- ✓ Boolean boost for articles with structured infobox — v1.0
- ✓ score_mode: sum, boost_mode: multiply — v1.0
- ✓ 300ms debounce search — results update as user types — v1.1
- ✓ Result list shows title, source domain, highlighted excerpt — v1.1
- ✓ Full article text in detail pane on click/Enter — no browser tab opens — v1.1
- ✓ Filter sidebar for manufacturer, era_bucket, body style — persists across query retypes — v1.1
- ✓ Query terms highlighted in result excerpts — v1.1
- ✓ Result count and query time shown below search box — v1.1
- ✓ Dark teal theme default — v1.1
- ✓ Arrow keys / Enter / Escape keyboard navigation — v1.1
- ✓ Flask web server on localhost:5000 — single `python main.py` starts ES + web server — v1.1
- ✓ Browser-based search UI (dark theme, debounce, filter sidebar, detail pane) replacing PyQt6 — v1.1
- ✓ REST API endpoints `/api/search` and `/api/status` — v1.1
- ✓ PyQt6 removed from dependencies — v1.1

### Active (v1.2)

- [ ] Article rendering: Wikipedia/blog tables not displayed in detail view — v1.2
- [ ] Article rendering: Body text too large (link text being ingested with article body) — v1.2
- ✓ Fuzzy search — fuzziness: "AUTO" on multi_match — v1.2 (Validated in Phase 10: search-quality-sort)
- ✓ Phrase search — detect quoted queries → route to match_phrase — v1.2 (Validated in Phase 10: search-quality-sort)
- ✓ Alternative sort buttons: "By date", "By relevance", "By size" — v1.2 (Validated in Phase 10: search-quality-sort)
- [ ] Year range filter (production_start / production_end) — v1.2
- [ ] Country of origin filter — v1.2
- ✓ Pagination (previous / next result pages, 10 per page, total hit count) — v1.2 (Validated in Phase 12: pagination)
- [ ] Search history (last 10 queries, localStorage) — v1.2
- [ ] Dark / light mode toggle in header — v1.2

### Deferred (v1.3+)

- [ ] Empirical tuning of function_score weights against real indexed data (carried from v1.0)
- [ ] Windows clean-machine smoke test (carried from v1.0 — Linux/WSL only for v1.1)
- [ ] Full installer / startup shortcut (Windows .bat, macOS .command)
- [ ] `/api/article/{id}` endpoint for fetching individual articles by ES _id
- [ ] Favorites — save articles for later reading in localStorage
- [ ] Export results — download results as JSON or CSV
- [ ] Score explainer — "Why this result?" ES score breakdown

### Out of Scope

- Motorcycles, trucks, and non-car vehicles — cars only; keeps database under 2 GB and scope focused
- AI/ML-based relevance — deliberate choice; scoring uses only explicit math via Elasticsearch function_score
- Online/cloud mode — the product promise is offline-first; no external calls at search time
- Periodic auto-update — scraper is a one-shot tool; re-running it refreshes the database manually
- User accounts or saved searches — single-user local tool, no auth complexity needed
- PyInstaller packaging — removed in v1.1; `python main.py` is the distribution model

## Current Milestone: v1.2 Search Quality & UX Polish

**Goal:** Fix article rendering bugs and add smarter search, richer filtering, and UX controls to make NitroFind feel like a complete research tool.

**Target features:**
- Article rendering fixes: Wikipedia/blog tables not rendered; text too large (link text ingested)
- Fuzzy search — fuzziness: "AUTO" on multi_match (tolerate typos)
- Phrase search — detect quoted queries → match_phrase routing
- Alternative sort buttons: "By date", "By relevance", "By size"
- Year range filter (production_start / production_end, already in schema)
- Country of origin filter
- Pagination (previous / next result pages)
- Search history (last 10 queries, localStorage)
- Dark / light mode toggle in header

## Context

**Current state:** v1.1 shipped 2026-06-04. Browser-based SPA replaced PyQt6 desktop UI. Flask web server on localhost:5000. All v1.1 requirements (16/16) delivered.

- Tech stack: Python 3.11, Elasticsearch 8.18, Flask 3.1.3, BeautifulSoup4, mediawikiapi, vanilla JS
- ES node: `xpack.security.enabled: false`, `network.host: 127.0.0.1`, JVM heap pinned at 512 MB
- Distribution: `python main.py` on localhost (no PyInstaller bundle)
- Database hard cap: 2 GB (scraper size guard at 1.8 GB)
- PyQt6 and qt-material fully removed from dependencies

**Known limitations:**
- function_score weights are literature-derived, not empirically tuned (requires live indexed data)
- Blog scraper covers Hagerty; CSS selectors for Car and Driver/Road & Track/Hemmings not yet validated against live HTML
- Windows clean-machine smoke test not yet run (Linux/WSL only)
- Manufacturer filter uses free-text input only (no aggregation endpoint to populate dropdown dynamically)

## Constraints

- **Database size**: Must stay under 2 GB — drives scraper selectivity and data compression decisions
- **Tech stack**: Python + Elasticsearch + Flask — PyQt6 removed in v1.1
- **No AI/ML**: Relevance is pure mathematical function_score — no models, no embeddings, no API calls
- **Offline at search time**: All data must be local; Elasticsearch node runs on localhost

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Cars only (all eras) | Keeps DB under 2 GB; aligns with enthusiast focus | ✓ Good — no scope creep |
| Relevance = source quality signals, not car specs | User wants article authority, not a performance leaderboard | ✓ Good — function_score clean |
| Full article text in detail view | Enthusiasts want to read the actual content, not just a snippet | ✓ Good — confirmed in v1.0 PyQt6 + v1.1 browser |
| Instant search + filter panel combined | Best of both: fluid discovery + precise narrowing | ✓ Good — debounce + filter sidebar both shipped |
| function_score with explicit math only | No AI dependency; deterministic, inspectable, reproducible results | ✓ Good — constraint held throughout |
| Horizontal-layer phase structure | Each phase is a complete technical subsystem | ✓ Good — each phase independently testable |
| ES cold-start deadline: 180s (not 60s) | Observed ~120s actual cold-start on target machine | ✓ Good — real-world validated |
| State dict pattern for shared mutable state | Closures need mutable reference; nonlocal insufficient; GIL-safe for single-writer pattern | ✓ Good — extended to es_client in v1.1 |
| Flask dev server (no WSGI/HTTPS) | Local single-user tool — Flask dev server sufficient for localhost | ✓ Good — no over-engineering |
| Linux/WSL-only for v1.1 | Remove win32 branches to simplify es_manager.py; Windows support deferred | ✓ Good — reduced code complexity |
| `data-state` CSS attribute selectors for SPA views | No JS show/hide; pure CSS state machine; FOUC prevented by hardcoded `data-state=home` in HTML | ✓ Good — clean architecture |
| System-font stack over self-hosted web fonts | Offline-safe, zero setup, no font loading jank | ✓ Good — aligns with offline-first product promise |
| PyInstaller onedir (not --onefile) | Avoids AV false-positives and per-launch extraction delay | ✓ Good (v1.0 only — removed in v1.1) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-05 — Phase 12 complete: pagination shipped (prev/next, 10 per page, total hit count)*
