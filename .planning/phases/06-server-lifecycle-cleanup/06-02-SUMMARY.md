---
phase: 06-server-lifecycle-cleanup
plan: 02
subsystem: api
tags: [flask, elasticsearch, threading, subprocess, python]

# Dependency graph
requires:
  - phase: 06-01
    provides: nitrofind/es_manager.py with ES_URL, shutdown_es, validate_es_home
provides:
  - nitrofind/server.py: Flask app, state dict, GET /, GET /api/status, start_es_background, _es_health_poller, _fetch_index_stats
  - tests/test_server.py: 5 unit tests covering SRVR-02/03, API-03/04 via Flask test_client
affects: [06-03-PLAN, main.py rewrite, Phase 7 /api/search, Phase 8 frontend]

# Tech tracking
tech-stack:
  added: [flask==3.1.3, werkzeug==3.1.8, itsdangerous==2.2.0]
  patterns:
    - "Module-level state dict for shared mutable state between background thread and Flask routes (GIL-safe single writer)"
    - "Flask test_client + monkeypatch.setitem for route unit tests without live ES"
    - "503 warmup guard: check state['ready'] before any ES client call"
    - "daemon=True threading.Thread for background lifecycle — exits with main thread"

key-files:
  created:
    - nitrofind/server.py
    - tests/test_server.py
  modified: []

key-decisions:
  - "state dict is module-level (not class attribute) to avoid closure/global fragility — shared by reference between poller thread and route handlers"
  - "shutdown_es re-exported from server.py via noqa F401 so main.py can import it from one location"
  - "GET / returns D-13 placeholder HTML — intentional stub per plan, Phase 8 will replace it"
  - "_fetch_index_stats wraps cat.indices in try/except returning (0,0) — non-fatal failure path after ready=True"

patterns-established:
  - "Pattern: 503 warmup guard — state['ready'] check before any ES API call in Flask routes (T-06-05 security mitigation)"
  - "Pattern: monkeypatch.setitem(server.state, key, value) for Flask route unit tests"
  - "Pattern: daemon=True thread for one-shot background initialization tasks"

requirements-completed: [SRVR-02, SRVR-03, API-03, API-04]

# Metrics
duration: 15min
completed: 2026-06-03
---

# Phase 06 Plan 02: Server Routes and Background ES Poller Summary

**Flask app with 503 warmup guard, /api/status health endpoint, and daemon-thread ES health poller using module-level state dict**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-03T14:35:00Z
- **Completed:** 2026-06-03T14:50:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `nitrofind/server.py` (177 lines): Flask app, module-level state dict, GET / placeholder, GET /api/status with 503 warmup guard, `_start_es_process`, `_fetch_index_stats` (handles `store.size` dotted key), `_es_health_poller` (180s deadline, 2s poll, green/yellow accept), and `start_es_background` daemon thread
- Created `tests/test_server.py`: 5 unit tests covering all route behaviors using Flask test_client with monkeypatched state — no live ES, no real subprocess
- Flask 3.1.3 installed as system package (was in `requirements.in` as `flask>=3.1` but not yet installed in environment)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create nitrofind/server.py with Flask routes and the background ES poller** - `5a198d7` (feat)
2. **Task 2: Create tests/test_server.py covering routes and PORT handling** - `d3b7468` (test)

## Files Created/Modified

- `nitrofind/server.py` — Flask app, state dict, routes, ES background poller machinery
- `tests/test_server.py` — 5 unit tests: test_port_env_var, test_status_before_ready, test_status_after_ready, test_status_response_shape, test_root_returns_html

## Decisions Made

- The GET / route returns the D-13 placeholder HTML string as specified — this is intentionally minimal and Phase 8 will replace it with the full search UI
- `shutdown_es` is re-exported from `server.py` via `from nitrofind.es_manager import ES_URL, shutdown_es` with a `# noqa: F401` comment so `main.py` (Plan 03) can import it from a single location if desired
- Flask was installed using `--break-system-packages` since the system Python is managed by the OS package manager; this matches the project's development environment setup

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

`GET /` returns `<h1>NitroFind</h1><p>Search UI coming in Phase 8.</p>` — this is the D-13 intentional placeholder per plan spec. It correctly confirms the server is up and is not blocking the plan's goal. Phase 8 will replace this with the search UI.

## Issues Encountered

Flask 3.1.3 was not installed in the Python environment. Installed via `python3 -m pip install "flask>=3.1" --break-system-packages`. This was required for `import nitrofind.server` to succeed. The package is already listed in `requirements.in` as `flask>=3.1` (added in Plan 01 wave).

## Threat Flags

No new threat surface beyond the plan's threat model. The two routes (`GET /` and `GET /api/status`) are exactly as specified in CONTEXT.md D-11/D-12/D-13 and the threat register T-06-05/T-06-06/T-06-07. Binding host is configured in `main.py` (Plan 03), not in `server.py`.

## Self-Check: PASSED

- `nitrofind/server.py` exists: FOUND
- `tests/test_server.py` exists: FOUND
- Commit `5a198d7` exists: FOUND
- Commit `d3b7468` exists: FOUND
- `pytest tests/test_server.py -x -q`: 5 passed
- `python3 -c "import nitrofind.server"`: exits 0
- No PyQt6/SearchEngine imports in server.py: confirmed

## Next Phase Readiness

- `nitrofind/server.py` exposes `app`, `state`, and `start_es_background` — all three symbols that Plan 03 (`main.py`) imports
- All 5 server tests pass via `pytest tests/test_server.py -x -q`
- Plan 03 can now proceed with `from nitrofind.server import app, state, start_es_background`

---
*Phase: 06-server-lifecycle-cleanup*
*Completed: 2026-06-03*
