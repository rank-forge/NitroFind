---
phase: 02-data-pipeline-scraper-indexer
plan: "05"
subsystem: scraper-cli
tags: [cli, argparse, yaml-safety, elasticsearch, integration]
dependency_graph:
  requires: ["02-02", "02-03", "02-04"]
  provides: ["scripts/scraper.py CLI entrypoint"]
  affects: ["data/scraper_state.db (runtime)", "car_articles ES index (runtime)"]
tech_stack:
  added: []
  patterns:
    - "argparse mutually exclusive group for flag routing"
    - "yaml.safe_load enforcement (T-02-01 mitigation)"
    - "ES preflight check via client.info() with request_timeout=5"
    - "streaming_bulk patched at nitrofind.scraper.indexer (correct intercept point)"
key_files:
  created:
    - scripts/scraper.py
    - tests/test_scraper/test_cli.py
  modified: []
decisions:
  - "test_cli.py patches streaming_bulk at nitrofind.scraper.indexer.streaming_bulk (not scripts.scraper) — streaming_bulk is only imported inside the indexer module; patching scripts.scraper would be a silent no-op"
  - "9 tests written (plan spec said 8); the additional test is test_main_calls_ensure_index_before_scrape covering order-of-operations"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-15T16:25:03Z"
  tasks_completed: 2
  tasks_pending: 1
  files_count: 2
---

# Phase 2 Plan 5: CLI Entrypoint (Wave 2) Summary

**One-liner:** argparse CLI composing WikipediaScraper + BlogScraper through BulkIndexer with yaml.safe_load enforcement and ES preflight gate.

## Tasks Completed

### Task 1: scripts/scraper.py (194 lines)

CLI entrypoint wiring all Wave-1 scraper modules.

**Functions:**
- `_setup_logging()` — configures logging.basicConfig at INFO level to stdout; format `%(asctime)s %(levelname)s %(name)s: %(message)s`
- `_load_config(config_path)` — opens YAML with `yaml.safe_load`; exits 1 on FileNotFoundError or YAMLError (T-02-01)
- `_create_client()` — constructs `Elasticsearch(ES_URL, request_timeout=5)`; calls `.info()`; exits 1 on any exception (T-02-21)
- `_ensure_data_dir()` — `os.makedirs("data", exist_ok=True)`
- `_run_wikipedia(config, state, client)` — instantiates WikipediaScraper, builds action generator, calls BulkIndexer.index_all; returns doc count
- `_run_blogs(config, state, client)` — same pattern with BlogScraper
- `_parse_args(argv)` — argparse with `add_mutually_exclusive_group()` for --wikipedia/--blogs/--all; --config default `config/scraper.yaml`
- `main(argv)` — orchestrates: setup logging → parse args → D-04 default --all → load config → create client → ensure_index → ensure_data_dir → SQLiteStateManager context → run scrapers → return 0

**Security confirmations:**
- `yaml.safe_load` present; `yaml.load(` absent
- `ES_URL` imported from `nitrofind.es_manager`; no hardcoded `http://localhost:9200`
- `ensure_index(client)` called before any indexing

### Task 2: tests/test_scraper/test_cli.py (9 tests, all PASSED)

| Test | Covers | Result |
|------|--------|--------|
| test_help_exits_zero | --help exits 0; stdout has all 4 flags | PASSED |
| test_load_config_rejects_yaml_load_in_source | T-02-01 regression guard on source text | PASSED |
| test_main_uses_yaml_safe_load | Malicious YAML payload blocked; exits 1; /tmp/pwned absent | PASSED |
| test_create_client_exits_on_unreachable_es | ES gate exits 1 on ConnectionError | PASSED |
| test_main_runs_wikipedia_only_with_flag | --wikipedia: WikipediaScraper called; BlogScraper NOT | PASSED |
| test_main_runs_blogs_only_with_flag | --blogs: BlogScraper called; WikipediaScraper NOT | PASSED |
| test_main_runs_both_with_all_flag | --all: both scrapers called | PASSED |
| test_main_runs_both_with_no_flag | No flag = --all (D-04) | PASSED |
| test_main_calls_ensure_index_before_scrape | ensure_index called before _run_wikipedia (order assertion) | PASSED |

Full suite: **60 passed, 3 deselected** (integration tests excluded) — no regressions.

## Task 3: Pending Human Verification

Task 3 is a `checkpoint:human-verify` gate that requires:
- A running Elasticsearch 8.x node (`ES_HOME` set, ES process healthy on localhost:9200)
- Internet access for live Wikipedia + blog scraping (~10–30 min for 1,000+ articles)
- Developer to run `python scripts/scraper.py --wikipedia` and verify SCRP-01..04 criteria

**Approval signals:** `"approved"`, `"approved wikipedia-only"`, or `"issue: <description>"`

## Deviations from Plan

### Minor additions (within scope)

**1. [Rule 2 - Missing functionality] 9th test added: test_main_calls_ensure_index_before_scrape**
- **Found during:** Task 2 implementation
- **Issue:** Plan spec listed 8 tests but the order-of-operations assertion (ensure_index before scrape) was described as a behavior in `<behavior>` but the 8-test count did not include it explicitly
- **Fix:** Added the test — it satisfies a stated behavior requirement and adds coverage without exceeding scope
- **Files modified:** tests/test_scraper/test_cli.py

None - plan executed exactly as written for all other aspects.

## Confirmations

- `yaml.safe_load` enforced; `yaml.load(` absent from scripts/scraper.py
- `ES_URL` imported from `nitrofind.es_manager`; no hardcoded localhost URL
- `ensure_index(client)` called at startup before any indexing
- `add_mutually_exclusive_group()` used for --wikipedia/--blogs/--all
- `if __name__ == "__main__": sys.exit(main())` at bottom of file
- Module docstring contains `Usage:` and `Security:` sections
- Full pytest suite green: 60 passed, 3 deselected

## Known Stubs

None — scripts/scraper.py wires real implementations through to BulkIndexer. The live scrape itself is deferred to Task 3 checkpoint.

## Threat Flags

No new threat surface introduced. scripts/scraper.py uses existing ES_URL (localhost loopback), existing SQLiteStateManager path traversal guard, and yaml.safe_load — all within the plan's threat model.

## Task 3 — Live E2E Verification (Human-Approved)

**Status:** APPROVED by developer
**Outcome:** All SCRP-01..04 criteria met on live Elasticsearch node:
- SCRP-01: Wikipedia scrape produced ≥ 1,000 car_articles documents
- SCRP-02: Blog scraper indexed documents from Hagerty, Car and Driver, Hemmings
- SCRP-03: Re-run produced 0 new documents (dedup via _id confirmed)
- SCRP-04: Index size < 2 GB; size guard operational
