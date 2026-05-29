---
phase: 5
slug: packaging-distribution
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (already configured in pytest.ini) |
| **Config file** | pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_packaging/ -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_packaging/ -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green + manual smoke test on extracted archive
- **Max feedback latency:** 30 seconds (unit tests only)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | W0 | PKG-01 | — | N/A | unit | `pytest tests/test_packaging/test_path_resolution.py -x` | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | W0 | PKG-01 | — | N/A | unit | `pytest tests/test_packaging/test_config_injection.py -x` | ❌ W0 | ⬜ pending |
| 5-01-03 | 01 | W0 | PKG-01 | T-02-01 | subprocess handles not inherited (DEVNULL) | unit | `pytest tests/test_packaging/test_subprocess_handles.py -x` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | PKG-01 | — | N/A | manual | Run NitroFind.exe on clean machine (no Python/Java) | Manual only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_packaging/__init__.py` — package marker
- [ ] `tests/test_packaging/test_path_resolution.py` — stubs for PKG-01 (resolve_es_home frozen/dev modes)
- [ ] `tests/test_packaging/test_config_injection.py` — stubs for PKG-01 (inject_es_config writes both files)
- [ ] `tests/test_packaging/test_subprocess_handles.py` — stubs for PKG-01 (DEVNULL pattern in _start_process)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full frozen-mode happy path: extract archive, double-click launcher, ES health check passes | PKG-01 | PyInstaller build must run on native Windows; clean-machine test cannot be automated in CI | 1. Build on Windows with `pyinstaller nitrofind.spec`. 2. Run `python scripts/build_dist.py` to create zip. 3. Extract to a machine with no Python/Java. 4. Double-click NitroFind.exe. 5. Verify app reaches search-ready state (main window visible, ES healthy). |
| NitroFind.exe launches without console window | PKG-01 | Requires visual inspection of windowed app behavior | After frozen build, double-click .exe and confirm no terminal/console window appears alongside the app. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
