# Phase 6: Server Lifecycle & Cleanup - Research

**Researched:** 2026-06-03
**Domain:** Flask dev server lifecycle, threading, PyQt6 removal, subprocess management
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Linux/WSL only. All `sys.platform == "win32"` branches in `es_manager.py` are removed — no `CREATE_NEW_PROCESS_GROUP`, no `shell=True`, no `CTRL_BREAK_EVENT`, no `.bat` path suffix. `_es_binary_path()` returns `{es_home}/bin/elasticsearch` unconditionally.
- **D-02:** Flask starts immediately and returns HTTP 503 with `{"status": "starting"}` on all endpoints until ES is healthy. A background `threading.Thread` starts the ES subprocess and polls cluster health; once healthy, it sets a shared flag that Flask routes check.
- **D-03:** ES cold-start deadline: 180 seconds.
- **D-04:** Health poll interval: 2 seconds.
- **D-05:** Accept `green` or `yellow` cluster status as healthy.
- **D-06:** `try/finally` block wrapping `app.run()` in `main.py`. Flask dev server raises `KeyboardInterrupt` on Ctrl+C; the `finally` block calls `shutdown_es(process)` to terminate the ES subprocess.
- **D-07:** Strip `ESHealthWorker` (QThread-based) from `es_manager.py`. Keep `resolve_es_home`, `inject_es_config`, `validate_es_home`, `shutdown_es`, `_es_binary_path` — simplified: remove frozen-mode logic from `resolve_es_home`, remove all Windows branches.
- **D-08:** New `nitrofind/server.py` holds the Flask app, `/api/status`, `GET /`, and `start_es_background()`.
- **D-09:** Shared state between background thread and Flask routes: module-level dict in `server.py` (same pattern as v1.0 `main.py`).
- **D-10:** Remove `PyQt6==6.11.0`, `qt-material==2.17` from `requirements.in`. Remove all `from PyQt6.*` and `from qt_material import *` imports. Delete `nitrofind/ui/` directory.
- **D-11:** During warmup: `HTTP 503`, body `{"status": "starting"}`.
- **D-12:** When healthy: `HTTP 200`, body `{"status": "ok", "es_health": "<green|yellow|red>", "doc_count": <int>, "index_size_bytes": <int>}`. Fetch from `client.cat.indices(index="car_articles", h=["docs.count", "store.size"], bytes="b", format="json")`.
- **D-13:** `GET /` returns minimal HTML: `<h1>NitroFind</h1><p>Search UI coming in Phase 8.</p>`.

### Claude's Discretion

None recorded.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRVR-01 | `python main.py` starts ES 8.18 and Flask web server — no separate steps | Flask.run() blocks; background threading.Thread starts ES before or concurrently; both run from single invocation |
| SRVR-02 | Flask listens on `http://localhost:5000`; port overridable via `PORT` env var | Flask.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000))) — verified pattern |
| SRVR-03 | Flask returns HTTP 503 with `{"status": "starting"}` during ES warmup | Module-level readiness flag checked per-request; jsonify() + 503 tuple return |
| SRVR-04 | Ctrl+C exits both Flask and ES cleanly — no orphaned JVM | try/finally around app.run(); KeyboardInterrupt propagates from Werkzeug; finally calls shutdown_es(process) |
| API-03 | `GET /api/status` returns JSON with ES health, doc count, index size | client.cat.indices() with bytes="b"; jsonify dict return |
| API-04 | `GET /` serves main HTML search page (placeholder for Phase 8) | Return minimal HTML string with 200 OK |
| CLEN-01 | PyQt6, PyQt6-Qt6, PyQt6-sip, qt-material removed from requirements and imports | Remove from requirements.in; delete nitrofind/ui/; fix es_manager.py and search/engine.py imports |
</phase_requirements>

---

## Summary

Phase 6 is a brownfield rewrite with a clearly bounded scope: swap `main.py` from a PyQt6 desktop entry point to a Flask web server entry point, strip PyQt6 from the dependency tree, and simplify `es_manager.py` by removing Qt and Windows code. The technical surface is small — Flask dev server lifecycle, Python `threading.Thread` for background ES startup, and a single shared state dict.

The most important technical facts to plan around: Flask's dev server raises `KeyboardInterrupt` on Ctrl+C (verified via Werkzeug), which means `try/finally` is the correct shutdown pattern without needing `signal.signal()`. The background `threading.Thread` pattern (not `QThread`) is a pure Python stdlib solution with no new dependencies. The `threading.Thread(daemon=True)` flag ensures the health-poller thread does not block process exit if `finally` runs.

A hidden scope item surfaces in the PyQt6 removal: `nitrofind/search/engine.py` also imports PyQt6 (`QThreadPool`, `QRunnable`, `pyqtSignal`). This file is NOT imported by Phase 6 code paths (`main.py` and `server.py` do not import `SearchEngine`), so Phase 6 does not need to rewrite the search engine. However, CLEN-01's literal requirement ("no PyQt6/qt-material import in codebase") would be violated if `search/engine.py` remains untouched. The plan must either (a) rewrite `search/engine.py` to remove PyQt6 in this phase, or (b) defer it explicitly to Phase 7 where `/api/search` needs the engine anyway. Deferral is the cleaner path — the planner must decide and document this explicitly.

**Primary recommendation:** Implement Phase 6 in four sequential waves: (1) add Flask to requirements and regenerate lockfile, (2) rewrite `es_manager.py` (strip Qt/Windows), (3) create `nitrofind/server.py`, (4) rewrite `main.py` and delete `nitrofind/ui/`. The search/engine.py PyQt6 dependency should be deferred to Phase 7 with an explicit note in CLEN-01 acceptance.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ES subprocess start/stop | Backend process | — | ES JVM is a subprocess of the Python process; all lifecycle lives in the Python layer |
| Health polling | Backend process (threading.Thread) | — | Background thread in main Python process; no web layer involvement |
| HTTP 503 warmup guard | API / Backend (Flask route) | — | Each HTTP request checks the in-memory readiness flag set by background thread |
| `/api/status` data fetch | API / Backend (Flask route) | ES (data source) | Route queries ES cat.indices for live stats |
| `GET /` placeholder | API / Backend (Flask route) | — | Static HTML string response; no frontend server tier needed at this phase |
| Dependency cleanup | Build/packaging | — | requirements.in + pip-compile + file deletion |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 (latest) | Web server, routing, JSON responses | Locked in CLAUDE.md / PROJECT.md; only new dependency this phase adds |
| threading (stdlib) | Python 3.11 stdlib | Background ES health poller | Pure stdlib; replaces QThread; no new dependency |
| subprocess (stdlib) | Python 3.11 stdlib | ES JVM process management | Already used in es_manager.py; kept unchanged |
| elasticsearch | 8.19.3 (current pinned) | ES client for health check + cat.indices | Already in requirements.txt |
| pip-tools | 7.5.3 (installed) | Regenerate requirements.txt after removing PyQt6 | Already installed in dev environment |

[VERIFIED: pypi.org] Flask 3.1.3 is the current latest on PyPI (confirmed via `pip3 index versions flask`).
[VERIFIED: pypi.org] pip-tools 7.5.3 is installed and confirmed via `pip3 show pip-tools`.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os (stdlib) | Python stdlib | Read `PORT` env var for SRVR-02 | `int(os.environ.get("PORT", 5000))` in app.run() |
| time (stdlib) | Python stdlib | Monotonic clock for 180s deadline | `time.monotonic()` — already pattern from ESHealthWorker |
| logging (stdlib) | Python stdlib | Background thread logging | `logging.getLogger("nitrofind.server")` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `threading.Thread` | `concurrent.futures.ThreadPoolExecutor` | ThreadPoolExecutor is heavier; a single thread is sufficient for one-shot ES startup |
| `threading.Thread` | `asyncio` + `asyncio.subprocess` | Asyncio would require Flask to run in async mode or use a separate event loop — unnecessary complexity for this use case |
| `try/finally` shutdown | `signal.signal(SIGINT, handler)` | Signal handler approach adds complexity; Flask/Werkzeug already propagates KeyboardInterrupt cleanly from its SIGINT handler on Linux |

**Installation:**
```bash
pip install flask>=3.1
pip-compile requirements.in
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| flask | PyPI | ~16 yrs | Very high (tens of millions/mo) | github.com/pallets/flask | [OK] | Approved |

**slopcheck verdict:** `[OK]` for flask (run: `slopcheck install flask --json` — result confirmed OK).

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
python main.py
    │
    ├── validate_es_home() → raise ValueError if ES_HOME invalid (exits)
    ├── inject_es_config()  → writes elasticsearch.yml + jvm.options
    │
    ├── start_es_background(es_home, state)
    │       └── threading.Thread(target=_es_health_poller, daemon=True).start()
    │               └── subprocess.Popen([es_bin], stdin=DEVNULL, ...)
    │                       └── polls cluster.health() every 2s (max 180s)
    │                               └── sets state["ready"] = True (or logs failure)
    │
    └── try:
            app.run(host="127.0.0.1", port=PORT)  ←── blocks here
            ┌── GET /           → HTML placeholder (200)
            ├── GET /api/status → check state["ready"]
            │       ├── not ready → {"status": "starting"} (503)
            │       └── ready   → {"status": "ok", "es_health": ...,
            │                       "doc_count": int, "index_size_bytes": int} (200)
            └── (future) GET /api/search  [Phase 7]
        finally:
            shutdown_es(state["process"])  ← SIGTERM → wait(10s) → kill()
```

### Recommended Project Structure

```
nitrofind/
├── es_manager.py     # modified: strip ESHealthWorker, QThread, Windows branches
├── es_schema.py      # untouched
├── server.py         # NEW: Flask app, routes, start_es_background(), state dict
├── search/           # untouched in Phase 6 (engine.py still imports PyQt6; deferred)
│   ├── engine.py
│   ├── models.py
│   └── query_builder.py
└── scraper/          # untouched

main.py               # rewritten: Flask lifecycle entry point, no Qt imports
requirements.in       # remove PyQt6==6.11.0, qt-material==2.17; add flask>=3.1
requirements.txt      # regenerated via pip-compile

DELETE:
nitrofind/ui/         # entire directory: 5 files
tests/test_loading_window.py
tests/test_ui/        # 3 test files (test_main_window.py, test_filter_sidebar.py, test_result_delegate.py)
```

### Pattern 1: Flask JSON Response with Status Code

**What:** Return a Python dict as JSON with an explicit HTTP status code using a tuple return.
**When to use:** Both `/api/status` responses.
**Example:**
```python
# Source: flask.palletsprojects.com/en/stable/quickstart/#apis-with-json
from flask import Flask, jsonify
app = Flask(__name__)

@app.route("/api/status")
def api_status():
    if not state["ready"]:
        return {"status": "starting"}, 503     # dict return auto-jsonified in Flask 3.x
    return {
        "status": "ok",
        "es_health": state["es_health"],
        "doc_count": state["doc_count"],
        "index_size_bytes": state["index_size_bytes"],
    }, 200
```

### Pattern 2: Background threading.Thread with try/finally Shutdown

**What:** Daemon thread polls ES health and sets a shared state dict; main thread runs Flask; finally block cleans up the ES process.
**When to use:** This is the core lifecycle pattern for Phase 6.
**Example:**
```python
# Source: Python docs threading.Thread + established v1.0 pattern (D-09)
import threading
import time
from elasticsearch import Elasticsearch

state = {
    "ready": False,
    "process": None,
    "es_health": None,
    "doc_count": 0,
    "index_size_bytes": 0,
}

def _es_health_poller(es_home: str) -> None:
    from nitrofind.es_manager import shutdown_es
    try:
        state["process"] = _start_es_process(es_home)
    except OSError as exc:
        logging.getLogger("nitrofind.server").error("ES start failed: %s", exc)
        return

    client = Elasticsearch("http://localhost:9200", request_timeout=2)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if state["process"].poll() is not None:
            logging.getLogger("nitrofind.server").error("ES process exited unexpectedly")
            return
        try:
            resp = client.cluster.health()
            if resp["status"] in ("green", "yellow"):
                state["ready"] = True
                return
        except Exception:
            pass
        time.sleep(2)
    logging.getLogger("nitrofind.server").warning("ES did not become healthy within 180s")


def start_es_background(es_home: str) -> None:
    t = threading.Thread(target=_es_health_poller, args=(es_home,), daemon=True)
    t.start()
```

### Pattern 3: try/finally Flask Shutdown

**What:** Flask's Werkzeug server raises KeyboardInterrupt on Ctrl+C (SIGINT on Linux). The finally block fires unconditionally.
**When to use:** `main.py` entry point — wraps the blocking `app.run()` call.
**Example:**
```python
# Source: Flask docs + Werkzeug behavior (verified)
def main() -> None:
    es_home = validate_es_home(resolve_es_home())
    inject_es_config(es_home, config_src)
    start_es_background(es_home)   # from nitrofind.server
    port = int(os.environ.get("PORT", 5000))
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    finally:
        if state["process"] is not None:
            shutdown_es(state["process"])
```

**Critical:** `use_reloader=False` is mandatory. The Werkzeug reloader forks a child process; a reloader child would call `start_es_background()` again, spawning a second ES JVM. Always disable the reloader in this lifecycle model.

### Pattern 4: cat.indices for /api/status data

**What:** Fetch document count and index size from ES without a search query.
**When to use:** `GET /api/status` after `state["ready"]` is True.
**Example:**
```python
# Source: elasticsearch-py 8.x client, ES cat.indices API
from elasticsearch import Elasticsearch

def _fetch_index_stats(client: Elasticsearch) -> tuple[int, int]:
    """Returns (doc_count, size_in_bytes). Returns (0, 0) on error."""
    try:
        result = client.cat.indices(
            index="car_articles",
            h=["docs.count", "store.size"],
            bytes="b",
            format="json",
        )
        if result:
            row = result[0]
            return int(row.get("docs.count") or 0), int(row.get("store.size") or 0)
    except Exception as exc:
        logging.getLogger("nitrofind.server").warning("cat.indices failed: %s", exc)
    return 0, 0
```

**Note:** `cat.indices` returns `store.size` in bytes when `bytes="b"` is set. The field name in the response dict is `"store.size"` (with a dot), not `"store_size"`. [ASSUMED — verify field name at implementation time against live ES response.]

### Anti-Patterns to Avoid

- **Flask debug=True in this lifecycle:** `debug=True` implicitly enables `use_reloader=True`, which forks a second process. That second process will re-enter `main()` and attempt to start a second ES JVM. Use `debug=False` (or `use_reloader=False` explicitly) at all times.
- **threading.Thread(daemon=False) for health poller:** A non-daemon thread keeps the Python process alive after `app.run()` returns. If the finally block runs and ES shuts down but the poller thread is stuck in `time.sleep(2)`, the process hangs for up to 2 seconds. Daemon thread exits with the main thread automatically.
- **Importing SearchEngine in server.py:** `nitrofind/search/engine.py` imports PyQt6. Importing it in Phase 6 code would re-introduce the very dependency being removed. Do not import `SearchEngine` until Phase 7 (after it is rewritten).
- **Reading cat.indices when not ready:** The `/api/status` handler must check `state["ready"]` before calling the ES client. Calling `cat.indices` while ES is starting will raise `ConnectionError` or return empty.
- **state dict shared without locks:** The state dict is read by Flask route handlers (potentially in multiple threads, since Flask's dev server is threaded by default). Writes happen from one background thread. For a single writer and multiple readers of simple Python values (bool, int, str), the GIL makes this safe — no explicit Lock needed for this use case.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON responses | Custom `json.dumps()` + `Response()` | Return dict literal from Flask route | Flask 3.x auto-converts dict/list return values to JSON responses — `jsonify()` or dict return both work |
| HTTP status codes | Custom WSGI response objects | Tuple return `(dict, status_code)` | Flask handles this natively; no extra imports |
| ES process termination | Custom kill sequence | `shutdown_es()` in `es_manager.py` | Already implemented with SIGTERM + 10s timeout + kill fallback |
| requirements lockfile | Manual hash computation | `pip-compile requirements.in` | pip-tools 7.5.3 already installed; regenerates requirements.txt with hashes |

**Key insight:** The entire HTTP layer in this phase fits in ~60 lines. Do not add abstractions or a factory function pattern unless the planner's task decomposition requires it for testability.

---

## Common Pitfalls

### Pitfall 1: Werkzeug Reloader Spawns Duplicate ES Process
**What goes wrong:** If `app.run(debug=True)` or `app.run(use_reloader=True)` is used, Werkzeug forks a child process to watch for code changes. That child re-executes `main()` from the top, calling `start_es_background()` a second time, spawning a second ES JVM on the same port (9200). The second ES fails to start (port conflict), logging confusion ensues.
**Why it happens:** Werkzeug's reloader runs the app module in a child process; Python's `if __name__ == "__main__"` guard does NOT protect against this because Werkzeug re-imports the module.
**How to avoid:** Always pass `use_reloader=False` to `app.run()`. Debug UI (interactive debugger) can still be enabled with `debug=True, use_reloader=False` if needed, but for a headless server this isn't needed.
**Warning signs:** Two `elasticsearch` processes in `ps aux`; second startup fails with "Address already in use: 9200".

### Pitfall 2: cat.indices "store.size" Field Name Has a Dot
**What goes wrong:** The cat.indices response row uses `"store.size"` as the key (a dot in the key name), not `"store_size"`. Accessing `row["store_size"]` raises `KeyError` silently if using `.get()` and returns `None`, producing `0` after `int(None or 0)`.
**Why it happens:** ES cat API uses dotted field names by convention when `h=` parameter selects sub-fields.
**How to avoid:** Use `row.get("store.size") or 0` in the response parsing. Verify field names against a real cat.indices response in the integration test. [ASSUMED — field name verification needed at implementation time]
**Warning signs:** `index_size_bytes` always returns `0` even when documents are indexed.

### Pitfall 3: PyQt6 Import in search/engine.py Violates CLEN-01 Literally
**What goes wrong:** CLEN-01 says "no PyQt6/qt-material import in codebase." `nitrofind/search/engine.py` imports `from PyQt6.QtCore import ...` on line 32. If not addressed, `pip install -r requirements.txt` will still succeed (PyQt6 removed from requirements) but running `grep -r "from PyQt6" .` will show a remaining import, failing the acceptance condition literally.
**Why it happens:** The search engine's threading model uses QThreadPool/QRunnable. Phase 6 scope does not include the search API, so the engine is not imported by Phase 6 code. But the file exists.
**How to avoid:** Two options: (a) Defer `search/engine.py` rewrite to Phase 7 — update CLEN-01 acceptance criteria to read "no PyQt6 import in Phase 6 code paths" (or note explicitly that engine.py is deferred); (b) Delete `search/engine.py` and its tests in Phase 6, accepting that Phase 7 starts fresh. Option (a) is safer and preserves test coverage. The plan must make this explicit.
**Warning signs:** `grep -r "from PyQt6" nitrofind/` returns `nitrofind/search/engine.py` after Phase 6 is complete.

### Pitfall 4: shutdown_es() Called on None Process
**What goes wrong:** If ES startup fails (`OSError` from `Popen`), `state["process"]` remains `None`. The `finally` block calls `shutdown_es(state["process"])` which passes `None` — `shutdown_es()` calls `process.poll()` immediately raising `AttributeError`.
**Why it happens:** The error path in `_es_health_poller` returns early without setting `state["process"]`. The finally block runs regardless.
**How to avoid:** Guard the finally block: `if state["process"] is not None: shutdown_es(state["process"])`. The existing `shutdown_es()` function does not guard against None input.
**Warning signs:** `AttributeError: 'NoneType' object has no attribute 'poll'` on Ctrl+C when ES failed to start.

### Pitfall 5: requirements.txt Still Contains PyQt6 Hashes After pip-compile
**What goes wrong:** If `requirements.txt` is manually edited instead of regenerated via `pip-compile`, stale PyQt6 entries remain. `pip install -r requirements.txt` may still try to install them if the hash is present.
**Why it happens:** `requirements.txt` is a generated lockfile. Manual editing is fragile with hash-based pinning.
**How to avoid:** After removing `PyQt6==6.11.0` and `qt-material==2.17` from `requirements.in`, always regenerate with `pip-compile --generate-hashes requirements.in`. Verify the output contains no `pyqt6` entries. [VERIFIED: pip-tools 7.5.3 is installed]

---

## Code Examples

### Flask app.run() with PORT env var (SRVR-02)

```python
# Source: Flask docs flask.palletsprojects.com/en/stable/api/#flask.Flask.run
import os
port = int(os.environ.get("PORT", 5000))
app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
```

### Flask dict return as JSON with status code (D-11, D-12)

```python
# Source: Flask docs flask.palletsprojects.com/en/stable/quickstart/#apis-with-json
# In Flask 3.x, returning a dict from a view auto-calls jsonify().
# Tuple (body, status_code) sets the HTTP status.
@app.route("/api/status")
def api_status():
    if not state["ready"]:
        return {"status": "starting"}, 503
    return {"status": "ok", "es_health": state["es_health"],
            "doc_count": state["doc_count"],
            "index_size_bytes": state["index_size_bytes"]}, 200
```

### Subprocess start for Linux (D-01)

```python
# Source: existing es_manager.py _start_process() — Windows branches removed
def _start_process(es_home: str) -> subprocess.Popen:
    es_bin = os.path.join(es_home, "bin", "elasticsearch")
    return subprocess.Popen(
        [es_bin],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
```

### Flask test client for unit tests (Validation Architecture)

```python
# Source: Flask docs flask.palletsprojects.com/en/stable/testing/
def test_status_starting(app_not_ready):
    client = app_not_ready.test_client()
    resp = client.get("/api/status")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "starting"}
```

---

## Runtime State Inventory

> Not applicable — this is not a rename/refactor/migration phase. Phase 6 rewrites code files and removes a dependency; no stored data, live service config, OS-registered state, or secret keys embed the changed identifiers.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All | ✓ | 3.12.3 (system) | — |
| pip3 | Package install | ✓ | 26.1.1 | — |
| pip-tools (pip-compile) | requirements.txt regen | ✓ | 7.5.3 | manual edit (fragile) |
| Flask | SRVR-01..04, API-03, API-04 | Available on PyPI (not yet in venv) | 3.1.3 | — |
| elasticsearch client | API-03 | ✓ (in requirements.txt) | 8.19.3 | — |
| pytest | Test suite | ✓ (in requirements.txt) | 9.0.3 | — |

**Note on Python version:** The system Python is 3.12.3 and the project targets 3.11. Verify the project venv uses Python 3.11 before running pip-compile. Running pip-compile with Python 3.12 generates a lockfile compatible with 3.12 but may include hashes for wheels that differ from 3.11 wheels. The requirements.txt header already shows `pip-compile with Python 3.12` — this is acceptable as long as all packages support 3.11 as well, which Flask 3.1.x does. [ASSUMED — project venv Python version not directly verified]

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** Flask (not in venv yet — added to requirements.in and installed via pip-compile/pip install).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (exists at repo root) |
| Quick run command | `pytest tests/ -m "not integration" -x -q` |
| Full suite command | `pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRVR-01 | `python main.py` starts ES + Flask from single invocation | smoke/manual | manual: run `python main.py`, open browser | manual-only (requires live ES) |
| SRVR-02 | Flask listens on localhost:5000; PORT env var overrides | unit | `pytest tests/test_server.py::test_port_env_var -x` | ❌ Wave 0 |
| SRVR-03 | Returns HTTP 503 during warmup; 200 when ready | unit | `pytest tests/test_server.py::test_status_before_ready tests/test_server.py::test_status_after_ready -x` | ❌ Wave 0 |
| SRVR-04 | Ctrl+C exits cleanly — no orphaned JVM | manual | manual: run `python main.py`, press Ctrl+C, check `ps aux | grep elasticsearch` | manual-only |
| API-03 | `GET /api/status` returns correct JSON shape | unit | `pytest tests/test_server.py::test_status_response_shape -x` | ❌ Wave 0 |
| API-04 | `GET /` returns HTML with expected content | unit | `pytest tests/test_server.py::test_root_returns_html -x` | ❌ Wave 0 |
| CLEN-01 | No PyQt6/qt-material imports in codebase | static/grep | `grep -r "from PyQt6\|import PyQt6\|from qt_material" nitrofind/ main.py` returns empty | automated grep |

### Sampling Rate

- **Per task commit:** `pytest tests/test_server.py -x -q` (new server tests only)
- **Per wave merge:** `pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_server.py` — covers SRVR-02, SRVR-03, API-03, API-04
- [ ] `tests/test_es_manager_v2.py` — covers simplified `es_manager.py` (no Windows branches, no ESHealthWorker)

**Existing tests to delete in this phase:**
- `tests/test_loading_window.py` — tests PyQt6 LoadingWindow (CLEN-01)
- `tests/test_ui/test_main_window.py` — PyQt6 (CLEN-01)
- `tests/test_ui/test_filter_sidebar.py` — PyQt6 (CLEN-01)
- `tests/test_ui/test_result_delegate.py` — PyQt6 (CLEN-01)

**Existing tests to update (not delete):**
- `tests/test_es_manager.py` — currently tests `ESHealthWorker` (QThread). After stripping ESHealthWorker, these tests must be updated: remove `test_worker_emits_ready`, `test_worker_emits_failed` (test a class that no longer exists). Keep `test_missing_es_home`, `test_shutdown_graceful`, `test_shutdown_kills_on_timeout`.
- `tests/test_search/test_engine.py` — currently imports from PyQt6 indirectly via SearchEngine. If search/engine.py PyQt6 dependency is deferred to Phase 7, the test file needs a skip guard (`try: import PyQt6` pattern like `test_loading_window.py` uses). [ASSUMED: confirm whether engine.py is deleted or deferred]

---

## Security Domain

> `security_enforcement` not set to false in config.json — section included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Flask dev server; no auth in scope (localhost only, per REQUIREMENTS.md Out of Scope) |
| V3 Session Management | No | No sessions; stateless API |
| V4 Access Control | No | No roles/users; single-user local tool |
| V5 Input Validation | Partial | PORT env var: `int(os.environ.get("PORT", 5000))` — raises ValueError on non-integer; should be caught with a clear error message |
| V6 Cryptography | No | No crypto operations in this phase |

### Known Threat Patterns for Flask dev server on localhost

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Binding to 0.0.0.0 instead of 127.0.0.1 | Information Disclosure | Always use `host="127.0.0.1"` (CONTEXT.md: WSL-only, no external access needed) |
| Debug mode on in production | Elevation of Privilege | Use `debug=False, use_reloader=False` (also prevents duplicate ES spawn — Pitfall 1) |
| Port injection via PORT env var | Tampering | `int(os.environ.get("PORT", 5000))` raises ValueError on non-integer; wrap in try/except with sys.exit |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyQt6 QThread for background work | `threading.Thread` (stdlib) | This phase | Removes Qt dependency from process management |
| ESHealthWorker as QThread subclass | Module-level `_es_health_poller` function + Thread | This phase | 40 lines → ~15 lines; no Qt event loop needed |
| Flask `jsonify()` explicit call | Return dict directly from view (auto-jsonified) | Flask 1.0+ | Less verbose; dict return is the current standard |
| `requirements.txt` with PyQt6 hashes | `requirements.txt` without Qt packages | This phase | `pip install -r requirements.txt` no longer requires Qt |

**Deprecated/outdated:**
- `ESHealthWorker` (QThread): removed in this phase — replaced by `threading.Thread`
- `qt_material.apply_stylesheet()`: removed in this phase — no UI layer
- PyInstaller frozen-mode branch in `resolve_es_home()`: removed — PyInstaller dropped in v1.1 per PROJECT.md

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cat.indices` response row key for store size is `"store.size"` (dotted) when using `h=["store.size"]` | Code Examples, Common Pitfalls | `/api/status` always returns `index_size_bytes: 0`; fixable by printing raw response in integration test |
| A2 | Project venv uses Python 3.11 (not the system 3.12.3) | Environment Availability | pip-compile generates 3.12-targeted lockfile; minor incompatibility risk for 3.11-specific wheels |
| A3 | `search/engine.py` PyQt6 dependency is deferred to Phase 7 (not deleted in Phase 6) | Common Pitfall 3, Wave 0 Gaps | CLEN-01 acceptance check ("no PyQt6 import") will fail if grep is run literally; must note deferral explicitly in plan |

---

## Open Questions

1. **CLEN-01 scope: does it include `search/engine.py`?**
   - What we know: `search/engine.py` imports `from PyQt6.QtCore import ...`. CLEN-01 says "no PyQt6/qt-material import in codebase." Phase 6 does not import SearchEngine in any Phase 6 code path.
   - What's unclear: Whether CLEN-01 is satisfied by removing PyQt6 from requirements.txt while leaving search/engine.py untouched, or whether every file must be clean.
   - Recommendation: The plan should explicitly defer `search/engine.py` rewrite to Phase 7 (where it is needed for `/api/search`), and update the CLEN-01 acceptance condition to "no PyQt6 import in Phase 6 code paths (`main.py`, `server.py`, `es_manager.py`)".

2. **`tests/test_search/test_engine.py` fate**
   - What we know: It imports SearchEngine which imports PyQt6. After PyQt6 is removed from requirements.txt, the test file either fails at import or needs a skip guard.
   - What's unclear: Whether this test file should be deleted (if engine.py is rewritten in Phase 7 from scratch) or patched with a try/import guard.
   - Recommendation: Add the same `try: import PyQt6; PYQT6_AVAILABLE` skip pattern used in `test_loading_window.py`. This keeps test coverage for when PyQt6 is available during Phase 7 transition.

---

## Sources

### Primary (HIGH confidence)
- Flask 3.1.x official docs (flask.palletsprojects.com/en/stable/) — Flask.run() parameters, dict JSON response, use_reloader behavior
- PyPI registry (pypi.org/project/flask/) — Flask 3.1.3 version confirmed via `pip3 index versions flask`
- Existing codebase: `nitrofind/es_manager.py` — verified shutdown_es(), _start_process(), state dict pattern
- Existing codebase: `main.py` — verified v1.0 QThread pattern being replaced

### Secondary (MEDIUM confidence)
- Werkzeug serving docs (werkzeug.palletsprojects.com/en/stable/serving/) — reloader behavior, threaded mode
- Python docs threading.Thread (docs.python.org) — daemon flag behavior, GIL safety for simple shared state

### Tertiary (LOW confidence)
- ES cat.indices field name format — `"store.size"` dotted key — [ASSUMED from common ES cat API behavior; verify with live response]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Flask 3.1.3 confirmed on PyPI; threading is stdlib; all other deps already in lockfile
- Architecture: HIGH — Pattern is directly derived from v1.0 ESHealthWorker with Qt removed; Flask lifecycle behavior verified from official docs
- Pitfalls: HIGH for Pitfall 1 (use_reloader), 3 (search/engine.py), 4 (None process), 5 (pip-compile); MEDIUM for Pitfall 2 (cat.indices field name assumed)

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (stable ecosystem; Flask 3.x stable)
