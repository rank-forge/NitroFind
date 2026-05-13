# Phase 1: Infrastructure & Schema Foundation - Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 11 (new files — greenfield project)
**Analogs found:** 0 / 11 (no existing source files; all patterns sourced from RESEARCH.md official-doc excerpts)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `main.py` | entrypoint | event-driven | none | no analog |
| `nitrofind/__init__.py` | package marker | — | none | no analog |
| `nitrofind/es_manager.py` | worker/service | event-driven | none | no analog |
| `nitrofind/es_schema.py` | service/config | request-response | none | no analog |
| `nitrofind/ui/__init__.py` | package marker | — | none | no analog |
| `nitrofind/ui/loading_window.py` | component | event-driven | none | no analog |
| `nitrofind/ui/main_window.py` | component | request-response | none | no analog |
| `config/elasticsearch.yml` | config | — | none | no analog |
| `config/jvm.options` | config | — | none | no analog |
| `requirements.in` | config | — | none | no analog |
| `requirements.txt` | config | — | none | no analog |
| `tests/test_es_schema.py` | test | request-response | none | no analog |
| `tests/test_es_manager.py` | test | event-driven | none | no analog |
| `tests/test_lockfile.py` | test | — | none | no analog |
| `tests/integration/test_es_startup.py` | test | request-response | none | no analog |
| `scripts/setup_es.py` | utility | file-I/O | none | no analog |
| `pytest.ini` | config | — | none | no analog |

**Note:** The project is greenfield — `CLAUDE.md` is the only file in the repository. Every pattern below is sourced from the code examples in RESEARCH.md, which were in turn derived from official PyQt6 (Riverbank), Elasticsearch Python client, and pip-tools documentation. These are the canonical patterns; the planner must copy them directly.

---

## Pattern Assignments

### `main.py` (entrypoint, event-driven)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Pattern 3 (ES lifecycle wiring), Pattern 6 (qt-material), Pattern 1 (QThread)

**Imports pattern:**
```python
import sys
import os
from PyQt6.QtWidgets import QApplication
from qt_material import apply_stylesheet
from nitrofind.es_manager import ESHealthWorker
from nitrofind.ui.loading_window import LoadingWindow
from nitrofind.ui.main_window import StubMainWindow
```

**ES_HOME validation pattern** (D-01, D-02 — exit on missing env var):
```python
es_home = os.environ.get("ES_HOME")
if not es_home:
    print("ES_HOME is not set. Set it to your Elasticsearch 8.18 directory.")
    sys.exit(1)
es_bin = os.path.join(es_home, "bin", "elasticsearch")
if not os.path.isfile(es_bin):
    print(f"Elasticsearch binary not found at: {es_bin}")
    sys.exit(1)
```

**Qt-material theme pattern** (Pattern 6 — MUST be called before any window is created):
```python
app = QApplication(sys.argv)
apply_stylesheet(app, theme="dark_teal.xml")
```

**Signal wiring pattern** (Pitfall 4 — connect signals BEFORE thread.start()):
```python
loading_window = LoadingWindow()
worker = ESHealthWorker(es_home)

# Connect before start() to avoid race condition
worker.es_ready.connect(on_es_ready)
worker.es_failed.connect(loading_window.show_error)

app.aboutToQuit.connect(lambda: worker.shutdown_es())
loading_window.show()
worker.start()

sys.exit(app.exec())
```

---

### `nitrofind/es_manager.py` (worker/service, event-driven)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Pattern 1 (QThread worker), Pattern 2 (cross-platform Popen), Pattern 4 (health polling)

**Imports pattern:**
```python
import subprocess
import signal
import sys
import os
import time
from PyQt6.QtCore import QThread, pyqtSignal
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError
```

**QThread subclass with signals pattern** (Pattern 1):
```python
class ESHealthWorker(QThread):
    es_ready = pyqtSignal()
    es_failed = pyqtSignal(str)  # reason string

    def __init__(self, es_home: str):
        super().__init__()
        self._es_home = es_home
        self.process: subprocess.Popen | None = None
```

**Cross-platform subprocess startup pattern** (Pattern 2, security validation):
```python
def _start_process(self) -> subprocess.Popen:
    es_bin = os.path.join(self._es_home, "bin", "elasticsearch")
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([es_bin], **kwargs)
```

**Health polling run() pattern** (Pattern 4, D-04 — 2s interval, 60s timeout, green/yellow):
```python
def run(self):
    self.process = self._start_process()
    client = Elasticsearch("http://localhost:9200", request_timeout=2)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        # Check if process died
        if self.process.poll() is not None:
            self.es_failed.emit("Elasticsearch process exited unexpectedly.")
            return
        try:
            resp = client.cluster.health()
            if resp["status"] in ("green", "yellow"):
                self.es_ready.emit()
                return
        except Exception:
            pass  # ES not yet accepting connections
        time.sleep(2)
    self.es_failed.emit("Elasticsearch did not become healthy within 60 seconds.")
```

**Cross-platform graceful shutdown pattern** (Pattern 2, D-05, Pitfall 1):
```python
def shutdown_es(self) -> None:
    if self.process is None or self.process.poll() is not None:
        return  # already exited
    if sys.platform == "win32":
        self.process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        self.process.terminate()
    try:
        self.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        self.process.kill()
        self.process.wait()
```

---

### `nitrofind/es_schema.py` (service/config, request-response)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Pattern 3 (idempotent index creation), SCHEMA-01..04 field list

**Imports pattern:**
```python
from elasticsearch import Elasticsearch
```

**Full mapping definition pattern** (Pattern 3, SCHEMA-01..04, D-08/D-09, L-02):
```python
CAR_ARTICLES_MAPPING = {
    "dynamic": "false",          # Pitfall 6: string not boolean
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
        # SCHEMA-03: full text + display excerpt
        "body":          {"type": "text", "analyzer": "standard"},
        "excerpt":       {"type": "keyword"},   # Pitfall 5: keyword not text
        # SCHEMA-04: automotive facets
        "manufacturer":       {"type": "keyword"},
        "production_start":   {"type": "integer"},
        "production_end":     {"type": "integer"},
        "body_style":         {"type": "keyword"},
        "era_bucket":         {"type": "keyword"},   # D-09
        "country_of_origin":  {"type": "keyword"},
        # L-02: flattened prevents mapping explosion from varied infobox shapes
        "specs":              {"type": "flattened"},
    }
}
```

**Idempotent index creation pattern** (Pattern 3 — ignore_status=[400] skips "already exists"):
```python
def ensure_index(client: Elasticsearch) -> None:
    client.options(ignore_status=[400]).indices.create(
        index="car_articles",
        mappings=CAR_ARTICLES_MAPPING,
        settings={"number_of_shards": 1, "number_of_replicas": 0},
    )
```

---

### `nitrofind/ui/loading_window.py` (component, event-driven)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Pattern 5 (SpinnerWidget), D-06, D-07

**Imports pattern:**
```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QPen, QColor
```

**SpinnerWidget pattern** (Pattern 5 — 48×48, 4px pen, #26a69a, 120° arc, 30°/100ms):
```python
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

**LoadingWindow layout pattern** (D-06 — branding, spinner, status text; D-07 — error state):
```python
class LoadingWindow(QWidget):
    """
    Dedicated loading window — NOT QSplashScreen (D-06).
    Shows spinner + status text; transitions to error state on failure (D-07).
    """
    def __init__(self):
        super().__init__()
        # ... frameless, fixed 360×240, centered layout
        # error state: hide spinner, show error label + Retry/Quit buttons

    def show_error(self, reason: str) -> None:
        """Switch to error state: replace spinner with message + two buttons."""
        self._spinner.hide()
        self._status_label.setText(reason)
        # show retry_button and quit_button
```

**Error state buttons pattern** (D-07 — Retry terminates and restarts; Quit calls QApplication.quit()):
```python
retry_button = QPushButton("Retry")
quit_button = QPushButton("Quit")
quit_button.clicked.connect(QApplication.quit)
# retry_button.clicked connected to a handler in main.py that terminates stale
# process and calls worker.start() again
```

---

### `nitrofind/ui/main_window.py` (component, request-response)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Architecture Patterns (stub placeholder for Phase 4)

**Pattern:**
```python
from PyQt6.QtWidgets import QMainWindow, QLabel
from PyQt6.QtCore import Qt

class StubMainWindow(QMainWindow):
    """Placeholder main window. Phase 4 replaces this with full search UI."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NitroFind — Ready")
        self.setMinimumSize(800, 600)
        label = QLabel("Search engine ready.", self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)
```

---

### `config/elasticsearch.yml` (config)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Pattern 7, L-01, Pitfall 2, Pitfall 3

**Complete file pattern:**
```yaml
# Pitfall 2: discovery.type: single-node required or ES hangs on quorum wait
# Pitfall 3: all three xpack ssl settings required to avoid keystore conflict
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node
xpack.security.enabled: false
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
```

---

### `config/jvm.options` (config)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Pattern 7, L-01

**Complete file pattern:**
```
# Place in: $ES_HOME/config/jvm.options.d/nitrofind.options
-Xms512m
-Xmx512m
```

---

### `requirements.in` (config)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Code Examples section

**Complete file pattern:**
```
# Source: CLAUDE.md stack; versions verified via pypi.org 2026-05-12
elasticsearch==8.*
PyQt6==6.11.0
qt-material==2.17
requests>=2.32,<3
```

**Note:** `pip-tools`, `pytest`, and `pytest-qt` are dev-only tools — do NOT add to `requirements.in`. Install them with `pip install pip-tools pytest pytest-qt` outside the lockfile.

---

### `scripts/setup_es.py` (utility, file-I/O)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Open Question 2 (setup guide recommendation)

**Core pattern:**
```python
import os
import shutil
import sys

def main():
    es_home = os.environ.get("ES_HOME")
    if not es_home:
        print("ES_HOME is not set.")
        sys.exit(1)
    config_src = os.path.join(os.path.dirname(__file__), "..", "config")
    es_config_dir = os.path.join(es_home, "config")
    shutil.copy(
        os.path.join(config_src, "elasticsearch.yml"),
        os.path.join(es_config_dir, "elasticsearch.yml"),
    )
    jvm_options_dir = os.path.join(es_config_dir, "jvm.options.d")
    os.makedirs(jvm_options_dir, exist_ok=True)
    shutil.copy(
        os.path.join(config_src, "jvm.options"),
        os.path.join(jvm_options_dir, "nitrofind.options"),
    )
    print("ES configuration installed.")

if __name__ == "__main__":
    main()
```

---

### `pytest.ini` (config)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Validation Architecture

**Complete file pattern:**
```ini
[pytest]
markers =
    integration: requires a live Elasticsearch instance (deselect with '-m "not integration"')
```

---

### Test files

#### `tests/test_es_schema.py` (test, request-response)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Validation Architecture — SCHEMA-01..04 test map

**Pattern:**
```python
from unittest.mock import MagicMock, call
from nitrofind.es_schema import ensure_index, CAR_ARTICLES_MAPPING

def test_mapping_has_required_fields():
    props = CAR_ARTICLES_MAPPING["properties"]
    # SCHEMA-01
    for field in ("title", "url", "source_domain", "article_id", "scraped_at"):
        assert field in props
    # SCHEMA-02
    for field in ("published_at", "word_count", "has_infobox", "image_count"):
        assert field in props
    # SCHEMA-03
    assert props["body"]["type"] == "text"
    assert props["excerpt"]["type"] == "keyword"
    # SCHEMA-04
    for field in ("manufacturer", "production_start", "production_end",
                  "body_style", "era_bucket", "country_of_origin"):
        assert field in props
    assert props["specs"]["type"] == "flattened"

def test_dynamic_is_string_false():
    # Pitfall 6: must be the string "false", not boolean
    assert CAR_ARTICLES_MAPPING["dynamic"] == "false"

def test_ensure_index_idempotent():
    mock_client = MagicMock()
    ensure_index(mock_client)
    ensure_index(mock_client)
    # options(ignore_status=[400]) called both times — no exception raised
    assert mock_client.options.call_count == 2
```

#### `tests/test_es_manager.py` (test, event-driven)

**Analog:** none — greenfield
**Source doc:** RESEARCH.md Validation Architecture — INFRA-02, INFRA-03, INFRA-04 test map

**Pattern:**
```python
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch, PropertyMock
import pytest
from nitrofind.es_manager import ESHealthWorker, shutdown_es

def test_missing_es_home(monkeypatch):
    monkeypatch.delenv("ES_HOME", raising=False)
    # main.py exits with message when ES_HOME not set
    # (test via subprocess or by testing the validation function directly)

def test_shutdown_graceful():
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # process alive
    shutdown_es(mock_process)
    if sys.platform == "win32":
        mock_process.send_signal.assert_called_once()
    else:
        mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called_once_with(timeout=10)

def test_shutdown_kills_on_timeout():
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="es", timeout=10)
    shutdown_es(mock_process)
    mock_process.kill.assert_called_once()
```

---

## Shared Patterns

### QThread Signal Connection Order
**Source:** RESEARCH.md Pitfall 4
**Apply to:** `main.py`

Always connect signals BEFORE calling `thread.start()`. Connecting after start() risks a race condition where the signal fires before the slot is registered.

```python
# CORRECT — connect first, start second
worker.es_ready.connect(on_es_ready)
worker.es_failed.connect(loading_window.show_error)
worker.start()
```

### ES_HOME Path Validation
**Source:** RESEARCH.md Security Domain (path traversal threat)
**Apply to:** `main.py`, `scripts/setup_es.py`

Validate that `ES_HOME` is a real directory and that the binary exists before passing to `subprocess.Popen`. Prevents arbitrary binary execution via a maliciously set env var.

```python
es_home = os.environ.get("ES_HOME")
if not es_home:
    print("ES_HOME is not set. Set it to your Elasticsearch 8.18 directory.")
    sys.exit(1)
es_bin = os.path.join(es_home, "bin", "elasticsearch")
if not os.path.isfile(es_bin):
    print(f"Elasticsearch binary not found at: {es_bin}")
    sys.exit(1)
```

### qt-material Application Order
**Source:** RESEARCH.md Pattern 6
**Apply to:** `main.py`

`apply_stylesheet()` must be called immediately after `QApplication(sys.argv)` and before any window is created. Calling it after a window is created leaves some widgets unstyled.

```python
app = QApplication(sys.argv)
apply_stylesheet(app, theme="dark_teal.xml")
# Only now create LoadingWindow, StubMainWindow, etc.
```

### Elasticsearch Client Connection
**Source:** RESEARCH.md Code Examples
**Apply to:** `nitrofind/es_manager.py`, `nitrofind/es_schema.py`, any future service using ES

No auth, no TLS — security is disabled by design (L-01).

```python
from elasticsearch import Elasticsearch
client = Elasticsearch("http://localhost:9200")
```

### Era Bucket Calculation
**Source:** RESEARCH.md D-08, D-10
**Apply to:** Phase 2 scraper (not Phase 1, but document here for downstream)

```python
def era_bucket(production_start: int | None) -> str:
    if production_start is None:
        return "Unknown"
    return f"{(production_start // 10) * 10}s"
```

---

## No Analog Found

All files have no codebase analog — this is a fully greenfield project.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `main.py` | entrypoint | event-driven | First file in the project |
| `nitrofind/es_manager.py` | worker | event-driven | No QThread workers exist yet |
| `nitrofind/es_schema.py` | service | request-response | No ES client code exists yet |
| `nitrofind/ui/loading_window.py` | component | event-driven | No PyQt6 UI code exists yet |
| `nitrofind/ui/main_window.py` | component | request-response | No PyQt6 UI code exists yet |
| `config/elasticsearch.yml` | config | — | No config files exist yet |
| `config/jvm.options` | config | — | No config files exist yet |
| `requirements.in` | config | — | No dependency files exist yet |
| `scripts/setup_es.py` | utility | file-I/O | No scripts exist yet |
| All test files | test | various | No tests exist yet |

**Planner action:** Use the RESEARCH.md patterns above verbatim. They are sourced from official documentation (Riverbank PyQt6 docs, Elasticsearch Python client docs, pip-tools docs) and were verified against live PyPI versions on 2026-05-12.

---

## Metadata

**Analog search scope:** entire repository (`/mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind/`)
**Files scanned:** 1 (`CLAUDE.md` only — all other patterns are from RESEARCH.md)
**Greenfield confirmation:** `find` found no `.py` files in the project tree
**Pattern extraction date:** 2026-05-13
**Pattern sources:** RESEARCH.md Patterns 1–7, official docs (Riverbank, Elastic, pip-tools)
