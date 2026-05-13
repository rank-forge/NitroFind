# Phase 1: Infrastructure & Schema Foundation - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Python venv scaffold, Elasticsearch 8.18 lifecycle management (start via subprocess + QThread, health polling, clean shutdown), and the locked `car_articles` index mapping. Phase 1 produces no scraper logic and no search UI — only the foundation every downstream phase builds on.

</domain>

<decisions>
## Implementation Decisions

### ES Binary Location
- **D-01:** Locate ES via the `ES_HOME` environment variable. Binary path: `$ES_HOME/bin/elasticsearch`.
- **D-02:** If `ES_HOME` is not set at startup, exit immediately with a clear error message: `"ES_HOME is not set. Set it to your Elasticsearch 8.18 directory."` No fallback to PATH or relative paths.

### Startup Architecture
- **D-03:** Single `main.py` entry point. `QApplication` is created first, showing a loading window immediately. A `QThread` worker starts the ES subprocess and polls cluster health; it emits a signal when ES is ready, which triggers the transition from loading window to the main search window.
- **D-04:** Health check: `GET /_cluster/health` (via `requests` or the `elasticsearch` client), 2-second polling interval, 60-second total timeout. Accept `green` or `yellow` cluster status as healthy.
- **D-05:** Shutdown: connect `QApplication.aboutToQuit` to a handler that calls `process.terminate()`, then `process.wait(timeout=10)`. If ES does not exit within 10 seconds, call `process.kill()`.

### Loading Screen
- **D-06:** Show a dedicated loading window (not `QSplashScreen`, not the main window) containing: NitroFind branding, an animated spinner, and the static status text `"Starting search engine..."`. This window stays visible until the QThread signals ES readiness, then the main window replaces it.
- **D-07:** If ES fails to start within 60 seconds (timeout) or crashes (non-zero exit), replace the spinner with an error message and two buttons: **Retry** (terminates the stale process, restarts polling) and **Quit** (calls `QApplication.quit()`).

### era_bucket Schema
- **D-08:** `era_bucket` stores decade string labels derived from `production_start` year via integer math: `f"{(year // 10) * 10}s"` — e.g., `"1960s"`, `"2020s"`. Phase 2 scraper populates this field.
- **D-09:** ES field type: `keyword` — exact-match filtering, no text analysis. Required by Phase 4 filter sidebar aggregations.
- **D-10:** When `production_start` is missing or unknown: store `era_bucket = "Unknown"`. Filter sidebar may show or hide the "Unknown" bucket — Phase 4 decides.

### Pre-Discussion Locked Decisions (from STATE.md / CLAUDE.md)
- **L-01:** ES 8.18 config: `xpack.security.enabled: false`, `xpack.security.http.ssl.enabled: false`, `network.host: 127.0.0.1`, JVM heap: `-Xms512m -Xmx512m`.
- **L-02:** Index mapping uses `dynamic: false` and `flattened` type for any infobox/specs sub-field to prevent mapping explosion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase & Requirements
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria (5 items), and requirements list (INFRA-01 through SCHEMA-04)
- `.planning/REQUIREMENTS.md` — Full INFRA-01..04 and SCHEMA-01..04 requirement text with acceptance conditions
- `.planning/PROJECT.md` — Tech stack constraints, ES config decisions, key decisions table

### Technology Stack
- `CLAUDE.md` — ES 8.18 rationale and config specifics, PyQt6 version, Python 3.11 requirement, elasticsearch==8.x client, full alternatives-considered table

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project. No existing Python modules, components, or utilities.

### Established Patterns
- None yet — Phase 1 establishes the patterns all later phases follow.

### Integration Points
- `main.py` will be the entry point created in this phase; Phase 2 (scraper CLI) and Phase 4 (PyQt UI) will import from the modules scaffolded here.

</code_context>

<specifics>
## Specific Ideas

No specific UI references or examples surfaced during discussion. Loading window design is open to standard Qt approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Infrastructure & Schema Foundation*
*Context gathered: 2026-05-12*
