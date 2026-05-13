# Requirements: NitroFind

**Defined:** 2026-05-12
**Core Value:** Instant, noise-free access to deep automotive knowledge — the entire database on your machine, searchable in milliseconds.

## v1 Requirements

### Infrastructure

- [x] **INFRA-01**: Developer can run the app from a Python venv with a pinned lockfile (reproducible environment across machines)
- [ ] **INFRA-02**: App starts a local Elasticsearch 8.18 node as a subprocess on launch (localhost:9200, TLS disabled, security disabled)
- [ ] **INFRA-03**: App terminates the Elasticsearch process cleanly when the user quits
- [ ] **INFRA-04**: App shows a loading state while Elasticsearch warms up and becomes healthy (cold start takes 5–15 seconds)

### Data Schema

- [ ] **SCHEMA-01**: Each indexed document contains core identity fields: title, url, source_domain, article_id, scraped_at
- [ ] **SCHEMA-02**: Each indexed document contains relevance scoring fields: published_at, word_count, has_infobox, image_count
- [ ] **SCHEMA-03**: Each indexed document contains full plain-text body (for full-text search) and a 300-character excerpt (for result list display)
- [ ] **SCHEMA-04**: Each indexed document contains automotive facet fields: manufacturer, production_start, production_end, body_style, era_bucket, country_of_origin (required by filter sidebar)

### Scraper

- [ ] **SCRP-01**: Scraper fetches car articles from Wikipedia using the MediaWiki API (structured JSON, not HTML parsing)
- [ ] **SCRP-02**: Scraper fetches articles from at least one automotive blog (Car and Driver, Hagerty, Hemmings, or Road & Track) using BeautifulSoup4
- [ ] **SCRP-03**: Scraper uses MediaWiki page ID as the Elasticsearch document `_id` to prevent duplicate articles from redirect paths
- [ ] **SCRP-04**: Scraper stops indexing and logs a warning when the index approaches 1.8 GB (before hitting the 2 GB hard cap)

### Relevance Scoring

- [ ] **RLVN-01**: Search results are ranked using Elasticsearch function_score with Gaussian recency decay (articles published recently score higher; ~2-year half-life)
- [ ] **RLVN-02**: function_score includes an article length signal using a logarithmic modifier on word_count (longer articles score higher, with diminishing returns)
- [ ] **RLVN-03**: function_score includes a boolean boost for articles that have a structured infobox (has_infobox = true)
- [ ] **RLVN-04**: Relevance signals are combined additively (score_mode: sum) so that a missing signal does not zero out a result; text match relevance acts as a multiplier (boost_mode: multiply)

### Search Interface

- [ ] **SRCH-01**: Search results update as the user types, with a 300ms debounce to avoid hammering Elasticsearch on every keystroke
- [ ] **SRCH-02**: Result list displays title, source domain, and a highlighted excerpt for each matching article
- [ ] **SRCH-03**: Selecting a result displays the full article text inline in a detail pane (no browser needed)
- [ ] **SRCH-04**: Filter sidebar lets the user narrow results by manufacturer, production era (era_bucket), and body style without clearing the search query

### UI Quality

- [ ] **UIPL-01**: Query terms are highlighted in the result excerpts so users can see why an article matched
- [ ] **UIPL-02**: Result count and query time are displayed below the search box (e.g., "42 results (0.08s)")
- [ ] **UIPL-03**: UI ships with a dark theme as default
- [ ] **UIPL-04**: User can navigate results with arrow keys, open with Enter, and clear the search box with Escape

### Packaging

- [ ] **PKG-01**: App can be distributed as a PyInstaller bundle alongside a pre-extracted Elasticsearch directory (no Python or Java install required by the end user)

## v2 Requirements

### Filters (Extended)

- **FILT-01**: Filter by engine type (inline-4, V8, flat-6, rotary, etc.)
- **FILT-02**: Filter by country of manufacture
- **FILT-03**: Filter by drivetrain (RWD, FWD, AWD, 4WD)

### Relevance (Extended)

- **RLVN-V2-01**: Domain authority tier weight (manual 1–5 per source domain) as an additional function_score signal
- **RLVN-V2-02**: Inbound link count signal (sqrt modifier) for cross-referenced authority

### Data

- **DATA-01**: Database update workflow — re-run scraper and incrementally re-index without full wipe
- **DATA-02**: Source whitelist/blacklist configuration file for controlling which domains are scraped

### UI

- **UI-V2-01**: Full installer with desktop shortcut (NSIS on Windows, .dmg on macOS)
- **UI-V2-02**: Light/dark theme toggle
- **UI-V2-03**: Search history (last N queries, persisted locally)
- **UI-V2-04**: Bookmarking — save articles to a local favorites list

## Out of Scope

| Feature | Reason |
|---------|--------|
| Motorcycles, trucks, other non-car vehicles | Keeps database under 2 GB; aligns with enthusiast focus |
| AI/ML-based relevance (embeddings, semantic search) | Deliberate design choice — deterministic math only |
| Online/cloud sync or API calls at search time | Offline-first is the core product promise |
| User accounts or authentication | Single-user local tool |
| Real-time database auto-update | Scraper is a one-shot tool; manual re-run is sufficient |
| Web scraping non-automotive content | Out of domain scope |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| SCHEMA-01 | Phase 1 | Pending |
| SCHEMA-02 | Phase 1 | Pending |
| SCHEMA-03 | Phase 1 | Pending |
| SCHEMA-04 | Phase 1 | Pending |
| SCRP-01 | Phase 2 | Pending |
| SCRP-02 | Phase 2 | Pending |
| SCRP-03 | Phase 2 | Pending |
| SCRP-04 | Phase 2 | Pending |
| RLVN-01 | Phase 3 | Pending |
| RLVN-02 | Phase 3 | Pending |
| RLVN-03 | Phase 3 | Pending |
| RLVN-04 | Phase 3 | Pending |
| SRCH-01 | Phase 4 | Pending |
| SRCH-02 | Phase 4 | Pending |
| SRCH-03 | Phase 4 | Pending |
| SRCH-04 | Phase 4 | Pending |
| UIPL-01 | Phase 4 | Pending |
| UIPL-02 | Phase 4 | Pending |
| UIPL-03 | Phase 4 | Pending |
| UIPL-04 | Phase 4 | Pending |
| PKG-01 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-12*
*Last updated: 2026-05-12 after initial definition*
