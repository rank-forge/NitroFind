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

---

## v1.1 Web Interface — Shipped 2026-06-04

**Phases:** 6–8 | **Plans:** 7 | **Timeline:** 2026-06-03 → 2026-06-04 (2 days)
**Files changed:** 89 | **Lines:** +12,077 / -3,140 | **Commits:** ~65

### Delivered

PyQt6 desktop UI replaced with a browser-based Flask web app — `python main.py` starts ES + web server; search available at `localhost:5000`.

### Key Accomplishments

1. Flask 3.1.3 added; PyQt6, qt-material fully removed — `nitrofind/ui/` deleted, `requirements.txt` Qt-free (CLEN-01)
2. `nitrofind/server.py`: Flask app with module-level state dict, daemon-thread ES health poller, `/api/status`, 503 warmup guard (SRVR-02, SRVR-03, API-03)
3. `main.py` rewritten as Flask lifecycle entry point — validates ES home, injects config, starts background poller, runs Flask, shuts down ES cleanly on Ctrl+C (SRVR-01, SRVR-04)
4. `GET /api/search` thin wrapper over existing query builder: highlight-or-fallback excerpts, filter forwarding, 503 guard, `?size`/`?from` passthrough (API-01, API-02)
5. Three-state SPA: dark teal CSS custom properties, `data-state` attribute view switching, vanilla JS 300ms debounce with AbortController, warmup polling, result rendering (SRCH-01–04, UIPL-01–03)
6. Arrow-key/Enter/Escape keyboard navigation, result count + query time display — feature-parity with v1.0 PyQt6 UI in the browser

### Requirements: 16/16 Complete

All v1.1 requirements delivered. No known gaps at close.

### Known Deferred Items

- Empirical tuning of `function_score` weights (requires live indexed data — carried from v1.0)
- Windows clean-machine smoke test (Linux/WSL only for v1.1 — carried from v1.0)
- `PYQT6_AVAILABLE` skip guard in `tests/test_search/test_engine.py` — minor cleanup for v1.2

### Archive

- Roadmap: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- Requirements: [milestones/v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md)
