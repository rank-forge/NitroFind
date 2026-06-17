---
phase: 09-article-rendering-fixes
plan: "02"
subsystem: scraper
tags: [bug-fix, scraper, elasticsearch, html-parsing, body-html]
dependency_graph:
  requires: ["09-01"]
  provides: ["strip_nav_sections", "_clean_wikipedia_html", "_fetch_html_body", "_BLOG_NOISE_SELECTORS", "body_html-doc-key", "body_html-es-field", "--recreate-flag"]
  affects: ["nitrofind/scraper/cleaner.py", "nitrofind/scraper/wikipedia.py", "nitrofind/scraper/blogs.py", "nitrofind/es_schema.py", "scripts/scraper.py"]
tech_stack:
  added: []
  patterns: ["MediaWiki Parse API for rendered HTML", "BeautifulSoup decompose() noise removal", "ES index:false field for stored-not-tokenized HTML"]
key_files:
  created: []
  modified:
    - nitrofind/scraper/cleaner.py
    - nitrofind/scraper/wikipedia.py
    - nitrofind/scraper/blogs.py
    - nitrofind/es_schema.py
    - scripts/scraper.py
decisions:
  - "Used pageid= (not page=title) in MediaWiki Parse API call to prevent redirect aliasing (Pitfall 4)"
  - "Captured body_html = str(container) BEFORE get_text() in blogs.py to preserve HTML structure (Pitfall 3)"
  - "Used text/index:False for body_html ES field — NOT keyword (keyword ignore_above=256 would truncate)"
  - "Both .navbox AND .navbox-styles removed from Wikipedia HTML (Pitfall 2 — companion CSS blocks)"
  - "_fetch_html_body() returns empty string on any exception (T-09-02-I1 accept disposition)"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-17"
  tasks_completed: 2
  files_changed: 5
---

# Phase 09 Plan 02: Data-Production Fixes (BUG-01 + BUG-02) Summary

**One-liner:** Scraper now emits `body_html` (rendered HTML with tables) and noise-free `body` (nav sections stripped) for both Wikipedia and blog sources, backed by new ES schema field and `--recreate` flag.

## What Was Built

### Task 1: cleaner.strip_nav_sections + Wikipedia HTML fetch/clean + body_html doc key

**cleaner.py:**
- Added `_WIKIPEDIA_NAV_SECTIONS` frozenset constant (references, external links, see also, further reading, bibliography, notes, footnotes)
- Added `strip_nav_sections(content: str) -> str` pure function that splits on `== Section ==` headers and drops content under nav-named sections while preserving real content headings
- Updated module docstring to include `strip_nav_sections` in the Exports list

**wikipedia.py:**
- Added `from bs4 import BeautifulSoup` import
- Extended cleaner import to include `strip_nav_sections`
- Added `_WIKIPEDIA_NOISE_SELECTORS` list (16 selectors including both `.navbox` and `.navbox-styles`)
- Added module-level function `_clean_wikipedia_html(raw_html)` that strips noise, selects `.mw-parser-output`, rewrites relative URLs to absolute, prefixes protocol-relative img srcs, and strips `on*` attrs + `data:` URI src/href values
- Added `WikipediaScraper._fetch_html_body(self, pageid: int) -> str` method calling MediaWiki Parse API via `self._session.get()` with `action=parse&pageid=<id>&prop=text&disabletoc=1&format=json`
- Updated `_fetch_and_build_doc()`: `body_text = strip_nav_sections(page.content)`, `body_html = self._fetch_html_body(pageid)`, added `"body_html": body_html` to returned doc dict

**Tests GREEN:** `test_cleaner.py` + `test_wikipedia.py` (24 passed)

### Task 2: Blog noise expansion + body_html capture + ES schema field + --recreate flag

**blogs.py:**
- Added `_BLOG_NOISE_SELECTORS` module-level constant with 14-selector expanded noise list (adds .breadcrumb, .article-meta, .tag-list, .related-articles, [class*='related'], .newsletter-signup, .author-bio, .share-buttons, .comments, .sidebar beyond the original 7)
- Replaced inline `soup.select("script, style, ...")` with `soup.select(_BLOG_NOISE_SELECTORS)`
- Added `body_html = str(container)` BEFORE `container.get_text()` in `_fetch_article()`
- Added `"body_html": body_html` to returned doc dict

**es_schema.py:**
- Added `"body_html"` field to `CAR_ARTICLES_MAPPING["properties"]` after `"excerpt"` with `{"type": "text", "index": False}` — stored in `_source` but not tokenized

**scripts/scraper.py:**
- Added `INDEX_NAME = "car_articles"` constant
- Added `--recreate` boolean flag to `_parse_args()`
- Added recreate logic in `main()`: if `args.recreate`, calls `client.indices.delete(index=INDEX_NAME, ignore_unavailable=True)` then logs warning before `ensure_index(client)` rebuilds the index

**Tests GREEN:** `test_blogs.py` + `test_es_schema.py` (15 passed)

## Verification Results

```
python3 -m pytest tests/test_scraper/ tests/test_es_schema.py -m "not integration" -q
60 passed, 2 deselected
```

```
PYTHONPATH=. python3 scripts/scraper.py --help | grep -- "--recreate"
--recreate  Delete and rebuild the car_articles index before scraping — required after a schema change
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 3551e8e | feat(09-02): add strip_nav_sections, _clean_wikipedia_html, and body_html to Wikipedia scraper |
| Task 2 | d0baca7 | feat(09-02): add blog noise expansion, body_html capture, ES schema field, and --recreate flag |

## Deviations from Plan

None — plan executed exactly as written. All patterns from 09-PATTERNS.md applied verbatim. All pitfalls from 09-RESEARCH.md explicitly addressed.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced beyond those in the plan's `<threat_model>`. The `_fetch_html_body()` method calls the existing Wikipedia API endpoint already used by `_get_category_members_raw()` — same session, same User-Agent, same rate limit. No new threat flags.

XSS hygiene applied per T-09-02-T1:
- `_clean_wikipedia_html()` strips `<script>`, `style`, and `on*` event handler attributes
- `data:` URI src/href values are removed
- Blog scraper removes `script, style` via `_BLOG_NOISE_SELECTORS`

## Known Stubs

None. All implemented functions are fully wired:
- `strip_nav_sections()` is called in `_fetch_and_build_doc()` on `page.content`
- `_fetch_html_body()` is called in `_fetch_and_build_doc()` and the result is stored in `body_html`
- `body_html` field is in both scrapers' doc dicts and in `CAR_ARTICLES_MAPPING`
- `--recreate` flag calls `client.indices.delete()` before `ensure_index()`

## Self-Check: PASSED

Files created/modified:
- [FOUND] nitrofind/scraper/cleaner.py — contains `def strip_nav_sections(` and `_WIKIPEDIA_NAV_SECTIONS = frozenset(`
- [FOUND] nitrofind/scraper/wikipedia.py — contains `def _clean_wikipedia_html(`, `def _fetch_html_body(`, `.navbox-styles` in selector list, `strip_nav_sections(page.content)`, `body_html` key in doc
- [FOUND] nitrofind/scraper/blogs.py — contains `_BLOG_NOISE_SELECTORS`, `body_html = str(container)`, `body_html` key in doc
- [FOUND] nitrofind/es_schema.py — `body_html` with `"type": "text", "index": False`
- [FOUND] scripts/scraper.py — `--recreate` flag, `indices.delete(`

Commits verified:
- [FOUND] 3551e8e — Task 1
- [FOUND] d0baca7 — Task 2
