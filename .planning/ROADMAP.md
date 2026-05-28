# Roadmap: NitroFind

## Overview

NitroFind is built in five sequential phases, each unblocking the next. Infrastructure and schema come first because every downstream artifact depends on a correctly configured Elasticsearch node and a locked index mapping. The data pipeline runs next to populate real content, which allows relevance scoring to be tuned empirically against actual documents. The desktop UI is built last against a tested search layer, and distribution packaging closes the loop.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure & Schema Foundation** - Elasticsearch node running, index schema locked, venv reproducible
- [x] **Phase 2: Data Pipeline (Scraper + Indexer)** - Wikipedia and blog articles scraped, cleaned, deduplicated, and indexed under 2 GB (completed 2026-05-15)
- [ ] **Phase 3: Search Logic & Relevance Scoring** - function_score query engine built and tuned against real data
- [ ] **Phase 4: Desktop UI** - PyQt6 application with instant search, filters, detail view, and keyboard navigation
- [ ] **Phase 5: Packaging & Distribution** - PyInstaller bundle + Elasticsearch directory ship as a runnable app on a clean machine

## Phase Details

### Phase 1: Infrastructure & Schema Foundation
**Goal**: A reproducible Python environment, a correctly configured local Elasticsearch 8.18 node (TLS off, heap pinned, single-node), and a locked car_articles index mapping are in place before any scraping or UI code is written.
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04
**Success Criteria** (what must be TRUE):
  1. Running `pip install -r requirements.txt` in a fresh venv produces an identical dependency tree on any machine (lockfile present, no version drift)
  2. `python main.py` starts the Elasticsearch subprocess, polls cluster health, and reports green or yellow within 60 seconds — no manual ES startup required
  3. Quitting the app terminates the Elasticsearch process cleanly (no orphaned JVM processes remain after exit)
  4. The car_articles index exists in ES with explicit mapping (dynamic: false, flattened specs field, all SCHEMA fields present) — `GET /car_articles/_mapping` shows the full schema with no dynamically inferred fields
  5. The UI shows a loading/splash state while ES warms up and transitions to the main window only after the cluster health check passes
**Plans**: 4 plans
- [x] 01-01-PLAN.md — Python lockfile + ES config files + setup_es.py + pytest scaffold (INFRA-01)
- [x] 01-02-PLAN.md — ESHealthWorker + shutdown_es + car_articles schema + unit/integration tests (INFRA-02/03/04, SCHEMA-01..04)
- [x] 01-03-PLAN.md — SpinnerWidget + LoadingWindow (loading/error states) + StubMainWindow + state-machine tests (INFRA-04 UI side)
- [x] 01-04-PLAN.md — main.py wiring + end-to-end manual verification checkpoint (INFRA-02/03/04 end-to-end)

### Phase 2: Data Pipeline (Scraper + Indexer)
**Goal**: A one-shot CLI scraper populates the car_articles index with clean, deduplicated automotive articles from Wikipedia and at least one automotive blog, staying under 2 GB of ES storage.
**Depends on**: Phase 1
**Requirements**: SCRP-01, SCRP-02, SCRP-03, SCRP-04
**Success Criteria** (what must be TRUE):
  1. Running the scraper CLI indexes at least 1,000 Wikipedia car articles with no duplicate documents (MediaWiki pageid used as ES _id — re-running the scraper produces no duplicate count increase)
  2. At least one automotive blog domain (Car and Driver, Hagerty, Hemmings, or Road & Track) has articles successfully indexed with title, body text, and excerpt fields populated
  3. Every indexed document contains only plain text in the body field — no raw HTML tags — and the excerpt field is 300 characters or fewer
  4. When the index approaches 1.8 GB, the scraper halts and logs a warning without writing further documents, and the final ES index size stays below 2 GB
**Plans**: TBD

### Phase 3: Search Logic & Relevance Scoring
**Goal**: A tested Python search layer translates a query string and optional filter set into an Elasticsearch function_score query, returns ranked ArticleResult objects with highlighted excerpts, and produces results whose ranking reflects source quality signals on real indexed data.
**Depends on**: Phase 2
**Requirements**: RLVN-01, RLVN-02, RLVN-03, RLVN-04
**Success Criteria** (what must be TRUE):
  1. Searching for a well-known car (e.g., "Ferrari 308") returns the Wikipedia article for that car in the top 3 results — demonstrating that text relevance and recency decay work together
  2. An article published in the last two years scores measurably higher than an otherwise-equal article published a decade ago (Gaussian decay with ~2-year half-life is active)
  3. A long, infobox-equipped article consistently outscores a short, infobox-free article for the same query — confirming both the log(word_count) modifier and has_infobox boost are active
  4. An article with no published_at field does not score 1.0 on the recency signal — it receives the configured missing-field fallback score instead of distorting ranking
  5. All ES calls in the search layer execute without blocking: calling the query builder from a background thread returns results via callback without touching the main thread
**Plans**: 3 plans
**Wave 1:**
- [x] 03-01-PLAN.md — ArticleResult dataclass + build_function_score_query + build_search_body (RLVN-01..04)
**Wave 2** *(blocked on Wave 1 completion)*:
- [x] 03-02-PLAN.md — SearchEngine with QRunnable/_SearchSignals worker (RLVN-01 threading)
**Wave 3** *(blocked on Wave 2 completion)*:
- [ ] 03-03-PLAN.md — Unit + integration test suite for models, query_builder, and engine (RLVN-01..04)
**Cross-cutting constraints:** ES index name hard-coded as "car_articles" in all files; ES_URL imported from nitrofind.es_manager; logger uses % formatting throughout.
**UI hint**: no

### Phase 4: Desktop UI
**Goal**: A native PyQt6 desktop application delivers instant search, a filter sidebar, inline article rendering, dark theme, and keyboard navigation — with all Elasticsearch I/O running off the main thread.
**Depends on**: Phase 3
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04, UIPL-01, UIPL-02, UIPL-03, UIPL-04
**Success Criteria** (what must be TRUE):
  1. Typing in the search box updates results within 300ms of the user pausing (debounce active) — the result list changes without any button press or page reload
  2. Each result row displays the article title, source domain, and an excerpt with matching query terms visually highlighted
  3. Clicking a result (or pressing Enter) displays the full article text in a detail pane inside the app — no browser window opens
  4. Filtering by manufacturer, era bucket, or body style in the sidebar narrows results without clearing the search query, and the filter state persists if the user types a new query
  5. The app renders with a dark theme by default, and the user can navigate results with arrow keys, open with Enter, and clear the search box with Escape
**Plans**: TBD
**UI hint**: yes

### Phase 5: Packaging & Distribution
**Goal**: A first-time user on a clean machine (no Python, no Java installed) can run NitroFind by extracting a single archive and double-clicking the launcher.
**Depends on**: Phase 4
**Requirements**: PKG-01
**Success Criteria** (what must be TRUE):
  1. On a clean machine with no Python or Java installed, extracting the distributed archive and running the launcher starts NitroFind and reaches the search-ready state (ES health check passes)
  2. The distributed package includes the pre-extracted Elasticsearch 8.18 directory alongside the PyInstaller bundle — no separate ES download step is required
  3. The launcher correctly configures elasticsearch.yml and jvm.options (TLS off, heap pinned to 512 MB) before starting the ES subprocess — default ES settings are never used
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Schema Foundation | 4/4 | Complete | 2026-05-13 |
| 2. Data Pipeline (Scraper + Indexer) | 5/5 | Complete   | 2026-05-15 |
| 3. Search Logic & Relevance Scoring | 0/3 | Planned | - |
| 4. Desktop UI | 0/TBD | Not started | - |
| 5. Packaging & Distribution | 0/TBD | Not started | - |
