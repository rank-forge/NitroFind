# Phase 6: Server Lifecycle & Cleanup - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite `main.py` from a PyQt6 desktop entry point to a Flask web server entry point. A single `python main.py` starts Elasticsearch and Flask together. Flask returns HTTP 503 until ES is healthy, then serves requests. Ctrl+C terminates both cleanly. Adds `/api/status` and `GET /` endpoints. Removes all PyQt6 dependencies.

</domain>

<decisions>
## Implementation Decisions

### Platform Target
- **D-01:** Linux/WSL only. No Windows support required. All `sys.platform == "win32"` branches in `es_manager.py` are removed — no `CREATE_NEW_PROCESS_GROUP`, no `shell=True`, no `CTRL_BREAK_EVENT`, no `.bat` path suffix. `_es_binary_path()` returns `{es_home}/bin/elasticsearch` unconditionally.

### ES Startup Model
- **D-02:** Flask starts immediately and returns HTTP 503 with `{"status": "starting"}` on all endpoints until ES is healthy. A background `threading.Thread` starts the ES subprocess and polls cluster health; once healthy, it sets a shared flag that the Flask routes check.
- **D-03:** ES cold-start deadline: 180 seconds (validated in v1.0 — actual cold-start ~120s on target machine).
- **D-04:** Health poll interval: 2 seconds (carried from v1.0 ESHealthWorker pattern).
- **D-05:** Accept `green` or `yellow` cluster status as healthy (same as v1.0).

### Ctrl+C / Graceful Shutdown
- **D-06:** `try/finally` block wrapping `app.run()` in `main.py`. Flask dev server raises `KeyboardInterrupt` on Ctrl+C; the `finally` block calls `shutdown_es(process)` to terminate the ES subprocess. No explicit `signal.signal()` override needed — Flask's built-in SIGINT handling is sufficient on Linux.

### Code Structure
- **D-07:** Strip `ESHealthWorker` (QThread-based) from `es_manager.py`. Keep the subprocess/path utilities — `resolve_es_home`, `inject_es_config`, `validate_es_home`, `shutdown_es`, `_es_binary_path` — but simplify them: remove frozen-mode (PyInstaller) logic from `resolve_es_home` (PyInstaller removed in v1.1), and remove all Windows-specific branches.
- **D-08:** New `nitrofind/server.py` holds: the Flask app, `/api/status`, `GET /`, and the `start_es_background()` function that spawns the threading.Thread health poller. `main.py` imports from `nitrofind.server` and `nitrofind.es_manager`.
- **D-09:** The mutable state shared between the background thread and Flask routes uses a simple module-level dict in `server.py` (same state-dict pattern as v1.0 `main.py` — avoids closure/global fragility).

### PyQt6 Cleanup
- **D-10:** Remove from `requirements.in`: `PyQt6==6.11.0`, `qt-material==2.17`. Regenerate `requirements.txt`. Remove all `from PyQt6.*` and `from qt_material import *` imports across the codebase. Delete `nitrofind/ui/` directory (all five files: `loading_window.py`, `main_window.py`, `filter_sidebar.py`, `result_delegate.py`, `spinner.py`).

### /api/status Response Shape
- **D-11:** During warmup: `HTTP 503`, body `{"status": "starting"}`.
- **D-12:** When healthy: `HTTP 200`, body `{"status": "ok", "es_health": "<green|yellow|red>", "doc_count": <int>, "index_size_bytes": <int>}`. Fetch doc count and index size from `client.cat.indices(index="car_articles", h=["docs.count", "store.size"], bytes="b", format="json")`.

### GET / Placeholder
- **D-13:** `GET /` returns a minimal HTML page for Phase 8 to replace. Just enough to confirm the server is up: `<h1>NitroFind</h1><p>Search UI coming in Phase 8.</p>`. No assets, no CSS.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase & Requirements
- `.planning/ROADMAP.md` — Phase 6 goal, success criteria (5 items), requirements list (SRVR-01..04, API-03, API-04, CLEN-01)
- `.planning/REQUIREMENTS.md` — Full requirement text with acceptance conditions for SRVR-01..04, API-03, API-04, CLEN-01
- `.planning/PROJECT.md` — Tech stack constraints, v1.1 milestone goal, key decisions table

### Existing Implementation to Modify
- `main.py` — Current v1.0 PyQt6 entry point; to be fully rewritten for Flask lifecycle
- `nitrofind/es_manager.py` — Subprocess/path utilities to keep (stripped of QThread/PyQt6); `ESHealthWorker` to be removed
- `requirements.in` — Remove PyQt6==6.11.0 and qt-material==2.17; add Flask

### New Files to Create
- `nitrofind/server.py` — New file: Flask app, `/api/status`, `GET /`, `start_es_background()`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nitrofind/es_manager.py`: `validate_es_home()`, `inject_es_config()`, `shutdown_es()`, `_es_binary_path()`, `ES_URL` — all reusable after stripping PyQt6 imports and Windows branches
- `nitrofind/es_manager.py`: `resolve_es_home()` — reusable but simplify: remove frozen-mode (PyInstaller) branch; just return `os.environ.get("ES_HOME")`
- `nitrofind/es_schema.py`: `ensure_index(client)` — call this after ES is healthy, before Flask starts accepting search requests
- `nitrofind/search/engine.py` — untouched in Phase 6; Phase 7 wires it to `/api/search`

### Established Patterns
- State dict pattern (`state = {"worker": None}`) from v1.0 `main.py` — reuse as module-level dict in `server.py` for the shared ES process + readiness flag
- 180s deadline + 2s poll interval — kept from `ESHealthWorker.run()`
- `subprocess.Popen([es_bin], stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, close_fds=True)` — keep this pattern; drop Windows-specific kwargs

### Integration Points
- `main.py` imports `nitrofind.server.create_app()` (or equivalent) and `nitrofind.es_manager` utilities
- `nitrofind/ui/` directory is deleted entirely — no imports remain after cleanup
- `requirements.in` and `requirements.txt` updated together (pip-compile workflow)

</code_context>

<specifics>
## Specific Ideas

- User runs exclusively in WSL terminal — all code and docs can assume Linux/POSIX. No "Windows users" callouts needed in comments or error messages.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-Server Lifecycle & Cleanup*
*Context gathered: 2026-06-03*
