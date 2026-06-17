---
phase: 9
slug: article-rendering-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-17
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python3 -m pytest tests/test_scraper/ tests/test_search/ -m "not integration" -q` |
| **Full suite command** | `python3 -m pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_scraper/ tests/test_search/ tests/test_es_schema.py -m "not integration" -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -m "not integration" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 0 | BUG-01 | — | N/A | unit | `pytest tests/test_scraper/test_cleaner.py::test_strip_nav_sections_removes_references -x` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 0 | BUG-01 | — | N/A | unit | `pytest tests/test_scraper/test_cleaner.py::test_strip_nav_sections_removes_external_links -x` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 0 | BUG-01 | — | N/A | unit | `pytest tests/test_scraper/test_wikipedia.py::test_clean_wikipedia_html_preserves_tables -x` | ❌ W0 | ⬜ pending |
| 09-01-04 | 01 | 0 | BUG-01 | — | N/A | unit | `pytest tests/test_scraper/test_wikipedia.py::test_clean_wikipedia_html_removes_navboxes -x` | ❌ W0 | ⬜ pending |
| 09-01-05 | 01 | 0 | BUG-01 | — | N/A | unit | `pytest tests/test_scraper/test_wikipedia.py::test_fetch_and_build_doc_returns_body_html -x` | ❌ W0 | ⬜ pending |
| 09-01-06 | 01 | 0 | BUG-01 | — | N/A | unit | `pytest tests/test_scraper/test_blogs.py::test_doc_has_body_html_field -x` | ❌ W0 | ⬜ pending |
| 09-01-07 | 01 | 0 | BUG-02 | — | N/A | unit | `pytest tests/test_scraper/test_blogs.py::test_breadcrumb_excluded_from_body -x` | ❌ W0 | ⬜ pending |
| 09-01-08 | 01 | 0 | BUG-02 | — | N/A | unit | `pytest tests/test_scraper/test_blogs.py::test_related_articles_excluded_from_body -x` | ❌ W0 | ⬜ pending |
| 09-01-09 | 01 | 0 | BUG-01, BUG-02 | — | N/A | unit | `pytest tests/test_search/test_models.py::test_body_html_field_default -x` | ❌ W0 | ⬜ pending |
| 09-01-10 | 01 | 0 | BUG-01 | — | N/A | unit | `pytest tests/test_es_schema.py::test_body_html_field_present -x` | ❌ W0 | ⬜ pending |
| 09-01-11 | 01 | 1 | BUG-01 | — | N/A | unit | `pytest tests/test_search/test_api_search.py::test_search_result_shape -x` | ✅ update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scraper/test_cleaner.py` — new tests for `strip_nav_sections()` (References removed, Design preserved, External Links removed)
- [ ] `tests/test_scraper/test_wikipedia.py` — new tests for `_clean_wikipedia_html()` (table preserved, navbox removed) and `_fetch_and_build_doc()` `body_html` key presence
- [ ] `tests/test_scraper/test_blogs.py` — new tests for `body_html` field presence, breadcrumb exclusion, related-articles exclusion
- [ ] `tests/test_search/test_models.py` — new test for `ArticleResult.body_html` default
- [ ] `tests/test_es_schema.py` — new test for `body_html` in `CAR_ARTICLES_MAPPING.properties`
- [ ] Update `tests/test_search/test_api_search.py::test_search_result_shape` — add `body_html` to expected keys set and fix pre-existing `body` inclusion

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Detail pane renders HTML tables visually | BUG-01 | Requires live ES + UI session | Open browser UI, search "Ferrari 308", click result, verify table appears in detail pane |
| Detail pane body shows no nav links | BUG-02 | Requires live ES + UI session | Open browser UI, search "Hagerty", click result, verify no sidebar/nav text in body |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
