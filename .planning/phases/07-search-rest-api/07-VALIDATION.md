---
phase: 7
slug: search-rest-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` (project root) |
| **Quick run command** | `python3 -m pytest tests/test_search/test_api_search.py -q` |
| **Full suite command** | `python3 -m pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_search/test_api_search.py -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -m "not integration" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | API-01 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -q` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | API-01, API-02 | T-07-01..06 | query in multi_match value; index hard-coded; size clamped; filter values in term field | unit | `pytest tests/test_search/test_api_search.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_search/test_api_search.py` — new file; stubs for all 8 test cases (API-01, API-02, SRVR-03)

*Existing infrastructure in `tests/test_server.py` and `tests/test_search/` covers all Phase 6 requirements. No changes to existing test files needed.*

---

## Test Cases

| Test | Requirement | Command |
|------|-------------|---------|
| `test_search_returns_result_array` | API-01 | `pytest tests/test_search/test_api_search.py::test_search_returns_result_array -x` |
| `test_search_result_shape` | API-01 | `pytest tests/test_search/test_api_search.py::test_search_result_shape -x` |
| `test_excerpt_uses_highlight` | API-01 | `pytest tests/test_search/test_api_search.py::test_excerpt_uses_highlight -x` |
| `test_excerpt_fallback` | API-01 | `pytest tests/test_search/test_api_search.py::test_excerpt_fallback -x` |
| `test_manufacturer_filter_forwarded` | API-02 | `pytest tests/test_search/test_api_search.py::test_manufacturer_filter_forwarded -x` |
| `test_empty_filter_param_ignored` | API-02 | `pytest tests/test_search/test_api_search.py::test_empty_filter_param_ignored -x` |
| `test_search_503_while_not_ready` | SRVR-03 | `pytest tests/test_search/test_api_search.py::test_search_503_while_not_ready -x` |
| `test_search_empty_q_returns_empty` | API-01 | `pytest tests/test_search/test_api_search.py::test_search_empty_q_returns_empty -x` |

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
