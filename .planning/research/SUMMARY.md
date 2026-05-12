# Project Research Summary

**Project:** NitroFind — Offline Automotive Desktop Search Engine
**Domain:** Desktop reference application; offline search over a curated content corpus
**Researched:** 2026-05-12
**Confidence:** HIGH

---

## Executive Summary

NitroFind is a single-user offline desktop encyclopedia for automotive enthusiasts: a local Elasticsearch 8.x node holds all scraped content, a PyQt6 GUI provides instant search and inline article rendering, and a one-shot Python scraper populates the database from Wikipedia and four automotive blog domains. The architecture separates cleanly into two phases — a data pipeline (scrape → index, run manually) and a search runtime (Elasticsearch node + GUI, run always) — with Elasticsearch as the sole shared state between them. This separation means the pipeline and UI can be built and tested independently, which is the right strategy for managing scope and debugging early problems.

The recommended stack is non-negotiable by project constraints (Python + Elasticsearch + PyQt) but the research validates specific version choices that prevent known failure modes: Elasticsearch 8.18.x over 9.x (avoids aggregation regressions and TLS-by-default complexity), Python 3.11 (stable sweet spot for PyQt6 and elasticsearch-py 8.x compatibility), PyQt6 6.11 over PyQt5 (Qt6 rendering pipeline required for a modern feel). The relevance model uses Elasticsearch function_score with four signals — domain authority, recency decay, article length, and image count — combined with score_mode: sum and boost_mode: multiply. This delivers deterministic, inspectable ranking without any ML dependency, which aligns with the project's explicit no-AI constraint.

The top risks are infrastructure-level, not product-level: Elasticsearch 8's TLS-by-default breaks plain HTTP connections out of the box; JVM heap defaults claim 4–8 GB on a desktop machine; storing raw HTML instead of extracted text will exhaust the 2 GB cap before meaningful content is indexed; and blocking the PyQt main thread with synchronous ES calls produces an unusable UI. All four are avoidable with explicit configuration decisions made in the first build phase, before any scraping or UI work begins. The scraper carries secondary risks around Wikipedia disambiguation pages, duplicate content via redirect chains, and rate limiting on commercial blog sites — all addressed by using the MediaWiki API for Wikipedia and building URL deduplication with pageid-as-_id from the start.

---

## Key Findings

### Recommended Stack

The stack is fixed by project constraints; research focused on validating correct versions and ruling out alternatives. Every major technology choice has a documented rationale for why it beats the alternatives in this specific context.

**Core technologies:**

| Technology | Version | Purpose | Key rationale |
|------------|---------|---------|---------------|
| Elasticsearch | 8.18.x | Full-text search + function_score ranking | ES9 has aggregation regression reports; ES8 security-disabled single-node mode is simpler for local desktop |
| Python | 3.11.x | All application logic | Stable compatibility ceiling for both elasticsearch-py 8.x and PyQt6 6.11 |
| PyQt6 | 6.11.0 | Desktop GUI | Qt6 rendering pipeline required for modern feel; PyQt5 is feature-frozen on Qt5 |
| elasticsearch-py | 8.18.x (`"elasticsearch>=8,<9"`) | Python ES client | Pin to 8.x; 9.x client against 8.x server breaks API calls; elasticsearch-dsl merged into core at 8.18 |
| requests + BeautifulSoup4 | 2.32.x / 4.12.x | Blog scraping | Scrapy is overkill for 5 fixed domains; no JavaScript rendering needed |
| mediawikiapi | latest | Wikipedia data | Use structured MediaWiki API, not raw HTML — more stable, rate-limit aware, returns infobox data |
| SQLite (stdlib) | 3.x | Scraper URL state tracking | Dedup only; not a content mirror of the ES index |
| PyInstaller | 6.x | App packaging | Best PyQt6 hooks; Elasticsearch is NOT bundled — ships as a separate pre-extracted directory |

**Critical version pins:** Do not use elasticsearch>=9; do not use PyQt5; do not use Scrapy or Selenium.

See `.planning/research/STACK.md` for full rationale and alternatives analysis.

### Expected Features

**Must have (table stakes) — MVP:**
- As-you-type instant search with 150–300 ms debounce and match highlighting
- Result list: title + source domain badge + 2-line summary snippet
- Inline article detail pane (split-pane: results left, article right)
- Sidebar filters: Manufacturer, Era bucket, Body Style, Country of Origin, Source Domain
- Dark/light theme toggle
- Keyboard navigation: Ctrl+L (search focus), Arrow+Enter (result selection), Escape (clear)
- function_score with all four static signals configured from day one
- Zero-results messaging, persistent filter state across searches

**Should have (differentiators) — ship if time allows:**
- Era bucket browsing (Pre-War, Vintage/Classic, Malaise, Modern, Contemporary) — unique first-class filter
- Infobox spec panel in article detail view — structured data alongside prose
- Source domain badge in results (Wikipedia vs. Hagerty vs. Car and Driver)
- Query history (session-only, arrow-up recall)
- Keyboard shortcut Ctrl+L / Ctrl+K for search focus from anywhere

**Defer to later milestones:**
- Engine type and drivetrain secondary filters (reliable field extraction required first)
- Article source quality badge ("High/Medium/Low" from score) — needs score calibration after real data
- Secondary filter facets: engine configuration, drivetrain/layout

**Explicit anti-features (never build):**
- Background indexer at startup
- Auto-update / phone-home behavior
- Pagination (numbered pages signal ranking failure — use scroll-to-load instead)
- Spell autocorrect (breaks automotive proper nouns like "Koenigsegg", "Giulietta")
- Settings sprawl — expose only theme, font size, results count

See `.planning/research/FEATURES.md` for full filter taxonomy, document field schema, and relevance signal hierarchy.

### Architecture Approach

The system is two architecturally separate phases connected only through the Elasticsearch index. The data pipeline (scraper → indexer) is a CLI-driven, one-shot process that writes NDJSON files and bulk-indexes them into ES. The search runtime (Elasticsearch node + PyQt6 GUI) is a persistent process where the UI dispatches all ES queries to background QRunnable workers via QThreadPool, and receives results via pyqtSignal — the main thread never touches the ES HTTP layer directly.

**Major components:**

| Component | Responsibility |
|-----------|---------------|
| `core/launcher.py` | Starts/stops ES subprocess; polls /_cluster/health for yellow/green; shows splash during 5–15s JVM warmup |
| `core/config.py` | Central constants; read-only; imported by all other modules |
| `core/models.py` | ArticleResult dataclass; shared between search/ and ui/ |
| `scraper/wikipedia.py` | MediaWiki API fetcher; uses pageid as document ID to prevent redirect duplicates |
| `scraper/blog_parsers/<domain>.py` | One file per domain; BS4+lxml extraction; ~50 lines each |
| `scraper/state.py` | SQLite URL dedup checkpoint |
| `indexer/schema.py` | Explicit ES mapping; defined before first document; dynamic: false; flattened type for variable infobox data |
| `indexer/bulk_indexer.py` | Reads NDJSON; validates required fields; bulk-indexes in batches of 200 |
| `search/query_builder.py` | Builds multi_match + function_score + bool.filter query DSL |
| `search/result_parser.py` | Parses ES response into list[ArticleResult] with highlight snippets |
| `ui/workers.py` | SearchWorker(QRunnable) + SearchSignals(QObject) — all ES I/O off the main thread |
| `ui/search_bar.py` | QLineEdit + QTimer 300 ms debounce; dispatches workers |
| `ui/result_list.py` | QListView + QAbstractListModel (not QListWidget) for virtual rendering |
| `ui/filter_panel.py` | Filter checkboxes/lists; state persists across searches |
| `ui/detail_view.py` | QTextBrowser rendering full article body from ES _source |

**Hard architectural boundary:** ui/ never imports from scraper/ or indexer/. ui/ only imports from search/. The ES client lives in search/client.py as a singleton passed by reference to worker threads.

See `.planning/research/ARCHITECTURE.md` for full data flow diagrams, ES schema, function_score query implementation, and the 11-step build order.

### Critical Pitfalls

**Critical (cause rewrites or total failure):**

1. **Elasticsearch 8 TLS by default (C-1)** — ES 8.x starts with xpack.security.enabled: true and HTTPS; plain http://localhost:9200 returns ConnectionError. Prevention: set xpack.security.enabled: false, xpack.security.http.ssl.enabled: false, network.host: 127.0.0.1 in elasticsearch.yml before first boot. Address in Phase 1.

2. **JVM heap defaults consume 4–8 GB on desktop (C-2)** — ES auto-sizes to 50% of system RAM. On an 8 GB machine this starves the OS and PyQt process. Prevention: pin jvm.options to -Xms512m -Xmx512m. Sufficient for a 2 GB read-heavy index. Address in Phase 1.

3. **Raw HTML storage blows the 2 GB cap (C-3)** — A Wikipedia article averages 40 KB HTML but 8 KB plain text. 20,000 articles × 40 KB = 800 MB HTML alone. Prevention: strip HTML to plain text at scrape time using trafilatura or readability-lxml; never store raw HTML in ES. Address in Phase 2.

4. **No URL deduplication causes 3–5x article count bloat (C-4)** — Wikipedia's link graph produces many paths to the same article. Prevention: use Wikipedia pageid (not title) as ES _id; normalize blog URLs before fetching; content-hash check before indexing. Address in Phase 2.

5. **Blocking the PyQt main thread with ES calls (C-6)** — es.search() in a textChanged slot blocks the UI thread for 5–200 ms per query. Prevention: all ES calls run in QRunnable workers dispatched via QThreadPool; results returned via pyqtSignal. Address in Phase 3.

**Moderate (significant quality problems):**

6. **Decay functions return 1.0 for missing published_date (M-1)** — undated scraped articles score as if published today, distorting freshness signal. Prevention: use script_score with explicit missing-field handling, or pre-compute a publish_date_score float field with missing: 0.3. Address during relevance scoring.

7. **Dynamic mapping explosion from variable infobox fields (M-2)** — Wikipedia infoboxes have wildly different keys across article types; hits 1,000-field limit. Prevention: dynamic: false on the index; store variable infobox data in a single specs field with type: flattened. Address in Phase 1 schema design.

8. **ES startup blocks UI with no feedback (M-3)** — JVM takes 15–45 seconds cold; a blank window looks like a crash. Prevention: show splash screen before app.exec(); poll /_cluster/health?wait_for_status=yellow&timeout=60s. Address in Phase 1/4.

9. **Wikipedia disambiguation and non-article pages enter the index (C-5)** — disambiguation pages look valid but contain no useful content. Prevention: filter by MediaWiki namespace 0; check pageprops for disambiguation flag. Address in Phase 2.

10. **Commercial blog rate limiting / IP block (M-4)** — Car and Driver, Road and Track, Hagerty run WAF. Full-speed scraping triggers 429s. Prevention: 2–5 second randomized delay; validate response body length. Address in Phase 2.

See `.planning/research/PITFALLS.md` for full pitfall inventory with detection signs and code patterns.

---

## Implications for Roadmap

### Suggested Phase Structure

The build order follows a strict dependency chain: infrastructure before schema, schema before scraper, scraper before indexer, indexed data before search logic, search logic before UI. Violating this order requires painful rework when field names change or ES configuration must be corrected.

---

### Phase 1: Infrastructure and Schema Foundation

**Rationale:** Everything downstream depends on Elasticsearch being correctly configured and the index schema being locked. Schema changes after data is indexed require a full re-index. Configure ES before writing a single line of scraper or UI code.

**Delivers:**
- Elasticsearch 8.18.x running on localhost with TLS disabled, heap pinned, discovery.type: single-node, number_of_replicas: 0
- car_articles index created with explicit mapping (dynamic: false, flattened type for infobox, all filter/score fields defined)
- core/config.py, core/models.py, and core/launcher.py with ES health check
- Startup splash screen that polls cluster health before showing the main window

**Avoids:** C-1 (TLS), C-2 (heap), M-2 (mapping explosion), M-3 (startup blocking UI), m-4 (disk watermark)

**Research flag:** Standard patterns. ES single-node configuration is well-documented. Skip research-phase for this phase.

---

### Phase 2: Data Pipeline — Scraper and Indexer

**Rationale:** The search runtime is useless without data. Building the scraper before the UI keeps the two workstreams fully independent. The scraper must produce clean, deduplicated content within the 2 GB envelope before any UI work begins.

**Delivers:**
- scraper/wikipedia.py: MediaWiki API fetcher using pageid as document ID; namespace-0 filter; disambiguation detection
- scraper/blog_parsers/<domain>.py: one file each for caranddriver, roadandtrack, hagerty, hemmings; BS4+lxml; 2–5s crawl delay; response validation
- scraper/state.py: SQLite URL dedup checkpoint
- indexer/bulk_indexer.py: reads NDJSON, validates required fields, bulk-indexes in batches of 200
- Full pipeline smoke test: scrape 100 articles, index, verify count in ES

**Avoids:** C-3 (raw HTML), C-4 (URL dedup), C-5 (disambiguation pages), M-4 (rate limiting), M-5 (Wikipedia redirect duplicates), m-5 (infobox KeyError)

**Research flag:** Blog parser selectors are MEDIUM confidence — site structures may change. Manually inspect each domain's HTML before writing the parser. No research-phase needed but allocate discovery time per domain.

---

### Phase 3: Search Logic and Relevance Scoring

**Rationale:** With real indexed data available from Phase 2, the relevance model can be built and tuned against actual articles. Scoring without real data produces untestable weights. This phase delivers the core query engine that the UI consumes as a black-box service.

**Delivers:**
- search/client.py: ES client singleton
- search/query_builder.py: multi_match + function_score with four signals; bool.filter for sidebar filters; fuzziness: AUTO for typo tolerance
- search/result_parser.py: response to list[ArticleResult] with highlight snippets, scores, metadata
- Score calibration: representative queries against real data; adjust weights until ranking matches intuition
- Fix for M-1: script_score with explicit missing handling for published_date

**Avoids:** M-1 (decay missing field), m-2 (negative script scores), Anti-pattern 6 (score_mode: multiply with zero signals)

**Research flag:** function_score weight tuning is empirical — cannot be pre-determined. Build in a scoring test harness (log explain=true responses for representative queries) to make tuning fast. No research-phase needed.

---

### Phase 4: PyQt6 Desktop UI

**Rationale:** The UI consumes the search/ layer as a complete API. Building it last means the underlying data quality and query behavior are known quantities. UI polish and search quality cannot be evaluated in isolation.

**Delivers:**
- ui/main_window.py: split-pane layout (result list left, detail view right, filter panel sidebar)
- ui/search_bar.py: QLineEdit + QTimer 300 ms debounce + QRunnable worker dispatch (never blocks main thread)
- ui/result_list.py: QListView + QAbstractListModel with virtual rendering; domain badge; highlight rendering
- ui/filter_panel.py: Manufacturer, Era bucket, Body Style, Country of Origin, Source Domain filters; persistent state across searches
- ui/detail_view.py: QTextBrowser rendering full article body; infobox spec panel if time allows
- Keyboard shortcuts: Ctrl+L (search focus), Arrow+Enter (navigate results), Escape (clear)
- Dark/light theme via qt-material

**Avoids:** C-6 (main thread blocking), m-1 (QListWidget lag on 200+ items)

**Research flag:** QWebEngineView vs QTextBrowser for article rendering needs a decision before UI work starts. For MVP, QTextBrowser is recommended unless scraped content includes rich HTML layout that requires WebEngine. Low-risk decision point, not a research-phase trigger.

---

### Phase 5: Packaging and Distribution

**Rationale:** Distribution is not a Phase 1 problem but needs a clear model from day one. PyInstaller cannot bundle the JVM — this constraint must inform how the app is installed and documented.

**Delivers:**
- PyInstaller 6.x spec file bundling the PyQt6 app
- Installer (NSIS on Windows, shell script on Linux/macOS) placing the pre-extracted Elasticsearch 8.18.x directory alongside the Python executable
- Setup script configuring elasticsearch.yml, jvm.options, and verifying Java availability
- End-to-end smoke test on a clean machine

**Avoids:** m-3 (JVM not bundleable by PyInstaller)

**Research flag:** NSIS installer packaging for Windows with bundled ES directory is MEDIUM confidence — this combination is uncommon in public documentation. Flag for research-phase during planning if targeting Windows as primary platform.

---

### Phase Ordering Rationale

- Infrastructure before everything: ES misconfiguration discovered in Phase 3 would require re-indexing all Phase 2 data.
- Schema before scraping: field names and types set in Phase 1 are what the scraper must produce. A schema change after indexing requires a full re-index.
- Data before UI: search quality cannot be evaluated without representative data; relevance weights cannot be tuned against empty or synthetic data.
- Scraper and indexer before search logic: function_score weights need real document distributions to tune.
- Search logic before UI: the UI consumes search/ as a complete, tested service. Building them in parallel adds integration risk.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 5 (Packaging):** Windows NSIS + bundled ES directory — uncommon pattern, sparse documentation. Use research-phase if targeting Windows as the primary distribution target.
- **Phase 2 (Blog parsers):** Each domain's HTML structure must be manually inspected before writing the parser. Allocate discovery time per domain; not a research-phase trigger.

Phases with well-documented standard patterns (skip research-phase):

- **Phase 1 (ES Infrastructure):** Official Elastic documentation covers all configuration decisions.
- **Phase 3 (Search Logic):** function_score query structure is fully documented; weight tuning is empirical.
- **Phase 4 (PyQt6 UI):** QRunnable/QThreadPool and QListView+model patterns are documented in official PyQt6 docs.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations verified against official PyPI, elastic.co release notes, and Riverbank Computing docs. Version pins have documented rationale. |
| Features | HIGH | Grounded in analysis of direct UX comparators (Zeal, Kiwix) and Wikipedia's own Infobox Automobile template schema. Anti-features backed by documented user complaints. |
| Architecture | HIGH | Component boundaries and data flow follow official Elasticsearch and PyQt6 patterns. Code samples verified against official docs. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls verified against official Elastic troubleshooting docs and GitHub issues. Blog rate-limiting behavior is MEDIUM — WAF configurations change. |

**Overall confidence:** HIGH

### Gaps to Address

- **Blog parser selector stability (MEDIUM):** CSS selectors for Car and Driver, Road and Track, Hagerty, and Hemmings will drift as sites update. Mitigation: build per-domain parsers to be easily replaceable; validate output on each scraper run; log articles with suspiciously short body text as a detection heuristic.

- **function_score weight calibration (MEDIUM):** Signal weights (domain authority: 2.0, recency: 1.5, word count: 0.8, image count: 0.3) are based on information retrieval literature but are not tuned against NitroFind's actual corpus. Weight tuning is an empirical task in Phase 3 with real indexed data. Plan for iteration time.

- **Windows JVM startup time on HDDs (MEDIUM):** Research cites 15–45 seconds cold start. The upper bound on spinning HDDs with Windows Defender scanning is unknown and potentially longer. The splash screen with a 90-second timeout should handle this but should be validated during Phase 4 QA on slow hardware.

- **2 GB envelope with full content scope (MEDIUM):** The cap is tight for Wikipedia automotive articles + 4 blog domains. The exact article count achievable within 2 GB depends on average article length after cleaning — this needs empirical measurement during Phase 2 pilot scraping. Plan a hard cutoff point before indexing to avoid exceeding the cap.

---

## Sources

### Primary (HIGH confidence)

- Elasticsearch 8.19 reference docs (elastic.co/guide) — function_score, mappings, analyzers, cluster health, JVM settings
- elasticsearch-py 8.x on PyPI — version history, DSL merge into core at 8.18.0
- PyQt6 6.11 on PyPI — current version, Python >=3.10 requirement
- Riverbank Computing PyQt6 docs — QRunnable, QThread, QThreadPool, signals
- Elastic blog — Elasticsearch 9.0 release notes — rationale for staying on 8.x
- Wikipedia Template:Infobox automobile — automotive data field taxonomy (35+ fields)
- Elastic troubleshooting docs — high JVM pressure, mapping explosion, disk watermark, corruption
- PyInstaller 6.x docs — PyQt6 hooks, common pitfalls

### Secondary (MEDIUM confidence)

- pythonguis.com PyQt6 tutorials — QThreadPool multithreading, packaging with PyInstaller, PyQt5 vs PyQt6
- Zeal offline browser and GitHub issues — UX comparator, real user complaints
- Kiwix offline reader — offline encyclopedia feature set
- Elastic blog — function scoring — score_mode / boost_mode guidance
- Elasticsearch GitHub issue #7788 — decay missing field returns 1.0 (M-1 pitfall source)
- MediaWiki web scraping access docs — rate limits, API preference
- Automobile-Catalog and Teoalida Car Database — filter taxonomy reference
- Classic car era standards (PreWarCar.com, American Collectors Insurance) — era boundary conventions

### Tertiary (LOW confidence)

- Elasticsearch 9.x aggregation regression reports — cited in community posts, not formally benchmarked against NitroFind's specific query patterns. The decision to stay on 8.x is conservative and correct regardless.
- Blog site CSS selectors for article extraction — based on site inspection at research time; will need re-validation during Phase 2.

---

*Research completed: 2026-05-12*
*Ready for roadmap: yes*
