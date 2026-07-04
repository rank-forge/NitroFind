---
phase: 12
slug: pagination
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-04
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/test_search/ -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_search/ -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 0 | PAGE-01 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_default"` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 0 | PAGE-01 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_page_2"` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 0 | PAGE-01 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_page_zero"` | ❌ W0 | ⬜ pending |
| 12-01-04 | 01 | 0 | PAGE-01 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_invalid_page"` | ❌ W0 | ⬜ pending |
| 12-01-05 | 01 | 0 | PAGE-02 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_total"` | ❌ W0 | ⬜ pending |
| 12-01-06 | 01 | 0 | PAGE-02 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -q -k "pagination_wrapper"` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 1 | PAGE-01, PAGE-02 | — | `page` param coerced via `_safe_int_param`; non-integer → 1; `from_` never negative | unit | `pytest tests/test_search/ -q` | ✅ (updated) | ⬜ pending |
| 12-02-02 | 02 | 1 | PAGE-01, PAGE-02 | — | N/A | manual | See manual table below | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_search/test_api_search.py` — update 4 existing tests for new response shape (RED before implementing)
  - `test_search_returns_result_array` → `isinstance(data["results"], list)`
  - `test_search_result_shape` → `data["results"][0]`; no `took_ms` per-item; add `data["total"]`, `data["took_ms"]`, `data["page"]`
  - `test_excerpt_uses_highlight` → `resp.get_json()["results"][0]["excerpt"]`
  - `test_excerpt_fallback` → `resp.get_json()["results"][0]["excerpt"]`
- [ ] `tests/test_search/test_api_search.py` — add 6 new pagination unit tests (RED before implementing)
  - `test_pagination_default` — no `page` param → ES receives `from_=0, size=10`
  - `test_pagination_page_2` — `page=2` → ES receives `from_=10, size=10`
  - `test_pagination_page_zero` — `page=0` clamped to 1 → `from_=0`
  - `test_pagination_invalid_page` — `page="abc"` → `from_=0`
  - `test_pagination_total` — response includes `total` key with `hits.total.value`
  - `test_pagination_wrapper` — response includes `took_ms` at wrapper level, NOT per-item

*No new test files needed — all tests go into existing `test_api_search.py`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Previous/Next buttons visible below result list | PAGE-01 | Requires live browser + ES | Search any term; verify pagination row appears below results |
| Previous disabled on page 1 | PAGE-01 | DOM interaction requires browser | On page 1, verify Previous button has `disabled` attribute |
| Next disabled on last page | PAGE-01 | DOM interaction requires browser | Navigate to last page; verify Next button is disabled |
| Stats line shows total across all pages | PAGE-02 | Requires live ES with indexed data | Search "ferrari"; verify stats line shows total > 10 if >10 docs exist |
| Clicking Next loads next 10 results | PAGE-01 | Requires browser interaction | On page 1, click Next; verify new 10 results load, Previous becomes enabled |
| Clicking Previous returns to prior page | PAGE-01 | Requires browser interaction | On page 2, click Previous; verify same results as page 1 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
