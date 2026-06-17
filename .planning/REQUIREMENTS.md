# Requirements: NitroFind v1.2

**Defined:** 2026-06-17
**Core Value:** Instant, noise-free access to deep automotive knowledge — the entire database on your machine, searchable in milliseconds.
**Milestone goal:** Fix article rendering bugs and add smarter search, richer filtering, and UX controls to make NitroFind feel like a complete research tool.

## v1.2 Requirements

### Bug Fixes (BUG)

- [ ] **BUG-01**: Article detail pane renders HTML table elements from Wikipedia and blog articles (currently tables are stripped or not displayed)
- [ ] **BUG-02**: Article body contains only article prose — navigation links, sidebar text, and anchor text are excluded from the ingested body

### Search Quality (QURY)

- [ ] **QURY-01**: User searches with typos ("Ferari", "Lamborgini") and gets correct results — fuzziness: "AUTO" applied to multi_match query
- [ ] **QURY-02**: User wraps a phrase in quotes ("V8 engine") and gets phrase-match results — query routed automatically to match_phrase

### Sort Controls (SORT)

- [ ] **SORT-01**: User can sort results by relevance (default), newest-first (date), or largest-first (size) via toggle buttons in the search UI
- [ ] **SORT-02**: `GET /api/search` accepts an optional `sort` param (`relevance` | `date` | `size`) and applies the corresponding ES sort order

### Filtering (FILT)

- [ ] **FILT-01**: User can filter results by year range (from / to) using `production_start` / `production_end` — fields already mapped in the ES index schema
- [ ] **FILT-02**: User can filter results by country of origin via a free-text input in the filter sidebar
- [ ] **FILT-03**: `GET /api/search` accepts `year_from`, `year_to`, and `country` params and applies them as ES filter clauses alongside the existing `manufacturer`, `era_bucket`, and `body_style` filters

### Pagination (PAGE)

- [ ] **PAGE-01**: Result list shows results in pages (default 10 per page) with Previous / Next navigation buttons
- [ ] **PAGE-02**: Result count below the search box shows total hits across all pages (e.g. "248 results (0.08s)")

### Search History (HIST)

- [ ] **HIST-01**: Last 10 unique search queries are saved to localStorage automatically as the user searches
- [ ] **HIST-02**: User can view the history list and click an entry to re-execute that query

### Theme Toggle (THME)

- [ ] **THME-01**: User can toggle between dark and light themes via a button in the header; preference is stored in localStorage and applied on page reload

## Future Requirements (v1.3+)

- Empirical tuning of function_score weights against real indexed data
- Windows clean-machine smoke test
- Full installer / startup shortcut (Windows .bat, macOS .command)
- `/api/article/{id}` endpoint for fetching individual articles by ES _id
- Favorites — save articles for later reading in localStorage
- Export results — download results as JSON or CSV
- Score explainer — "Why this result?" showing ES function_score breakdown

## Out of Scope (v1.2)

- AI/ML-based relevance — deliberate constraint; scoring uses only explicit math
- Online/cloud mode — offline-first product promise; no external calls at search time
- Periodic auto-update — scraper is a one-shot tool
- User accounts or saved searches — single-user local tool, no auth complexity
- Score explainer — deferred to v1.3

## Requirement Traceability

| Requirement | Phase | Delivered in | Outcome |
|-------------|-------|-------------|---------|
| BUG-01 | Phase 9 | — | — |
| BUG-02 | Phase 9 | — | — |
| QURY-01 | Phase 10 | — | — |
| QURY-02 | Phase 10 | — | — |
| SORT-01 | Phase 10 | — | — |
| SORT-02 | Phase 10 | — | — |
| FILT-01 | Phase 11 | — | — |
| FILT-02 | Phase 11 | — | — |
| FILT-03 | Phase 11 | — | — |
| PAGE-01 | Phase 12 | — | — |
| PAGE-02 | Phase 12 | — | — |
| HIST-01 | Phase 13 | — | — |
| HIST-02 | Phase 13 | — | — |
| THME-01 | Phase 13 | — | — |

---
*Defined: 2026-06-17 for milestone v1.2*
