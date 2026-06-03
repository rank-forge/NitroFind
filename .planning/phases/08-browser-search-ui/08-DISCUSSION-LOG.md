# Phase 8: Browser Search UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 8-browser-search-ui
**Areas discussed:** Design direction, Filter placement, Article view, ES warmup state

---

## Design Direction / Taste-Skill Application

| Option | Description | Selected |
|--------|-------------|----------|
| Design principles only | Apply dark mode, typography, color, no-AI-clichés to plain CSS + vanilla JS | ✓ |
| Tailwind via CDN | Add Tailwind CDN script, keep vanilla JS | |
| Full React stack | Add React/Tailwind build pipeline to Flask project | |

**User's choice:** The user initially answered "I want an interface like Google. not just an api, but a frontend using taste skill" — overriding the framing entirely. This shifted the layout model from three-column app to a Google two-state (home vs results) interface.
**Notes:** Taste-skill section 13 explicitly excludes product/app UI (dashboards, dense data) — the skill applies as a design quality bar, not a framework prescription. Vanilla CSS with CSS custom properties is the correct execution path for a Flask-served offline tool.

---

## Filter Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Filter row below search bar (Google-style) | Horizontal row of dropdowns below search box in results state | ✓ |
| Left sidebar | Filter controls in fixed left sidebar | |

**User's choice:** Filter row below search bar
**Notes:** Consistent with Google's results page aesthetic; keeps full viewport width available for results.

---

## Article View

| Option | Description | Selected |
|--------|-------------|----------|
| Right-side panel slides in | Results stay visible on left; article pane slides in from right | |
| Full-page article view | Click transitions to full-page view; back arrow returns to results | ✓ |
| Overlay / modal | Article appears in centered modal over results | |

**User's choice:** Full-page article view
**Notes:** Simpler layout; full reading width. Back navigation must preserve search query and filter state.

---

## ES Warmup / Startup State

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-poll + status dot | Disabled search box + status line; JS polls /api/status every 2s; activates on ready | ✓ |
| Static "starting up" message | Plain text page; user manually refreshes | |

**User's choice:** Auto-poll + status dot
**Notes:** No manual refresh required. Status indicator fades when `status == "ok"`.

---

## Claude's Discretion

- Font choice: taste-skill typography rules (no Inter as default); system-font stack for offline safety
- Home→results state transition: smooth CSS animation (search box slides to top)
- Corner radius: one consistent scale across all interactive elements
- Result count display format: "42 results (0.08s)" below filter row

## Deferred Ideas

- Light/dark theme toggle — v1.2+ per REQUIREMENTS.md
- Mobile responsiveness — localhost desktop tool; out of scope for v1.1
- Search history (localStorage) — v1.2+
- `/api/article/{id}` endpoint — v1.2+
