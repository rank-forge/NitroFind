# Technology Stack

**Project:** NitroFind — Offline Automotive Desktop Search Engine
**Researched:** 2026-05-12

---

## Recommended Stack

### Search Engine

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Elasticsearch | 8.x (latest 8.18) | Full-text search, function_score ranking | See rationale below |

**Use Elasticsearch 8.x, not 9.x.**

Elasticsearch 9.0 was released in early 2025 and is the current major version (latest: 9.4.0 as of May 2026). However, for this project, pin to the **8.x line** (specifically 8.18.x):

- ES9 has documented reports of performance regressions for aggregation-heavy queries compared to ES8 on certain workloads. Since NitroFind uses `function_score` with multiple scoring functions (date decay, domain boost, length scoring), this matters.
- The elasticsearch-py client v8.x (`elasticsearch8` on PyPI, or `elasticsearch==8.x`) is stable, well-documented, and has a mature Python API for `function_score` DSL. The 9.x client merges DSL into the core package, which is fine, but the 8.x ecosystem is more battle-tested for this use case.
- The breaking changes in ES9 (ES|QL, new index formats, changed defaults) provide no benefit for a local single-node text search with no cloud/cluster needs.
- ES 8.x supports security-disabled single-node mode via `xpack.security.enabled: false` in `elasticsearch.yml`, which is the cleanest local desktop configuration — no TLS, no certificates, no auth tokens needed.
- JVM heap can be reduced to 512 MB–1 GB in `jvm.options.d/` for a desktop environment. With a 2 GB index cap, an ES8 node with 1 GB heap is sufficient.

**Why not lighter alternatives?**

- **Meilisearch**: Does NOT support `function_score` or equivalent. Its custom ranking is limited to sort-by-attribute ordering, not composite mathematical scoring. NitroFind's relevance model (date decay + domain authority + completeness) requires weighted multi-function scoring. Meilisearch cannot implement this without workarounds that would undermine the entire scoring design. Ruled out.
- **Typesense**: Same issue — no equivalent of Elasticsearch's `function_score`. Supports numeric boost fields but not multi-function weighted composites with decay functions. Ruled out.
- **OpenSearch**: Apache 2.0 license and very close feature parity with Elasticsearch 8. Would work technically. However, the Python client ecosystem, documentation quality, and Stack Overflow community are thinner. OpenSearch is the right call for log analytics at scale, not for this use case. Stick with ES because the stack is already fixed per project constraints.
- **SQLite FTS5**: Capable of full-text search, but `function_score`-equivalent custom scoring requires custom code rather than declarative query DSL. Much more maintenance burden than ES for a 2 GB text corpus. Not considered.

**Confidence:** HIGH — verified via official Elastic release notes and PyPI.

---

### Core Framework / Language

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11.x | All application logic (scraper, indexer, search service) | Compatibility ceiling: elasticsearch-py 8.x and PyQt6 6.11 both require Python >=3.10; 3.11 is the sweet spot — faster than 3.10, more stable than 3.12/3.13 for PyQt native bindings |

**Confidence:** HIGH

---

### Desktop UI

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PyQt6 | 6.11.0 | Desktop GUI (search bar, filter panel, result list, detail view) | See rationale below |

**Use PyQt6, not PyQt5.**

- PyQt6 6.11.0 is the current stable release (March 30, 2026, pip installable). PyQt5 has not received feature updates in years and uses older Qt5 rendering pipeline.
- PyQt6 binds to Qt6, which has a significantly improved rendering pipeline, better HiDPI/scaling support, and a cleaner enum namespace (no more `Qt.AlignLeft` ambiguity). For a "fluid, modern feel comparable to a browser search experience," Qt6's rendering is noticeably better.
- PyQt6 requires Python >=3.10, which aligns with the elasticsearch-py constraint, so no version split is needed.
- The migration from PyQt5 to PyQt6 is straightforward; the differences are enum namespacing and minor import changes — not a concern on a greenfield project.
- PyQt6 (Riverbank Computing commercial license or GPL) is acceptable for a single-user local tool.

**Companion UI libraries:**

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyQt6-Qt6 | (installed auto with PyQt6) | Qt runtime binaries | Always, installed as dep |
| PyQt6-sip | (installed auto with PyQt6) | C++ binding layer | Always, installed as dep |
| qt-material | latest | Material Design stylesheet for PyQt6 | Apply once at startup for modern look without custom QSS |
| QDarkStyle | latest | Alternative dark theme | Use if qt-material proves incompatible |

**Threading pattern for instant search:** Use `QTimer` (300 ms debounce) connected to a `QRunnable` via `QThreadPool`. The search query runs in a worker thread; results are signaled back to the UI thread via `pyqtSignal`. Do NOT query Elasticsearch on the main GUI thread — this freezes the UI. `QThread` subclassing is the alternative but `QThreadPool + QRunnable` is lighter for short-lived, frequent search tasks.

**Confidence:** HIGH — verified via PyPI, pythonguis.com current docs.

---

### Python Elasticsearch Client

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| elasticsearch | 8.18.x (pip: `elasticsearch==8.*`) | Python client for all ES operations | See rationale below |

**Use the `elasticsearch` package pinned to the 8.x major version.**

As of May 2026, `elasticsearch` on PyPI is at version 9.4.0 (follows ES server version). Installing `pip install "elasticsearch>=8,<9"` pins to the 8.x client, which connects to an ES 8.x server. Do NOT mix client major version with server major version — an ES9 client against an ES8 server will fail on certain API calls.

The 8.x client (`elasticsearch8` package on PyPI is the legacy name; the main `elasticsearch` package at `>=8,<9` is equivalent):

- Full support for `function_score` queries via the Python DSL built into 8.x.
- `elasticsearch-dsl` as a separate package was merged into the core client at 8.18.0 — no separate install needed. The DSL provides `Q('function_score', ...)` query objects that make complex scoring queries readable.
- Type annotations added in 8.x make IDE completion useful.
- Python >=3.10 required (matches PyQt6 and Python 3.11 target).

**Do NOT use:**
- `elasticsearch9` or `elasticsearch>=9` — connects to ES9 server; unnecessary major version upgrade with regression risks.
- `elasticsearch7` — outdated, missing 8.x index APIs.
- `elasticsearch-dsl` as a standalone pip install — it is now deprecated and redirects to the core client; importing from it still works but is a dead-end dependency.

**Confidence:** HIGH — verified via PyPI release history and elastic.co docs.

---

### Scraper Stack

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| requests | latest (2.32.x) | HTTP fetching for all blog targets | Simple, synchronous, appropriate for a one-shot scraper with deliberate rate limiting |
| httpx | latest (0.27.x) | Async HTTP when/if concurrent fetching is needed | Drop-in requests replacement with async support; useful if scraping multiple automotive blogs in parallel |
| BeautifulSoup4 | latest (4.12.x) | HTML parsing for blog articles | Targeted parsing of known page structures; simpler than Scrapy for fixed-target scraping |
| lxml | latest | Parser backend for BS4 | Faster than html.parser for large Wikipedia pages |
| mediawikiapi | latest | Wikipedia-specific API access | Use the MediaWiki API (not raw HTML scraping) for Wikipedia — more stable, structured, respects rate limits |

**Use requests + BeautifulSoup4, NOT Scrapy.**

Scrapy is designed for large-scale crawls of unknown site structures with a pipeline architecture. NitroFind scrapes a small, fixed set of known sources (Wikipedia automotive pages + 4-5 known automotive blog domains). The overhead of defining Scrapy spiders, items, pipelines, and middlewares is not justified.

The right pattern for NitroFind:
1. For Wikipedia: Use `mediawikiapi` (wraps MediaWiki REST API) — returns structured JSON with page content, categories, infoboxes. No HTML parsing needed.
2. For automotive blogs (Car and Driver, Road & Track, Hagerty, Hemmings): Use `requests` to fetch known article URLs, `BeautifulSoup4 + lxml` to extract article body, title, author, publish date from predictable CSS selectors per domain. One parser file per domain (~50 lines each).

**Do NOT use Scrapy** because:
- Its spider/item/pipeline abstraction adds 300+ lines of boilerplate for what is essentially a 5-domain targeted fetcher.
- Scrapy's async architecture (Twisted) is incompatible with the `asyncio`-based httpx if mixing is needed.
- The project's one-shot scraper model (run once, index, done) does not need Scrapy's resumable crawl state.

**Do NOT use Selenium/Playwright** — all target sites render content server-side. JavaScript rendering is unnecessary and would slow scraping 10x.

**Confidence:** HIGH for this use case. MEDIUM for blog-specific parsing (site structures may change).

---

### Data Storage

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| JSON (newline-delimited) | — | Scraper output format | Intermediate storage between scraper and indexer |
| Elasticsearch indices | 8.x | Primary search store | Single source of truth for search |
| SQLite | 3.x (stdlib) | Scraper state tracking only | Track which URLs have been scraped to support re-runs without re-fetching |

**Storage strategy: JSON files as scraper output, direct Elasticsearch indexing, SQLite for scraper state only.**

Do NOT maintain a separate relational database (PostgreSQL, SQLite) as a mirror of the Elasticsearch index. Reasons:
- Elasticsearch is already a persistent store (data lives in `$ES_HOME/data/`). Maintaining a sync between two databases adds complexity with no payoff.
- The 2 GB constraint applies to the Elasticsearch index size, not an additional database. Storing the same text twice would double storage consumption.
- NitroFind has no relational query needs — there are no JOINs, no transactions, no foreign keys. Elasticsearch's document model is the right fit.

**Workflow:**
1. Scraper runs → writes structured JSON files to `./data/raw/` (newline-delimited JSON, one file per source domain)
2. Indexer script reads JSON files → bulk-indexes into Elasticsearch via `elasticsearch-py` bulk API
3. SQLite `scraper_state.db` tracks `(url, scraped_at, status)` to avoid re-fetching on re-runs

**Compression:** Store article body text compressed in Elasticsearch? No — store raw text in ES (it handles its own compression of stored fields via LZ4). Keep raw JSON files after indexing as a backup/re-index safety net.

**Confidence:** HIGH

---

### App Packaging

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PyInstaller | 6.x (latest) | Package Python app into standalone executable | Broadest PyQt6 hook support, largest community |

**Use PyInstaller, not cx_Freeze or Nuitka.**

PyInstaller 6.x has explicit hooks for PyQt6 (`hook-PyQt6.*.py` in the hook library) that automatically bundle Qt plugins, platform DLLs, and image format handlers. cx_Freeze lacks mature PyQt6 hooks and requires manual specification of Qt resources. Nuitka is a compiler (produces native code) — useful for IP protection or startup speed, but massively increases build complexity and is not warranted for a local desktop tool.

**Important caveat — Elasticsearch is NOT bundled in the PyInstaller package.**

Elasticsearch is a Java process (JVM). PyInstaller bundles Python. The correct distribution model:
- Ship PyInstaller-packaged Python app as the "NitroFind" executable.
- Elasticsearch is installed separately by the user (or via a setup script that downloads and configures the ES 8.x archive). 
- A `launch.py` / startup script checks if an ES process is running on `localhost:9200`, starts it if not, and waits for it to be healthy before opening the UI.

This is the only viable model. Bundling the JVM inside a PyInstaller exe would produce a 500 MB+ executable, defeat the purpose of PyInstaller, and break ES's internal path resolution.

**Confidence:** HIGH for PyInstaller choice. HIGH for the "ES runs separately" model.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Search engine | Elasticsearch 8.x | Meilisearch | No function_score equivalent; cannot implement composite decay+boost scoring |
| Search engine | Elasticsearch 8.x | Typesense | Same limitation as Meilisearch on multi-function scoring |
| Search engine | Elasticsearch 8.x | OpenSearch | Would work technically; thinner Python ecosystem and docs; stack is fixed to ES anyway |
| Search engine | Elasticsearch 8.x | Elasticsearch 9.x | Aggregation regression reports; no benefit for this use case; adds upgrade risk |
| UI | PyQt6 | PyQt5 | Outdated Qt5 renderer; no new features; PyQt6 is the 2025 standard for new projects |
| UI | PyQt6 | PySide6 | Nearly identical API; PyQt6 has slightly better community documentation for PyPI install; either works |
| UI | PyQt6 | Tkinter | Tkinter cannot produce a "browser-like" fluid search experience; no threading primitives |
| Scraper | requests + BS4 | Scrapy | Overkill for fixed-target scraping; Twisted async conflicts with project architecture |
| Scraper | requests + BS4 | Selenium | Target sites are server-rendered; JS rendering unnecessary and slow |
| Data store | ES only + SQLite state | PostgreSQL mirror | Doubles storage; no relational query need; violates 2 GB constraint |
| Packaging | PyInstaller | cx_Freeze | Immature PyQt6 hooks; manual Qt resource specification |
| Packaging | PyInstaller | Nuitka | Compilation complexity unjustified; no IP protection need for local tool |
| ES client | elasticsearch==8.x | elasticsearch-dsl (standalone) | Deprecated; now merged into core client at 8.18.0 |

---

## Installation

```bash
# Create environment (Python 3.11 recommended)
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Core search client (pin to ES8 major)
pip install "elasticsearch>=8,<9"

# Desktop UI
pip install PyQt6

# Modern UI theme
pip install qt-material

# Scraper
pip install requests httpx "beautifulsoup4>=4.12" lxml mediawikiapi

# Packaging (dev only)
pip install pyinstaller
```

Elasticsearch 8.x server: Download the archive from https://www.elastic.co/downloads/past-releases#elasticsearch
and configure `config/elasticsearch.yml` with:
```yaml
network.host: 127.0.0.1
xpack.security.enabled: false
cluster.name: nitrofind
node.name: nitrofind-local
```
And `config/jvm.options.d/heap.options`:
```
-Xms512m
-Xmx1g
```

---

## Sources

- Elasticsearch release notes (current): https://www.elastic.co/docs/release-notes/elasticsearch
- elasticsearch-py on PyPI: https://pypi.org/project/elasticsearch/
- PyQt6 on PyPI: https://pypi.org/project/PyQt6/
- PyQt5 vs PyQt6 guide: https://www.pythonguis.com/faq/pyqt5-vs-pyqt6/
- PyInstaller + PyQt6 packaging: https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/
- Meilisearch function scoring roadmap: https://roadmap.meilisearch.com/c/149-scoring-function
- Elasticsearch JVM heap configuration: https://www.elastic.co/docs/reference/elasticsearch/jvm-settings
- Scrapy vs BeautifulSoup comparison: https://oxylabs.io/blog/scrapy-vs-beautifulsoup
- Elasticsearch 9.0 release notes: https://www.elastic.co/blog/whats-new-elastic-search-9-0-0
- QThreadPool multithreading in PyQt6: https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/
