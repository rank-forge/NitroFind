# Roadmap: NitroFind

## Milestones

- ✅ **v1.0 MVP** — Phases 1–5 (shipped 2026-05-29)
- 📋 **v1.1 Web Interface** — Phases 6–8 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–5) — SHIPPED 2026-05-29</summary>

- [x] Phase 1: Infrastructure & Schema Foundation (4/4 plans) — completed 2026-05-13
- [x] Phase 2: Data Pipeline (Scraper + Indexer) (5/5 plans) — completed 2026-05-15
- [x] Phase 3: Search Logic & Relevance Scoring (3/3 plans) — completed 2026-05-28
- [x] Phase 4: Desktop UI (4/4 plans) — completed 2026-05-28
- [x] Phase 5: Packaging & Distribution (2/2 plans) — completed 2026-05-29

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### 📋 v1.1 Web Interface

- [ ] **Phase 6: Server Lifecycle & Cleanup** (3 plans) - Rewrite main.py for ES + Flask, remove PyQt6, add /api/status
- [x] **Phase 7: Search REST API** - /api/search endpoint wrapping existing SearchEngine with filter support (completed 2026-06-03)
- [ ] **Phase 8: Browser Search UI** - Single-page HTML/CSS/JS dark-theme UI with debounce, filters, detail pane

## Phase Details

### Phase 6: Server Lifecycle & Cleanup

**Goal**: Users (and developers) can start the app with a single command and get a running server that responds at localhost:5000 — no Qt, no PyInstaller bundle required
**Depends on**: Nothing (brownfield — v1.0 ES infrastructure kept)
**Requirements**: SRVR-01, SRVR-02, SRVR-03, SRVR-04, API-03, API-04, CLEN-01
**Success Criteria** (what must be TRUE):

  1. `python main.py` starts Elasticsearch and the Flask dev server; browser can reach http://localhost:5000
  2. `GET /api/status` returns JSON with ES health, document count, and index size
  3. `GET /api/status` returns HTTP 503 with `{"status": "starting"}` while ES is still warming up
  4. Pressing Ctrl+C exits cleanly — no orphaned JVM process visible in task manager
  5. `pip install -r requirements.txt` succeeds without any Qt package; no PyQt6/qt-material import in codebase**Plans**: 3 plans

**Wave 1**

  - [x] 06-01-PLAN.md — Add Flask, strip es_manager.py of Qt/Windows/ESHealthWorker, update its tests

**Wave 2** *(blocked on Wave 1 completion)*

  - [x] 06-02-PLAN.md — Create nitrofind/server.py (Flask app, /api/status, GET /, background ES poller) + tests

**Wave 3** *(blocked on Wave 2 completion)*

  - [x] 06-03-PLAN.md — Rewrite main.py as Flask lifecycle entry point, delete nitrofind/ui/, CLEN-01 cleanup

**UI hint**: yes

### Phase 7: Search REST API

**Goal**: The app exposes a stable JSON search endpoint that browsers (and any HTTP client) can query, returning ranked results with highlights and optional facet filters
**Depends on**: Phase 6
**Requirements**: API-01, API-02
**Success Criteria** (what must be TRUE):

  1. `GET /api/search?q=mustang` returns a JSON array with title, url, source_domain, excerpt (with ES highlight tags), score, and took_ms for each result
  2. `GET /api/search?q=mustang&manufacturer=Ford` narrows results to Ford articles using the existing `build_filter_clauses()` logic
  3. `GET /api/search?q=anything` while ES is still starting returns HTTP 503

**Plans**: 1 plan

**Wave 1**

  - [x] 07-01-PLAN.md — Extend state dict with es_client; TDD the /api/search route (ranked results, highlights, optional facet filters, 503 warmup guard)

### Phase 8: Browser Search UI

**Goal**: Users can search the automotive database from any browser at localhost:5000 — the same search capabilities as v1.0 PyQt6 UI, now in a dark-theme web page
**Depends on**: Phase 7
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04, UIPL-01, UIPL-02, UIPL-03
**Success Criteria** (what must be TRUE):

  1. Typing in the search box updates results after 300ms with no button press — results visible while still typing
  2. Each result row shows title, source domain, and an excerpt with query terms highlighted in bold
  3. Clicking a result or pressing Enter renders the full article text in a right-side detail pane without opening a new browser tab
  4. The filter sidebar (manufacturer, era_bucket, body_style) narrows results without clearing the search query; filter state survives retyping a new query
  5. UI renders with a dark background by default (CSS variables — no Qt dependency)
  6. Result count and query time appear below the search box (e.g., "42 results (0.08s)")
  7. Arrow keys move selection through results; Enter opens the selected result; Escape clears the search input

**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure & Schema Foundation | v1.0 | 4/4 | Complete | 2026-05-13 |
| 2. Data Pipeline (Scraper + Indexer) | v1.0 | 5/5 | Complete | 2026-05-15 |
| 3. Search Logic & Relevance Scoring | v1.0 | 3/3 | Complete | 2026-05-28 |
| 4. Desktop UI | v1.0 | 4/4 | Complete | 2026-05-28 |
| 5. Packaging & Distribution | v1.0 | 2/2 | Complete | 2026-05-29 |
| 6. Server Lifecycle & Cleanup | v1.1 | 0/3 | Not started | - |
| 7. Search REST API | v1.1 | 1/1 | Complete    | 2026-06-03 |
| 8. Browser Search UI | v1.1 | 0/? | Not started | - |
