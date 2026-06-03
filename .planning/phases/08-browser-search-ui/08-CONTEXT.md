# Phase 8: Browser Search UI - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the `GET /` placeholder (`<h1>NitroFind</h1><p>Search UI coming in Phase 8.</p>`) with a full Google-style search interface. Flask serves a single HTML page (`templates/index.html`) backed by `static/css/style.css` and `static/js/app.js`. No React, no npm — vanilla HTML/CSS/JS only.

The UI has three states:
1. **Home** — NitroFind logo + centered search box, no results visible
2. **Results** — Search bar at top, filter row (dropdown pills) below, results list below that
3. **Article** — Full-page article view on click; back arrow returns to results

</domain>

<decisions>
## Implementation Decisions

### Design Direction
- **D-01:** Google-style interface. Home state = minimal centered search box (logo above, nothing else). Results state = search bar fixed at top, filter row, results list below. Inspired by Google's two-state transition: idle → active on first keystroke.
- **D-02:** Design quality guided by `design-taste-frontend` skill principles (dark mode tokens, typography discipline, color calibration, no AI-clichés). Stack is vanilla HTML/CSS/JS — skill's framework defaults (React/Tailwind) do NOT apply, but its quality rules DO: off-black not pure black, one accent color, no neon glows, WCAG AA contrast everywhere.

### Layout — Three UI States
- **D-03:** Home state: NitroFind logo centered, search box centered below it, nothing else on screen. Mirrors Google's homepage.
- **D-04:** Results state: search bar at top (left-aligned logo + search box in a row), filter row directly below (manufacturer, era_bucket, body_style as dropdowns), result list below that. Full viewport width available for results.
- **D-05:** Article state: clicking a result or pressing Enter transitions to a full-page article view. Back arrow/button returns to the previous results state (preserving search query and filters). No new tab opens.

### Filter Behavior
- **D-06:** Filters appear in the results state as a horizontal row of `<select>` dropdowns directly below the search bar. Default option is "All" (no filter). Changing a filter immediately re-runs the search (no submit button). Filter state persists when the user retypes the query.

### ES Warmup / Status
- **D-07:** Page loads immediately showing the home state. Search box is visually disabled (cursor: not-allowed, reduced opacity) while ES is warming up. A small status line below the search box reads "Starting up…" during warmup. JS polls `/api/status` every 2 seconds. When `status == "ok"`, the status line fades out and the search box activates. No manual refresh required.

### File Structure
- **D-08:** Flask serves `templates/index.html` from the `GET /` route (replace raw HTML string with `render_template("index.html")`). Static assets in `static/css/style.css` and `static/js/app.js`. Standard Flask convention — no CDN dependencies, no build step.

### Dark Teal Theme
- **D-09:** CSS custom properties for all color tokens (not hard-coded hex values inline). Dark teal accent from v1.0. Off-black background (not pure `#000000`). No neon glows. One accent color locked across all states. WCAG AA minimum for all text.
- **D-10:** Excerpt `<b>` tags from ES highlight responses rendered via `innerHTML` — data originates from local ES index (not user input), so no XSS risk from this path.

### Keyboard Navigation
- **D-11:** Arrow keys move selection through results in the results state. Enter on a selected result opens the article view. Escape clears the search input and returns to home state. (UIPL-03 requirement — not a choice.)

### Claude's Discretion
- Font choice: apply taste-skill typography rules (no Inter as default; Geist, Outfit, or similar; or system-font stack as fallback if CDN is undesirable in offline mode).
- Corner radius: one consistent radius scale across all interactive elements.
- Transition between home and results state: smooth CSS transition (search box moves to top) preferred over a hard page swap.
- Result count display: shown below the filter row, e.g., "42 results (0.08s)".
- No React, no npm, no CDN for JS frameworks — plain browser APIs only.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase & Requirements
- `.planning/ROADMAP.md` — Phase 8 goal, success criteria (7 items), requirements list (SRCH-01..04, UIPL-01..03)
- `.planning/REQUIREMENTS.md` — Full requirement text with acceptance conditions for SRCH-01..04, UIPL-01..03
- `.planning/PROJECT.md` — Tech stack constraints (Python + Elasticsearch + Flask), dark teal theme decision

### Existing Implementation to Extend
- `nitrofind/server.py` — `GET /` route (replace raw string return with `render_template`), `/api/search` response shape, `/api/status` response shape
- `.planning/phases/06-server-lifecycle-cleanup/06-CONTEXT.md` — D-13: current `GET /` placeholder definition

### Design Quality Reference
- `.agents/skills/design-taste-frontend/SKILL.md` — Sections 4 (design engineering directives), 8 (dark mode protocol), 9 (AI tells to avoid). Apply principles; ignore React/Tailwind framework defaults.

</canonical_refs>

<code_context>
## Existing Code Insights

### API Response Shapes (reuse directly)
- `GET /api/search?q=...` returns JSON array: `[{title, url, source_domain, excerpt, score, took_ms}, ...]`
  - `excerpt` contains `<b>` highlight tags — render with `innerHTML`
  - `took_ms` = ES response time (same value for all results in a single response)
  - Filter params: `manufacturer`, `era_bucket`, `body_style` (all optional, append to query string)
- `GET /api/status` returns `{"status": "starting"}` (503 during warmup) or `{"status": "ok", "es_health": "...", "doc_count": N, "index_size_bytes": N}` (200 when ready)

### Current GET / Route
- `nitrofind/server.py:index()` — returns raw HTML string; replace with `return render_template("index.html")`
- Flask's `render_template` requires `templates/` folder at project root (Flask default)

### Established Patterns
- 300ms debounce already used in v1.0 PyQt UI — same timing applies in JS (`setTimeout` / `clearTimeout` pattern)
- State dict pattern in `server.py` — background thread sets `state["ready"]` when ES is healthy; `/api/status` exposes this to the browser

### Integration Points
- `GET /` must call `render_template("index.html")` — requires `from flask import render_template` import in `server.py`
- `static/` folder served automatically by Flask at `/static/` — no additional route needed
- Filter values for `era_bucket`: values indexed by scraper (check `nitrofind/es_schema.py` for known values or leave as free-text dropdowns populated from first search)

</code_context>

<specifics>
## Specific Ideas

- User referenced Google as the visual reference: two-state UI (idle home → active results), not a persistent three-column app layout.
- Taste-skill applied as a quality bar, not a framework prescription — vanilla CSS with CSS custom properties is the correct execution.
- Offline-friendly: no CDN fonts or CDN JS in production (localhost tool with no internet at search time). Self-host any fonts or use a system-font stack.

</specifics>

<deferred>
## Deferred Ideas

- Light/dark theme toggle — listed in REQUIREMENTS.md v1.2+ future requirements
- Mobile responsiveness — localhost desktop tool; not required for v1.1
- Search history (last N queries, localStorage) — v1.2+ per REQUIREMENTS.md
- `/api/article/{id}` endpoint for direct article fetch — v1.2+ per REQUIREMENTS.md

</deferred>

---

*Phase: 8-Browser Search UI*
*Context gathered: 2026-06-03*
