---
phase: 3
slug: search-logic-relevance-scoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml |
| **Quick run command** | `pytest tests/test_search/ -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_search/ -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | RLVN-01 | — | N/A | unit | `pytest tests/test_search/test_query_builder.py -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | RLVN-02 | — | N/A | unit | `pytest tests/test_search/test_query_builder.py -q` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | RLVN-03 | — | N/A | unit | `pytest tests/test_search/test_query_builder.py -q` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | RLVN-04 | — | N/A | unit | `pytest tests/test_search/test_query_builder.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_search/__init__.py` — test package init
- [ ] `tests/test_search/test_query_builder.py` — stubs for RLVN-01..04
- [ ] `tests/test_search/test_engine.py` — stubs for threading/callback model
- [ ] `tests/conftest.py` — shared fixtures (mock ES client)

*If existing infrastructure covers requirements, mark complete immediately.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Scoring visually ranks Ferrari 308 article in top 3 | RLVN-01 | Requires live indexed data | Run search query, inspect result order |
| Recency decay measurably penalizes old articles | RLVN-01 | Requires real dated documents | Use `explain=True`, compare decay scores |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
