---
phase: 13
slug: history-theme
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-06
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (project root) |
| **Quick run command** | `python3 -m pytest tests/test_server.py -x` |
| **Full suite command** | `python3 -m pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_server.py -x`
- **After every plan wave:** Run `python3 -m pytest tests/ -m "not integration"`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-T1 | 01 | 0 | HIST-01, HIST-02, THME-01 | — | N/A | unit | `python3 -m pytest tests/test_server.py::test_template_has_history_list tests/test_server.py::test_template_has_theme_toggle tests/test_server.py::test_template_has_fouc_prevention_script -x` | ❌ W0 | ⬜ pending |
| 13-02-T1 | 02 | 1 | HIST-01, HIST-02 | — | N/A | unit | `python3 -m pytest tests/test_server.py::test_template_has_history_list -x` | ✅ | ⬜ pending |
| 13-02-T2 | 02 | 1 | THME-01 | T-13-03 | `data-theme` on `<html>`, not `<body>`; FOUC inline script before stylesheet | unit | `python3 -m pytest tests/test_server.py -x` | ✅ | ⬜ pending |
| 13-02-T3 | 02 | 1 | HIST-01, HIST-02, THME-01 | T-13-01, T-13-02, T-13-04 | `textContent` for history labels; try/catch on all localStorage; namespaced keys | unit | `python3 -m pytest tests/test_server.py -x && node --check static/js/app.js` | ✅ | ⬜ pending |
| 13-03-T1 | 03 | 2 | HIST-01, HIST-02, THME-01 | — | N/A | unit | `python3 -m pytest tests/ -m "not integration"` | ✅ | ⬜ pending |
| 13-03-T2 | 03 | 2 | HIST-01, HIST-02, THME-01 | — | All features integrated; no regressions in search/pagination/filter/sort | manual | Human UI verification checkpoint | Manual only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_server.py::test_template_has_history_list` — stubs for HIST-01, HIST-02 (verifies `id="history-list"` container in rendered HTML)
- [ ] `tests/test_server.py::test_template_has_theme_toggle` — stub for THME-01 (verifies `id="theme-toggle"` button in rendered HTML)
- [ ] `tests/test_server.py::test_template_has_fouc_prevention_script` — stub for THME-01 (verifies inline `<script>` before stylesheet in `<head>`)

These three tests go in the existing `tests/test_server.py` using the existing `client_not_ready` fixture — no new test file needed.

*Existing test infrastructure (pytest.ini, conftest.py, Flask test_client) covers all phase requirements. No new framework installs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| History list populates after searches | HIST-01 | No browser automation (no Playwright/Selenium in project) | Execute 3+ searches; verify history list shows them most-recent-first below home search box |
| History item click re-executes search | HIST-02 | Requires real browser interaction | Click a history item; verify search box repopulates and results update |
| Theme toggle switches without reload | THME-01 | CSS custom property change is JS-driven | Click theme toggle; verify page switches to light/dark without reload |
| Theme persists after page reload | THME-01 | localStorage read-on-init can't be tested server-side | Toggle to light, refresh page, verify light theme is still active |
| No FOUC on reload | THME-01 | Timing issue invisible to server tests | Toggle to light, hard-refresh (Ctrl+Shift+R), verify no dark flash before light theme applies |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
