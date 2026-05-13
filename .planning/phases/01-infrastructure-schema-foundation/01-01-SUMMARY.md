---
phase: 01-infrastructure-schema-foundation
plan: "01"
subsystem: infrastructure
tags: [lockfile, elasticsearch-config, pytest, setup-script, dependency-management]
dependency_graph:
  requires: []
  provides:
    - requirements.in (top-level dep declarations)
    - requirements.txt (pinned lockfile with SHA256 hashes)
    - config/elasticsearch.yml (ES node config for Plans 02-04)
    - config/jvm.options (JVM heap config for ES)
    - scripts/setup_es.py (ES config installer)
    - pytest.ini (test scaffold for Plans 02-04)
    - tests/ package (INFRA-01 lockfile test)
  affects:
    - All subsequent plans depend on requirements.txt for deterministic installs
    - Plan 02 reads config/elasticsearch.yml and config/jvm.options at ES startup
    - Plans 02-04 drop their tests into the pytest scaffold created here
tech_stack:
  added:
    - elasticsearch==8.19.3 (pinned in lockfile)
    - PyQt6==6.11.0 (pinned in lockfile)
    - qt-material==2.17 (pinned in lockfile)
    - requests==2.34.0 (pinned in lockfile)
    - pip-tools==7.5.3 (dev-only, used for lockfile generation)
    - pytest==9.0.3 (dev-only, test runner)
  patterns:
    - pip-compile --generate-hashes for reproducible lockfiles
    - ES xpack security disabled (3-setting pattern to avoid keystore conflict)
    - ES_HOME path validation before file writes (T-01-01 mitigation)
    - pytest marker registration for integration test separation
key_files:
  created:
    - requirements.in
    - requirements.txt
    - .gitignore
    - config/elasticsearch.yml
    - config/jvm.options
    - scripts/setup_es.py
    - pytest.ini
    - tests/__init__.py
    - tests/integration/__init__.py
    - tests/test_lockfile.py
  modified: []
decisions:
  - "Lockfile generated with pip-tools 7.5.3 on Python 3.12.3 (target is 3.11; regenerate on 3.11 for strict reproducibility per RESEARCH.md A1)"
  - "pytest-qt not installed in dev environment (no PyQt6 binary available); to be added when Phase 4 UI tests are written with full PyQt6 install"
  - "All three xpack ssl settings set to false in elasticsearch.yml (Pitfall 3 mitigation)"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-05-13"
  tasks_completed: 3
  tasks_total: 3
  files_created: 10
  files_modified: 0
---

# Phase 1 Plan 1: Python Lockfile, ES Config, and pytest Scaffold Summary

**One-liner:** Pinned lockfile (pip-compile with SHA256 hashes), ES 8.x single-node config with xpack security fully disabled, and pytest scaffold with INFRA-01 lockfile verification test.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Python dependency lockfile + .gitignore | 694363f | requirements.in, requirements.txt, .gitignore |
| 2 | Elasticsearch config files + setup script | d0cb295 | config/elasticsearch.yml, config/jvm.options, scripts/setup_es.py |
| 3 | pytest scaffold + INFRA-01 lockfile test | c924568 | pytest.ini, tests/__init__.py, tests/integration/__init__.py, tests/test_lockfile.py |

## What Was Built

### Task 1: Python Dependency Lockfile

- `requirements.in` declares 4 top-level deps: `elasticsearch==8.*`, `PyQt6==6.11.0`, `qt-material==2.17`, `requests>=2.32,<3`
- `requirements.txt` generated via `pip-compile --generate-hashes requirements.in` (pip-tools 7.5.3, Python 3.12.3) — contains pinned transitive deps with SHA256 hashes for supply-chain verification
- `.gitignore` excludes venv, `__pycache__`, `.pytest_cache`, build artifacts

### Task 2: Elasticsearch Configuration

- `config/elasticsearch.yml`: all 6 required keys (network.host: 127.0.0.1, http.port: 9200, discovery.type: single-node, plus 3 xpack ssl disabled settings). Three xpack settings required to avoid keystore conflict (Pitfall 3 in RESEARCH.md).
- `config/jvm.options`: `-Xms512m -Xmx512m` (L-01 heap pin for desktop environment)
- `scripts/setup_es.py`: copies both config files to `$ES_HOME/config/`. Validates ES_HOME is a real directory and `$ES_HOME/bin/elasticsearch` is a real file before any writes (T-01-01 path traversal mitigation). Exits with D-02 error message on missing ES_HOME.

### Task 3: pytest Scaffold + INFRA-01 Test

- `pytest.ini`: registers `integration` marker so `pytest -m "not integration"` skips live-ES tests
- `tests/__init__.py`, `tests/integration/__init__.py`: package markers
- `tests/test_lockfile.py`: 3 assertions:
  - `test_no_loose_specifiers`: every package line in requirements.txt matches `name==version` pattern
  - `test_hashes_present`: at least one `--hash=sha256:` line present
  - `test_required_top_level_packages`: elasticsearch, PyQt6, qt-material, requests all pinned
- All 3 tests pass: `pytest tests/test_lockfile.py -x -q` exits 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] elasticsearch.yml comment contained "xpack" keyword causing grep count mismatch**
- **Found during:** Task 2 verification
- **Issue:** Plan's verification command `grep -c "xpack" config/elasticsearch.yml | grep -q "^3$"` expected exactly 3 xpack lines (the 3 config keys), but a comment line also mentioned "xpack ssl settings" giving count 4
- **Fix:** Changed comment to "security ssl settings" so only the 3 actual config keys contain "xpack"
- **Files modified:** config/elasticsearch.yml
- **Commit:** d0cb295

**2. [Rule 3 - Blocking] pytest-qt auto-loads and fails without PyQt6 installed**
- **Found during:** Task 3 TDD run
- **Issue:** Installing `pytest-qt` per plan instructions caused pytest to fail with `ERROR: pytest-qt requires either PySide6, PyQt5 or PyQt6 installed` since PyQt6 binary is not installed in the dev environment (it's in requirements.txt but not system-installed)
- **Fix:** Uninstalled pytest-qt. The lockfile tests use only standard library; pytest-qt is only needed for GUI tests written in Phase 4. Will be re-installed when Phase 4 begins with full PyQt6 install.
- **Files modified:** None (dev environment only)
- **Impact:** pytest runs cleanly; pytest-qt to be added back in Phase 4

## Known Stubs

None. This plan creates config files and infrastructure only — no data flows or UI rendering.

## Threat Surface Scan

No new threat surface introduced beyond what is documented in the plan's threat model. All T-01-01 through T-01-05 mitigations are in place.

## Self-Check: PASSED

Files verified:
- requirements.in: FOUND
- requirements.txt: FOUND (contains --hash=sha256:)
- .gitignore: FOUND (contains venv/)
- config/elasticsearch.yml: FOUND (contains discovery.type: single-node)
- config/jvm.options: FOUND (contains -Xms512m)
- scripts/setup_es.py: FOUND (valid Python, exits non-zero on missing ES_HOME)
- pytest.ini: FOUND (contains integration: marker)
- tests/__init__.py: FOUND
- tests/integration/__init__.py: FOUND
- tests/test_lockfile.py: FOUND (3 tests, all green)

Commits verified:
- 694363f: chore(01-01): Python dependency lockfile and .gitignore
- d0cb295: chore(01-01): Elasticsearch config files and setup script
- c924568: test(01-01): pytest scaffold and INFRA-01 lockfile test
