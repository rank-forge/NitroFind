---
phase: 6
slug: server-lifecycle-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (exists at repo root) |
| **Quick run command** | `pytest tests/test_server.py -x -q` |
| **Full suite command** | `pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_server.py -x -q`
- **After every plan wave:** Run `pytest tests/ -m "not integration" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| server-01 | 01 | 1 | SRVR-02 | T-06-01 | Flask binds to 127.0.0.1, not 0.0.0.0 | unit | `pytest tests/test_server.py::test_port_env_var -x` | ❌ W0 | ⬜ pending |
| server-02 | 01 | 1 | SRVR-03 | — | HTTP 503 returned before ES ready | unit | `pytest tests/test_server.py::test_status_before_ready -x` | ❌ W0 | ⬜ pending |
| server-03 | 01 | 1 | SRVR-03 | — | HTTP 200 returned after ES ready | unit | `pytest tests/test_server.py::test_status_after_ready -x` | ❌ W0 | ⬜ pending |
| api-status | 01 | 1 | API-03 | — | /api/status returns correct JSON shape | unit | `pytest tests/test_server.py::test_status_response_shape -x` | ❌ W0 | ⬜ pending |
| api-root | 01 | 1 | API-04 | — | GET / returns HTML with NitroFind content | unit | `pytest tests/test_server.py::test_root_returns_html -x` | ❌ W0 | ⬜ pending |
| clen-grep | 02 | 2 | CLEN-01 | — | No PyQt6/qt-material imports in Phase 6 code paths | static | `grep -r "from PyQt6\|import PyQt6\|from qt_material" nitrofind/server.py nitrofind/es_manager.py main.py` returns empty | automated grep | ⬜ pending |
| srvr-01-smoke | 01 | 1 | SRVR-01 | — | python main.py starts ES + Flask | manual | manual: `python main.py`, visit http://localhost:5000 | manual-only | ⬜ pending |
| srvr-04-shutdown | 01 | 1 | SRVR-04 | — | Ctrl+C exits cleanly, no orphaned JVM | manual | manual: `python main.py`, Ctrl+C, `ps aux \| grep elasticsearch` | manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_server.py` — stubs for SRVR-02, SRVR-03, API-03, API-04
- [ ] `tests/test_es_manager.py` — update: remove ESHealthWorker tests (`test_worker_emits_ready`, `test_worker_emits_failed`), keep subprocess/path tests

**Tests to delete (CLEN-01):**
- [ ] `tests/test_loading_window.py` — PyQt6 LoadingWindow tests
- [ ] `tests/test_ui/test_main_window.py` — PyQt6 UI tests
- [ ] `tests/test_ui/test_filter_sidebar.py` — PyQt6 UI tests
- [ ] `tests/test_ui/test_result_delegate.py` — PyQt6 UI tests

**Tests to update (not delete):**
- [ ] `tests/test_es_manager.py` — remove `test_worker_emits_ready`, `test_worker_emits_failed` (class deleted); keep `test_missing_es_home`, `test_shutdown_graceful`, `test_shutdown_kills_on_timeout`
- [ ] `tests/test_search/test_engine.py` — add PyQt6 skip guard (defer to Phase 7; search/engine.py PyQt6 dependency not removed in Phase 6)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `python main.py` starts ES and Flask together | SRVR-01 | Requires live Elasticsearch process; no mock | Run `python main.py` in WSL terminal; verify browser reaches http://localhost:5000 |
| Ctrl+C exits cleanly — no orphaned JVM | SRVR-04 | Requires live process and OS-level process inspection | Run `python main.py`, wait for Flask ready, press Ctrl+C; run `ps aux \| grep elasticsearch` to confirm no orphan |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
