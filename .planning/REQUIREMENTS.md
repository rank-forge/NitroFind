# Requirements: NitroFind v1.1

**Defined:** 2026-06-03
**Core Value:** Instant, noise-free access to deep automotive knowledge — the entire database on your machine, searchable in milliseconds.
**Milestone goal:** Replace the PyQt6 desktop UI with a Flask web server accessible at http://localhost:5000. Single `python main.py` starts Elasticsearch and the web server together. Scraper and search engine from v1.0 are preserved without rewrite.

## v1.1 Requirements

### Server Lifecycle

- [ ] **SRVR-01**: A single `python main.py` command starts Elasticsearch 8.18 and the Flask web server — no separate startup steps required
- [ ] **SRVR-02**: Flask server listens on `http://localhost:5000` (port overridable via `PORT` environment variable)
- [ ] **SRVR-03**: Flask server waits for Elasticsearch to pass a health check before accepting search requests; returns HTTP 503 with `{"status": "starting"}` during warmup
- [ ] **SRVR-04**: Ctrl+C (SIGINT) terminates both the Flask server and the Elasticsearch subprocess cleanly — no orphaned JVM processes after exit

### REST API

- [ ] **API-01**: `GET /api/search?q={query}` returns a JSON array of ranked results — each with title, url, source_domain, excerpt (with ES highlight tags), score, took_ms
- [ ] **API-02**: `GET /api/search` accepts optional filter params `manufacturer`, `era_bucket`, `body_style` that narrow results using the existing `build_filter_clauses()` logic
- [ ] **API-03**: `GET /api/status` returns JSON with Elasticsearch health (green/yellow/red), document count, and index size
- [ ] **API-04**: `GET /` serves the main HTML search page (single-page app entry point)

### Search Interface (Browser)

- [ ] **SRCH-01**: Search box updates results as the user types with a 300ms debounce — no button press required
- [ ] **SRCH-02**: Each result row displays the article title, source domain, and an excerpt with matching query terms visually highlighted (bold)
- [ ] **SRCH-03**: Clicking a result (or pressing Enter) displays the full article text in a right-side detail pane — no new browser tab opens
- [ ] **SRCH-04**: Filter sidebar (manufacturer, era_bucket, body_style) narrows results without clearing the search query; filter state persists across query retypes

### UI Quality (Browser)

- [ ] **UIPL-01**: UI ships with a dark theme as default (CSS variables — no Qt dependency)
- [ ] **UIPL-02**: Result count and query time are displayed below the search box (e.g., "42 results (0.08s)")
- [ ] **UIPL-03**: User can navigate results with arrow keys, open with Enter, and clear the search box with Escape

### Cleanup

- [ ] **CLEN-01**: PyQt6, PyQt6-Qt6, PyQt6-sip, and qt-material removed from requirements.txt and all imports — app no longer requires a Qt install

## Future Requirements (v1.2+)

- Full installer / startup shortcut (Windows .bat, macOS .command)
- Light/dark theme toggle in the browser UI
- Search history (last N queries, persisted in localStorage)
- Bookmarking — save articles to a favorites list
- `/api/article/{id}` endpoint for fetching individual articles by ES _id
- Filter by engine type, drivetrain, country of manufacture

## Out of Scope

| Feature | Reason |
|---------|--------|
| Motorcycles, trucks, non-car vehicles | Keeps database under 2 GB |
| AI/ML-based relevance | Deliberate — deterministic math only |
| Online/cloud mode | Offline-first is the core product promise |
| User accounts or authentication | Single-user local tool |
| Production deployment / WSGI / HTTPS | Local dev server only — Flask dev server is sufficient for localhost |
| PyInstaller packaging | Removed — `python main.py` is the distribution model for v1.1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRVR-01 | Phase 6 | Pending |
| SRVR-02 | Phase 6 | Pending |
| SRVR-03 | Phase 6 | Pending |
| SRVR-04 | Phase 6 | Pending |
| API-01 | Phase 7 | Pending |
| API-02 | Phase 7 | Pending |
| API-03 | Phase 7 | Pending |
| API-04 | Phase 7 | Pending |
| SRCH-01 | Phase 8 | Pending |
| SRCH-02 | Phase 8 | Pending |
| SRCH-03 | Phase 8 | Pending |
| SRCH-04 | Phase 8 | Pending |
| UIPL-01 | Phase 8 | Pending |
| UIPL-02 | Phase 8 | Pending |
| UIPL-03 | Phase 8 | Pending |
| CLEN-01 | Phase 6 | Pending |

**Coverage:**
- v1.1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-03*
