---
phase: 10
slug: search-quality-sort
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` (project root) |
| **Quick run command** | `pytest tests/ -x -q -m "not integration"` |
| **Full suite command** | `pytest tests/ -q -m "not integration"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q -m "not integration"`
- **After every plan wave:** Run `pytest tests/ -q -m "not integration"`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 0 | QURY-01 | — | N/A | unit | `pytest tests/test_search/test_query_builder.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 0 | QURY-02 | — | N/A | unit | `pytest tests/test_search/test_query_builder.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 0 | SORT-01 | — | N/A | unit | `pytest tests/test_search/test_query_builder.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 0 | SORT-02 | — | N/A | unit | `pytest tests/test_search/test_api_search.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_search/test_query_builder.py` — RED tests for fuzzy routing, phrase routing, sort param passing
- [ ] `tests/test_search/test_api_search.py` — RED tests for `GET /api/search?sort=date` and `sort=size` param acceptance

*Existing test infrastructure (pytest.ini, conftest.py) already in place — Wave 0 adds stubs only.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sort buttons render and toggle active state | SORT-01 | Browser UI interaction | Open app, search "ferrari", click "By date" → results reorder newest-first, button shows active state |
| Quoted phrase returns exact-phrase results ranked above scattered-word results | QURY-02 | Requires real ES index with data | Search `"V8 engine"` → verify phrase matches appear before scattered-word matches |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
