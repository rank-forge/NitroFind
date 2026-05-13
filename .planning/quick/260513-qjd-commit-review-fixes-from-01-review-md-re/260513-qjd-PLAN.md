---
phase: quick-260513-qjd
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - main.py
  - nitrofind/es_manager.py
  - nitrofind/ui/loading_window.py
  - nitrofind/ui/spinner.py
  - scripts/setup_es.py
  - tests/test_es_manager.py
  - tests/test_loading_window.py
  - tests/test_lockfile.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "All 15 tests pass after the commit"
    - "All 8 modified files are included in a single atomic commit"
    - "Commit message references the review report and all 12 findings"
  artifacts:
    - path: "main.py"
      provides: "CR-02 fix (ensure_index exception handling), WR-01 fix (ES_URL constant)"
    - path: "nitrofind/es_manager.py"
      provides: "CR-01 fix (_es_binary_path), CR-03 fix (_stop_requested), WR-01 fix (ES_URL), WR-03 fix"
    - path: "nitrofind/ui/loading_window.py"
      provides: "IN-02 fix (primaryScreen null check)"
    - path: "nitrofind/ui/spinner.py"
      provides: "WR-02 fix (hideEvent/showEvent timer control)"
    - path: "scripts/setup_es.py"
      provides: "CR-01 fix (_es_binary_path in setup), WR-04 fix (backup existing yml)"
    - path: "tests/test_es_manager.py"
      provides: "WR-05 fix (remove dead monkeypatch from test_missing_es_home)"
    - path: "tests/test_loading_window.py"
      provides: "IN-03 fix (remove redundant per-function skipif decorators)"
    - path: "tests/test_lockfile.py"
      provides: "CR-04 fix (pytest.fail on missing requirements.txt)"
  key_links: []
---

<objective>
Stage and commit all 8 files modified during the Phase 1 code review remediation.

Purpose: Preserve the review fixes (CR-01 through CR-04, WR-01 through WR-05, IN-01 through IN-03) in version control as a single atomic commit so the repository history clearly records the remediation of all 12 findings from 01-REVIEW.md.
Output: One git commit containing all 8 modified files with all 15 tests passing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/01-infrastructure-schema-foundation/01-REVIEW.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Verify tests pass, then stage and commit all 8 review-fix files</name>
  <files>main.py, nitrofind/es_manager.py, nitrofind/ui/loading_window.py, nitrofind/ui/spinner.py, scripts/setup_es.py, tests/test_es_manager.py, tests/test_loading_window.py, tests/test_lockfile.py</files>
  <action>
Run the full test suite first to confirm all 15 tests pass. If any test fails, stop and report the failure — do not commit broken code.

If all tests pass, stage exactly the 8 files listed above (do not use `git add .` or `git add -A`; add each file by explicit path to avoid accidentally staging unrelated files).

Commit with the message below, passed via heredoc to preserve formatting:

  fix(01): resolve all 12 findings from Phase 1 code review (01-REVIEW.md)

  CR-01: add _es_binary_path() helper — use .bat on Windows in both
         es_manager.py and scripts/setup_es.py
  CR-02: wrap ensure_index() call in on_es_ready() with try/except;
         show_error() on failure instead of silently freezing the UI
  CR-03: retain last exception in health-poll loop; surface exception
         type in es_failed message instead of swallowing all errors
  CR-04: guard _read_requirements() with pytest.fail when
         requirements.txt is absent (not FileNotFoundError)

  WR-01: introduce ES_URL constant in es_manager.py; import and use it
         in main.py to eliminate three hardcoded localhost:9200 strings
  WR-02: override hideEvent/showEvent in SpinnerWidget to stop/start
         timer — prevent 10 Hz event-loop wakeup while widget is hidden
  WR-03: add _stop_requested flag to ESHealthWorker; check it in the
         polling loop so shutdown_es() can interrupt time.sleep(2)
  WR-04: back up existing elasticsearch.yml before overwriting in
         setup_es.py
  WR-05: remove dead monkeypatch.delenv from test_missing_es_home —
         validate_es_home() takes a direct argument, not env var

  IN-02: null-check QApplication.primaryScreen() before calling
         .geometry() to prevent AttributeError in headless environments
  IN-03: remove four redundant per-function @pytest.mark.skipif
         decorators in test_loading_window.py — pytestmark is sufficient

  (IN-01 addressed by inline comment in requirements.in documenting
  intentional major-pin strategy)

The commit must be signed with the existing git identity (no --no-gpg-sign, no --no-verify).
  </action>
  <verify>
    <automated>cd /mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind && python -m pytest tests/ -x -q 2>&1 | tail -5 && git log --oneline -1</automated>
  </verify>
  <done>All 15 tests pass. `git log --oneline -1` shows the new commit with the fix(01) subject line. `git show --stat HEAD` lists exactly the 8 modified files and no others.</done>
</task>

</tasks>

<verification>
git show --stat HEAD — confirm exactly 8 files in the commit diff, no extras.
git log --oneline -3 — confirm the new commit sits cleanly on top of the Phase 1 completion commit (ef13549).
python -m pytest tests/ -q — all 15 tests pass.
</verification>

<success_criteria>
Single commit on main branch containing all 8 review-fix files. All 15 tests green. Commit message enumerates all 12 findings (CR-01–04, WR-01–05, IN-01–03) so the fix is auditable without reading the diff.
</success_criteria>

<output>
No SUMMARY.md required — this is a quick task, not a phase plan.
</output>
