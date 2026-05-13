# Phase 2: Data Pipeline (Scraper + Indexer) - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

A one-shot CLI scraper populates the `car_articles` Elasticsearch index with clean, deduplicated automotive articles from Wikipedia (via MediaWiki API) and at least one automotive blog (via BeautifulSoup4). The scraper produces a running SQLite state file so interrupted runs can be resumed. Phase 2 delivers no UI code and no search logic — only the data pipeline that makes Phase 3 possible.

</domain>

<decisions>
## Implementation Decisions

### Wikipedia Article Selection Scope
- **D-01:** Walk Wikipedia category trees recursively, starting from root car categories defined in a config file. Depth limit: 2 levels from each root category.
- **D-02:** Filter articles before indexing: only index pages that have an infobox (`has_infobox = true`). Infobox presence distinguishes structured car articles from disambiguation pages, list articles, and stubs.
- **D-03:** Root categories are stored in a config file (e.g., `config/scraper.yaml` or `config/scraper_config.py`), not hardcoded. Researcher selects the best starting Wikipedia categories. User can adjust without touching source code.

### Scraper CLI Design
- **D-04:** Single entrypoint (`scraper.py` or `scripts/scraper.py`). Optional source flags: `--wikipedia`, `--blogs`, `--all` (default). Simple and discoverable.
- **D-05:** Progress reporting via live logging to stdout: log current category being walked, running article count indexed, and current index size estimate. No external progress bar library required.
- **D-06:** Resume support via SQLite state tracking (CLAUDE.md prescribes this). Track scraped page IDs/URLs. Re-runs skip already-indexed articles — safe to interrupt anytime without re-fetching.

### Pre-locked Decisions (from CLAUDE.md + Phase 1)
- **L-01:** Wikipedia source: MediaWiki API only — no raw HTML parsing (SCRP-01). Use `mediawikiapi` library.
- **L-02:** Blog source: BeautifulSoup4 + `requests` (SCRP-02). At least one of: Car and Driver, Hagerty, Hemmings, Road & Track.
- **L-03:** MediaWiki page ID used as ES document `_id` for Wikipedia articles — prevents duplicates from redirect paths (SCRP-03).
- **L-04:** Scraper halts and logs a warning when index approaches 1.8 GB (SCRP-04).
- **L-05:** `body` field must contain plain text only — no HTML tags (SCHEMA-03).
- **L-06:** `excerpt` is capped at 300 characters (SCHEMA-03).
- **L-07:** `era_bucket` derived from `production_start` via `f"{(year // 10) * 10}s"` (D-08 from Phase 1). Set to `"Unknown"` when `production_start` is missing (D-10 from Phase 1).
- **L-08:** ES index schema is fully locked — see `nitrofind/es_schema.py` `CAR_ARTICLES_MAPPING`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase & Requirements
- `.planning/ROADMAP.md` — Phase 2 goal, success criteria (4 items), and requirements list (SCRP-01 through SCRP-04)
- `.planning/REQUIREMENTS.md` — Full SCRP-01..04 requirement text with acceptance conditions
- `.planning/PROJECT.md` — Tech stack constraints, data pipeline context, key decisions table

### Technology Stack
- `CLAUDE.md` — Full stack rationale: mediawikiapi for Wikipedia, requests + BS4 for blogs, SQLite for scraper state, elasticsearch==8.x client, Python 3.11, scraper architecture decisions

### Existing Implementation (Phase 1 outputs)
- `nitrofind/es_schema.py` — `CAR_ARTICLES_MAPPING` (all indexed fields, types, and constraints) + `ensure_index()` (idempotent index creation to call at scraper startup)
- `nitrofind/es_manager.py` — `ES_URL` constant (`http://localhost:9200`), `ESHealthWorker` pattern (not used by scraper directly, but shows ES client usage conventions)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nitrofind/es_schema.py` — `ensure_index(client)` is idempotent; scraper should call it at startup to guarantee the index exists before writing documents
- `nitrofind/es_manager.py` — `ES_URL = "http://localhost:9200"` — import this constant rather than hardcoding the URL again
- `nitrofind/es_manager.py` — `validate_es_home()` pattern for pre-flight validation; scraper should do equivalent validation (e.g., check ES is reachable on localhost:9200 before starting a long scrape run)

### Established Patterns
- ES client initialized as `Elasticsearch(ES_URL, request_timeout=2)` — short request timeout per call; scraper may want a longer timeout for bulk indexing
- `dynamic: "false"` on the index prevents field injection — scraper documents MUST only include fields defined in `CAR_ARTICLES_MAPPING`; any extra keys will be silently dropped by ES
- `flattened` type on `specs` field — Wikipedia infobox key-value pairs can be stored here without mapping explosion
- Error handling pattern: catch `Exception`, log with type name (see `ESHealthWorker.run()`)

### Integration Points
- Scraper calls `ensure_index()` at startup (from `es_schema.py`)
- Scraper indexes documents into `"car_articles"` index using `client.index(index="car_articles", id=<page_id>, document=<doc>)` or bulk API
- Scraper reads root categories from `config/scraper.yaml` (new file, created in this phase)
- Scraper writes SQLite state to a path like `data/scraper_state.db` (new file, created at runtime)

</code_context>

<specifics>
## Specific Ideas

No specific UI references or examples surfaced during discussion. Scraper is a CLI-only tool — no GUI component.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-Data Pipeline (Scraper + Indexer)*
*Context gathered: 2026-05-13*
