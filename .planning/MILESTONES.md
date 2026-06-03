# NitroFind — Milestones

## v1.0 MVP — Shipped 2026-05-29

**Phases:** 1–5 | **Plans:** 18 | **Timeline:** 2026-05-12 → 2026-05-29 (17 days)
**Lines of code:** ~9,136 Python | **Files changed:** 143 | **Commits:** 182

### Delivered

Full offline automotive search app — from zero to distributable Windows executable.

### Key Accomplishments

1. Reproducible Python venv + ES 8.18 single-node (TLS off, heap pinned) starts and terminates cleanly from `python main.py`
2. One-shot CLI scraper ingests Wikipedia car articles (MediaWiki API) and Hagerty blog articles into a car_articles ES index with 1.8 GB size guard
3. `function_score` search engine: Gaussian recency decay (730d scale) + log1p length signal + has_infobox boost; score_mode sum, boost_mode multiply; all results delivered via QRunnable worker (non-blocking)
4. PyQt6 MainWindow with 300ms debounce search, ES highlight rendering in ResultDelegate, single-select FilterSidebar, stale-result guard, full keyboard nav; dark_teal Material theme verified human-in-the-loop
5. PyInstaller onedir bundle + `scripts/build_dist.py` assembly: resolve_es_home() frozen-mode path resolution, inject_es_config() idempotent config writer, DEVNULL-hardened subprocess — ships as `NitroFind-v1.0-windows-x86_64.zip`

### Known Deferred Items at Close: 5 (see STATE.md Deferred Items)

- Phase 3 live ranking quality checks (requires live ES + indexed data)
- Phase 5 Windows clean-machine smoke test (requires machine without Python/Java)
- Phase 4 VERIFICATION.md not updated to `passed` (UAT file shows all scenarios approved)
- Quick task tracking record stale (work done at commit a5f8dce)

### Archive

- Roadmap: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- Requirements: [milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)
