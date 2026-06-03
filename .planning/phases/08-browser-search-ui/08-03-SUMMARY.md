---
phase: 08-browser-search-ui
plan: "03"
subsystem: test-suite
tags: [testing, flask, pytest, uat]
dependency_graph:
  requires: ["08-01"]
  provides: ["test coverage for render_template route", "manual UAT checklist"]
  affects: ["tests/test_server.py"]
tech_stack:
  added: []
  patterns: ["Flask test_client with monkeypatch", "structural HTML marker assertion"]
key_files:
  created:
    - .planning/phases/08-browser-search-ui/08-HUMAN-UAT.md
  modified:
    - tests/test_server.py
decisions:
  - "Use data-state=\"home\" as structural template marker in test_root_uses_template — it is only present in the rendered template, not in any raw string"
  - "Use client_not_ready fixture for GET / tests — index() does not check state[\"ready\"], it always serves the HTML shell"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 08 Plan 03: Server Test Suite Update and Human UAT Checklist Summary

**One-liner:** Updated Flask GET / tests to assert render_template resolution via <!DOCTYPE html> and data-state structural marker; created 7-item browser UAT checklist for SRCH/UIPL requirements.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update test_root_returns_html and add test_root_uses_template | 506081d | tests/test_server.py |
| 2 | Create 08-HUMAN-UAT.md browser smoke-test checklist | 171b53d | .planning/phases/08-browser-search-ui/08-HUMAN-UAT.md |

## What Was Built

### Task 1: Updated test suite for render_template route

Modified `tests/test_server.py` to match the new `render_template("index.html")` GET / route from Plan 01:

- `test_root_returns_html`: Added `assert b"<!DOCTYPE html>" in resp.data` — proves render_template resolved the template (not a raw `<h1>` string). Updated docstring to "GET / returns HTTP 200 with rendered index.html template".
- `test_root_uses_template` (new): Asserts `resp.content_type.startswith("text/html")` and `b'data-state="home"' in resp.data`. The `data-state="home"` marker is a structural attribute from `<body data-state="home">` in `templates/index.html` — it is only present when render_template actually resolves the template file.
- Updated module docstring API-04 line to reference "renders index.html template" and name both test functions.
- All 5 tests pass: `python3 -m pytest tests/test_server.py -x -q` exits 0.

### Task 2: Human UAT checklist

Created `.planning/phases/08-browser-search-ui/08-HUMAN-UAT.md` with:
- Setup instruction: `python main.py`, then open http://localhost:5000
- 13 markdown checkboxes (7 required minimum) covering all 7 ROADMAP success criteria:
  - SRCH-01: 300ms debounced search
  - SRCH-02: Result row content and excerpt highlighting
  - SRCH-03: Article view in-place (no new tab) + back navigation
  - SRCH-04: Filters persist across query changes
  - UIPL-01: Dark theme with teal accent
  - UIPL-02: "N results (X.XXs)" line
  - UIPL-03: Arrow/Enter/Escape keyboard navigation
- ES warmup behavior (D-07) additional section

## Verification

- `python3 -m pytest tests/test_server.py -x -q` exits 0 (5 passed)
- `test_root_returns_html` contains `assert b"<!DOCTYPE html>" in resp.data`
- `test_root_uses_template` checks `resp.content_type.startswith("text/html")` and `b'data-state="home"' in resp.data`
- `08-HUMAN-UAT.md` contains 13 `- [ ]` checkbox items (>= 7 required)
- All 7 requirement IDs (SRCH-01..04, UIPL-01..03) present in UAT file

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan modifies tests and creates a UAT checklist only. No UI data flows.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

- [x] tests/test_server.py modified and verified
- [x] .planning/phases/08-browser-search-ui/08-HUMAN-UAT.md created and verified
- [x] Commit 506081d exists (test(08-03): update test_root_returns_html and add test_root_uses_template)
- [x] Commit 171b53d exists (docs(08-03): create 08-HUMAN-UAT.md browser smoke-test checklist)
- [x] 5 pytest tests pass
