# Phase 5: Packaging & Distribution - Research

**Researched:** 2026-05-29
**Domain:** PyInstaller 6 frozen app packaging, ES 8.18 directory bundling, Windows distribution
**Confidence:** HIGH (PyInstaller mechanics), MEDIUM (archive size estimates), HIGH (ES config injection)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PKG-01 | App can be distributed as a PyInstaller bundle alongside a pre-extracted Elasticsearch directory (no Python or Java install required by the end user) | Covered by: PyInstaller onedir spec, ES directory layout, path resolution pattern, config injection, subprocess pitfalls |
</phase_requirements>

---

## Summary

Phase 5 packages the NitroFind PyQt6 desktop app into a frozen, self-contained Windows distribution. The core challenge is two-part: first, producing a PyInstaller onedir bundle that includes all PyQt6/qt-material/elasticsearch-py assets without manual DLL hunting; second, bundling the pre-extracted Elasticsearch 8.18 directory alongside the Python bundle in a single top-level archive so the end user never runs an installer or downloads ES separately.

The existing `es_manager.py` already handles ES subprocess lifecycle correctly for development (env-var-driven `ES_HOME`). For the frozen distribution, `ES_HOME` must be computed at runtime from the executable's own directory — eliminating the env-var requirement entirely. Additionally, `setup_es.py` (which currently copies configs from the repo's `config/` tree) must be replaced by a runtime config-injection function that writes `elasticsearch.yml` and `jvm.options.d/nitrofind.options` directly into the bundled ES directory on first launch, before the ES process starts.

The biggest physical constraint is archive size. The Elasticsearch 8.18 Windows zip alone is 468 MB (compressed). The PyInstaller onedir bundle for a PyQt6 + qt-material app is approximately 80–250 MB depending on which Qt modules are pulled in. The combined distribution archive will likely be in the 600–800 MB range — well within a zip-distributable format, but too large for a GitHub release binary. This should be distributed as a direct-download zip from a storage host, not a GitHub Artifact.

**Primary recommendation:** Use PyInstaller onedir mode with a hand-written `.spec` file. Ship as a flat zip: the zip extracts to a single top-level folder containing the PyInstaller `_internal/` tree, the NitroFind.exe launcher, and a sibling `elasticsearch-8.18.0/` directory. Config injection happens once at startup. No NSIS installer required for v1.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Python app + all deps frozen | PyInstaller bundle | — | PyInstaller collects all .py, Qt DLLs, site-packages |
| ES process lifecycle | Launcher (NitroFind.exe) | — | main.py already owns start/stop/health-check |
| ES configuration injection | Launcher startup code | — | Must write config BEFORE es subprocess spawns |
| ES binary + JDK | Bundled ES directory | — | ES 8.x ships its own bundled OpenJDK; no system Java needed |
| Archive assembly | Build script | — | Post-PyInstaller step: copy ES dir + zip the whole tree |
| Path resolution (ES_HOME) | Runtime path detection | — | sys.executable parent, not env var, in frozen context |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyInstaller | 6.20.0 (current 6.x) | Freeze Python app to standalone exe | Project-fixed per CLAUDE.md; 9.8M downloads/month; native PyQt6 hooks built-in [VERIFIED: PyPI registry] |
| PyQt6 | 6.11.0 (already installed) | Qt runtime already bundled by PyInstaller | Auto-collected by PyInstaller hook-PyQt6.* hooks [VERIFIED: PyPI registry] |
| qt-material | 2.17 (already installed) | Theme — data files must be explicitly collected | No built-in PyInstaller hook; requires manual collect_data_files [VERIFIED: PyPI registry] |

### Supporting (build-time only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyInstaller | 6.20.0 | Build tool | Dev/CI only; not shipped to end user |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyInstaller onedir | PyInstaller onefile | onefile extracts to temp dir on every launch — 1–3 second startup delay for a 250 MB bundle; ES cold start already takes 120s so perception matters at the Python launch step; onedir starts in milliseconds [ASSUMED] |
| Zip archive | NSIS installer | NSIS = desktop shortcut, Add/Remove Programs entry, proper uninstall. Required for v2 (UI-V2-01). For v1, zip is simpler, no script toolchain, cross-compilable from WSL. [ASSUMED] |
| Hand-written .spec | pyinstaller CLI flags | .spec file is version-controlled, reproducible, and the only way to include collect_data_files calls for qt-material [CITED: pyinstaller.org/en/stable/spec-files.html] |

**Installation (dev environment only):**
```bash
pip install pyinstaller==6.*
```

**Version verification:**
```
pip index versions pyinstaller
# Current: 6.20.0 (confirmed 2026-05-29)
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| pyinstaller | PyPI | 13+ yrs | ~9.8M/week | github.com/pyinstaller/pyinstaller | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

**Note:** No new end-user packages are introduced in Phase 5. `pyinstaller` is a build-time-only tool — it is not shipped inside the frozen bundle. The packages already in `requirements.txt` (PyQt6, elasticsearch, qt-material, etc.) were vetted in prior phases.

---

## Architecture Patterns

### System Architecture Diagram

```
Distribution archive (NitroFind-v1.0-windows-x86_64.zip)
  └── NitroFind/                         <- extracted top-level folder
        ├── NitroFind.exe                <- PyInstaller onedir launcher
        ├── _internal/                   <- all Python + Qt DLLs
        │     ├── base_library.zip
        │     ├── PyQt6/                 <- Qt platform plugins, DLLs
        │     ├── qt_material/           <- theme XML + font files
        │     ├── elasticsearch/         <- ES Python client
        │     └── nitrofind/             <- app package tree
        └── elasticsearch-8.18.0/        <- pre-extracted ES directory
              ├── bin/
              │     └── elasticsearch.bat
              ├── config/                <- NitroFind writes here on first run
              │     ├── elasticsearch.yml
              │     └── jvm.options.d/
              │           └── nitrofind.options
              ├── jdk/                   <- bundled OpenJDK (no system Java needed)
              ├── lib/
              └── ...

Runtime flow:
  User double-clicks NitroFind.exe
      └── [frozen] main.py runs
              └── resolve_es_home()  <- compute ES dir from sys.executable parent
              └── inject_es_config() <- write elasticsearch.yml + jvm.options.d/nitrofind.options
              └── validate_es_home() <- existing check: dir + binary exist
              └── ESHealthWorker.start() <- spawns elasticsearch.bat subprocess
              └── QApplication loop
```

### Recommended Project Structure

```
NitroFind/                      (project root)
├── main.py                     (entry point — needs frozen-mode path logic)
├── nitrofind/
│   ├── es_manager.py           (needs resolve_es_home() + inject_es_config() additions)
│   └── ...
├── config/
│   ├── elasticsearch.yml       (bundled as datas in .spec — source of truth)
│   └── jvm.options             (bundled as datas in .spec — source of truth)
├── scripts/
│   ├── setup_es.py             (existing — used in dev only, not for frozen dist)
│   └── build_dist.py           (NEW — post-PyInstaller assembly + zip script)
├── nitrofind.spec              (NEW — PyInstaller spec file, hand-written)
└── dist/
    └── NitroFind/              (PyInstaller onedir output, before assembly)
```

### Pattern 1: Frozen-Mode ES_HOME Resolution

**What:** In the frozen distribution, ES is a sibling directory of the launcher. The app must compute its own path from `sys.executable` instead of reading `ES_HOME` from the environment.

**When to use:** Always, in `es_manager.py` or `main.py`, before calling `validate_es_home()`.

```python
# Source: pyinstaller.org/en/stable/runtime-information.html
import sys
import os
from pathlib import Path

def resolve_es_home() -> str | None:
    """
    In frozen (PyInstaller) mode, ES lives as a sibling directory of the exe:
      NitroFind.exe
      elasticsearch-8.18.0/

    Falls back to ES_HOME env var for dev mode (non-frozen).
    """
    if getattr(sys, 'frozen', False):
        # sys.executable = .../NitroFind/NitroFind.exe
        launcher_dir = Path(sys.executable).parent
        # Glob for any elasticsearch-8.* directory alongside the launcher
        candidates = sorted(launcher_dir.glob("elasticsearch-8.*"))
        if candidates:
            return str(candidates[0])
        return None  # missing from archive — will fail validate_es_home()
    # Dev mode: respect ES_HOME env var as before
    return os.environ.get("ES_HOME")
```

**Integration point:** `main.py` calls `resolve_es_home()` instead of `os.environ.get("ES_HOME")`, then passes result to `validate_es_home()` unchanged.

### Pattern 2: Config Injection at First Launch

**What:** Write `elasticsearch.yml` and `jvm.options.d/nitrofind.options` into the bundled ES `config/` directory before starting the ES subprocess. This replaces the developer-run `scripts/setup_es.py` for the frozen distribution.

**When to use:** In `main.py` (or `es_manager.py`) after `resolve_es_home()` resolves a valid path but before `ESHealthWorker.start()`.

```python
# Source: elastic.co/guide/en/elasticsearch/reference/8.19/advanced-configuration.html
import shutil
import os
from pathlib import Path

def inject_es_config(es_home: str, config_src_dir: str) -> None:
    """
    Copy NitroFind's elasticsearch.yml and jvm.options into the bundled ES config dir.

    es_home:        path to elasticsearch-8.18.0/ directory
    config_src_dir: directory containing our elasticsearch.yml and jvm.options
                    (in frozen mode: sys._MEIPASS / 'config'  or  __file__-relative)

    Idempotent: overwrites on every launch to ensure correct settings even if
    the user tampers with the bundled config files.
    """
    es_config = os.path.join(es_home, "config")

    # Write elasticsearch.yml
    shutil.copy(
        os.path.join(config_src_dir, "elasticsearch.yml"),
        os.path.join(es_config, "elasticsearch.yml"),
    )

    # Write jvm.options.d/nitrofind.options
    jvm_dir = os.path.join(es_config, "jvm.options.d")
    os.makedirs(jvm_dir, exist_ok=True)
    shutil.copy(
        os.path.join(config_src_dir, "jvm.options"),
        os.path.join(jvm_dir, "nitrofind.options"),
    )
```

**Config source path in frozen mode:**
```python
# Source: pyinstaller.org/en/stable/runtime-information.html
if getattr(sys, 'frozen', False):
    # config/ was added to datas in .spec as ('config', 'config')
    # In onedir mode, __file__ of main module is inside _internal/
    # Use sys._MEIPASS which always points to _internal/
    config_src = os.path.join(sys._MEIPASS, "config")
else:
    config_src = os.path.join(os.path.dirname(__file__), "config")
```

### Pattern 3: PyInstaller .spec File for NitroFind

**What:** A hand-written spec file that collects qt-material data files, bundles the `config/` directory, and uses onedir mode.

```python
# nitrofind.spec
# Source: pyinstaller.org/en/stable/spec-files.html
#         pyinstaller.org/en/stable/hooks.html (collect_data_files)

from PyInstaller.utils.hooks import collect_data_files, collect_all

# Collect qt-material theme XML + font files (no built-in hook)
# [ASSUMED - based on known qt-material issue #10 pattern; verify during build]
qt_material_datas, qt_material_binaries, qt_material_hiddenimports = collect_all('qt_material')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_material_binaries,
    datas=[
        ('config', 'config'),          # elasticsearch.yml + jvm.options -> _internal/config/
        *qt_material_datas,            # theme XMLs + fonts -> _internal/qt_material/...
    ],
    hiddenimports=[
        'PyQt6.sip',                   # most common PyQt6 hidden import
        *qt_material_hiddenimports,
    ],
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
    upx=False,           # UPX can corrupt Qt DLLs; leave off for safety
    console=False,       # no console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # add .ico path here when available
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

**Build command:**
```bash
pyinstaller nitrofind.spec
# Output: dist/NitroFind/  (the _internal/ tree + NitroFind.exe)
```

### Pattern 4: Subprocess in Windowed (No-Console) Mode

**What:** When `console=False` in the EXE spec, `sys.stdout` and `sys.stderr` are `None`. Any subprocess spawned that inherits file handles raises `[Error 6] The handle is invalid` on Windows.

**Fix — redirect ES subprocess output explicitly:**
```python
# Source: github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess
# Apply in ESHealthWorker._start_process()

import subprocess, sys

def _start_process(self) -> subprocess.Popen:
    es_bin = _es_binary_path(self._es_home)
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,   # ES logs go to its own logs/ dir anyway
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        kwargs["shell"] = True
    return subprocess.Popen([es_bin], **kwargs)
```

**Also add at `main.py` startup (before QApplication):**
```python
# Guard against sys.stdout/stderr being None in windowed frozen mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
```

### Pattern 5: Post-Build Archive Assembly

**What:** A Python script that copies the Elasticsearch directory alongside the PyInstaller output and zips everything into the distributable archive.

```python
# scripts/build_dist.py
import shutil, zipfile, os
from pathlib import Path

DIST_DIR    = Path("dist/NitroFind")          # PyInstaller onedir output
ES_SRC_DIR  = Path(os.environ["ES_BUNDLE"])   # path to elasticsearch-8.18.0/ to bundle
OUT_ZIP     = Path("dist/NitroFind-v1.0-windows-x86_64.zip")

# 1. Copy ES directory alongside PyInstaller output
es_dest = DIST_DIR / ES_SRC_DIR.name
if es_dest.exists():
    shutil.rmtree(es_dest)
shutil.copytree(ES_SRC_DIR, es_dest)

# 2. Zip the whole NitroFind/ folder
with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for f in DIST_DIR.rglob("*"):
        zf.write(f, Path("NitroFind") / f.relative_to(DIST_DIR))

print(f"Created: {OUT_ZIP}  ({OUT_ZIP.stat().st_size / 1024**2:.0f} MB)")
```

### Anti-Patterns to Avoid

- **Do not use `--onefile` mode:** ES cannot be bundled inside the PyInstaller self-extracting archive alongside Python — it requires a stable file-system path for its own JVM startup. onefile also adds multi-second cold-start overhead per Python launch. [CITED: pyinstaller.org/en/stable/operating-mode.html]
- **Do not set `console=True` without redirecting subprocess handles:** Causes `[Error 6] handle is invalid` when Popen inherits `None` stdout from the windowed app. [CITED: github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess]
- **Do not use `ES_JAVA_OPTS` instead of jvm.options.d:** Elastic docs state "We do not recommend using ES_JAVA_OPTS in production" as it overrides all other JVM options. [CITED: elastic.co/guide/en/elasticsearch/reference/8.19/advanced-configuration.html]
- **Do not inline `sys._MEIPASS` everywhere:** Use `__file__` for finding resources relative to the frozen module; use `sys._MEIPASS` only when you explicitly need the `_internal/` root. [CITED: pyinstaller.org/en/stable/runtime-information.html]
- **Do not use UPX on Qt binaries:** UPX compression frequently corrupts Qt DLLs, causing import errors at runtime on Windows. Set `upx=False` in the spec EXE block. [ASSUMED — widely reported community pattern]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collecting qt-material theme data files | Manual glob over site-packages | `collect_all('qt_material')` in spec | PyInstaller hook utilities handle namespace packages, subdir discovery, and cross-platform paths automatically [CITED: pyinstaller.org/en/stable/hooks.html] |
| PyQt6 plugin/DLL collection | Manual DLL copying | PyInstaller built-in hook-PyQt6.* | PyInstaller ships hooks for every PyQt6.Qt* submodule; they auto-collect platform plugins and OpenSSL [CITED: pyinstaller.org/en/stable/hooks.html] |
| ES process health check | Custom HTTP poller | Existing `ESHealthWorker` | Already implemented and tested in Phase 1; no rewrite needed |
| Archive creation | tar+gzip + custom packaging | stdlib `zipfile.ZipFile` | Python stdlib, no dependencies, produces standard .zip that Windows Explorer can extract natively |

**Key insight:** The hard work in this phase is PyInstaller configuration (spec file), path resolution logic in `es_manager.py`, and the subprocess handle fix — not new library integrations. The bulk of the packaging machinery is in PyInstaller itself.

---

## Common Pitfalls

### Pitfall 1: qt-material theme files not bundled (most likely failure)
**What goes wrong:** App freezes then crashes immediately with `FileNotFoundError: ... qt_material/fonts` or a blank/unstyled window.
**Why it happens:** PyInstaller has no built-in hook for `qt-material`. The package's XML themes and font files are pure data, not imports — PyInstaller never discovers them via import analysis.
**How to avoid:** Use `collect_all('qt_material')` in the spec to collect all data files and submodules. The `datas` from `collect_all` covers the fonts and XML. Confirm with a test build before final assembly.
**Warning signs:** App launches but looks unstyled, or crashes with a path-related error on the qt_material package.

### Pitfall 2: `[Error 6] The handle is invalid` on ES subprocess start
**What goes wrong:** `subprocess.Popen` raises `OSError: [WinError 6]` when starting ES.
**Why it happens:** PyInstaller `console=False` sets `sys.stdout` and `sys.stderr` to `None`. `Popen` tries to inherit these as file handles — the null values are invalid Windows handles.
**How to avoid:** Explicitly pass `stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` to every `subprocess.Popen` call in `es_manager.py`. [CITED: github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess]
**Warning signs:** Error appears only in the frozen build, not in dev mode. The app works fine running `python main.py` but fails as an exe.

### Pitfall 3: ES starts with default security settings (TLS + auth enabled)
**What goes wrong:** ES starts but the cluster health check fails with `ConnectionError: SSL required` or `AuthenticationException`.
**Why it happens:** If `inject_es_config()` is not called before `ESHealthWorker.start()`, or if the config directory path is wrong, ES uses its own defaults — which in 8.x enable xpack.security.
**How to avoid:** Call `inject_es_config()` before `worker.start()` in `main.py`. Verify the written `elasticsearch.yml` contains the three `xpack.security.*: false` lines. Log the config destination path on startup for debugging.
**Warning signs:** ES log output mentions "SSL", "authentication", or "keystore".

### Pitfall 4: `ES_HOME` env var relied on in frozen build
**What goes wrong:** On the end user's clean machine, `ES_HOME` is not set. `validate_es_home(None)` raises `ValueError` and the app exits immediately.
**Why it happens:** `main.py` currently reads `os.environ.get("ES_HOME")`. This works in dev but fails in distribution.
**How to avoid:** Replace the `os.environ.get("ES_HOME")` call with `resolve_es_home()` which computes the path from `sys.executable.parent` in frozen mode and falls back to `ES_HOME` in dev mode.
**Warning signs:** App fails with "ES_HOME is not set" on a clean machine with the archive properly extracted.

### Pitfall 5: Config injection writes to `sys._MEIPASS/config` instead of ES config dir
**What goes wrong:** `inject_es_config()` resolves config source correctly but the destination is the wrong directory.
**Why it happens:** Confusing the config source (from `_internal/config/`, inside the PyInstaller bundle) with the config destination (inside `elasticsearch-8.18.0/config/`).
**How to avoid:** Distinguish the two paths explicitly in variable naming: `config_src` (source inside frozen bundle) vs `es_config_dir` (destination inside bundled ES directory). See Pattern 2.
**Warning signs:** ES starts with default settings; logs show the config/jvm.options.d/nitrofind.options file is missing.

### Pitfall 6: Build must be run on Windows (not WSL)
**What goes wrong:** PyInstaller built on Linux/WSL produces a Linux ELF binary, not a Windows .exe.
**Why it happens:** PyInstaller always builds for the platform it runs on. WSL is Linux.
**How to avoid:** Run `pyinstaller nitrofind.spec` from a native Windows Python installation (not WSL). The build script and `.spec` file can be developed in WSL but execution must be on native Windows.
**Warning signs:** `dist/NitroFind/NitroFind` has no `.exe` extension; `file` reports ELF.

### Pitfall 7: `close_fds=True` not set on Windows subprocess
**What goes wrong:** Dangling file descriptors from the parent process prevent NitroFind.exe from being overwritten during updates (the binary is "locked").
**Why it happens:** When `close_fds` defaults to `False` on Windows (pre-Python 3.12 default), child processes inherit file handles that keep parent files open.
**How to avoid:** Add `close_fds=True` to the ES `Popen` call (in addition to the DEVNULL redirects). [CITED: github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess]

---

## Code Examples

### Complete `resolve_es_home()` implementation

```python
# Source: pyinstaller.org/en/stable/runtime-information.html
def resolve_es_home() -> str | None:
    """Compute ES_HOME in frozen mode from launcher location; fall back to env var in dev."""
    if getattr(sys, 'frozen', False):
        launcher_dir = Path(sys.executable).parent
        candidates = sorted(launcher_dir.glob("elasticsearch-8.*"))
        return str(candidates[0]) if candidates else None
    return os.environ.get("ES_HOME")
```

### Updated `_start_process()` for windowed frozen mode

```python
# Source: github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess
def _start_process(self) -> subprocess.Popen:
    es_bin = _es_binary_path(self._es_home)
    kwargs: dict = {
        "stdin":  subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        kwargs["shell"] = True
    return subprocess.Popen([es_bin], **kwargs)
```

### Full `nitrofind.spec` outline (condensed)

```python
# Source: pyinstaller.org/en/stable/spec-files.html
from PyInstaller.utils.hooks import collect_all
qt_datas, qt_bins, qt_hidden = collect_all('qt_material')

a = Analysis(
    ['main.py'],
    datas=[('config', 'config'), *qt_datas],
    binaries=qt_bins,
    hiddenimports=['PyQt6.sip', *qt_hidden],
    ...
)
exe = EXE(..., console=False, upx=False, ...)
coll = COLLECT(exe, a.binaries, a.datas, ..., name='NitroFind')
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `--add-data src:dst` CLI flag | Hand-written `.spec` file with `collect_all()` | PyInstaller 4+ | Spec files are reproducible and version-controlled; CLI flags get unwieldy for 3+ datas entries |
| `sys._MEIPASS` for all resource paths | `__file__` preferred; `sys._MEIPASS` for root-relative only | PyInstaller 5+ | `__file__` is set correctly in frozen mode and works identically in dev mode |
| PyInstaller onedir output at `dist/AppName/AppName.exe` | PyInstaller 6 places DLLs in `dist/AppName/_internal/` with `AppName.exe` at root | PyInstaller 6.0 (2023) | The exe is at the top level; `_internal/` is the hidden DLL store; old tutorials showing DLLs at the same level as the exe are outdated |

**Deprecated/outdated:**
- `elasticsearch-dsl` as standalone pip install: merged into `elasticsearch==8.18+` core client. Don't add it to `datas` or `hiddenimports` separately — it's already part of the `elasticsearch` package collected by PyInstaller.
- `--noconsole` flag: This is the old PyInstaller CLI name. In `.spec` files use `console=False` inside the `EXE()` block. Both work but `.spec` form is canonical.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `collect_all('qt_material')` is sufficient to bundle all qt-material data files (XML + fonts) | Standard Stack, Pattern 3, Pitfall 1 | If wrong, build will succeed but app will crash or be unstyled at launch. Fix: manually add `datas=[(<path_to_qt_material>, 'qt_material')]` using `pip show qt_material` location. |
| A2 | `console=False` in the .spec EXE block is the correct way to suppress the console window in PyInstaller 6 | Pattern 3 | If wrong, a console window will appear on double-click. Low risk — widely documented. |
| A3 | UPX corrupts Qt DLLs on Windows — `upx=False` should be set in the spec | Anti-Patterns, Pattern 3 | If wrong, enabling UPX would reduce binary size by ~20-30%. Risk of corruption is real and community-confirmed. Keep `upx=False`. |
| A4 | PyInstaller onedir output for NitroFind (PyQt6 + qt-material + elasticsearch-py) will be approximately 80–250 MB | Summary, Archive size estimates | Actual size depends on which Qt submodules PyInstaller collects. Must measure after first build. No functional risk. |
| A5 | The final distributable zip (PyInstaller bundle + ES 8.18 directory) will be in the 600–800 MB range | Summary | ES zip alone is 468 MB compressed; PyInstaller bundle compresses well. Actual zip size must be measured post-build. |
| A6 | Elasticsearch 8.18 on Windows includes a bundled OpenJDK, so no system Java is required on the end-user machine | Architecture Patterns | Confirmed by Elastic documentation that ES ships with bundled OpenJDK. Low risk. |

---

## Open Questions

1. **Where will the distribution zip be hosted?**
   - What we know: GitHub Releases has a 2 GB limit per release, so the zip can technically be attached but 600–800 MB is a heavy GitHub release asset.
   - What's unclear: Is there a preferred hosting location (Google Drive, S3, GitHub Releases)?
   - Recommendation: Out of scope for v1; build the zip and confirm size. Note in success criteria that the zip must be extractable and double-clickable — where it's hosted is a deployment decision, not a packaging decision.

2. **Icon file (.ico) for the executable?**
   - What we know: `icon=None` in the spec works but produces a default PyInstaller icon.
   - What's unclear: Whether the user wants a custom icon.
   - Recommendation: Treat as optional for v1. The spec already has `icon=None` with a comment; replacing it with `icon='nitrofind.ico'` requires only a 1-line spec change.

3. **Should the app support being run from a network share or portable USB drive?**
   - What we know: The path resolution uses `sys.executable.parent` which works for relative paths regardless of drive letter.
   - What's unclear: Whether ES's bundled JDK handles UNC paths (\\server\share) on Windows.
   - Recommendation: Out of scope for v1. Assume local drive extraction only.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 (Windows) | PyInstaller build | Build machine only | — | Must install on Windows build machine; WSL Python cannot produce Windows exe |
| PyInstaller 6.x | Build | Not installed in current venv | 6.20.0 (latest on PyPI) | Install: `pip install pyinstaller==6.*` |
| Windows (native, not WSL) | PyInstaller build | WSL only on dev machine | — | Build must be executed on native Windows Python — WSL produces Linux ELF |
| Elasticsearch 8.18 Windows x86_64 zip | Archive assembly | Not downloaded | 8.18.0 | Download: `artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.18.0-windows-x86_64.zip` (468 MB) |

**Missing dependencies with no fallback:**
- Native Windows Python installation for running `pyinstaller nitrofind.spec`. The current dev environment is WSL2 Linux. A Windows Python 3.11 must be available to build the distribution.

**Missing dependencies with fallback:**
- PyInstaller 6.x: not currently installed, but trivially `pip install`-able on the Windows Python where the build runs.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x (already configured in pytest.ini) |
| Config file | pytest.ini (existing) |
| Quick run command | `pytest tests/test_packaging/ -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PKG-01 | `resolve_es_home()` returns correct sibling path in frozen mode | unit | `pytest tests/test_packaging/test_path_resolution.py -x` | Wave 0 |
| PKG-01 | `inject_es_config()` writes both files to ES config dir | unit | `pytest tests/test_packaging/test_config_injection.py -x` | Wave 0 |
| PKG-01 | `_start_process()` with DEVNULL redirects does not raise on launch | unit (mock Popen) | `pytest tests/test_packaging/test_subprocess_handles.py -x` | Wave 0 |
| PKG-01 | Full frozen-mode happy path on clean machine | manual smoke | manual — run NitroFind.exe on a machine without Python/Java | Manual only |

### Sampling Rate
- **Per task commit:** `pytest tests/test_packaging/ -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work` + manual smoke test on extracted archive

### Wave 0 Gaps
- [ ] `tests/test_packaging/__init__.py` — package marker
- [ ] `tests/test_packaging/test_path_resolution.py` — covers `resolve_es_home()` frozen/dev modes
- [ ] `tests/test_packaging/test_config_injection.py` — covers `inject_es_config()` writes
- [ ] `tests/test_packaging/test_subprocess_handles.py` — covers DEVNULL pattern in `_start_process()`

---

## Security Domain

> `security_enforcement` not explicitly set to false — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — no user auth in this phase |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | `validate_es_home()` already validates path before exec (T-02-01 from Phase 1) |
| V6 Cryptography | no | N/A — no new crypto |

### Known Threat Patterns for Distribution

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| User replaces bundled ES binary with malicious executable | Tampering | `validate_es_home()` already checks `isfile(es_bin)` before exec; nothing weaker introduced by bundling |
| Malicious archive extraction path traversal (zip slip) | Tampering | End user extracts zip themselves; extraction is user-controlled. Document "extract to trusted location" in README. |
| ES subprocess inheriting PyInstaller modified `PATH` / `SetDllDirectory` | Elevation | Explicit `env=None` (inherits process env) is acceptable for ES; on Windows `SetDllDirectoryW(None)` before Popen if ES fails to find its own DLLs — see Pitfall below. |

---

## Sources

### Primary (HIGH confidence)
- [pyinstaller.org/en/stable/runtime-information.html](https://pyinstaller.org/en/stable/runtime-information.html) — sys.frozen, sys._MEIPASS, __file__ behavior in frozen apps
- [pyinstaller.org/en/stable/spec-files.html](https://pyinstaller.org/en/stable/spec-files.html) — datas syntax, Analysis/EXE/COLLECT structure
- [pyinstaller.org/en/stable/hooks.html](https://pyinstaller.org/en/stable/hooks.html) — collect_data_files, collect_all, collect_submodules API
- [pyinstaller.org/en/stable/common-issues-and-pitfalls.html](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html) — windowed mode sys.stdout=None, subprocess PATH contamination
- [elastic.co/guide/en/elasticsearch/reference/8.19/advanced-configuration.html](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/advanced-configuration.html) — jvm.options.d file format, ES_JAVA_OPTS caveat

### Secondary (MEDIUM confidence)
- [github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-subprocess) — STARTUPINFO pattern, DEVNULL fix, close_fds
- [pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/](https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/) — PyQt6 hidden imports (PyQt6.sip), console=False, icon parameter
- [pythonguis.com/faq/packaged-installer-file-sizes/](https://www.pythonguis.com/faq/packaged-installer-file-sizes/) — PyQt6 bundle size estimates (30–80 MB installer, 80–250 MB onedir)
- [artifacts.elastic.co — elasticsearch-8.18.0-windows-x86_64.zip HTTP headers](https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.18.0-windows-x86_64.zip) — 468 MB compressed (confirmed via Content-Length: 491001314)

### Tertiary (LOW confidence)
- [github.com/UN-GCPDS/qt-material/issues/10](https://github.com/UN-GCPDS/qt-material/issues/10) — qt-material fonts packaging error report (specific fix not visible in issue; pattern inferred)

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — PyInstaller 6.x is the project-fixed tool; versions confirmed via PyPI registry
- Architecture / Path Resolution: HIGH — PyInstaller official docs explicitly describe sys.frozen, sys._MEIPASS, and __file__ behavior
- Config Injection: HIGH — Elastic official docs describe jvm.options.d semantics and ES_JAVA_OPTS caveats
- Subprocess Windowed Pitfall: HIGH — PyInstaller official docs + wiki document the DEVNULL fix
- qt-material collect_all: MEDIUM — collect_all pattern is from official PyInstaller hooks docs; that qt-material specifically needs it is ASSUMED from the known issue report
- Archive size estimates: MEDIUM — ES zip size confirmed (468 MB); Python bundle size is a range estimate, must measure
- UPX avoidance: ASSUMED — widely reported community pattern; not in official docs

**Research date:** 2026-05-29
**Valid until:** ~2026-08-29 (PyInstaller 6.x and ES 8.x are stable tracks; 90-day validity reasonable)
