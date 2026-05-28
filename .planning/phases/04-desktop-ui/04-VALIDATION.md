---
phase: 4
slug: desktop-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-qt 4.5.0 |
| **Config file** | `pytest.ini` (exists — `markers` only; PyQt6 auto-detected) |
| **Quick run command** | `pytest tests/test_ui/ -m "not integration" -x` |
| **Full suite command** | `pytest tests/ -m "not integration" -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_ui/ -m "not integration" -x`
- **After every plan wave:** Run `pytest tests/ -m "not integration" -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-??-01 | TBD | 0 | SRCH-01 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_debounce_timer_interval -x` | ❌ W0 | ⬜ pending |
| 04-??-02 | TBD | 0 | SRCH-01 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_search_bar_triggers_debounce -x` | ❌ W0 | ⬜ pending |
| 04-??-03 | TBD | 1 | SRCH-02 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_result_list_populates -x` | ❌ W0 | ⬜ pending |
| 04-??-04 | TBD | 1 | SRCH-02 | — | N/A | unit | `pytest tests/test_ui/test_result_delegate.py::test_html_result_to_html -x` | ❌ W0 | ⬜ pending |
| 04-??-05 | TBD | 1 | SRCH-03 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_result_click_updates_detail -x` | ❌ W0 | ⬜ pending |
| 04-??-06 | TBD | 1 | SRCH-04 | — | N/A | unit | `pytest tests/test_ui/test_filter_sidebar.py::test_collect_filters -x` | ❌ W0 | ⬜ pending |
| 04-??-07 | TBD | 1 | SRCH-04 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_filter_preserved_on_retype -x` | ❌ W0 | ⬜ pending |
| 04-??-08 | TBD | 1 | UIPL-01 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_highlight_tags_in_result_html -x` | ❌ W0 | ⬜ pending |
| 04-??-09 | TBD | 1 | UIPL-02 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_status_label_updated -x` | ❌ W0 | ⬜ pending |
| 04-??-10 | TBD | 1 | UIPL-03 | — | N/A | code review | verified by main.py code review — no new test needed | Existing (main.py) | ⬜ pending |
| 04-??-11 | TBD | 1 | UIPL-04 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_escape_clears_search -x` | ❌ W0 | ⬜ pending |
| 04-??-12 | TBD | 1 | UIPL-04 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_enter_opens_result -x` | ❌ W0 | ⬜ pending |
| 04-??-13 | TBD | 1 | UIPL-04 | — | N/A | unit | `pytest tests/test_ui/test_main_window.py::test_arrow_key_navigation -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ui/__init__.py` — package marker
- [ ] `tests/test_ui/test_main_window.py` — covers SRCH-01, SRCH-02, SRCH-03, SRCH-04, UIPL-01, UIPL-02, UIPL-04
- [ ] `tests/test_ui/test_result_delegate.py` — covers SRCH-02, UIPL-01
- [ ] `tests/test_ui/test_filter_sidebar.py` — covers SRCH-04

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dark theme renders correctly | UIPL-03 | Visual inspection required | Launch app, confirm dark background and light text throughout |
| Result excerpts visually highlighted | UIPL-01 | Delegate rendering requires visual check | Search for known term, verify `<b>` highlights appear bold in result list |
| 300ms debounce feel | SRCH-01 | Timing UX requires human judgment | Type quickly and observe results only update after pausing ~300ms |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
