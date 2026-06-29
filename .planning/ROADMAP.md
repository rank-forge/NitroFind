# Roadmap: NitroFind

## Milestones

- ✅ **v1.0 MVP** — Phases 1–5 (shipped 2026-05-29)
- ✅ **v1.1 Web Interface** — Phases 6–8 (shipped 2026-06-04)
- 🔄 **v1.2 Search Quality & UX Polish** — Phases 9–13 (in progress)

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

<details>
<summary>✅ v1.1 Web Interface (Phases 6–8) — SHIPPED 2026-06-04</summary>

- [x] Phase 6: Server Lifecycle & Cleanup (3/3 plans) — completed 2026-06-03
- [x] Phase 7: Search REST API (1/1 plans) — completed 2026-06-03
- [x] Phase 8: Browser Search UI (3/3 plans) — completed 2026-06-04

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

### v1.2 Search Quality & UX Polish (Phases 9–13)

- [x] **Phase 9: Article Rendering Fixes** - Fix table stripping and body text bloat in the detail pane (completed 2026-06-25)
- [x] **Phase 10: Search Quality & Sort** - Add fuzzy/phrase search routing and sort controls (completed 2026-06-26)
- [ ] **Phase 11: Extended Filtering** - Year range and country filters in API and UI
- [ ] **Phase 12: Pagination** - Result pages with Previous / Next navigation and total hit count
- [ ] **Phase 13: History & Theme** - Search history (localStorage) and dark/light theme toggle

## Phase Details

### Phase 9: Article Rendering Fixes
**Goal**: Users see clean, properly formatted article content in the detail pane
**Depends on**: Nothing (bug fixes, self-contained)
**Requirements**: BUG-01, BUG-02
**Success Criteria** (what must be TRUE):
  1. Opening a Wikipedia article in the detail pane shows rendered tables (make/model specs, production years) rather than missing or stripped table content
  2. Article body text contains only prose — navigation menus, sidebar links, and anchor text are absent from the displayed content
  3. A Hagerty blog article opened in the detail pane similarly shows any embedded tables and contains no navigation link text
**Plans**: 4 plans
  - [x] 09-01-PLAN.md — Failing-test scaffold (Wave 0: RED tests for strip_nav_sections, _clean_wikipedia_html, body_html)
  - [ ] 09-02-PLAN.md — Scraper + ES schema (BUG-01 HTML capture, BUG-02 noise removal, body_html field, --recreate flag)
  - [ ] 09-03-PLAN.md — Search/API/frontend (body_html through model→API→innerHTML render + table CSS)
  - [ ] 09-04-PLAN.md — Index re-create + re-scrape + human UI verification (checkpoint)

### Phase 10: Search Quality & Sort
**Goal**: Users get correct results despite typos and can control result ordering
**Depends on**: Phase 9
**Requirements**: QURY-01, QURY-02, SORT-01, SORT-02
**Success Criteria** (what must be TRUE):
  1. Searching "Ferari" or "Lamborgini" returns the expected manufacturer articles (fuzzy tolerance applied)
  2. Searching `"V8 engine"` (with quotes) returns articles that contain the exact phrase, ranked above articles with the words scattered
  3. Clicking "By date" reorders visible results newest-first; clicking "By size" reorders largest-first; clicking "By relevance" restores default scoring order
  4. The `GET /api/search?sort=date` and `sort=size` params produce correctly ordered ES results independent of the UI
**Plans**: 2 plans
  - [x] 10-01-PLAN.md — Backend query routing: fuzzy (QURY-01), phrase routing (QURY-02), sort param (SORT-02)
  - [x] 10-02-PLAN.md — Frontend sort UI: toggle buttons wired to sort= param (SORT-01)
**UI hint**: yes

### Phase 11: Extended Filtering
**Goal**: Users can narrow results to a specific production era and country of origin
**Depends on**: Phase 10
**Requirements**: FILT-01, FILT-02, FILT-03
**Success Criteria** (what must be TRUE):
  1. Entering "1960" in the Year From field and "1975" in the Year To field limits results to articles whose production period overlaps that range
  2. Entering "Germany" in the Country filter returns only articles tagged with German origin
  3. Year range and country filters combine correctly with the existing manufacturer, era_bucket, and body style filters — all active filters apply simultaneously
  4. The `GET /api/search?year_from=&year_to=&country=` params are accepted and mapped to ES filter clauses
**Plans**: 3 plans
  - [x] 11-01-PLAN.md — Failing-test scaffold (Wave 0: RED tests for year/country filter clauses + API forwarding)
  - [ ] 11-02-PLAN.md — Backend: extend build_filter_clauses (FILT-01/02) + api_search param coercion (FILT-03)
  - [ ] 11-03-PLAN.md — Frontend filter-row controls (year/country inputs) + human UI verification (checkpoint)
**UI hint**: yes

### Phase 12: Pagination
**Goal**: Users can navigate through more than 10 results without losing context
**Depends on**: Phase 11
**Requirements**: PAGE-01, PAGE-02
**Success Criteria** (what must be TRUE):
  1. A search returning more than 10 results shows only 10 at a time with Previous and Next buttons below the result list
  2. Clicking Next loads the next 10 results; clicking Previous returns to the prior page without re-executing the full query from scratch
  3. The result count line reads "248 results (0.08s)" — total hits across all pages, not just the current page
**Plans**: TBD
**UI hint**: yes

### Phase 13: History & Theme
**Goal**: Users can revisit past searches and choose their preferred visual theme
**Depends on**: Phase 9
**Requirements**: HIST-01, HIST-02, THME-01
**Success Criteria** (what must be TRUE):
  1. After executing several searches the history list shows the last 10 unique queries, most recent first
  2. Clicking a query in the history list immediately re-executes that search and populates the search box with the query text
  3. Clicking the theme toggle in the header switches between dark and light themes without a page reload
  4. After toggling to light mode and refreshing the page, the light theme is still active (preference persisted in localStorage)
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
| 6. Server Lifecycle & Cleanup | v1.1 | 3/3 | Complete | 2026-06-03 |
| 7. Search REST API | v1.1 | 1/1 | Complete | 2026-06-03 |
| 8. Browser Search UI | v1.1 | 3/3 | Complete | 2026-06-04 |
| 9. Article Rendering Fixes | v1.2 | 4/4 | Complete | 2026-06-25 |
| 10. Search Quality & Sort | v1.2 | 2/2 | Complete    | 2026-06-26 |
| 11. Extended Filtering | v1.2 | 1/3 | In Progress|  |
| 12. Pagination | v1.2 | 0/? | Not started | - |
| 13. History & Theme | v1.2 | 0/? | Not started | - |
