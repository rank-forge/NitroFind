---
phase: 01-infrastructure-schema-foundation
plan: "03"
subsystem: ui
tags: [pyqt6, loading-window, spinner, state-machine, pytest-qt, ui-components]
dependency_graph:
  requires:
    - 01-01 (pytest scaffold, requirements.txt)
  provides:
    - nitrofind/ui/spinner.py (SpinnerWidget — animated arc QWidget)
    - nitrofind/ui/loading_window.py (LoadingWindow with retry_clicked signal)
    - nitrofind/ui/main_window.py (StubMainWindow placeholder for Phase 4)
    - tests/test_loading_window.py (INFRA-04 UI state-machine tests, 4 tests)
  affects:
    - Plan 04 (main.py wires ESHealthWorker signals to LoadingWindow.show_error and retry_clicked)
tech_stack:
  added:
    - pytest-qt==4.5.0 (dev-only; installed alongside pytest for qtbot fixture)
  patterns:
    - Custom QWidget + QPainter + QTimer arc animation (UI-SPEC Pattern 5)
    - FramelessWindowHint + WindowStaysOnTopHint for loading window (not QSplashScreen per D-06)
    - pyqtSignal class attribute for cross-component signal surface
    - QLabel.setText() for error state (safe: Qt does not execute HTML by default, T-03-02)
    - qtbot.waitSignal() for pytest-qt idiomatic signal assertion
    - QT_QPA_PLATFORM=offscreen for headless GUI testing on WSL2/Linux
key_files:
  created:
    - nitrofind/__init__.py
    - nitrofind/ui/__init__.py
    - nitrofind/ui/spinner.py
    - nitrofind/ui/loading_window.py
    - nitrofind/ui/main_window.py
    - tests/test_loading_window.py
  modified: []
decisions:
  - "pytest-qt 4.5.0 installed as dev dependency (not in requirements.in) to provide qtbot fixture for UI state-machine tests"
  - "QT_QPA_PLATFORM=offscreen used for test execution on WSL2/Linux where no X display is guaranteed at CI time"
  - "LoadingWindow uses property accessors (spinner, status_label, retry_button, quit_button) so tests access widgets via stable names rather than private _name convention"
  - "StubMainWindow is intentionally minimal — Phase 4 replaces it entirely; it is not a bug stub"
metrics:
  duration: "~3 minutes"
  completed_date: "2026-05-13"
  tasks_completed: 3
  tasks_total: 3
  files_created: 6
  files_modified: 0
---

# Phase 1 Plan 3: UI Components — LoadingWindow, SpinnerWidget, StubMainWindow Summary

**One-liner:** PyQt6 frameless LoadingWindow with two-state machine (loading/error), custom SpinnerWidget arc animation, StubMainWindow placeholder, and four pytest-qt state-machine tests covering all INFRA-04 UI assertions.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | SpinnerWidget custom QWidget | 72dd863 | nitrofind/__init__.py, nitrofind/ui/__init__.py, nitrofind/ui/spinner.py |
| 2 | LoadingWindow + StubMainWindow | 5ab283a | nitrofind/ui/loading_window.py, nitrofind/ui/main_window.py |
| 3 | LoadingWindow state-machine tests | f21e710 | tests/test_loading_window.py |

## What Was Built

### Task 1: SpinnerWidget

- `nitrofind/__init__.py` and `nitrofind/ui/__init__.py`: package markers
- `nitrofind/ui/spinner.py`: `SpinnerWidget(QWidget)` — 48x48 px, transparent background (`WA_TranslucentBackground`), accent color `#26a69a`, 120-degree arc, 30-degree rotation per 100 ms tick (1200 ms per revolution)
- `QPen` with `Qt.PenCapStyle.RoundCap` for smooth arc endpoints
- `QTimer(self)` parented to widget — destroyed automatically when widget is destroyed, preventing timer leak (T-03-04 accepted risk)
- `QProgressBar` not used (UI-SPEC Pattern 5 explicit prohibition — animation inconsistent across platforms)

### Task 2: LoadingWindow and StubMainWindow

- `nitrofind/ui/loading_window.py`: `LoadingWindow(QWidget)` — frameless 360x240 with `FramelessWindowHint | WindowStaysOnTopHint` (NOT `QSplashScreen` per D-06)
- State 1 (loading): spinner visible, `"Starting search engine..."` status text, buttons hidden
- State 2 (error): spinner hidden, status label updated to reason, Retry and Quit visible
- `retry_clicked = pyqtSignal()` class attribute — Plan 04 (main.py) connects this to worker restart
- Quit wired to `QApplication.instance().quit` — no confirmation dialog per Copywriting Contract
- Full UI-SPEC styling: `#1e1e2e` background, `#26a69a` Retry button, `#ef5350` Quit button, QSS via `objectName` selectors (`retryButton`, `quitButton`)
- `show_error(reason: str)` and `reset_to_loading()` fully implemented
- `nitrofind/ui/main_window.py`: `StubMainWindow(QMainWindow)` — title `"NitroFind — Ready"` (em-dash), 800x600 minimum, centered `"Search engine ready."` label. Phase 4 replaces this entirely.

### Task 3: State-Machine Tests

- `tests/test_loading_window.py`: 4 pytest-qt tests using `qtbot` fixture
  - `test_initial_state_is_loading`: State 1 verification
  - `test_show_error_transitions_to_error_state`: State 2 verification
  - `test_retry_button_emits_signal`: `retry_clicked` signal emission via `qtbot.waitSignal()`
  - `test_reset_to_loading_restores_state`: State 1 restoration
- All 4 tests pass with `QT_QPA_PLATFORM=offscreen` for headless execution
- Full suite (`pytest -m "not integration"`) passes: 7 tests (3 lockfile + 4 loading_window)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] pytest-qt was not pre-installed**
- **Found during:** Task 3 setup
- **Issue:** Plan 01-01 noted pytest-qt was uninstalled because PyQt6 was not available at that time. For Plan 03, PyQt6 6.11.0 is installed and pytest-qt is required.
- **Fix:** Installed `pytest-qt==4.5.0` via `pip install --break-system-packages pytest-qt` before writing tests.
- **Files modified:** None (dev environment only; pytest-qt is not in requirements.in per PATTERNS.md note)
- **Commit:** N/A (dev install)

**2. [Rule 2 - Missing functionality] Property accessors added to LoadingWindow**
- **Found during:** Task 3 — tests reference `window.spinner`, `window.status_label`, etc.
- **Issue:** The plan's test contract names attributes without the `_` prefix (e.g., `window.spinner.isVisible()`), but the implementation used private `_spinner` etc. per Python convention.
- **Fix:** Added `@property` accessors (`spinner`, `status_label`, `retry_button`, `quit_button`) that expose the private attributes under the public names expected by the tests. This is cleaner than making the attributes public directly, as it preserves encapsulation.
- **Files modified:** `nitrofind/ui/loading_window.py`
- **Commit:** 5ab283a

## Known Stubs

`StubMainWindow` is an intentional plan-specified placeholder, not an unintended stub. The plan explicitly states: "No other widgets (Phase 4 replaces this entirely)." It is tracked for Phase 4 replacement.

No unintended stubs exist — all data flows (status label text, button visibility, signal emission) are fully wired.

## Threat Surface Scan

No new threat surface beyond the plan's threat model. All T-03-xx threats accounted for:

- **T-03-02 (mitigate):** `show_error(reason)` renders via `QLabel.setText()`. Qt QLabel does NOT execute HTML by default — no script injection risk. `setTextFormat(Qt.TextFormat.RichText)` is NOT used anywhere in the implementation.
- **T-03-03 (mitigate):** Raw JVM stack traces/exit codes not passed to `show_error()`. The reason mapping to static Copywriting Contract strings happens in Plan 04 (main.py), not here.
- **T-03-04 (accept):** SpinnerWidget timer parented to self — destroyed with widget. Exactly one LoadingWindow per app lifecycle.

## Open Questions for Plan 04 Manual Checkpoint

1. Does the spinner animation render smoothly at the expected 30°/100ms rate on the target Windows desktop (WSL2 dev environment cannot render GUI; tests run offscreen)?
2. Does `qt_material.apply_stylesheet(app, theme="dark_teal.xml")` interact cleanly with the `QWidget#loadingWindow { background-color: #1e1e2e; }` override? The objectName-targeted rule should take precedence.
3. Does the window centering via `screen.center() - self.rect().center()` work correctly on multi-monitor setups? `primaryScreen()` always returns the primary monitor.

## Self-Check: PASSED

Files verified:
- nitrofind/__init__.py: FOUND
- nitrofind/ui/__init__.py: FOUND
- nitrofind/ui/spinner.py: FOUND (contains 120 * 16, #26a69a, WA_TranslucentBackground, QTimer, start(100))
- nitrofind/ui/loading_window.py: FOUND (contains FramelessWindowHint, retry_clicked, show_error, reset_to_loading)
- nitrofind/ui/main_window.py: FOUND (contains NitroFind — Ready, AlignCenter)
- tests/test_loading_window.py: FOUND (4 test functions, qtbot.waitSignal, qtbot.mouseClick)

Commits verified:
- 72dd863: feat(01-03): SpinnerWidget custom QWidget with animated arc
- 5ab283a: feat(01-03): LoadingWindow state machine and StubMainWindow placeholder
- f21e710: test(01-03): LoadingWindow state-machine tests for INFRA-04 UI side

Test results:
- pytest tests/test_loading_window.py -x -q: 4 passed
- pytest -m "not integration" -x -q: 7 passed
