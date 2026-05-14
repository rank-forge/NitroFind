---
phase: 2
slug: data-pipeline-scraper-indexer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing project setup) |
| **Config file** | `pytest.ini` (root-level, already exists) |
| **Quick run command** | `pytest tests/test_scraper/ -x -m "not integration"` |
| **Full suite command** | `pytest tests/ -x -m "not integration"` |
| **Estimated runtime** | ~10 seconds (unit), ~60 seconds (with integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_scraper/ -x -m "not integration"`
- **After every plan wave:** Run `pytest tests/ -x -m "not integration"`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds (unit suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | SCRP-01 | — | N/A | unit | `pytest tests/test_scraper/test_wikipedia.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | SCRP-02 | — | N/A | unit | `pytest tests/test_scraper/test_blogs.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | SCRP-03 | — | N/A | integration | `pytest tests/test_scraper/test_indexer.py -x -m integration` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | SCRP-04 | — | N/A | unit | `pytest tests/test_scraper/test_indexer.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | SCRP-03, SCRP-04 | T-02-05, T-02-06, T-02-07 | Parameterized SQL queries; bulk index size guard halts before 1.8 GB | unit | `pytest tests/test_scraper/test_cleaner.py tests/test_scraper/test_state.py tests/test_scraper/test_indexer.py -x -m "not integration"` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | SCRP-02 | — | N/A | unit | `pytest tests/test_scraper/test_blogs.py -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | SCRP-01 | — | N/A | unit | `pytest tests/test_scraper/test_cleaner.py -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | SCRP-01, SCRP-03 | T-02-09, T-02-10, T-02-11, T-02-13 | Honest User-Agent (no browser impersonation); visited_categories cycle guard; auto_suggest=False prevents redirect ambiguity | unit | `pytest tests/test_scraper/test_wikipedia.py -x -m "not integration"` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | SCRP-04 | — | N/A | unit | `pytest tests/test_scraper/test_indexer.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scraper/__init__.py` — package init
- [ ] `tests/test_scraper/test_wikipedia.py` — stubs for SCRP-01 (category walk, infobox filter, page fetch)
- [ ] `tests/test_scraper/test_blogs.py` — stubs for SCRP-02 (blog fetch, 403 handling)
- [ ] `tests/test_scraper/test_cleaner.py` — stubs for SCHEMA-03 (HTML strip, excerpt ≤300 chars)
- [ ] `tests/test_scraper/test_indexer.py` — stubs for SCRP-03 (dedup), SCRP-04 (size halt)
- [ ] `tests/test_scraper/test_state.py` — stubs for SQLite state: is_visited, mark_visited, resume logic

Mocking strategy: `unittest.mock.patch` for mediawikiapi; `requests-mock` or `responses` for blog HTTP. ES integration tests require live ES node (`@pytest.mark.integration`).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Blog CSS selectors match current site structure | SCRP-02 | Site layout changes; automated fetch blocked by Cloudflare on all targets | Open browser devtools on target blog, inspect article container element, note selector, update `config/scraper.yaml` |
| Blog domain accessible without 403 | SCRP-02 | TLS fingerprinting cannot be tested without live scraping attempt | Run `python scripts/scraper.py --blogs` with browser-like User-Agent; confirm 200 response and non-empty body |
| 1,000+ infobox Wikipedia articles indexed | SCRP-01 | Requires actual ES index count via API | Run `curl localhost:9200/car_articles/_count` after scrape; verify count ≥ 1,000 |
| Index stays below 2 GB after full scrape | SCRP-04 | Requires actual ES disk usage | Run `curl localhost:9200/car_articles/_stats/store` after scrape; verify `primaries.store.size_in_bytes < 2_000_000_000` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
