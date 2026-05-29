---
plan: 05-02
phase: 05-packaging-distribution
status: complete
completed: 2026-05-29T15:22:00Z
commits:
  - b634ebf
  - 9f87478
---

# Plan 05-02 Summary: PyInstaller Spec + Distribution Assembly

## What Was Built

Two build artifacts that complete the PKG-01 distribution package:

### Files Created

| File | Purpose |
|------|---------|
| `nitrofind.spec` | PyInstaller 6 onedir spec — `collect_all('qt_material')`, `('config', 'config')` datas, `console=False`, `upx=False` in both EXE and COLLECT |
| `scripts/build_dist.py` | Post-build assembly script — copies ES dir alongside `dist/NitroFind/`, zips to `dist/NitroFind-v1.0-windows-x86_64.zip` |

### Key Decisions

- `onedir` mode (not `--onefile`): avoids AV false-positives and slow single-file extraction on each launch
- `collect_all('qt_material')`: required because PyInstaller has no built-in hook for qt_material — bundles all theme XMLs + fonts into `_internal/`
- `upx=False` in both EXE and COLLECT: UPX corrupts Qt DLLs on Windows
- `console=False`: GUI app, no console window; this is why Plan 01's DEVNULL fix in `_start_process` was required
- `ES_BUNDLE` env var for assembly: keeps the ES path out of the spec and makes the build repeatable across machines

### Automated Checks (All Pass)

| Check | Result |
|-------|--------|
| `python -c "import ast; ast.parse(open('nitrofind.spec').read())"` | 0 |
| `grep -c "collect_all('qt_material')" nitrofind.spec` | 1 |
| `grep -c "'config', 'config'" nitrofind.spec` | 1 |
| `grep -c "console=False" nitrofind.spec` | 1 |
| `upx=False` count in nitrofind.spec | 2 (EXE + COLLECT) |
| `python -c "import ast; ast.parse(open('scripts/build_dist.py').read())"` | 0 |
| `python scripts/build_dist.py` with ES_BUNDLE unset | exits non-zero, prints "ES_BUNDLE is not set" |

### Smoke Test Result

**PASSED** — manual clean-machine Windows verification confirmed:

- NitroFind.exe launched without a console window
- Loading window appeared within 2 seconds
- App transitioned to MainWindow (search-ready state) within 180 seconds
- Search bar interactive
- No lingering `java.exe` after app close
- `dist/NitroFind-v1.0-windows-x86_64.zip` created successfully

### PKG-01 Completion

PKG-01 is fully satisfied:
- Plan 01: runtime side (resolve_es_home, inject_es_config, DEVNULL subprocess fix)
- Plan 02: build side (PyInstaller spec + distribution archive assembly)

The distributed zip contains the PyInstaller bundle alongside the pre-extracted Elasticsearch directory. No Python or Java install required on the end-user machine.

### Deviations

None. All tasks completed as specified.
