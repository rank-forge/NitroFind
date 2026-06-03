---
phase: 8
slug: browser-search-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (project root) |
| **Quick run command** | `pytest tests/test_server.py -x` |
| **Full suite command** | `pytest tests/ -m "not integration" -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_server.py -x`
- **After every plan wave:** Run `pytest tests/ -m "not integration" -x`
- **Before `/gsd-verify-work`:** Full suite must be green + manual smoke test of all 7 success criteria

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | API-04 | T-07-01 | render_template wired, GET / returns 200 with HTML | unit | `pytest tests/test_server.py::test_root_returns_html -x` | ✅ (needs update) | ⬜ pending |
| 08-01-02 | 01 | 1 | UIPL-01 | — | CSS custom properties present, dark theme tokens defined | manual | open localhost:5000 | ❌ W0 | ⬜ pending |
| 08-02-01 | 01 | 2 | SRCH-01 | T-07-01 | 300ms debounce: search fires after keystroke pause | manual | type in search box | ❌ W0 | ⬜ pending |
| 08-02-02 | 01 | 2 | SRCH-02 | — | Excerpt b-tags rendered bold; body uses textContent | manual | observe result rows | ❌ W0 | ⬜ pending |
| 08-02-03 | 01 | 2 | SRCH-03 | — | Click/Enter opens article view, no new tab | manual | click result | ❌ W0 | ⬜ pending |
| 08-02-04 | 01 | 2 | SRCH-04 | — | Filter state persists across query retypes | manual | change filter, retype query | ❌ W0 | ⬜ pending |
| 08-02-05 | 01 | 2 | UIPL-02 | — | Result count + took_ms shown below search box | manual | observe stats line | ❌ W0 | ⬜ pending |
| 08-02-06 | 01 | 2 | UIPL-03 | — | Arrow/Enter/Escape keyboard nav works | manual | keyboard through results | ❌ W0 | ⬜ pending |
| 08-03-01 | 01 | 3 | API-04 | — | Updated test_root_returns_html passes | unit | `pytest tests/test_server.py -x` | ✅ (update) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `templates/index.html` — does not exist yet; created in Wave 1
- [ ] `static/css/style.css` — does not exist yet; created in Wave 1
- [ ] `static/js/app.js` — does not exist yet; created in Wave 2
- [ ] `tests/test_server.py::test_root_returns_html` — needs update after render_template switch (Wave 3)

*No new test framework install required — pytest 9.0.3 already in environment.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 300ms debounce fires results while typing | SRCH-01 | Browser JS behavior — no pytest jsdom | Start server, open localhost:5000, type slowly in search box; results appear after 300ms pause |
| Excerpt highlight b-tags render bold | SRCH-02 | DOM rendering — not testable via Flask test client | Search for a common term; verify matching words appear bold in result excerpts |
| Click/Enter opens article full-page (no new tab) | SRCH-03 | Browser interaction — no headless browser | Click a result; verify article fills viewport; click back arrow to return |
| Filter dropdown narrows results, state persists | SRCH-04 | Full user flow — filter + retype sequence | Select a filter, type a query, retype with new query; filter selection remains |
| Dark background and teal accent visible | UIPL-01 | Visual/CSS — not byte-level testable | Load page; verify dark off-black background, teal accent on search box and links |
| "42 results (0.08s)" stats line | UIPL-02 | DOM content — manual count check | Search for common term; verify result count and time appear below search box |
| Arrow keys navigate, Enter opens, Escape clears | UIPL-03 | Keyboard event — no jsdom | In results state: press Down/Up to move selection; Enter to open article; Escape to clear |
| ES warmup "Starting up…" status disappears on ready | D-07 | ES state dependency | Start app fresh; observe "Starting up..." fade out; search box activates without page refresh |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
