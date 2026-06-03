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
- ✓ 300ms debounce search — results update as user types — v1.0
- ✓ Result list shows title, source domain, highlighted excerpt — v1.0
- ✓ Full article text in detail pane on click/Enter — no browser opens — v1.0
- ✓ Filter sidebar for manufacturer, era_bucket, body style — persists across query retypes — v1.0
- ✓ Query terms highlighted in result excerpts — v1.0
- ✓ Result count and query time shown below search box — v1.0
- ✓ Dark teal theme default — v1.0
- ✓ Arrow keys / Enter / Escape keyboard navigation — v1.0
- ✓ PyInstaller onedir bundle + pre-extracted ES dir — no Python/Java required — v1.0

### Active (v1.1)

- [ ] Flask web server on localhost:5000 — single `python main.py` starts ES + web server
- [ ] Browser-based search UI (dark theme, debounce, filter sidebar, detail pane) replacing PyQt6
- [ ] REST API endpoints `/api/search` and `/api/status`
- [ ] PyQt6 removed from dependencies
- [ ] Empirical tuning of function_score weights against real indexed data (carried from v1.0)

### Out of Scope

- Motorcycles, trucks, and non-car vehicles — cars only; keeps database under 2 GB and scope focused
- AI/ML-based relevance — deliberate choice; scoring uses only explicit math via Elasticsearch function_score
- Online/cloud mode — the product promise is offline-first; no external calls at search time
- Periodic auto-update — scraper is a one-shot tool; re-running it refreshes the database manually
- User accounts or saved searches — single-user local tool, no auth complexity needed

## Context

**Current state:** v1.0 archived 2026-05-29. v1.1 in progress — replacing PyQt6 UI with Flask web server.
- ~9,136 lines of Python (v1.0); v1.1 removes PyQt6/qt-material, adds Flask
- Tech stack: Python 3.11, Elasticsearch 8.18, Flask, BeautifulSoup4, mediawikiapi
- ES node: `xpack.security.enabled: false`, `network.host: 127.0.0.1`, JVM heap pinned at 512 MB
- Distribution: `python main.py` on localhost (no PyInstaller bundle in v1.1)
- Database hard cap: 2 GB (scraper size guard at 1.8 GB)

**Known limitations at v1.0:**
- function_score weights are literature-derived, not empirically tuned (no live indexed data during development)
- Blog scraper covers Hagerty; CSS selectors for Car and Driver/Road & Track/Hemmings not yet validated against live HTML
- Windows clean-machine smoke test not yet run

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
| Full article text in detail view | Enthusiasts want to read the actual content, not just a snippet | ✓ Good — QTextBrowser no-browser wiring confirmed |
| Instant search + filter panel combined | Best of both: fluid discovery + precise narrowing | ✓ Good — debounce + filter sidebar both shipped |
| function_score with explicit math only | No AI dependency; deterministic, inspectable, reproducible results | ✓ Good — constraint held throughout |
| Horizontal-layer phase structure | Each phase is a complete technical subsystem | ✓ Good — each phase independently testable |
| ES cold-start deadline: 180s (not 60s) | Observed ~120s actual cold-start on target machine | ✓ Good — real-world validated |
| State dict pattern for ESHealthWorker replacement | Closures need mutable reference; nonlocal insufficient | ✓ Good — clean Retry flow |
| PyInstaller onedir (not --onefile) | Avoids AV false-positives and per-launch extraction delay | ✓ Good — standard pattern for Qt apps |
| upx=False in spec | UPX corrupts Qt DLLs on Windows | ✓ Good — avoid corruption |
| ES_BUNDLE env var for assembly | Keeps ES path out of spec for repeatable builds | ✓ Good — build-time decoupling |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
## Current Milestone: v1.1 Web Interface

**Goal:** Replace PyQt6 with a Flask web server accessible at http://localhost:5000 — single `python main.py` starts ES and the web server together.

**Target features:**
- Flask server lifecycle (starts ES + web server, graceful shutdown)
- REST API (`/api/search`, `/api/status`)
- Browser UI: dark theme, debounce search, filter sidebar, detail pane
- PyQt6 removed from dependencies

---
*Last updated: 2026-06-03 — v1.1 milestone started*
