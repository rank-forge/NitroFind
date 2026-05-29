"""nitrofind.spec — PyInstaller onedir build spec for NitroFind.
PKG-01: produces the frozen NitroFind bundle (dist/NitroFind/) that ships
alongside the elasticsearch-8.18.0/ directory in the distribution archive.
"""
# Source: pyinstaller.org/en/stable/spec-files.html
# PKG-01: onedir mode — ES cannot be bundled inside a onefile self-extracting
# archive because it requires a stable filesystem path for its own JVM startup.
# Onefile also adds multi-second cold-start overhead per Python launch.

from PyInstaller.utils.hooks import collect_all

# Source: pyinstaller.org/en/stable/hooks.html
# Pitfall 1: no built-in hook for qt_material; collect_all is required to
# bundle theme XML + font files (Pitfall 1)
qt_datas, qt_bins, qt_hidden = collect_all('qt_material')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_bins,
    datas=[
        ('config', 'config'),   # PKG-01: elasticsearch.yml + jvm.options -> _internal/config/
        *qt_datas,              # PKG-01 Pitfall 1: theme XMLs + fonts
    ],
    hiddenimports=['PyQt6.sip', *qt_hidden],   # Source: pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/
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
    console=False,  # PKG-01: GUI app — no console window (T-05-01 related: console=False requires DEVNULL in _start_process)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,      # replace with 'nitrofind.ico' when available (UI-V2-01)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,           # Anti-pattern: UPX corrupts Qt DLLs; must match EXE block
    upx_exclude=[],
    name='NitroFind',    # output dir: dist/NitroFind/
)

# Build command (run on native Windows Python 3.11, not WSL — RESEARCH.md Pitfall 6):
#   pyinstaller nitrofind.spec
# Output: dist/NitroFind/NitroFind.exe + dist/NitroFind/_internal/
# Then run: ES_BUNDLE=/path/to/elasticsearch-8.18.0 python scripts/build_dist.py
