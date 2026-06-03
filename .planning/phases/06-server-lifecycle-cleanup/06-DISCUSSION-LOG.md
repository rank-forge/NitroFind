# Phase 6: Server Lifecycle & Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 6-server-lifecycle-cleanup
**Areas discussed:** Platform target (user-initiated)

---

## Platform Target

| Option | Description | Selected |
|--------|-------------|----------|
| Linux/WSL only | Strip all Windows-specific code; simpler subprocess, SIGTERM shutdown | ✓ |
| Cross-platform | Keep win32 branches, .bat path, CTRL_BREAK_EVENT, CREATE_NEW_PROCESS_GROUP | |

**User's choice:** Free-text — "The only thing I wanted to discuss is that I will only run using the wsl terminal, so there is no need to be thinking about windows, and other bs."
**Notes:** User did not want to discuss ES startup model, Ctrl+C wiring, or es_manager restructuring individually — flagged the platform constraint and approved Claude's proposed defaults for everything else.

---

## Claude's Discretion

All implementation decisions below were proposed by Claude and approved by the user without modification:

- **ES startup model:** Flask-503 model — Flask starts immediately, background `threading.Thread` polls ES health, sets shared flag
- **Ctrl+C shutdown:** `try/finally` around `app.run()` — Flask's `KeyboardInterrupt` triggers `finally` block
- **Code structure:** Strip `ESHealthWorker` from `es_manager.py`; new `nitrofind/server.py` for Flask app + lifecycle
- **`/api/status` shape:** `{"status": "starting"}` (503) during warmup; `{"status": "ok", "es_health": ..., "doc_count": ..., "index_size_bytes": ...}` (200) when healthy
- **`GET /` placeholder:** Minimal HTML only — replaced by Phase 8 UI
- **PyQt6 cleanup:** Delete `nitrofind/ui/` directory entirely; remove PyQt6 + qt-material from requirements

## Deferred Ideas

None — discussion stayed within phase scope.
