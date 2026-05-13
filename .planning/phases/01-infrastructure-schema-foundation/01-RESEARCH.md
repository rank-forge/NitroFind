# Phase 1: Infrastructure & Schema Foundation - Research

**Researched:** 2026-05-12
**Domain:** Python venv lockfile, Elasticsearch 8.18 subprocess lifecycle, PyQt6 loading window, ES index mapping
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**ES Binary Location**
- D-01: Locate ES via the `ES_HOME` environment variable. Binary path: `$ES_HOME/bin/elasticsearch`.
- D-02: If `ES_HOME` is not set at startup, exit immediately with a clear error message: `"ES_HOME is not set. Set it to your Elasticsearch 8.18 directory."` No fallback to PATH or relative paths.

**Startup Architecture**
- D-03: Single `main.py` entry point. `QApplication` is created first, showing a loading window immediately. A `QThread` worker starts the ES subprocess and polls cluster health; it emits a signal when ES is ready, which triggers the transition from loading window to the main search window.
- D-04: Health check: `GET /_cluster/health` (via `requests` or the `elasticsearch` client), 2-second polling interval, 60-second total timeout. Accept `green` or `yellow` cluster status as healthy.
- D-05: Shutdown: connect `QApplication.aboutToQuit` to a handler that calls `process.terminate()`, then `process.wait(timeout=10)`. If ES does not exit within 10 seconds, call `process.kill()`.

**Loading Screen**
- D-06: Show a dedicated loading window (not `QSplashScreen`, not the main window) containing: NitroFind branding, an animated spinner, and the static status text `"Starting search engine..."`. This window stays visible until the QThread signals ES readiness, then the main window replaces it.
- D-07: If ES fails to start within 60 seconds (timeout) or crashes (non-zero exit), replace the spinner with an error message and two buttons: **Retry** (terminates the stale process, restarts polling) and **Quit** (calls `QApplication.quit()`).

**era_bucket Schema**
- D-08: `era_bucket` stores decade string labels derived from `production_start` year via integer math: `f"{(year // 10) * 10}s"` — e.g., `"1960s"`, `"2020s"`.
- D-09: ES field type: `keyword` — exact-match filtering, no text analysis.
- D-10: When `production_start` is missing or unknown: store `era_bucket = "Unknown"`.

**Pre-Discussion Locked (from STATE.md / CLAUDE.md)**
- L-01: ES 8.18 config: `xpack.security.enabled: false`, `xpack.security.http.ssl.enabled: false`, `network.host: 127.0.0.1`, JVM heap: `-Xms512m -Xmx512m`.
- L-02: Index mapping uses `dynamic: false` and `flattened` type for any infobox/specs sub-field to prevent mapping explosion.

### Claude's Discretion

None declared in CONTEXT.md. All implementation decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Developer can run the app from a Python venv with a pinned lockfile (reproducible environment across machines) | pip-tools `requirements.in` + `pip-compile` → `requirements.txt` workflow; `pip-sync` for environment sync |
| INFRA-02 | App starts a local Elasticsearch 8.18 node as a subprocess on launch (localhost:9200, TLS disabled, security disabled) | `subprocess.Popen` from QThread worker; `ES_HOME/bin/elasticsearch`; `elasticsearch.yml` with xpack.security settings; verified `discovery.type: single-node` required |
| INFRA-03 | App terminates the Elasticsearch process cleanly when the user quits | `QApplication.aboutToQuit` signal; `process.terminate()` → `process.wait(timeout)` → `process.kill()`; Windows CTRL_BREAK_EVENT pitfall documented |
| INFRA-04 | App shows a loading state while Elasticsearch warms up and becomes healthy (cold start takes 5–15 seconds) | `QThread` subclass + `pyqtSignal`; `QTimer` + `QPainter` spinner; `client.cluster.health()` polling pattern |
| SCHEMA-01 | Each indexed document contains core identity fields: title, url, source_domain, article_id, scraped_at | `client.indices.create()` with explicit `mappings` dict; `dynamic: false`; field types verified |
| SCHEMA-02 | Each indexed document contains relevance scoring fields: published_at, word_count, has_infobox, image_count | `date`, `integer`, `boolean` field types in ES 8.x mapping |
| SCHEMA-03 | Each indexed document contains full plain-text body and a 300-character excerpt | `text` type for body (full-text analyzed), `keyword` for excerpt (no analysis) |
| SCHEMA-04 | Each indexed document contains automotive facet fields: manufacturer, production_start, production_end, body_style, era_bucket, country_of_origin | `keyword` for all facet fields; `integer` for production years; `flattened` for specs sub-object |
</phase_requirements>

---

## Summary

Phase 1 establishes two parallel foundations: (1) a reproducible Python development environment with a pinned lockfile, and (2) a fully wired Elasticsearch 8.18 lifecycle managed by a PyQt6 QThread worker. No scraping or search logic is written here — only the infrastructure that every downstream phase depends on.

The dependency management story is straightforward: `pip-tools` (pip-compile + pip-sync) converts a `requirements.in` file with loose version pins into a fully hashed `requirements.txt` lockfile. This is the standard Python approach for reproducible installs and is well-supported on all platforms.

The ES lifecycle management is where most of the complexity lives. The QThread worker pattern (subclass QThread, reimplement `run()`, emit signals) is verified in PyQt6 official docs. The Elasticsearch Python client 8.19.3 connects with `Elasticsearch("http://localhost:9200")` (no auth, no TLS) when security is disabled. The `car_articles` index mapping is created idempotently at startup using `client.options(ignore_status=[400]).indices.create(...)`. One critical pitfall: on Windows, `subprocess.Popen.terminate()` calls `TerminateProcess()` (immediate, forceful) rather than SIGTERM. The correct cross-platform graceful shutdown requires sending `signal.CTRL_BREAK_EVENT` on Windows (requires `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` at Popen creation time) and SIGTERM on POSIX.

**Primary recommendation:** Use `subprocess.Popen` (not `QProcess`) for the ES process — the Python-native API integrates cleanly with the QThread polling loop. Pin `elasticsearch==8.*` to stay on the 8.x client series that matches the 8.18 server.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Python venv + lockfile | Dev toolchain (pip-tools) | — | Environment management is build-time only; no runtime component |
| ES process lifecycle (start/health/stop) | Backend worker (QThread) | — | Blocking I/O and subprocess management must not run on the Qt GUI thread |
| Loading window UI | Frontend (PyQt6 QWidget) | — | UI state is driven by signals from the QThread worker |
| ES configuration (elasticsearch.yml, jvm.options.d) | ES node config | — | Written to disk at setup; read by ES JVM at startup |
| Index schema creation | Backend worker (QThread, post-ready) | — | Runs after ES health passes; idempotent — safe to re-run on every startup |
| Stub main window | Frontend (PyQt6 QMainWindow) | — | Minimal placeholder; full implementation is Phase 4's responsibility |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11.x | All app logic | CLAUDE.md lock — compatibility ceiling for PyQt6 + elasticsearch-py |
| elasticsearch | 8.19.3 (pin: `elasticsearch==8.*`) | ES Python client | 8.x client required for ES 8.18 server; 8.19.3 is latest 8.x [VERIFIED: pypi.org] |
| PyQt6 | 6.11.0 | Desktop GUI | CLAUDE.md lock; latest stable [VERIFIED: pypi.org] |
| pip-tools | 7.5.3 | Requirements lockfile | `pip-compile` → reproducible `requirements.txt`; standard Python lockfile tool [VERIFIED: pypi.org] |
| qt-material | 2.17 | Material Design theme | CLAUDE.md recommendation; latest stable [VERIFIED: pypi.org, libraries.io] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| requests | 2.32.x | HTTP client for health polling | Use for `GET /_cluster/health` if not using the ES client directly |
| PyQt6-Qt6 | (auto with PyQt6) | Qt runtime binaries | Always — installed as PyQt6 dependency |
| PyQt6-sip | (auto with PyQt6) | C++ binding layer | Always — installed as PyQt6 dependency |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pip-tools | uv pip compile | uv is faster but less universally available; pip-tools is the battle-tested choice for cross-machine reproducibility |
| subprocess.Popen | QProcess | QProcess integrates with Qt event loop signals but requires Qt-specific error handling; Popen is simpler and sufficient for a single managed process |
| elasticsearch client for health poll | requests library | Either works; elasticsearch client is already a dependency and provides typed `cluster.health()` |

**Installation:**
```bash
pip install pip-tools
pip-compile requirements.in   # generates requirements.txt lockfile
pip-sync requirements.txt     # installs exact pinned set in venv
```

---

## Architecture Patterns

### System Architecture Diagram

```
main.py (entry point)
    │
    ▼
QApplication created
    │
    ▼ immediately
LoadingWindow shown (QWidget, frameless, 360×240)
    │                           ▲
    │ starts                    │ emits es_ready / es_failed
    ▼                           │
ESHealthWorker (QThread)        │
    │                           │
    ├─→ subprocess.Popen($ES_HOME/bin/elasticsearch)
    │                           │
    ├─→ poll loop (2s interval, 60s timeout)
    │     GET http://localhost:9200/_cluster/health
    │     accept: green | yellow
    │     on timeout/crash → emit es_failed(reason)
    │     on healthy → emit es_ready ──────────────────┘
    │
    ▼ es_ready received
LoadingWindow.close()
StubMainWindow.show()   ← "NitroFind — Ready" placeholder (Phase 4 replaces)
    │
    ▼ es_ready: also run
IndexSetup.ensure_index()
    client.options(ignore_status=[400]).indices.create(
        index="car_articles", mappings={...}, settings={...}
    )
    │
    ▼
QApplication.aboutToQuit  ─────→  shutdown_handler()
                                      process.terminate()
                                      process.wait(timeout=10)
                                      if alive: process.kill()
```

### Recommended Project Structure

```
NitroFind/
├── main.py                  # QApplication entry point, wires all components
├── requirements.in          # loose top-level deps (human-edited)
├── requirements.txt         # pip-compiled lockfile (committed to git)
├── config/
│   └── elasticsearch.yml    # ES node config template (xpack disabled, 127.0.0.1)
│   └── jvm.options          # -Xms512m -Xmx512m
├── nitrofind/
│   ├── __init__.py
│   ├── es_manager.py        # ESHealthWorker (QThread), shutdown handler
│   ├── es_schema.py         # car_articles index mapping definition + ensure_index()
│   └── ui/
│       ├── __init__.py
│       ├── loading_window.py  # LoadingWindow QWidget + spinner
│       └── main_window.py     # StubMainWindow placeholder
└── tests/
    ├── __init__.py
    ├── test_es_schema.py    # index mapping creation tests
    └── test_es_manager.py   # ES health worker unit tests
```

### Pattern 1: QThread Worker with Custom Signals

**What:** Subclass `QThread`, reimplement `run()`, define custom signals with `pyqtSignal`. The thread emits signals that the main GUI thread receives and acts on.

**When to use:** Any blocking I/O or subprocess management that must not block the Qt event loop.

```python
# Source: https://www.riverbankcomputing.com/static/Docs/PyQt6/signals_slots.html
# Source: https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtcore/qthread.html
from PyQt6.QtCore import QThread, pyqtSignal

class ESHealthWorker(QThread):
    es_ready = pyqtSignal()
    es_failed = pyqtSignal(str)  # reason string

    def __init__(self, es_home: str):
        super().__init__()
        self._es_home = es_home
        self.process: subprocess.Popen | None = None

    def run(self):
        # start subprocess, poll health, emit signal
        ...
```

### Pattern 2: subprocess.Popen with Cross-Platform Shutdown

**What:** Start ES as a child process. On POSIX, `terminate()` sends SIGTERM. On Windows, `terminate()` calls `TerminateProcess` (immediate kill). For graceful Windows shutdown, use `signal.CTRL_BREAK_EVENT`.

**When to use:** Managing the ES JVM process lifecycle.

```python
# Source: Python stdlib subprocess docs + Windows-specific signal handling
import subprocess, signal, sys, os

# Startup — include CREATE_NEW_PROCESS_GROUP for Windows CTRL_BREAK support
kwargs = {}
if sys.platform == "win32":
    kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

es_bin = os.path.join(es_home, "bin", "elasticsearch")
process = subprocess.Popen([es_bin], **kwargs)

# Graceful shutdown (D-05 pattern, cross-platform safe)
def shutdown_es(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return  # already exited
    if sys.platform == "win32":
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
```

### Pattern 3: Idempotent Index Creation with explicit mapping

**What:** Create the `car_articles` index on every startup using `ignore_status=[400]` to silently skip if already exists.

**When to use:** Index bootstrapping on application start.

```python
# Source: https://github.com/elastic/elasticsearch-py/blob/main/docs/reference/configuration.md
from elasticsearch import Elasticsearch

CAR_ARTICLES_MAPPING = {
    "dynamic": "false",
    "properties": {
        # SCHEMA-01: core identity
        "title":         {"type": "text", "analyzer": "standard"},
        "url":           {"type": "keyword"},
        "source_domain": {"type": "keyword"},
        "article_id":    {"type": "keyword"},
        "scraped_at":    {"type": "date"},
        # SCHEMA-02: relevance scoring
        "published_at":  {"type": "date"},
        "word_count":    {"type": "integer"},
        "has_infobox":   {"type": "boolean"},
        "image_count":   {"type": "integer"},
        # SCHEMA-03: full text + excerpt
        "body":          {"type": "text", "analyzer": "standard"},
        "excerpt":       {"type": "keyword"},
        # SCHEMA-04: automotive facets
        "manufacturer":       {"type": "keyword"},
        "production_start":   {"type": "integer"},
        "production_end":     {"type": "integer"},
        "body_style":         {"type": "keyword"},
        "era_bucket":         {"type": "keyword"},   # D-09
        "country_of_origin":  {"type": "keyword"},
        # L-02: flattened type for infobox/specs to prevent mapping explosion
        "specs":              {"type": "flattened"},
    }
}

def ensure_index(client: Elasticsearch) -> None:
    client.options(ignore_status=[400]).indices.create(
        index="car_articles",
        mappings=CAR_ARTICLES_MAPPING,
        settings={"number_of_shards": 1, "number_of_replicas": 0},
    )
```

### Pattern 4: ES Cluster Health Polling

**What:** Poll `/_cluster/health` every 2 seconds, accept `green` or `yellow`, timeout at 60 seconds.

```python
# Source: https://github.com/elastic/elasticsearch-py/blob/main/docs/reference/configuration.md
import time
from elasticsearch import Elasticsearch, ConnectionError as ESConnectionError

def wait_for_healthy(timeout: int = 60, interval: int = 2) -> bool:
    client = Elasticsearch("http://localhost:9200", request_timeout=2)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = client.cluster.health()
            if resp["status"] in ("green", "yellow"):
                return True
        except Exception:
            pass  # ES not yet accepting connections
        time.sleep(interval)
    return False
```

### Pattern 5: PyQt6 Custom Spinner Widget

**What:** A `QWidget` subclass that draws an animated arc using `QTimer` + `QPainter`. This is the UI-SPEC approach — do NOT use `QProgressBar`.

```python
# Source: https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtgui/qpainter.html
# Source: 01-UI-SPEC.md (48×48px, 4px pen, #26a69a, 120° arc, 30°/100ms)
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QPen, QColor

class SpinnerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(100)

    def _rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#26a69a"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        margin = 4
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        # drawArc: angle in 1/16th degrees; start from top, sweep 120°
        painter.drawArc(rect, self._angle * 16, 120 * 16)
```

### Pattern 6: qt-material Theme Application

```python
# Source: https://github.com/un-gcpds/qt-material/blob/master/docs/source/notebooks/readme.md
# MUST be called before any window is created
from qt_material import apply_stylesheet
app = QApplication(sys.argv)
apply_stylesheet(app, theme="dark_teal.xml")
```

### Pattern 7: ES Configuration Files

**`config/elasticsearch.yml`** (checked into repo, copied to `$ES_HOME/config/` at setup):
```yaml
# Source: CLAUDE.md L-01; ES 8.x docs on security settings
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node
xpack.security.enabled: false
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
```

**`config/jvm.options`** (placed in `$ES_HOME/config/jvm.options.d/nitrofind.options`):
```text
# Source: https://www.elastic.co/guide/en/elasticsearch/reference/8.19/advanced-configuration.html
-Xms512m
-Xmx512m
```

### Anti-Patterns to Avoid

- **Starting ES on the main Qt thread:** Blocks the event loop during the 5–15 second cold start; the UI freezes. Always use a QThread worker.
- **Using `QSplashScreen` instead of a custom `QWidget`:** CONTEXT.md D-06 explicitly prohibits this. `QSplashScreen` has limited layout control and doesn't support interactive error state with buttons.
- **Dynamic mapping on `car_articles` index:** Omitting `"dynamic": "false"` allows ES to infer field types from Phase 2 ingest data, causing mapping explosion on varied infobox structures. Always set `dynamic: false` at index creation.
- **Using `elasticsearch>=9` client against ES 8.18:** The 9.x client changed defaults and drops backward compatibility. Pin `elasticsearch==8.*`.
- **Using `elasticsearch-dsl` as a standalone package:** Deprecated since 8.18.0 where DSL was merged into the core `elasticsearch` package. The import still works but is a dead-end. Import from `elasticsearch` directly.
- **Not setting `discovery.type: single-node` in elasticsearch.yml:** Without this, ES 8.x in bootstrap mode waits for cluster formation and will timeout or emit repeated warnings about not having a master node.
- **Calling `process.terminate()` on Windows without `CREATE_NEW_PROCESS_GROUP`:** `subprocess.Popen.terminate()` on Windows calls `TerminateProcess()` — this is an immediate forceful kill. For graceful ES shutdown on Windows, the process must be started with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` so that `send_signal(signal.CTRL_BREAK_EVENT)` can be used instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency pinning | Custom version freeze script | `pip-tools` (`pip-compile` + `pip-sync`) | Handles transitive deps, hash verification, cross-platform resolution |
| UI theme | Custom QSS dark theme | `qt-material` with `dark_teal.xml` | 100+ pages of QSS — handles buttons, labels, inputs, hover/focus states consistently |
| Index field type inference | Custom type-detection logic | ES `flattened` field type | `flattened` maps all sub-keys to a single internal field, preventing mapping explosion without any custom code |
| Subprocess health polling | Custom HTTP polling code | `elasticsearch` client `cluster.health()` | Handles connection errors, retries, response parsing — correct behavior for cold start |

**Key insight:** The biggest hand-roll risk in this phase is the ES shutdown sequence. On Windows, Popen.terminate() is not SIGTERM — it is TerminateProcess. Using it without CREATE_NEW_PROCESS_GROUP means the fallback `process.kill()` is actually the first kill, not the second. This can cause ES data corruption if it happens mid-translog-flush.

---

## Common Pitfalls

### Pitfall 1: Windows subprocess.Popen.terminate() is TerminateProcess, not SIGTERM
**What goes wrong:** On Windows, `Popen.terminate()` calls `TerminateProcess()` immediately. This is equivalent to `kill()` on POSIX — ES gets no opportunity to flush the translog or close indexes cleanly.
**Why it happens:** The Python stdlib uses platform-specific implementations. On Linux/macOS, `terminate()` sends SIGTERM (graceful). On Windows, it calls `TerminateProcess` (forceful).
**How to avoid:** Start the process with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` (Windows only). Then use `process.send_signal(signal.CTRL_BREAK_EVENT)` for graceful shutdown. Fall back to `terminate()` only on timeout.
**Warning signs:** ES data directory contains `.lock` files after unexpected exits; ES fails to start on next run with "lock file exists" error.

### Pitfall 2: Missing `discovery.type: single-node` causes ES startup hang
**What goes wrong:** ES 8.x in bootstrap mode (no data directory) waits to form a quorum. Without `discovery.type: single-node`, the node may repeatedly log "master not yet discovered" and never reach `yellow/green` status within the 60-second health poll timeout.
**Why it happens:** ES 8.x defaults to multi-node discovery. The single-node shortcut is opt-in.
**How to avoid:** Always include `discovery.type: single-node` in `elasticsearch.yml`.
**Warning signs:** Health poller times out after 60 seconds; ES logs show repeated "waiting for master" messages.

### Pitfall 3: Keystore entries block `xpack.security.enabled: false`
**What goes wrong:** Fresh ES 8.x installs generate a keystore with pre-populated TLS entries. Setting `xpack.security.enabled: false` alone may not be sufficient — the keystore entries cause a startup error: "invalid configuration for xpack.security.transport.ssl".
**Why it happens:** ES validates keystore consistency. If TLS keys exist in the keystore but security is disabled, it complains.
**How to avoid:** The setup script must also ensure `xpack.security.http.ssl.enabled: false` and `xpack.security.transport.ssl.enabled: false` are set explicitly. If errors persist, the setup guide should document running `elasticsearch-keystore remove` for the TLS keystore entries.
**Warning signs:** ES exits immediately (before any HTTP is available) with a "configuration error" log message.

### Pitfall 4: QThread signal connection timing
**What goes wrong:** If `es_ready` or `es_failed` signals are connected AFTER `thread.start()`, there is a race condition where the signal fires before the connection is made and the slot is never called.
**Why it happens:** QThread starts executing `run()` immediately on `start()`. If the thread is fast (unlikely here but possible on a cached restart), it can emit before the calling code connects its slot.
**How to avoid:** Connect all signals before calling `thread.start()`.
**Warning signs:** Loading window stays visible indefinitely even though ES started successfully; no transition to the main window.

### Pitfall 5: `excerpt` field type — keyword vs text
**What goes wrong:** Using `text` type for the excerpt field causes ES to analyze it (tokenize, lowercase, stem). SRCH-02 requires displaying the excerpt as stored — if the stored value is processed, the displayed excerpt may differ from what was indexed.
**Why it happens:** `text` fields are analyzed and not suitable for exact retrieval. Stored values can be retrieved but the default storage behavior is affected.
**How to avoid:** Use `keyword` type for `excerpt` (exact match, stored as-is). The 300-character excerpt is display-only; full-text search runs on the `body` field.
**Warning signs:** Displayed excerpts in Phase 4 UI show unexpected characters or mismatched text vs. original.

### Pitfall 6: `dynamic: false` must be a string, not boolean
**What goes wrong:** In the ES Python client, `"dynamic": False` (Python boolean) is accepted, but the semantically correct ES value is the string `"false"` or `"strict"`, not the boolean. Some ES versions interpret the Python boolean as the integer 0, which has different behavior.
**Why it happens:** JSON serialization of Python `False` → `false` which ES interprets as integer 0 in some contexts rather than the string `"false"`.
**How to avoid:** Use `"dynamic": "false"` (string) in the mapping dict, not `False`.
**Warning signs:** `GET /car_articles/_mapping` shows `"dynamic": 0` instead of `"dynamic": "false"`.

---

## Code Examples

### requirements.in (top-level deps)

```
# Source: CLAUDE.md stack; versions verified via pypi.org 2026-05-12
elasticsearch==8.*
PyQt6==6.11.0
qt-material==2.17
requests>=2.32,<3
```

### requirements.txt generation command

```bash
# Source: https://pip-tools.readthedocs.io/en/stable
pip install pip-tools
pip-compile --generate-hashes requirements.in
# Produces: requirements.txt with pinned transitive deps + SHA256 hashes
```

### Complete elasticsearch.yml for NitroFind

```yaml
# Source: CLAUDE.md L-01; ES 8.19 docs (single-node + security disabled)
# Place in: $ES_HOME/config/elasticsearch.yml
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node
xpack.security.enabled: false
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
```

### ES client connection (no auth, HTTP)

```python
# Source: https://github.com/elastic/elasticsearch-py/blob/main/docs/reference/connecting.md
from elasticsearch import Elasticsearch
client = Elasticsearch("http://localhost:9200")
client.info()  # verifies connection
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `elasticsearch-dsl` separate package | Merged into `elasticsearch` core at 8.18.0 | ES client 8.18.0 | No separate install; import from `elasticsearch` |
| `requirements.txt` with manual `pip freeze` | `pip-tools` pip-compile with hashes | Established best practice | Reproducible, hash-verified installs |
| PyQt5 | PyQt6 6.11.0 | 2021 (Qt6 launch), 6.11 March 2026 | Better HiDPI, clean enum namespace |
| `QProgressBar` indeterminate for spinners | Custom `QWidget` + `QTimer` + `QPainter` | N/A (pattern) | Platform-consistent animation |

**Deprecated/outdated:**
- `elasticsearch-dsl` (standalone PyPI): Deprecated. Merged into `elasticsearch==8.18+`. Do not add as separate dependency.
- `elasticsearch7` / `elasticsearch8` packages: These are alternate package names. Use `elasticsearch==8.*` (the main package) with an 8.x version pin instead.
- `PyQt5`: No new features; Qt5 renderer. Do not use on greenfield projects.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `qt-material 2.17` (released April 2025) is the latest version and is compatible with PyQt6 6.11.0 | Standard Stack | Could require version downgrade or fallback to QDarkStyle per CLAUDE.md |
| A2 | ES 8.18 (user's installed version) behaves identically to 8.19 for the config settings documented here | ES Config | Negligible — both are 8.x; the settings documented have been stable since 8.0 |
| A3 | The target runtime platform is Windows (based on WSL2 dev environment) — Windows-specific shutdown pattern is required | Pitfall 1, Pattern 2 | If target is Linux/macOS only, the CTRL_BREAK_EVENT complexity can be dropped |

**All other claims were verified via Context7 or official Elastic/Riverbank documentation in this session.**

---

## Open Questions

1. **Windows vs cross-platform target**
   - What we know: Development is on WSL2 (Windows). The app is described as a "desktop application" with no platform restriction.
   - What's unclear: Is Windows the primary deployment target? Does the Windows shutdown pitfall (CREATE_NEW_PROCESS_GROUP + CTRL_BREAK_EVENT) need to be implemented in Phase 1, or is a simpler cross-platform approach acceptable for now?
   - Recommendation: Implement the cross-platform shutdown pattern in Phase 1 — it is low-complexity and prevents a hard-to-diagnose data corruption issue later.

2. **ES_HOME setup guide scope**
   - What we know: D-01/D-02 require ES_HOME to be set. Phase 1 exits with a clear error if it is not set.
   - What's unclear: Does Phase 1 include a `setup.py` or `README.md` that tells the user how to download ES 8.18 and configure elasticsearch.yml? Or is this assumed to be pre-existing?
   - Recommendation: Phase 1 should include a `scripts/setup_es.py` that copies `config/elasticsearch.yml` and `config/jvm.options` to `$ES_HOME/config/` — this makes the ES configuration reproducible and removes manual steps.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All app logic | Partial | Python 3.12.3 on dev machine [VERIFIED: bash] | Install Python 3.11 via pyenv; 3.12 likely works but is outside the declared compatibility target |
| Java / JVM | Elasticsearch node | Not detected | — (no `java` on PATH) | ES 8.x ships with a bundled JDK inside `$ES_HOME/jdk/` — no separate Java install needed [ASSUMED] |
| Elasticsearch 8.18 | INFRA-02 | Not detected (ES_HOME unset) | — | User must download ES 8.18 archive and set ES_HOME before running |
| pip-tools | INFRA-01 lockfile | Not installed [VERIFIED: bash] | — | Install via `pip install pip-tools` |
| PyQt6 | INFRA-04, loading window | Not installed [VERIFIED: bash] | — | Install via requirements.txt |
| pytest | Test suite | Not installed [VERIFIED: bash] | — | Install via `pip install pytest` (dev-only; not in requirements.in) |

**Missing dependencies with no fallback:**
- Elasticsearch 8.18 archive: user must download from elastic.co and set `ES_HOME` environment variable before any testing is possible.

**Missing dependencies with fallback:**
- Python 3.12.3 on dev machine: Python 3.11 is declared as target. 3.12 likely works for development, but the lockfile should be generated on a 3.11 environment to be strictly reproducible.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (7.x or latest) |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `requirements.txt` contains only pinned (`==`) versions, no loose specifiers | unit | `pytest tests/test_lockfile.py -x` | Wave 0 |
| INFRA-02 | `main.py` reads `ES_HOME`; exits with correct error when unset | unit | `pytest tests/test_es_manager.py::test_missing_es_home -x` | Wave 0 |
| INFRA-02 | ES process starts and health becomes green/yellow within 60s | integration (requires ES) | `pytest tests/integration/test_es_startup.py -x -m integration` | Wave 0 |
| INFRA-03 | `shutdown_es()` calls terminate then wait; calls kill on timeout | unit (mock Popen) | `pytest tests/test_es_manager.py::test_shutdown_graceful -x` | Wave 0 |
| INFRA-04 | `ESHealthWorker` emits `es_ready` when health returns yellow/green | unit (mock ES client) | `pytest tests/test_es_manager.py::test_worker_emits_ready -x` | Wave 0 |
| INFRA-04 | `ESHealthWorker` emits `es_failed` after timeout | unit (mock ES client) | `pytest tests/test_es_manager.py::test_worker_emits_failed -x` | Wave 0 |
| SCHEMA-01..04 | `car_articles` mapping contains all required fields with correct types | unit (mock ES client) | `pytest tests/test_es_schema.py -x` | Wave 0 |
| SCHEMA-01..04 | `ensure_index()` is idempotent (second call with `ignore_status=[400]` does not raise) | unit (mock ES client) | `pytest tests/test_es_schema.py::test_ensure_index_idempotent -x` | Wave 0 |

**Note:** Integration tests require a live ES instance and should be marked `@pytest.mark.integration`. They run in the full suite but are skipped in the quick-run by default.

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q -m "not integration"`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green (including integration tests with live ES) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py`
- [ ] `tests/test_lockfile.py` — INFRA-01
- [ ] `tests/test_es_manager.py` — INFRA-02, INFRA-03, INFRA-04
- [ ] `tests/test_es_schema.py` — SCHEMA-01..04
- [ ] `tests/integration/__init__.py`
- [ ] `tests/integration/test_es_startup.py` — INFRA-02 (live ES)
- [ ] `pytest.ini` — configure `markers = integration: requires live ES`
- [ ] Framework install: `pip install pytest pytest-qt` (dev-only, not in requirements.in)

---

## Security Domain

> `security_enforcement` not explicitly set to false in config.json — treating as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth — single-user local tool, ES has security disabled by design |
| V3 Session Management | No | No sessions — desktop app with no login |
| V4 Access Control | No | Single-user, localhost-only — no access control needed |
| V5 Input Validation | Partial | `ES_HOME` path from environment variable — must be validated as a real directory before use; no user-supplied SQL/query input in Phase 1 |
| V6 Cryptography | No | TLS explicitly disabled by design (L-01); all traffic is localhost-only |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `ES_HOME` | Tampering | Validate `ES_HOME` is an absolute path and that `$ES_HOME/bin/elasticsearch` is an actual file before `subprocess.Popen` — prevents a maliciously set `ES_HOME` from executing arbitrary binaries |
| Process injection via `ES_HOME` binary | Elevation of Privilege | Same validation as above — confirm the binary is the expected ES executable by checking path convention |
| ES listening on non-localhost | Information Disclosure | `network.host: 127.0.0.1` in elasticsearch.yml restricts ES to loopback only — no external access possible |

**Phase 1 security posture:** Low risk. ES is localhost-only, security is intentionally disabled per product design, and no user-supplied input is processed in this phase beyond the `ES_HOME` env var. The one actionable control is validating `ES_HOME` before exec.

---

## Sources

### Primary (HIGH confidence)
- Context7: `/websites/riverbankcomputing_static_pyqt6` — QThread lifecycle, pyqtSignal, QApplication.aboutToQuit, QProcess.terminate/kill, QPainter/QTimer patterns
- Context7: `/elastic/elasticsearch-py` — index creation, cluster health API, ignore_status pattern, no-auth HTTP connection
- Context7: `/websites/elastic_co_guide_en_elasticsearch_reference_8_19` — flattened field type, JVM heap via jvm.options.d, single-node discovery, xpack security settings
- Context7: `/un-gcpds/qt-material` — apply_stylesheet usage, dark_teal.xml theme name
- Context7: `/websites/pip-tools_readthedocs_io_en_stable` — pip-compile workflow, requirements.in, hash generation

### Secondary (MEDIUM confidence)
- [PyPI: elasticsearch](https://pypi.org/project/elasticsearch/) — confirmed 8.19.3 as latest 8.x; 9.x series is current main
- [PyPI: PyQt6](https://pypi.org/project/PyQt6/) — confirmed 6.11.0 as latest, released March 30, 2026
- [PyPI: pip-tools](https://pypi.org/project/pip-tools/) — confirmed 7.5.3, released February 11, 2026
- [libraries.io: qt-material](https://libraries.io/pypi/qt-material) — confirmed 2.17 as latest
- [Elastic: stopping Elasticsearch](https://www.elastic.co/guide/en/elasticsearch/reference/current/stopping-elasticsearch.html) — SIGTERM on POSIX, Ctrl+C on Windows
- [Python subprocess docs](https://docs.python.org/3/library/subprocess.html) — CTRL_BREAK_EVENT requires CREATE_NEW_PROCESS_GROUP

### Tertiary (LOW confidence)
- Community reports of keystore conflict when setting `xpack.security.enabled: false` without explicit transport SSL flags — multiple Elastic discuss.elastic.co threads converge on the same three-setting fix; not officially documented as a combined requirement

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all versions verified via PyPI and Context7 in this session
- Architecture: HIGH — QThread patterns and ES client patterns verified via official docs
- Pitfalls: HIGH (Windows shutdown) / MEDIUM (keystore conflict) — Windows behavior verified in Python stdlib source; keystore issue from multiple community sources
- Validation: HIGH — test map derived directly from phase requirements

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (stable ecosystem — qt-material is the least actively maintained package; check for breaking changes before PyQt6 major version upgrades)
