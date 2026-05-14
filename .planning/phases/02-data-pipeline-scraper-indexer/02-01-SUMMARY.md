---
phase: 02-data-pipeline-scraper-indexer
plan: "01"
subsystem: scraper-foundation
tags: [dependencies, config, test-stubs, wave-0]
dependency_graph:
  requires: []
  provides: [scraper-deps-locked, scraper-config, test-harness-wave0]
  affects: [02-02, 02-03, 02-04]
tech_stack:
  added: [mediawikiapi==1.3, beautifulsoup4==4.14.3, lxml==6.1.0, pyyaml==6.0.3]
  patterns: [pip-compile-with-hashes, yaml-safe-load, pytest-importorskip-in-test-body]
key_files:
  created:
    - requirements.in (updated — 4 new entries)
    - requirements.txt (recompiled — 413 line additions with hashes)
    - config/scraper.yaml
    - tests/test_scraper/__init__.py
    - tests/test_scraper/test_wikipedia.py
    - tests/test_scraper/test_blogs.py
    - tests/test_scraper/test_cleaner.py
    - tests/test_scraper/test_indexer.py
    - tests/test_scraper/test_state.py
  modified:
    - .gitignore (added data/ entry)
decisions:
  - "pytest.importorskip placed inside each test body (not at module level) so tests are individually collected and skipped with exit 0, rather than the entire module being skipped with exit 5"
  - "lxml version resolved to 6.1.0 (satisfies lxml>=5,<7); beautifulsoup4 to 4.14.3 (satisfies >=4.12,<5)"
metrics:
  duration: "4m 18s"
  completed: "2026-05-14T13:47:27Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 9
  files_modified: 2
---

# Phase 02 Plan 01: Scraper Foundation Summary

**One-liner:** Wave 0 foundation — mediawikiapi/BS4/lxml/pyyaml locked with hashes, scraper.yaml with 5 Wikipedia categories and Hagerty blog target, 17 test stubs across 5 modules all skipping cleanly.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add scraper dependencies and recompile lockfile | e799499 | requirements.in, requirements.txt |
| 2 | Create config/scraper.yaml and gitignore data/ | 74f7e25 | config/scraper.yaml, .gitignore |
| 3 | Create Wave 0 test stubs under tests/test_scraper/ | 27c9970 | 6 files under tests/test_scraper/ |

## requirements.txt New Entries

Packages added via `pip-compile --generate-hashes requirements.in`:

```
mediawikiapi==1.3          (--hash=sha256:452205c2... --hash=sha256:afac9b2...)
beautifulsoup4==4.14.3     (--hash=sha256:0918bfe4... --hash=sha256:6292b1c5...)
lxml==6.1.0                (--hash=sha256:00750d63... + platform variants)
pyyaml==6.0.3              (--hash=sha256:00c4bde8... + platform variants)
```

Transitive dependencies also added: soupsieve (BS4 dep), vcrpy + pytest-vcr + sphinx + related packages (mediawikiapi dev deps pulled in by pip-compile).

## config/scraper.yaml Structure

Top-level keys: `wikipedia`, `blogs`

| Key | Value |
|-----|-------|
| `wikipedia.root_categories` | 5-element list (Category:Automobiles by manufacturer, Category:Car models, Category:Sports cars, Category:Luxury vehicles, Category:Cars by year of introduction) |
| `wikipedia.max_depth` | 2 |
| `wikipedia.rate_limit_seconds` | 0.5 |
| `wikipedia.user_agent` | "NitroFind/1.0 (nullsecurity1337@gmail.com; personal offline research tool)" |
| `blogs.size_halt_bytes` | 1800000000 |
| `blogs.targets[0]` | hagerty — enabled: true |
| `blogs.targets[1]` | caranddriver — enabled: false |
| `blogs.targets[2]` | hemmings — enabled: false |

CSS selectors for all blog targets marked `# ASSUMED — verify at implementation`.

## Test Stub Files

| File | Module | Stubs | Requirements |
|------|--------|-------|--------------|
| test_wikipedia.py | nitrofind.scraper.wikipedia | 3 | SCRP-01 |
| test_blogs.py | nitrofind.scraper.blogs | 3 | SCRP-02 |
| test_cleaner.py | nitrofind.scraper.cleaner | 5 | SCHEMA-03, L-06, L-07 |
| test_indexer.py | nitrofind.scraper.indexer | 3 (1 @integration) | SCRP-03, SCRP-04 |
| test_state.py | nitrofind.scraper.state | 3 | D-06 |
| **Total** | | **17** | |

## pytest Verification

```
pytest tests/ -x -m "not integration"
→ 15 passed, 16 skipped, 2 deselected  (exit 0)
```

- 15 Phase 1 unit tests still pass
- 16 Wave 0 stubs skip cleanly (1 integration test deselected by -m filter)
- No collection errors

## Deviations from Plan

### Auto-applied Implementation Decision

**1. [Rule 2 - Correctness] pytest.importorskip placed inside test bodies, not at module level**

- **Found during:** Task 3 verification
- **Issue:** `pytest.importorskip` at module level causes pytest exit code 5 ("no tests collected") because the entire module is skipped. The plan's acceptance criteria requires exit 0.
- **Fix:** Moved `pytest.importorskip` calls inside each individual test function body. The string `pytest.importorskip("nitrofind.scraper.X"` is still present in every file (satisfying the acceptance criteria content check). Tests are now individually collected and individually skipped, giving exit 0 with `16 skipped`.
- **Files modified:** all 5 test_scraper/*.py files
- **Impact:** When Wave 1 implements the modules, `pytest.importorskip` calls inside test bodies will resolve successfully and execution will continue to the `pytest.skip("Wave 1 implementation")` body — Wave 1 plans replace those skip calls with actual assertions. No restructuring needed.

## Known Stubs

None — config/scraper.yaml CSS selectors are marked `# ASSUMED — verify at implementation` as explicit documentation. These are not code stubs; they are placeholder values in a YAML config file that will be validated and corrected during Plan 02-04 (blog scraper implementation).

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. The `data/` gitignore entry (T-02-03) and `pyyaml` with `yaml.safe_load` mandate (T-02-01) are both in place. Hash-locked requirements.txt addresses T-02-02.

## Self-Check: PASSED

- [x] requirements.in contains mediawikiapi==1.3, beautifulsoup4>=4.12,<5, lxml>=5,<7, pyyaml>=6.0,<7
- [x] requirements.txt contains hashes for all 4 new packages
- [x] config/scraper.yaml loads via yaml.safe_load(), has 5 root_categories, max_depth=2, hagerty enabled
- [x] .gitignore contains data/ line; all pre-existing entries preserved
- [x] tests/test_scraper/__init__.py + 5 stub test files present
- [x] pytest tests/ -x -m "not integration" exits 0 (15 passed, 16 skipped)
- [x] commits e799499, 74f7e25, 27c9970 all exist in git log
- [x] No nitrofind/scraper/ package files created (Wave 1 responsibility)
