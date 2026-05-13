---
phase: 01
slug: infrastructure-schema-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (latest 7.x or 8.x) |
| **Config file** | `pytest.ini` — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q -m "not integration"` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds (unit); ~90 seconds (full with integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q -m "not integration"`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green (including `@pytest.mark.integration` tests with live ES)
- **Max feedback latency:** ~5 seconds (unit only)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-lockfile | 01 | 1 | INFRA-01 | — | N/A | unit | `pytest tests/test_lockfile.py -x` | ❌ W0 | ⬜ pending |
| 01-es-home-check | 01 | 1 | INFRA-02 | T-es-home | ES_HOME validated as real directory before exec | unit | `pytest tests/test_es_manager.py::test_missing_es_home -x` | ❌ W0 | ⬜ pending |
| 01-es-startup | 01 | 2 | INFRA-02 | — | N/A | integration | `pytest tests/integration/test_es_startup.py -x -m integration` | ❌ W0 | ⬜ pending |
| 01-shutdown | 01 | 2 | INFRA-03 | — | N/A | unit | `pytest tests/test_es_manager.py::test_shutdown_graceful -x` | ❌ W0 | ⬜ pending |
| 01-worker-ready | 01 | 2 | INFRA-04 | — | N/A | unit | `pytest tests/test_es_manager.py::test_worker_emits_ready -x` | ❌ W0 | ⬜ pending |
| 01-worker-failed | 01 | 2 | INFRA-04 | — | N/A | unit | `pytest tests/test_es_manager.py::test_worker_emits_failed -x` | ❌ W0 | ⬜ pending |
| 01-schema-fields | 01 | 2 | SCHEMA-01,SCHEMA-02,SCHEMA-03,SCHEMA-04 | — | N/A | unit | `pytest tests/test_es_schema.py -x` | ❌ W0 | ⬜ pending |
| 01-schema-idempotent | 01 | 2 | SCHEMA-01..04 | — | N/A | unit | `pytest tests/test_es_schema.py::test_ensure_index_idempotent -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — test package init
- [ ] `tests/test_lockfile.py` — INFRA-01 lockfile verification stubs
- [ ] `tests/test_es_manager.py` — INFRA-02, INFRA-03, INFRA-04 unit test stubs
- [ ] `tests/test_es_schema.py` — SCHEMA-01..04 mapping verification stubs
- [ ] `tests/integration/__init__.py` — integration package init
- [ ] `tests/integration/test_es_startup.py` — INFRA-02 live ES integration stubs
- [ ] `pytest.ini` — configure `markers = integration: requires live ES`
- [ ] Framework install: `pip install pytest pytest-qt` (dev-only, not in requirements.in)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Loading window shows NitroFind branding, spinner animates, status text reads "Starting search engine..." | INFRA-04 / D-06 | Visual/animated behavior — cannot be asserted via pytest without display server | Launch `python main.py` with ES_HOME set; observe loading window for spinner animation and correct text before ES becomes healthy |
| Error state shows Retry + Quit buttons when ES fails | INFRA-04 / D-07 | Interactive UI state requiring ES failure simulation | Temporarily set ES_HOME to invalid path; observe error state with two buttons; verify Retry restarts polling and Quit exits cleanly |
| Main window replaces loading window after ES is healthy | INFRA-04 / D-03 | Window transition is visual — no automated assertion | Launch app normally; confirm loading window closes and main window ("NitroFind — Ready") appears within ~60s |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (unit suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
