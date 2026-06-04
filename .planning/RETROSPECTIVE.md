# NitroFind — Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-05-29
**Phases:** 5 | **Plans:** 18 | **Timeline:** 17 days (2026-05-12 → 2026-05-29)

### What Was Built

- Reproducible Python 3.11 environment + ES 8.18 single-node with startup/shutdown lifecycle (INFRA-01..04, SCHEMA-01..04)
- One-shot CLI scraper: Wikipedia via MediaWiki API + Hagerty blog via BeautifulSoup4, SQLite state tracking, 1.8 GB size guard, 51 unit tests
- Elasticsearch `function_score` search engine: Gaussian recency decay + log1p length + has_infobox boost; QRunnable worker; 66 unit tests + 3 integration skips
- PyQt6 MainWindow: 300ms debounce, ResultDelegate HTML rendering with ES highlight tags, single-select FilterSidebar, stale-result guard, dark_teal Material theme; 31 pytest-qt tests; full human UAT approved
- PyInstaller onedir distribution: `resolve_es_home()` frozen-mode path resolution, `inject_es_config()` idempotent config writer, DEVNULL-hardened subprocess, `nitrofind.spec` + `scripts/build_dist.py`

### What Worked

- **TDD RED/GREEN discipline in Phase 2**: Writing 17 stubs first (all skipping cleanly) before implementation meant each plan had a clear done signal and no test drift.
- **Phase 1 as a real blocker**: Treating Phase 1 as a genuine prerequisite (not just scaffolding) meant every subsequent phase had a real ES node to test against, not a mock.
- **Human-in-the-loop verification gates**: Explicitly checkpointing human verification at plan completion (Phase 4 Plan 04, Phase 5 Plan 02) prevented false "done" signals for UI and packaging work that can't be fully automated.
- **State dict pattern for mutable worker reference**: The `state = {"worker": None}` pattern in main.py was clean and required no refactoring when Retry was added — a non-obvious but correct design choice discovered during Phase 1.
- **function_score DSL in elasticsearch-py 8.18**: The merged `elasticsearch-dsl` in 8.18.0 made the four-function query builder readable without a separate package. Correct version pin from the start.

### What Was Inefficient

- **REQUIREMENTS.md checkboxes never updated during execution**: All 25 v1 requirements were implemented but the file showed only 5/25 checked off at milestone close. Future milestones should update checkboxes at each plan completion, not defer to close.
- **Context exhaustion at 76% of Phase 3** (2026-05-16): Forced a session break mid-phase. Planning sessions should aim for smaller plan units to stay inside comfortable context windows.
- **CSS selectors for 3 of 4 blog targets not validated**: Hagerty was implemented; Car and Driver, Road & Track, and Hemmings CSS selectors remain untested against live HTML. Insufficient time allocated for multi-target validation.
- **Phase 3 live ranking quality deferred**: All three ranking quality checks (Ferrari 308 top-3, recency separation, infobox separation) require a live ES node with real indexed data and were deferred. These should have been built into a Phase 6 validation plan, not left as floating deferred items.

### Patterns Established

- **Horizontal-layer phases**: Each phase is one complete technical subsystem — clean dependency ordering, independently verifiable.
- **Decimal phases for urgent insertions**: Not used in v1.0 but pattern established in ROADMAP numbering conventions.
- **DEVNULL-hardened subprocess for frozen apps**: `stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, close_fds=True` required any time a subprocess is launched from a `console=False` PyInstaller bundle.
- **`ES_BUNDLE` env var for build-time assembly**: Keeps the Elasticsearch path out of the PyInstaller spec — makes builds repeatable across machines without editing spec files.
- **`upx=False` in PyInstaller spec**: UPX corrupts Qt DLLs on Windows. Always disable for PyQt apps.
- **Verification score format**: `N/M must-haves verified` + `human_needed` status + explicit `why_human` per item makes verification reports actionable rather than vague.

### Key Lessons

1. **Update tracking artifacts during execution, not at close.** Checkboxes, verification status, and requirement status should be updated as each plan completes. Deferring to milestone close creates a documentation sprint that slows down archiving.
2. **Allocate a validation phase for empirical concerns.** function_score weight tuning and clean-machine smoke testing both require real data/hardware. If these are real acceptance criteria, plan a dedicated phase for them rather than calling them "human verification" of an otherwise-complete phase.
3. **ES cold-start is slow on real hardware.** Plan for 120–180s cold-start on a desktop machine. The 60s default from the plan spec was wrong — always test the actual target machine early.
4. **PyInstaller + PyQt6 requires explicit `collect_all('qt_material')`** and `upx=False`. These are not obvious from PyInstaller docs — document them in CLAUDE.md for the next packager.
5. **Blog scraper CSS selectors are fragile.** The MEDIUM confidence flag on selector stability was correct. Build selector validation into the scraper plan itself (fetch live HTML, confirm selectors) rather than marking it as a concern.

### Cost Observations

- Model: Claude Sonnet 4.6 throughout
- Sessions: Multiple (exact count not tracked; context exhaustion noted at Phase 3)
- Notable: Phase 4 (UI) was the most expensive phase — 4 plans, 31 pytest-qt tests, human UAT. UI work consistently costs more than backend work at equal plan count.

---

## Milestone: v1.1 — Web Interface

**Shipped:** 2026-06-04
**Phases:** 3 (6–8) | **Plans:** 7 | **Timeline:** 2 days (2026-06-03 → 2026-06-04)

### What Was Built

- Phase 6: Flask 3.1.3 added; PyQt6/qt-material removed; `es_manager.py` stripped to Linux-only utilities; `nitrofind/server.py` with state dict, 503 warmup guard, daemon-thread ES health poller, `/api/status`; `main.py` rewritten as Flask lifecycle entry point; `nitrofind/ui/` deleted
- Phase 7: `GET /api/search` thin wrapper over existing query builder — highlight-or-fallback excerpts, filter forwarding, 503 guard, `?size`/`?from` passthrough; 8 unit tests
- Phase 8: `templates/index.html` three-state SPA skeleton with `data-state` CSS switching; `static/css/style.css` dark teal custom properties system; `static/js/app.js` vanilla JS SPA — 300ms debounce with AbortController, warmup polling, result rendering, keyboard nav; 7-item human UAT checklist

### What Worked

- **2-day velocity**: A focused 3-phase migration (strip Qt → add API → add UI) completed in 2 days. The clean v1.0 abstractions (state dict, query builder, ES manager) meant v1.1 was mostly wiring, not rewriting.
- **`data-state` CSS attribute pattern**: Using a single `body[data-state=...]` attribute to switch views eliminated all JS show/hide logic and made the SPA state machine readable in CSS. Discovered cleanly during Phase 8 research.
- **AbortController for debounce**: Using AbortController to cancel in-flight fetches instead of debouncing at the timeout level is correct — prevents stale responses from landing after a newer query. Zero extra packages.
- **Module-level state dict extended naturally**: Adding `es_client` to the existing state dict in Phase 7 required zero refactoring. The pattern from v1.0 (Phase 1 Plan 04) paid off.
- **Explicit `_pkg_dir` for Flask template resolution**: Identifying the `Flask(__name__)` root_path pitfall early (from Phase 8 RESEARCH.md) prevented a frustrating runtime bug. Research-before-plan pays off for framework-specific pitfalls.

### What Was Inefficient

- **REQUIREMENTS.md checkboxes not updated during execution** (again): Same issue as v1.0 — all 16 requirements were delivered but only 2/16 were formally checked at close. Despite explicitly noting this in v1.0 retrospective, it happened again. Needs a hook or enforcement at plan completion, not a reminder.
- **Phase 8 had 3 plans but ROADMAP.md was not updated**: Progress table still showed Phase 6 and 8 as "Not started" at milestone close. Plan completions didn't update the roadmap table.
- **No milestone audit before close**: Skipped `/gsd-audit-milestone` — proceeded with `Proceed anyway` choice. No gaps found at close, but the habit of skipping the audit should be examined.

### Patterns Established

- **`_pkg_dir` Flask root**: `_pkg_dir = os.path.dirname(os.path.abspath(__file__))` then `Flask(__name__, template_folder=os.path.join(_pkg_dir, "..", "templates"))` — required when Flask app is inside a package subdirectory, not the project root.
- **`data-state` SPA state machine**: `body[data-state=home]`, `body[data-state=results]`, `body[data-state=article]` — CSS shows/hides sections based on attribute; JS only sets the attribute value. Clean separation.
- **AbortController fetch debounce**: Cancel in-flight XHR/fetch at the AbortController level when a new keystroke fires, not just at the setTimeout level. Prevents stale response race conditions.
- **503 warmup guard as single chokepoint**: `if not state["ready"]: return jsonify({"status": "starting"}), 503` — one guard per route, early return. Simple and testable.

### Key Lessons

1. **REQUIREMENTS.md checkbox drift is a structural problem, not a discipline problem.** It happened twice across two milestones despite being explicitly called out in v1.0 retrospective. A hook at plan completion to check the file would fix this.
2. **Flask framework pitfalls are well-documented but not obvious from the official docs.** The `template_folder` root_path issue, FOUC from missing initial `data-state`, and `innerHTML` vs `textContent` for highlight rendering all came from curated research. RESEARCH.md-before-plan-for-framework-heavy-phases is the right pattern.
3. **A 17-plan v1.0 provides clean abstractions for a fast v1.1.** The state dict, query builder, and ES manager from v1.0 were reused without modification in v1.1. Over-engineering at v1.0 would have hurt; under-engineering would have forced rewrites.
4. **ROADMAP.md progress table goes stale if not updated at plan completion.** Add roadmap table update to the plan-completion checklist.

### Cost Observations

- Model: Claude Sonnet 4.6 throughout
- Sessions: Multiple (exact count not tracked)
- Notable: Phase 8 (browser UI) was the most expensive v1.1 phase — 3 plans, HTML + CSS + JS + tests. UI work remains the heaviest investment relative to backend phases.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Timeline | Key Change |
|-----------|--------|-------|----------|------------|
| v1.0 | 5 | 18 | 17 days | Baseline — first milestone |
| v1.1 | 3 | 7 | 2 days | Faster execution — clean abstractions from v1.0 eliminated rewriting |

### Cumulative Quality

| Milestone | Files Changed | LOC Change | Tech Added |
|-----------|--------------|------------|------------|
| v1.0 | 143 | ~9,136 net | ES, PyQt6, requests, BS4, PyInstaller |
| v1.1 | 89 | +12,077 / -3,140 | Flask; removed PyQt6, qt-material |

### Top Lessons (Verified Across Milestones)

1. **Update tracking artifacts during execution** — deferred documentation creates close-time debt (confirmed across both milestones; structural fix needed).
2. **Empirical validation requirements (live data, clean machine) need their own phases** — deferred from v1.0, still open in v1.2.
3. **Clean v1.0 abstractions enable fast v1.1** — state dict, query builder, and ES manager reused without modification; velocity doubled despite fewer engineers.
