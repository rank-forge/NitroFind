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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Timeline | Key Change |
|-----------|--------|-------|----------|------------|
| v1.0 | 5 | 18 | 17 days | Baseline — first milestone |

### Cumulative Quality

| Milestone | Test Functions | Test Files | LOC (Python) |
|-----------|---------------|------------|---------------|
| v1.0 | 146 | 20 | ~9,136 |

### Top Lessons (Verified Across Milestones)

1. Update tracking artifacts during execution — deferred documentation creates close-time debt.
2. Empirical validation requirements (live data, clean machine) need their own phases.
