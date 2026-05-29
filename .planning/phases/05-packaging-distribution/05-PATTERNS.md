# Phase 5: Packaging & Distribution - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 8
**Analogs found:** 7 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `nitrofind/es_manager.py` | service | request-response | `nitrofind/es_manager.py` (self — additions) | exact |
| `main.py` | config/utility | request-response | `main.py` (self — additions) | exact |
| `nitrofind.spec` | config | batch | `scripts/setup_es.py` (build-time path logic) | partial |
| `scripts/build_dist.py` | utility | batch/file-I/O | `scripts/setup_es.py` | role-match |
| `tests/test_packaging/__init__.py` | config | — | `tests/__init__.py` | exact |
| `tests/test_packaging/test_path_resolution.py` | test | request-response | `tests/test_es_manager.py` | role-match |
| `tests/test_packaging/test_config_injection.py` | test | file-I/O | `tests/test_es_manager.py` + `tests/integration/test_es_startup.py` | role-match |
| `tests/test_packaging/test_subprocess_handles.py` | test | request-response | `tests/test_es_manager.py` | exact |

---

## Pattern Assignments

### `nitrofind/es_manager.py` — additions: `resolve_es_home()` + `inject_es_config()` + `_start_process()` fix

**Analog:** `nitrofind/es_manager.py` (existing file — additions inserted here)

**Imports pattern** (lines 21–28 — already in file, no new imports needed for resolve_es_home/inject_es_config):
```python
import os
import signal
import subprocess
import sys
import time
from pathlib import Path   # ADD THIS — used by resolve_es_home()
import shutil               # ADD THIS — used by inject_es_config()

from PyQt6.QtCore import QThread, pyqtSignal
from elasticsearch import Elasticsearch
```

**Existing module-level constant pattern** (line 35 — follow same style for placement):
```python
# ---------------------------------------------------------------------------
# Module-level constant — single source of truth for ES URL (WR-01)
# ---------------------------------------------------------------------------
ES_URL = "http://localhost:9200"
```
New functions `resolve_es_home()` and `inject_es_config()` go in the same section as `validate_es_home()` (after the constant, before ESHealthWorker). Preserve the `# ---` separator and docstring style.

**Existing validate_es_home docstring + signature pattern** (lines 53–72 — copy structure for new functions):
```python
def validate_es_home(es_home: str | None) -> str:
    """Validate that es_home is a real directory containing an ES binary.

    Raises ValueError with D-02 messages on failure.
    Returns es_home unchanged on success.

    Security: T-02-01 — prevents arbitrary binary execution via malicious ES_HOME.
    """
    if not es_home:
        raise ValueError(
            "ES_HOME is not set. Set it to your Elasticsearch 8.18 directory."
        )
    if not os.path.isdir(es_home):
        raise ValueError(f"ES_HOME is not a directory: {es_home}")

    es_bin = _es_binary_path(es_home)
    if not os.path.isfile(es_bin):
        raise ValueError(f"Elasticsearch binary not found at: {es_bin}")

    return es_home
```
`resolve_es_home()` is a pure function returning `str | None` — follow this return-type-annotated, clearly-documented style.

**Existing `_start_process()` pattern to replace** (lines 190–203 — the target of the DEVNULL fix):
```python
def _start_process(self) -> subprocess.Popen:
    """Start the ES JVM subprocess.

    Security — T-02-02: command is a list literal; shell=True is only used
    on Windows where it is required to execute .bat files (CR-01).
    Cross-platform — Pitfall 1: CREATE_NEW_PROCESS_GROUP on win32 required so
    shutdown_es() can send CTRL_BREAK_EVENT for graceful Windows shutdown.
    """
    es_bin = _es_binary_path(self._es_home)  # CR-01: platform-correct binary path
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        kwargs["shell"] = True  # CR-01: required to execute .bat files on Windows
    return subprocess.Popen([es_bin], **kwargs)
```
Replace with the DEVNULL + close_fds version. Keep all existing comments; ADD new ones referencing PKG-01 and the Pitfall 2 fix. The `kwargs: dict = {}` pattern and the win32-only `creationflags` block are the structural template.

---

### `main.py` — additions: `resolve_es_home()` call + `sys.stdout/stderr` guard

**Analog:** `main.py` (existing file — two targeted insertion points)

**Insertion point 1: replace `os.environ.get("ES_HOME")` line** (lines 56–61 — follow existing structure exactly):
```python
    # ------------------------------------------------------------------
    # Step 1: Validate ES_HOME BEFORE constructing any Qt object.
    # A ValueError here exits with a stderr message and non-zero status.
    # No QApplication is created, so no UI window can flash (T-04-01).
    # ------------------------------------------------------------------
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    es_home_raw = os.environ.get("ES_HOME")   # <-- REPLACE THIS LINE
    try:
        es_home = validate_es_home(es_home_raw)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)
```
Replace `es_home_raw = os.environ.get("ES_HOME")` with a call to `resolve_es_home()`. Import `resolve_es_home` in the existing `from nitrofind.es_manager import ...` line.

**Insertion point 2: `sys.stdout/stderr` guard** (before `logging.basicConfig`, at top of `main()` body):
```python
def main() -> None:
    # Guard against sys.stdout/stderr being None in windowed frozen mode (PKG-01).
    # PyInstaller console=False sets these to None; logging.basicConfig and
    # sys.stderr.write both crash if the stream is None.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    # ------------------------------------------------------------------
    # Step 1: Validate ES_HOME BEFORE constructing any Qt object.
    # ...
```
This guard comes before anything else in `main()` — including `logging.basicConfig` — so that the logging setup itself does not crash in windowed mode.

**`inject_es_config()` call insertion point** — between `resolve_es_home()` and `validate_es_home()`:
```python
    es_home_raw = resolve_es_home()

    # Inject NitroFind's config into the bundled ES directory before ES starts (PKG-01).
    # In frozen mode, config_src resolves to _internal/config/; in dev, to ./config/.
    if getattr(sys, 'frozen', False):
        config_src = os.path.join(sys._MEIPASS, "config")
    else:
        config_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

    if es_home_raw:
        inject_es_config(es_home_raw, config_src)

    try:
        es_home = validate_es_home(es_home_raw)
    ...
```
Import `inject_es_config` alongside `resolve_es_home` in the `from nitrofind.es_manager import ...` line.

---

### `nitrofind.spec` — NEW: PyInstaller spec file

**Analog:** `scripts/setup_es.py` (structural reference — path-relative logic, `os.path`/`pathlib` usage, single-file utility pattern)

**No direct spec analog exists in the codebase.** Use RESEARCH.md Pattern 3 as the primary template. The file lives at the project root, alongside `main.py`. Key conventions to follow from the codebase:

- Use `# Source:` comments attributing each decision (consistent with `es_manager.py`, `setup_es.py`, `main.py`)
- Use `# CR-01`, `# PKG-01` requirement tags in inline comments, matching the tagging style throughout the codebase
- `upx=False` in both EXE and COLLECT blocks — documented in RESEARCH.md Anti-Patterns
- `console=False` — GUI app, consistent with the PyQt6 UI architecture
- `icon=None` with a comment for future `.ico` substitution

**Spec structure** (from RESEARCH.md Pattern 3, lines 240–299):
```python
# nitrofind.spec
# Source: pyinstaller.org/en/stable/spec-files.html
# PKG-01: onedir mode — ES cannot be bundled inside a onefile self-extracting archive

from PyInstaller.utils.hooks import collect_all

qt_datas, qt_bins, qt_hidden = collect_all('qt_material')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_bins,
    datas=[
        ('config', 'config'),    # elasticsearch.yml + jvm.options -> _internal/config/
        *qt_datas,
    ],
    hiddenimports=['PyQt6.sip', *qt_hidden],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NitroFind',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,      # Anti-pattern: UPX corrupts Qt DLLs on Windows
    console=False,  # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,      # replace with 'nitrofind.ico' when available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NitroFind',
)
```

---

### `scripts/build_dist.py` — NEW: post-PyInstaller archive assembly

**Analog:** `scripts/setup_es.py` (role: utility script; data-flow: file-I/O; same `scripts/` location)

**Imports pattern** from `scripts/setup_es.py` (lines 1–18 — copy module-level docstring style):
```python
"""
scripts/build_dist.py — NitroFind distribution archive assembler.

Copies the pre-extracted Elasticsearch 8.18 directory alongside the
PyInstaller onedir output, then zips everything into the final distributable.

Usage:
    ES_BUNDLE=/path/to/elasticsearch-8.18.0 python scripts/build_dist.py

Requires:
    - PyInstaller onedir output at dist/NitroFind/ (run pyinstaller nitrofind.spec first)
    - ES_BUNDLE env var pointing to an extracted elasticsearch-8.18.0 directory

Security: no untrusted inputs; script is build-time only (dev machine / CI).
"""
import os
import shutil
import zipfile
from pathlib import Path
```

**Error handling pattern** from `scripts/setup_es.py` (lines 34–53 — validate inputs before acting, exit 1 on failure):
```python
    es_src = os.environ.get("ES_BUNDLE")
    if not es_src:
        print("ES_BUNDLE is not set. Set it to your elasticsearch-8.18.0 directory.")
        sys.exit(1)
    if not os.path.isdir(es_src):
        print(f"ES_BUNDLE is not a valid directory: {es_src}")
        sys.exit(1)
```

**File operation pattern** from `scripts/setup_es.py` (lines 59–82 — `shutil.copy`, `os.makedirs`, `os.path.join`):
```python
    # -- setup_es.py file copy pattern --
    es_config_dir = os.path.join(es_home, "config")
    jvm_options_dir = os.path.join(es_config_dir, "jvm.options.d")
    os.makedirs(jvm_options_dir, exist_ok=True)
    shutil.copy(src_jvm, dst_jvm)
    print(f"Copied jvm.options → {dst_jvm}")
```
For `build_dist.py`, replace `shutil.copy` with `shutil.copytree` for the ES directory, and add the `zipfile.ZipFile` loop from RESEARCH.md Pattern 5. Use `print()` for all output (not `logger`) — consistent with `setup_es.py`.

**`main()` wrapper pattern** from `scripts/setup_es.py` (lines 31–87):
```python
def main() -> None:
    # validate inputs
    # perform file operations
    # print progress

if __name__ == "__main__":
    main()
```

---

### `tests/test_packaging/__init__.py` — NEW: package marker

**Analog:** `tests/__init__.py` (lines 1–1 — single-line comment)

**Exact pattern to copy:**
```python
# pytest test packages
```
The existing `tests/__init__.py` contains only this comment. The `tests/test_scraper/__init__.py` is completely empty (0 bytes). Use the single-line comment form from `tests/__init__.py`.

---

### `tests/test_packaging/test_path_resolution.py` — NEW: unit tests for `resolve_es_home()`

**Analog:** `tests/test_es_manager.py` (lines 1–134 — exact role and mock pattern match)

**Module docstring pattern** (lines 1–13 of `tests/test_es_manager.py`):
```python
"""
Unit tests for nitrofind.es_manager — INFRA-02, INFRA-03, INFRA-04 coverage.

Test strategy:
  - Call worker.run() directly (synchronously) — never worker.start()
  - Patch subprocess.Popen and nitrofind.es_manager.Elasticsearch
  - No live ES or Qt event loop required

Requirement coverage:
  INFRA-02: ESHealthWorker starts ES subprocess; validate_es_home validates ES_HOME
  ...
"""
```
Adapt: reference `PKG-01`, describe `resolve_es_home()` frozen/dev test strategy, note that `sys.frozen` is patched via `monkeypatch`.

**Imports pattern** (lines 15–23 of `tests/test_es_manager.py`):
```python
import os
import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch, call

import pytest

from nitrofind.es_manager import ESHealthWorker, shutdown_es, validate_es_home
```
For `test_path_resolution.py`:
```python
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from nitrofind.es_manager import resolve_es_home
```

**Test function structure** (lines 30–43 of `tests/test_es_manager.py` — pytest function, `pytest.raises` pattern):
```python
def test_missing_es_home():
    """validate_es_home(None) and validate_es_home('') both raise ValueError..."""
    with pytest.raises(ValueError, match="ES_HOME is not set"):
        validate_es_home(None)
```
For frozen-mode tests, use `monkeypatch.setattr(sys, 'frozen', True)` and `monkeypatch.setattr(sys, 'executable', ...)` to simulate frozen state. Use `tmp_path` fixture for directory creation — consistent with `tests/test_scraper/test_state.py` (line 50).

**`monkeypatch` + `tmp_path` pattern** from `tests/test_scraper/test_state.py` (lines 50–63):
```python
def test_visited_persists_across_close_reopen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_file = str(tmp_path / "state.db")
    ...
```
For `test_path_resolution.py`, `tmp_path` creates the fake launcher directory; `monkeypatch.setattr` patches `sys.frozen` and `sys.executable`.

---

### `tests/test_packaging/test_config_injection.py` — NEW: unit tests for `inject_es_config()`

**Analog:** `tests/test_es_manager.py` (structure) + `tests/integration/test_es_startup.py` (file-system teardown pattern)

**Module docstring pattern** — same as other test files, referencing PKG-01 and describing `tmp_path`-based strategy:
```python
"""
Unit tests for nitrofind.es_manager.inject_es_config — PKG-01 coverage.

Test strategy:
  - Use tmp_path to create fake ES directory with config/ subdirectory
  - Create fake config source files (elasticsearch.yml, jvm.options)
  - Call inject_es_config() and assert files were written to expected destinations
  - No live ES or subprocess required

Requirement coverage:
  PKG-01: inject_es_config writes elasticsearch.yml to $ES_HOME/config/
  PKG-01: inject_es_config writes jvm.options to $ES_HOME/config/jvm.options.d/nitrofind.options
  PKG-01: inject_es_config creates jvm.options.d/ if it does not exist
  PKG-01: inject_es_config is idempotent (second call overwrites first)
"""
```

**`tmp_path` file-creation pattern** from `tests/test_scraper/test_state.py` (lines 50–63 — use `tmp_path` to build fixture paths):
```python
def test_inject_writes_elasticsearch_yml(tmp_path):
    es_home = tmp_path / "elasticsearch-8.18.0"
    (es_home / "config").mkdir(parents=True)
    config_src = tmp_path / "config_src"
    config_src.mkdir()
    (config_src / "elasticsearch.yml").write_text("network.host: 127.0.0.1\n")
    (config_src / "jvm.options").write_text("-Xms512m\n")

    from nitrofind.es_manager import inject_es_config
    inject_es_config(str(es_home), str(config_src))

    dst = es_home / "config" / "elasticsearch.yml"
    assert dst.exists()
    assert "127.0.0.1" in dst.read_text()
```

**Teardown pattern** — `tmp_path` is automatic in pytest; no explicit teardown needed (consistent with all existing tests that use `tmp_path`).

---

### `tests/test_packaging/test_subprocess_handles.py` — NEW: unit tests for DEVNULL `_start_process()`

**Analog:** `tests/test_es_manager.py` (lines 86–134 — exact match: patches `subprocess.Popen`, asserts kwargs)

**Core mock pattern** (lines 87–109 of `tests/test_es_manager.py`):
```python
def test_worker_emits_ready():
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # process alive

    mock_client = MagicMock()
    mock_client.cluster.health.return_value = {"status": "yellow"}

    with patch("nitrofind.es_manager.subprocess.Popen", return_value=mock_process), \
         patch("nitrofind.es_manager.Elasticsearch", return_value=mock_client):

        worker = ESHealthWorker("/fake/es_home")
        ...
        worker.run()
```
For `test_subprocess_handles.py`, patch `subprocess.Popen` and assert it was called with `stdin=subprocess.DEVNULL`, `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL`, and `close_fds=True`. Call `worker._start_process()` directly (not `worker.run()`) to isolate the subprocess kwargs test.

**Platform branch pattern** (lines 57–63 of `tests/test_es_manager.py`):
```python
    if sys.platform == "win32":
        mock_process.send_signal.assert_called_once_with(signal.CTRL_BREAK_EVENT)
        mock_process.terminate.assert_not_called()
    else:
        mock_process.terminate.assert_called_once()
        mock_process.send_signal.assert_not_called()
```
For the subprocess test, assert both branches: on win32, assert `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` and `shell=True` are present; on non-win32, assert they are absent. Use the same `if sys.platform == "win32":` conditional inside the test — consistent with existing pattern.

**`patch` + direct method call pattern** — instead of `worker.run()`, test `_start_process()` directly:
```python
def test_start_process_passes_devnull_to_popen(monkeypatch, tmp_path):
    """PKG-01 Pitfall 2: _start_process passes DEVNULL for all std handles."""
    # Create a fake ES binary to pass _es_binary_path lookup
    ...
    with patch("nitrofind.es_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        worker = ESHealthWorker(str(es_home))
        worker._start_process()

    call_kwargs = mock_popen.call_args[1]
    assert call_kwargs.get("stdin") == subprocess.DEVNULL
    assert call_kwargs.get("stdout") == subprocess.DEVNULL
    assert call_kwargs.get("stderr") == subprocess.DEVNULL
    assert call_kwargs.get("close_fds") is True
```

---

## Shared Patterns

### Module-level docstring format
**Source:** `nitrofind/es_manager.py` lines 1–19, `main.py` lines 1–21
**Apply to:** All new Python files (`scripts/build_dist.py`, test files)
```python
"""
<module>.<submodule> — <one-line description>.

<paragraph describing what this module exports or does>

Requirement coverage:
  PKG-01: <what this file covers>

Security mitigations (if applicable):
  T-xx-xx: <mitigation description>
"""
```

### Requirement tag inline comments
**Source:** Throughout `nitrofind/es_manager.py` (e.g., `# CR-01`, `# T-02-02`, `# WR-03`)
**Apply to:** All modified and new source files
```python
kwargs["stdin"] = subprocess.DEVNULL   # PKG-01: prevent WinError 6 in windowed frozen mode
kwargs["close_fds"] = True             # PKG-01 Pitfall 7: prevent handle lock on binary update
```

### `# Source:` attribution comments
**Source:** `nitrofind/es_manager.py` line 95, `config/elasticsearch.yml` line 1, `main.py` line 14
**Apply to:** `nitrofind.spec` (every non-obvious decision), `main.py` frozen-mode additions
```python
# Source: pyinstaller.org/en/stable/runtime-information.html
if getattr(sys, 'frozen', False):
    ...
```

### `tmp_path` + `monkeypatch` pytest fixtures
**Source:** `tests/test_scraper/test_state.py` lines 50–63
**Apply to:** All three new test files — for creating temp directories and patching `sys` attributes
```python
def test_something(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / "NitroFind.exe"))
    ...
```

### `with patch(...):` context manager for subprocess isolation
**Source:** `tests/test_es_manager.py` lines 99–106
**Apply to:** `test_subprocess_handles.py` and `test_path_resolution.py`
```python
with patch("nitrofind.es_manager.subprocess.Popen", return_value=mock_process), \
     patch("nitrofind.es_manager.Elasticsearch", return_value=mock_client):
    worker = ESHealthWorker("/fake/es_home")
    worker.run()
```

### `# ---------------------------------------------------------------------------` section separators
**Source:** `nitrofind/es_manager.py` lines 31, 40, 75, 109 — used to delimit every logical section
**Apply to:** All new functions added to `nitrofind/es_manager.py`
```python
# ---------------------------------------------------------------------------
# Frozen-mode path resolution (PKG-01)
# ---------------------------------------------------------------------------

def resolve_es_home() -> str | None:
    ...
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `nitrofind.spec` | config | batch | PyInstaller spec files have no Python equivalent in this codebase; no existing `.spec`, `setup.py`, or `pyproject.toml`; use RESEARCH.md Pattern 3 as primary reference |

---

## Metadata

**Analog search scope:** `nitrofind/`, `main.py`, `scripts/`, `tests/`, `config/`, `pytest.ini`
**Files scanned:** 12 source files read in full
**Pattern extraction date:** 2026-05-29
