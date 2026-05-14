# Phase 2: Data Pipeline (Scraper + Indexer) - Research

**Researched:** 2026-05-13
**Domain:** Wikipedia MediaWiki API, BeautifulSoup4 blog parsing, Elasticsearch 8.x bulk indexing, SQLite state tracking
**Confidence:** MEDIUM-HIGH (Wikipedia stack: HIGH; blog selector specifics: LOW — requires live HTML inspection at implementation time)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Walk Wikipedia category trees recursively, starting from root car categories defined in a config file. Depth limit: 2 levels from each root category.
- **D-02:** Filter articles before indexing: only index pages that have an infobox (`has_infobox = true`). Infobox presence distinguishes structured car articles from disambiguation pages, list articles, and stubs.
- **D-03:** Root categories stored in `config/scraper.yaml` — not hardcoded. User can adjust without touching source code.
- **D-04:** Single entrypoint (`scraper.py` or `scripts/scraper.py`). Optional source flags: `--wikipedia`, `--blogs`, `--all` (default).
- **D-05:** Progress reporting via live logging to stdout: current category, running article count, current index size estimate.
- **D-06:** Resume support via SQLite state tracking. Re-runs skip already-indexed articles.
- **L-01:** Wikipedia source: MediaWiki API only — no raw HTML parsing. Use `mediawikiapi` library.
- **L-02:** Blog source: BeautifulSoup4 + `requests`. At least one of: Car and Driver, Hagerty, Hemmings, Road & Track.
- **L-03:** MediaWiki page ID used as ES document `_id` for Wikipedia articles.
- **L-04:** Scraper halts and logs warning when index approaches 1.8 GB.
- **L-05:** `body` field must contain plain text only — no HTML tags.
- **L-06:** `excerpt` capped at 300 characters.
- **L-07:** `era_bucket` derived from `production_start` via `f"{(year // 10) * 10}s"`. Set to `"Unknown"` when `production_start` is missing.
- **L-08:** ES index schema is fully locked — see `nitrofind/es_schema.py` `CAR_ARTICLES_MAPPING`.

### Claude's Discretion

*(None declared — all implementation decisions were either locked or resolved during context gathering.)*

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCRP-01 | Scraper fetches car articles from Wikipedia using the MediaWiki API (structured JSON, not HTML parsing) | mediawikiapi 1.3: `category_members()` + `page()` provide all needed access; `custom_query` enables raw API calls for pagination |
| SCRP-02 | Scraper fetches articles from at least one automotive blog using BeautifulSoup4 | Hagerty is the recommended primary target (free articles accessible); CSS selectors require live inspection at implementation time |
| SCRP-03 | MediaWiki page ID used as ES document `_id` to prevent duplicates | `WikipediaPage.pageid` property returns int; ES bulk action format `{"_id": page.pageid}` enforces this |
| SCRP-04 | Scraper stops indexing and logs warning when index approaches 1.8 GB | `client.indices.stats(metric="store")` returns `primaries.store.size_in_bytes`; compare against `1_800_000_000` threshold |
</phase_requirements>

---

## Summary

Phase 2 builds a one-shot CLI scraper that populates the locked `car_articles` Elasticsearch index with clean, deduplicated automotive content from Wikipedia and at least one automotive blog. The scraper must walk Wikipedia's category trees using the MediaWiki Action API (via `mediawikiapi`), filter for infobox-equipped articles, strip all HTML from body text, generate 300-character excerpts, track progress in SQLite to support interrupted runs, and halt before the index exceeds 2 GB.

The Wikipedia pipeline is well-understood and has HIGH confidence: `mediawikiapi` 1.3 provides `category_members(cmtype="subcat")` for tree walking and `page(pageid=...)` for article retrieval; `WikipediaPage.pageid` delivers the deduplication key; `WikipediaPage.infobox` returns a dict (empty dict `{}` when absent, not `None`). The blog pipeline has MEDIUM-LOW confidence on CSS selectors because automotive media sites actively update layouts and several deploy Cloudflare bot protection. Hagerty (`hagerty.com/media`) is the recommended first blog target due to its broad free-access article catalog; Car and Driver is a backup if Hagerty proves inaccessible.

Elasticsearch bulk indexing via `helpers.streaming_bulk()` with `_id` set to the Wikipedia page ID gives automatic upsert-based deduplication — re-running the scraper produces zero net document-count change. Index size monitoring uses `client.indices.stats(metric="store")` returning `primaries.store.size_in_bytes`; a check every N documents (e.g., every 50 bulk actions) with a 1.8 GB halt threshold satisfies SCRP-04.

**Primary recommendation:** Build the Wikipedia pipeline first (it is deterministic and can reach 1,000+ infobox articles from 2-level category walks), then add one blog target (Hagerty preferred) with a fallback plan if bot protection blocks the crawler.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Wikipedia article retrieval | CLI / Scraper process | MediaWiki API (remote, internet) | One-shot CLI fetches from Wikipedia during scrape run; all data stored locally afterward |
| Blog article retrieval | CLI / Scraper process | Blog site HTTP (remote, internet) | Same pattern as Wikipedia; internet required only at scrape time |
| HTML stripping / text cleaning | CLI / Scraper process | — | Data transformation happens in the scraper before documents are sent to ES |
| Bulk document indexing | Elasticsearch (localhost) | elasticsearch-py client | ES owns persistence; client submits batches |
| Deduplication | Elasticsearch (localhost) | — | `_id`-based upsert means ES enforces uniqueness at the storage layer |
| Size guard (1.8 GB halt) | CLI / Scraper process | Elasticsearch stats API | Scraper polls ES stats; decision to halt lives in scraper logic |
| Scraper state / resume | SQLite (local file) | — | Lightweight stdlib solution; no separate DB process required |
| Config (root categories) | YAML file (`config/scraper.yaml`) | — | User-editable, not in source code |
| Infobox detection / extraction | CLI / Scraper process | mediawikiapi WikipediaPage | `page.infobox` returns dict; emptiness test determines `has_infobox` |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mediawikiapi | 1.3 | Wikipedia category walking + page retrieval | Locked by CLAUDE.md; wraps MediaWiki Action API; provides `.pageid`, `.infobox`, `.content`, `.category_members()` |
| elasticsearch | 8.19.3 | ES bulk indexing + stats queries | Already in `requirements.txt`; locked to 8.x per CLAUDE.md |
| beautifulsoup4 | 4.14.3 | Blog HTML parsing — extract article body text | Locked by CLAUDE.md; `get_text(strip=True)` removes all tags |
| lxml | 6.1.0 | BS4 parser backend | Faster than `html.parser` for large pages; already listed in CLAUDE.md stack |
| requests | 2.34.1 | HTTP fetching for blog targets | Already in `requirements.txt`; synchronous, deliberate rate-limiting friendly |
| pyyaml | 6.0.3 | Load `config/scraper.yaml` | Stdlib-quality YAML; `yaml.safe_load()` for config; no code execution risk |
| sqlite3 | stdlib | Scraper state DB | Zero-dependency; already in Python stdlib; single-threaded scraper has no concurrency issue |

[VERIFIED: PyPI registry — mediawikiapi 1.3, beautifulsoup4 4.14.3, lxml 6.1.0, requests 2.34.1, pyyaml 6.0.3]
[VERIFIED: requirements.txt — elasticsearch 8.19.3, requests 2.34.0 already pinned in lockfile]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| elasticsearch.helpers | (bundled with elasticsearch 8.x) | `streaming_bulk()` for batched upsert indexing | Use instead of per-document `client.index()` calls |
| logging (stdlib) | — | Progress reporting to stdout per D-05 | `logging.basicConfig(level=INFO)` + `logger.info()` for category/count/size lines |
| argparse (stdlib) | — | CLI flags `--wikipedia`, `--blogs`, `--all` per D-04 | Standard library; no external dep needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| mediawikiapi | Raw `requests` to MediaWiki Action API | More control over pagination; but mediawikiapi already wraps this correctly for the features we need |
| mediawikiapi | pywikibot | Pywikibot is more feature-complete but requires a separate config/login setup; overkill for read-only scraping |
| streaming_bulk | Per-document `client.index()` | Per-document calls are 10-100x slower; streaming_bulk is the correct tool for bulk ingest |
| pyyaml | tomllib (stdlib Python 3.11+) | TOML is also valid; YAML was chosen in CONTEXT.md (D-03 references `scraper.yaml`) |

**Installation (new packages to add to requirements.in):**
```bash
mediawikiapi==1.3
pyyaml>=6.0,<7
```

**Version verification:** Versions above confirmed against PyPI registry on 2026-05-13.

---

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────┐
                          │         scraper.py (CLI)            │
                          │  args: --wikipedia|--blogs|--all    │
                          └───────────────┬─────────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
   ┌──────────────────┐       ┌──────────────────────┐   ┌───────────────────┐
   │  config/          │       │  SQLite state DB     │   │  ES size check    │
   │  scraper.yaml     │       │  data/scraper_state  │   │  (every 50 docs)  │
   │  (root categories)│       │  .db                 │   │  halt at 1.8 GB   │
   └────────┬─────────┘       └──────────┬───────────┘   └───────────┬───────┘
            │                            │                            │
            ▼                            │                            │
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                     WikipediaScraper                                     │
   │  1. Walk root categories (depth ≤ 2) via category_members(cmtype=subcat)│
   │  2. Get article IDs via category_members(cmtype=page)                    │
   │  3. Skip IDs already in SQLite state                                     │
   │  4. Fetch page: mediawikiapi.page(pageid=...)                            │
   │  5. Filter: skip if page.infobox == {}                                   │
   │  6. Clean: strip HTML, build excerpt, compute era_bucket                 │
   │  7. Yield document dict matching CAR_ARTICLES_MAPPING                    │
   └───────────────────────────┬──────────────────────────────────────────────┘
                               │
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                     BlogScraper (≥ 1 target)                             │
   │  1. Fetch article index/sitemap page from target blog                    │
   │  2. Extract article URLs from listing page                               │
   │  3. Skip URLs already in SQLite state                                    │
   │  4. Fetch each article page with requests + User-Agent header            │
   │  5. Parse with BS4 lxml: find article container, get_text(strip=True)   │
   │  6. Build excerpt (≤ 300 chars), set has_infobox=False for blog articles │
   │  7. Yield document dict                                                  │
   └───────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                     Indexer / BulkWriter                                 │
   │  - streaming_bulk(client, actions_generator, chunk_size=100)             │
   │  - Each action: {"_index": "car_articles", "_id": page_id, ...doc...}   │
   │  - After each chunk: record IDs in SQLite, check ES store size           │
   │  - If store.size_in_bytes >= 1_800_000_000: log warning, raise StopIter │
   └───────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Elasticsearch 8.x  │
                    │  localhost:9200      │
                    │  index: car_articles│
                    └─────────────────────┘
```

### Recommended Project Structure

```
scripts/
└── scraper.py           # CLI entrypoint (D-04)
config/
└── scraper.yaml         # Root categories + blog targets (D-03)
data/
└── scraper_state.db     # SQLite runtime state (created on first run)
nitrofind/
└── scraper/             # New package
    ├── __init__.py
    ├── wikipedia.py     # WikipediaScraper class
    ├── blogs.py         # BlogScraper class (one class per target site)
    ├── cleaner.py       # HTML-to-text, excerpt generation, era_bucket logic
    ├── state.py         # SQLiteStateManager (open, is_visited, mark_visited)
    └── indexer.py       # BulkIndexer: wraps streaming_bulk + size guard
```

### Pattern 1: Category Tree Walking with mediawikiapi

**What:** Recursively enumerate Wikipedia categories to depth 2, collecting article page IDs.
**When to use:** Building the initial set of Wikipedia article IDs to fetch.

```python
# Source: mediawikiapi 1.3 API + MediaWiki API:Categorymembers docs
from mediawikiapi import MediaWikiAPI

wiki = MediaWikiAPI()
wiki.config.user_agent = "NitroFind/1.0 (nullsecurity1337@gmail.com)"

def walk_category(category_title: str, depth: int, max_depth: int = 2) -> list[int]:
    """Return article pageids within category tree to max_depth."""
    # Get article-type members (cmtype='page' excludes subcategories and files)
    article_titles = wiki.category_members(
        title=category_title, cmtype="page", cmlimit=500
    )
    # mediawikiapi.category_members returns titles; we need pageids
    # Use custom_query to get pageid alongside title in one call
    page_ids = []
    for title in article_titles:
        try:
            p = wiki.page(title=title, auto_suggest=False)
            page_ids.append(p.pageid)
        except Exception:
            continue

    if depth < max_depth:
        subcats = wiki.category_members(
            title=category_title, cmtype="subcat", cmlimit=500
        )
        for subcat in subcats:
            page_ids.extend(walk_category(subcat, depth + 1, max_depth))

    return page_ids
```

**Important:** `mediawikiapi.category_members()` with `follow_continue=False` returns only up to `cmlimit` results. Set `cmlimit=500` (MediaWiki API max for non-bots is 500) to minimize round-trips. The library's `category_members()` does not expose the raw `cmcontinue` pagination token — for exhaustive category walking, use `custom_query` or raw `requests` to the MediaWiki API directly. [VERIFIED: mediawikiapi 1.3 source, GitHub lehinevych/MediaWikiAPI]

**Alternative for large categories (>500 members) — use `custom_query`:**

```python
# Source: MediaWiki API:Categorymembers documentation (mediawiki.org)
def get_all_category_members_raw(session, category_title: str) -> list[dict]:
    """Paginate through all members using cmcontinue token."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_title,
        "cmtype": "page",
        "cmprop": "ids|title",
        "cmlimit": "500",
        "format": "json",
    }
    results = []
    while True:
        resp = session.get(url, params=params).json()
        results.extend(resp["query"]["categorymembers"])
        if "continue" not in resp:
            break
        params["cmcontinue"] = resp["continue"]["cmcontinue"]
    return results  # each item: {"pageid": int, "title": str}
```

### Pattern 2: Article Fetch + Infobox Filter

**What:** Fetch a Wikipedia page by ID, test for infobox presence, extract structured data.
**When to use:** After collecting page IDs from category walk, before indexing.

```python
# Source: mediawikiapi 1.3 WikipediaPage API
def fetch_and_filter(wiki: MediaWikiAPI, pageid: int) -> dict | None:
    """Returns document dict or None if article should be skipped."""
    import time
    try:
        page = wiki.page(pageid=pageid, auto_suggest=False)
    except Exception:
        return None

    # D-02: filter articles without infobox
    # WikipediaPage.infobox returns {} (empty dict) when no infobox exists
    if not page.infobox:
        return None

    body_text = page.content  # plain text; mediawikiapi strips wiki markup
    word_count = len(body_text.split())
    excerpt = body_text[:300].rsplit(" ", 1)[0]  # L-06: max 300 chars, no mid-word cut

    # Extract infobox fields for automotive facets
    infobox = page.infobox  # Dict[str, Any]
    production_start = parse_year(infobox.get("production", "") or infobox.get("years", ""))
    era_bucket = f"{(production_start // 10) * 10}s" if production_start else "Unknown"  # L-07

    return {
        "title": page.title,
        "url": page.url,
        "source_domain": "en.wikipedia.org",
        "article_id": str(page.pageid),
        "scraped_at": datetime.utcnow().isoformat(),
        "body": body_text,
        "excerpt": excerpt,
        "word_count": word_count,
        "has_infobox": True,
        "image_count": len(page.images),
        "manufacturer": infobox.get("manufacturer", ""),
        "production_start": production_start,
        "era_bucket": era_bucket,
        "specs": infobox,  # flattened ES type handles arbitrary shape
    }

    time.sleep(0.5)  # MediaWiki etiquette: serial requests, no hammering
```

[VERIFIED: mediawikiapi 1.3 source — `page.pageid` (int), `page.infobox` (dict, empty when absent), `page.content` (plain text), `page.images` (list)]

### Pattern 3: ES Bulk Indexing with Size Guard

**What:** Stream documents into ES in chunks of 100, checking index size every chunk, halting at 1.8 GB.
**When to use:** The indexer layer — wraps `streaming_bulk`.

```python
# Source: elasticsearch-py 8.x helpers docs
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

SIZE_HALT_BYTES = 1_800_000_000  # 1.8 GB (SCRP-04)
CHECK_EVERY_N_DOCS = 100

def index_documents(client: Elasticsearch, actions_generator):
    """Bulk-index documents, halting if index approaches 1.8 GB."""
    doc_count = 0
    for ok, info in streaming_bulk(
        client,
        actions_generator,
        chunk_size=100,
        raise_on_error=False,
        raise_on_exception=False,
    ):
        if not ok:
            logger.warning("Bulk error: %s", info)
            continue
        doc_count += 1
        if doc_count % CHECK_EVERY_N_DOCS == 0:
            if _index_size_bytes(client) >= SIZE_HALT_BYTES:
                logger.warning(
                    "Index approaching 2 GB limit (%.2f GB). Halting scraper. "
                    "SCRP-04 size guard triggered.",
                    SIZE_HALT_BYTES / 1e9,
                )
                return  # Generator is abandoned; no further indexing

def _index_size_bytes(client: Elasticsearch) -> int:
    """Return primary shard store size in bytes for car_articles."""
    stats = client.indices.stats(index="car_articles", metric="store")
    return stats["indices"]["car_articles"]["primaries"]["store"]["size_in_bytes"]
```

[VERIFIED: elasticsearch-py 8.x helpers docs — streaming_bulk signature; Elasticsearch 8.19 API docs — indices.stats response structure]

### Pattern 4: ES Bulk Action Format with _id Deduplication

**What:** Format a document as an ES bulk action that upserts by _id to prevent duplicates.
**When to use:** Building the actions generator fed to `streaming_bulk`.

```python
# Source: elasticsearch-py 8.x helpers documentation
def make_action(doc: dict, doc_id: str) -> dict:
    """Build a streaming_bulk-compatible action dict."""
    action = {"_index": "car_articles", "_id": doc_id}
    action.update(doc)
    return action

# Usage:
actions = (
    make_action(doc, doc["article_id"])
    for doc in fetch_wikipedia_articles()
)
```

**Why this works for deduplication:** When ES receives an index request with an existing `_id`, it updates (overwrites) the document rather than creating a duplicate. Running the scraper twice never increases the document count. [VERIFIED: Elasticsearch docs — index operation with explicit `_id`]

### Pattern 5: SQLite State Tracking

**What:** Track visited page IDs/URLs so interrupted runs resume without re-fetching.
**When to use:** Before fetching each article — check if already visited; after indexing — mark as visited.

```python
# Source: Python stdlib sqlite3 + CONTEXT.md D-06
import sqlite3

class ScraperState:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS visited (
                id TEXT PRIMARY KEY,   -- pageid (int as str) or URL
                source TEXT NOT NULL,  -- 'wikipedia' | 'hagerty' | etc.
                indexed_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def is_visited(self, item_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM visited WHERE id = ?", (item_id,)
        )
        return cur.fetchone() is not None

    def mark_visited(self, item_id: str, source: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO visited (id, source, indexed_at) VALUES (?, ?, datetime('now'))",
            (item_id, source),
        )
        self._conn.commit()
```

### Pattern 6: Blog Scraping with BeautifulSoup4

**What:** Fetch an automotive blog article page, extract clean body text.
**When to use:** For any blog target after obtaining the article URL.

```python
# Source: BeautifulSoup4 4.x docs; CLAUDE.md stack
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "NitroFind/1.0 (nullsecurity1337@gmail.com; personal offline research tool)",
}

def fetch_blog_article(url: str, article_container_selector: str) -> dict | None:
    """Fetch and parse one blog article. Returns document dict or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove known noise elements before extracting text
    for tag in soup.select("script, style, nav, footer, aside, .ad, .advertisement"):
        tag.decompose()

    container = soup.select_one(article_container_selector)
    if not container:
        return None

    # L-05: plain text only — get_text strips all HTML tags
    body_text = container.get_text(separator=" ", strip=True)
    # Collapse multiple whitespace
    import re
    body_text = re.sub(r"\s+", " ", body_text).strip()

    excerpt = body_text[:300].rsplit(" ", 1)[0]  # L-06

    return {
        "body": body_text,
        "excerpt": excerpt,
        "word_count": len(body_text.split()),
        "has_infobox": False,  # blog articles never have Wikipedia infoboxes
        # ... other fields populated from page metadata
    }
```

### Pattern 7: scraper.yaml Config File

```yaml
# config/scraper.yaml
wikipedia:
  root_categories:
    - "Category:Automobiles by manufacturer"
    - "Category:Cars by model year"
    - "Category:Sports cars"
    - "Category:Luxury vehicles"
    - "Category:Electric vehicles"
  max_depth: 2          # D-01: 2 levels from each root
  rate_limit_seconds: 0.5  # MediaWiki etiquette: serial requests

blogs:
  targets:
    - name: hagerty
      enabled: true
      base_url: "https://www.hagerty.com/media/"
      article_list_url: "https://www.hagerty.com/media/all-articles/"
      article_selector: "div.article-content"   # ASSUMED — verify at implementation
      listing_selector: "a.article-link"         # ASSUMED — verify at implementation
    - name: caranddriver
      enabled: false     # backup target — enable if hagerty blocked
      base_url: "https://www.caranddriver.com/"
      article_selector: "div.article-body-content"  # ASSUMED — verify at implementation
      listing_selector: "a.content-block"            # ASSUMED — verify at implementation
```

### Anti-Patterns to Avoid

- **Per-document ES indexing in a loop:** Using `client.index()` for each document is 10-100x slower than `streaming_bulk`. Never call `client.index()` inside the scraper's article loop.
- **HTML tags in body field:** ES `text` fields should contain only plain text. The field is analyzed, so raw HTML angle brackets appear literally in search and corrupt tokenization. Always call `get_text()` or use `page.content` (which is already plain text from mediawikiapi).
- **Ignoring `dynamic: "false"`:** The existing index mapping uses `dynamic: "false"`. Extra keys in a document dict are silently dropped by ES. Only include fields defined in `CAR_ARTICLES_MAPPING`.
- **Hardcoding Wikipedia category strings:** Violates D-03. All root categories must come from `config/scraper.yaml`.
- **Not setting a User-Agent on Wikipedia requests:** The MediaWiki API etiquette policy requires a meaningful User-Agent. Missing or generic User-Agent strings risk IP-level rate limiting.
- **Walking subcategories without a depth guard:** Wikipedia category trees are cyclic. Without a `visited_categories` set and depth limit, the walker recurses infinitely.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Batched bulk ES writes | Custom chunking loop | `elasticsearch.helpers.streaming_bulk` | Handles chunking, retries on 429, error reporting, memory-efficient generator consumption |
| HTML tag stripping | Custom regex tag removal | `BeautifulSoup.get_text(strip=True)` | Regex misses nested tags, malformed HTML, CDATA sections, script/style content |
| Wikipedia API pagination | Custom continue-token loop | mediawikiapi `category_members()` or `custom_query()` | Pagination token handling is error-prone; library handles it |
| Wikipedia rate limiting | Custom sleep logic | `time.sleep(0.5)` + serial requests (per MediaWiki etiquette) | Wikipedia does not require exponential backoff for read requests — serial with 0.5s delay is sufficient and safe |
| Config file parsing | `configparser` / custom INI parser | `yaml.safe_load()` | YAML supports lists natively (needed for `root_categories`); `safe_load` prevents arbitrary code execution |

**Key insight:** The ES helpers library, mediawikiapi's page retrieval, and BeautifulSoup's `get_text()` each handle a class of edge cases (HTML encoding, Unicode normalization, category continuation tokens) that custom implementations routinely miss on the first iteration.

---

## Common Pitfalls

### Pitfall 1: mediawikiapi `category_members()` Returns Titles, Not Page IDs

**What goes wrong:** `wiki.category_members(title="Category:Sports cars", cmtype="page")` returns a `List[str]` of page titles, not page IDs. Calling `wiki.page(title=t)` for each title triggers auto-suggest and redirect resolution, which can silently map multiple titles to the same underlying article (redirect trap).

**Why it happens:** The `mediawikiapi` library abstracts away page IDs in its `category_members()` return type for simplicity.

**How to avoid:** Use the raw `requests` MediaWiki API call with `cmprop=ids|title` to get both `pageid` and `title` simultaneously. Then fetch pages using `wiki.page(pageid=int_id, auto_suggest=False)`. Setting `auto_suggest=False` bypasses disambiguation and ensures you fetch the exact article you asked for.

**Warning signs:** Duplicate `article_id` values appearing in ES docs; document count not matching unique URL count.

### Pitfall 2: Wikipedia Infobox Dict Returns Empty `{}` for Articles Without Infoboxes — Not `None`

**What goes wrong:** Code checks `if page.infobox is None` and indexes disambiguation pages, list articles, and stubs — all of which lack infoboxes.

**Why it happens:** `WikipediaPage.infobox` always returns a dict (empty when no infobox is present). [VERIFIED: mediawikiapi 1.3 source inspection]

**How to avoid:** Check `if not page.infobox:` (treats both `None` and `{}` as false). Since infobox dict will always be a dict, the `not` check is the idiomatic Python test.

**Warning signs:** Has_infobox=True on articles whose titles are "List of ...", "... (disambiguation)", or similar.

### Pitfall 3: Blog Sites Return 403 / Cloudflare Challenge

**What goes wrong:** `requests.get(url)` returns HTTP 403 or an empty Cloudflare JS challenge page when scraping Hagerty or Car and Driver without a browser-like User-Agent.

**Why it happens:** Hagerty.com confirmed to return HTTP 403 on direct WebFetch. These sites use Cloudflare WAF, which inspects User-Agent, TLS fingerprints, and request headers.

**How to avoid:** Set a realistic browser-like `User-Agent` header. If 403 persists, fall back to the next target in the priority list (Car and Driver → Hemmings → Road & Track). Do NOT attempt Cloudflare bypass techniques — these violate robots.txt spirit and are legally risky.

**Fallback strategy:** If all four blog targets are inaccessible, the phase success criteria require only Wikipedia (1,000+ articles); blog indexing is "at least one" — if no blog is accessible, log a clear warning and complete with Wikipedia-only data. The phase reviewer will confirm.

**Warning signs:** Response status code 403; response body contains "Just a moment..." (Cloudflare) or minimal HTML without article content.

### Pitfall 4: Blog CSS Selectors Break Without Warning

**What goes wrong:** CSS selectors hardcoded at development time stop matching when the site redesigns.

**Why it happens:** Automotive media sites (Hagerty, Car and Driver) update templates periodically. Class names like `div.article-body` are CDN-served SPA bundles with hashed classnames.

**How to avoid:** Store selectors in `config/scraper.yaml` (not hardcoded). Fall back to semantic HTML selectors (`article`, `main`, `[role="main"]`) when class-based selectors fail. Log a WARNING if no article container is found for a URL, and skip that article rather than indexing an empty body.

**Warning signs:** `body` field contains navigation text, headers, footer content, or is extremely short (<100 chars) for what should be a feature article.

### Pitfall 5: ES `dynamic: "false"` Silently Drops Extra Fields

**What goes wrong:** Scraper builds a document dict with extra keys (e.g., `raw_infobox`, `debug_source`) that are not in `CAR_ARTICLES_MAPPING`. ES indexes the document without error, but those fields are silently discarded.

**Why it happens:** `dynamic: "false"` tells ES to ignore unknown fields — not reject them.

**How to avoid:** Validate document keys against `CAR_ARTICLES_MAPPING.properties.keys()` before bulk indexing during development. Remove any extra debug fields before shipping.

**Warning signs:** Fields that you expected to be searchable are missing from search results; `GET /car_articles/_mapping` does not list fields you added.

### Pitfall 6: Wikipedia Category Trees are Cyclic

**What goes wrong:** Category walker recurses infinitely because subcategory A → B → A is a valid Wikipedia structure.

**Why it happens:** Wikipedia's category graph has cycles. Without tracking visited categories, the walker keeps re-entering the same nodes.

**How to avoid:** Maintain a `visited_categories: set[str]` in the walker. Before recursing into a subcategory, check if it is already in the set; if so, skip.

**Warning signs:** Script runs indefinitely; SQLite visited table grows without bound; memory usage climbs continuously.

### Pitfall 7: `excerpt` Cuts Mid-Word

**What goes wrong:** `body_text[:300]` cuts at byte offset 300, which can land inside a multi-byte Unicode character or mid-word, producing a truncated excerpt.

**Why it happens:** Python string slicing by index does not respect word boundaries.

**How to avoid:** After slicing, trim back to the last space: `body_text[:300].rsplit(" ", 1)[0]`. This guarantees the excerpt ends on a word boundary and stays at or under 300 characters.

**Warning signs:** Excerpt field ends with a partial word or garbled Unicode character.

### Pitfall 8: Index Size Check Uses `total` Instead of `primaries`

**What goes wrong:** Code checks `total.store.size_in_bytes`, which includes replica shards. The NitroFind ES node runs with `number_of_replicas: 0` (set in `ensure_index()`), so `primaries` and `total` are equal — but if replicas are ever enabled, `total` will double-count.

**Why it happens:** Confusion between `primaries` and `total` in the ES stats response.

**How to avoid:** Always use `indices["car_articles"]["primaries"]["store"]["size_in_bytes"]` for the size guard. [VERIFIED: ES 8.19 indices stats API docs]

---

## Code Examples

### Verified: ES Index Size Check

```python
# Source: Elasticsearch 8.19 API docs — operation-indices-stats
def get_index_size_bytes(client: Elasticsearch, index: str = "car_articles") -> int:
    stats = client.indices.stats(index=index, metric="store")
    return stats["indices"][index]["primaries"]["store"]["size_in_bytes"]
```

### Verified: MediaWiki Category Members with Full Pagination

```python
# Source: MediaWiki API:Categorymembers documentation
def get_category_members_paginated(
    session: requests.Session,
    category_title: str,
    cmtype: str = "page",
) -> list[dict]:
    """Returns list of {pageid, title} dicts for all members."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_title,
        "cmtype": cmtype,
        "cmprop": "ids|title",
        "cmlimit": "500",
        "format": "json",
    }
    results = []
    while True:
        data = session.get(url, params=params).json()
        results.extend(data["query"]["categorymembers"])
        if "continue" not in data:
            break
        params["cmcontinue"] = data["continue"]["cmcontinue"]
        import time
        time.sleep(0.5)  # MediaWiki etiquette
    return results
```

### Verified: BeautifulSoup get_text for Plain Body

```python
# Source: BeautifulSoup4 4.x documentation
from bs4 import BeautifulSoup
import re

def extract_plain_text(html: str, container_selector: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    # Remove noise elements first
    for noise in soup.select("script, style, nav, footer, aside"):
        noise.decompose()
    container = soup.select_one(container_selector)
    if not container:
        return None
    raw = container.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", raw).strip()
```

### Verified: streaming_bulk Action Format

```python
# Source: elasticsearch-py 8.x helpers documentation
def build_wikipedia_action(doc: dict) -> dict:
    """Build a bulk action dict. _id set to pageid for deduplication (SCRP-03)."""
    action = {
        "_index": "car_articles",
        "_id": doc["article_id"],  # str(pageid) — L-03
    }
    action.update(doc)
    return action
```

---

## Runtime State Inventory

This phase does not rename, refactor, or migrate existing runtime state. Phase 2 creates new runtime artifacts:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — `car_articles` index exists but is empty (created idempotently by `ensure_index()` in Phase 1) | None; scraper populates it |
| Live service config | ES node already configured from Phase 1 (TLS off, security off, heap 512 MB) | None; scraper reads existing config |
| OS-registered state | None — Phase 1 did not register any OS-level tasks | None |
| Secrets/env vars | `ES_HOME` env var — established in Phase 1, unchanged | None |
| Build artifacts | None relevant to this phase | None |

**New runtime artifacts created by this phase:** `data/scraper_state.db` (SQLite file, created at runtime on first scraper invocation).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All scraper code | See note | 3.12.3 on WSL host | Project venv likely uses 3.11; confirm with `python --version` in venv |
| Elasticsearch 8.x | Index writing (SCRP-01–04) | Confirmed (Phase 1) | 8.18 | — |
| Internet access | Wikipedia/blog scraping (scrape time only) | ASSUMED (developer machine) | — | — |
| mediawikiapi | SCRP-01 | Not installed in project yet | 1.3 | — |
| pyyaml | Config file loading | Not installed in project yet | 6.0.3 | — |
| beautifulsoup4 | SCRP-02 blog parsing | Not in requirements.in | 4.14.3 | — |
| lxml | BS4 parser backend | Not in requirements.in | 6.1.0 | html.parser (slower) |

**Missing dependencies with no fallback (must add to requirements.in before Wave 1):**
- `mediawikiapi==1.3` — SCRP-01 is blocked without it
- `pyyaml>=6.0,<7` — Config loading blocked without it

**Missing dependencies with fallback:**
- `beautifulsoup4` and `lxml` — if `lxml` fails to install, `html.parser` can substitute (slower, less robust for malformed HTML)

**Note on Python version:** The WSL host runs Python 3.12.3 system-wide; the project venv may be pinned to 3.11 (per CLAUDE.md). Confirm the venv Python version before running. mediawikiapi 1.3 requires `>=3.9`, so both 3.11 and 3.12 are compatible.

---

## Blog Target Assessment

This section provides implementation-time guidance for selecting the primary blog target.

### Hagerty (`hagerty.com/media`) — RECOMMENDED FIRST ATTEMPT

**Access:** Has broad free article catalog (`/media/all-articles/`). Confirmed to return HTTP 403 on direct automated fetch without browser-like headers. [VERIFIED: WebFetch 403 on hagerty.com/media]

**Mitigation:** Set a realistic `User-Agent` header matching a real browser string. A fraction of Cloudflare-protected sites pass through with the correct header; others require TLS fingerprinting (not feasible with plain `requests`).

**Robots.txt summary:** Does not broadly disallow article scraping for general user agents; blocks media/image directories and specific admin paths. [CITED: hagerty.com/robots.txt via WebFetch]

**Fallback:** If Hagerty blocks with 403 after header tuning, switch to next target.

### Car and Driver (`caranddriver.com`) — BACKUP TARGET 1

**Access:** WebFetch returned connection error — likely Cloudflare. Robots.txt not retrievable via automated fetch. [VERIFIED: WebFetch connection error]

**Risk:** HIGH — likely protected by Cloudflare TLS fingerprinting. Requires live manual inspection to confirm accessibility.

### Hemmings (`hemmings.com`) — BACKUP TARGET 2

**Access:** WebFetch returned connection error. Note: Hemmings Classic Car magazine ceased publication February 2025; Hemmings Motor News content may be reduced. [VERIFIED: WebFetch connection error; CITED: classicoldsmobile.com forum post]

**Risk:** HIGH — similar bot protection concerns. Reduced article volume after magazine shutdown.

### Road & Track (`roadandtrack.com`) — BACKUP TARGET 3

**Access:** Not verified directly. Known to operate under Hearst Publishing which uses aggressive bot protection.

**Risk:** HIGH — likely behind authentication/subscription wall for full content.

### Decision Guidance for Planner

The plan should:
1. Attempt Hagerty first with browser-like headers
2. If Hagerty 403s consistently, attempt Car and Driver
3. If both fail, flag for human review — Wikipedia-only pass satisfies the minimum 1,000 article success criterion; blog requirement is "at least one" and may need a manual inspection sprint first

CSS selectors for all blog targets are `[ASSUMED]` and **must be verified by live HTML inspection** at implementation time. Store selectors in `config/scraper.yaml`, not hardcode. The planner should budget a manual inspection step (not automated) to capture current selectors.

---

## Wikipedia Root Category Recommendations

Based on research into Wikipedia's category structure for cars:

```yaml
# Recommended root categories for config/scraper.yaml
# Source: Wikipedia Category:Cars structure research [CITED: en.wikipedia.org/wiki/Category:Cars]
root_categories:
  - "Category:Automobiles by manufacturer"   # Manufacturer-organized; broad coverage
  - "Category:Car models"                    # Individual model articles
  - "Category:Sports cars"                   # Enthusiast-focused; high infobox density
  - "Category:Luxury vehicles"               # Well-documented articles
  - "Category:Cars by year of introduction"  # Temporal coverage; many model articles
```

**Scale estimate:** At depth=2 with `cmlimit=500`, each root category walks up to 500 direct subcategories and up to 500 articles per subcategory. "Automobiles by manufacturer" alone has hundreds of manufacturer subcategories (Ford, Toyota, etc.), each containing 10–100+ model articles. Reaching 1,000 infobox-equipped articles is achievable within the first two root categories. [ASSUMED — based on Wikipedia category size knowledge; verify against actual API calls]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (from existing project setup) |
| Config file | `pytest.ini` (root-level, already exists) |
| Quick run command | `pytest tests/test_scraper/ -x -m "not integration"` |
| Full suite command | `pytest tests/ -x -m "not integration"` |
| Integration marker | `@pytest.mark.integration` (already defined in pytest.ini) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCRP-01 | `walk_category()` returns page IDs for a mocked category response | unit | `pytest tests/test_scraper/test_wikipedia.py -x` | Wave 0 |
| SCRP-01 | `fetch_and_filter()` returns `None` for a page with empty infobox | unit | `pytest tests/test_scraper/test_wikipedia.py -x` | Wave 0 |
| SCRP-01 | `fetch_and_filter()` returns correct document dict for page with infobox | unit | `pytest tests/test_scraper/test_wikipedia.py -x` | Wave 0 |
| SCRP-02 | `extract_plain_text()` returns no HTML tags in output | unit | `pytest tests/test_scraper/test_cleaner.py -x` | Wave 0 |
| SCRP-02 | Blog fetcher returns `None` gracefully on HTTP 403 | unit | `pytest tests/test_scraper/test_blogs.py -x` | Wave 0 |
| SCRP-03 | Indexing same article twice produces no duplicate count increase | integration | `pytest tests/test_scraper/test_indexer.py -x -m integration` | Wave 0 |
| SCRP-04 | `index_documents()` halts and logs warning before 1.8 GB is exceeded | unit | `pytest tests/test_scraper/test_indexer.py -x` | Wave 0 |
| SCHEMA-03 | `excerpt` field is always 300 chars or fewer in generated docs | unit | `pytest tests/test_scraper/test_cleaner.py -x` | Wave 0 |
| SCHEMA-03 | `body` field contains no HTML tags (no `<` or `>` characters) | unit | `pytest tests/test_scraper/test_cleaner.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_scraper/ -x -m "not integration"`
- **Per wave merge:** `pytest tests/ -x -m "not integration"`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_scraper/__init__.py` — package init
- [ ] `tests/test_scraper/test_wikipedia.py` — covers SCRP-01 (category walk, infobox filter, page fetch)
- [ ] `tests/test_scraper/test_blogs.py` — covers SCRP-02 (blog fetch, 403 handling)
- [ ] `tests/test_scraper/test_cleaner.py` — covers SCHEMA-03 (HTML strip, excerpt length)
- [ ] `tests/test_scraper/test_indexer.py` — covers SCRP-03 (deduplication), SCRP-04 (size halt)
- [ ] `tests/test_scraper/test_state.py` — covers SQLite state: is_visited, mark_visited, resume logic

**Mocking strategy:** Use `unittest.mock.patch` to mock `mediawikiapi.MediaWikiAPI` page/category calls with pre-built fixture dicts. Use `requests-mock` or `responses` for blog HTTP calls. ES integration tests require live ES node (mark with `@pytest.mark.integration`).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Hagerty articles are accessible with a browser-like User-Agent header (no TLS fingerprinting block) | Blog Target Assessment | If wrong: need to switch to a different blog target; additional manual inspection sprint required |
| A2 | CSS selectors in `config/scraper.yaml` (e.g., `div.article-content` for Hagerty) match current site structure | Pattern 7 / Blog Target Assessment | If wrong: blog scraper returns empty body; selectors must be manually inspected and updated before implementation |
| A3 | Wikipedia root categories `"Category:Automobiles by manufacturer"` and `"Category:Car models"` contain 1,000+ infobox-equipped articles at depth=2 | Wikipedia Root Category Recommendations | If wrong: need to add more root categories or increase max_depth to 3 |
| A4 | The developer machine has internet access during scrape runs (not restricted) | Environment Availability | If wrong: scraper cannot fetch Wikipedia or blogs; must be run from a machine with internet access |
| A5 | mediawikiapi 1.3 `WikipediaPage.infobox` returns `{}` (empty dict) when no infobox exists, not `None` | Pattern 2 / Pitfall 2 | If wrong: `if not page.infobox` check still works for `None`; low risk |
| A6 | Project venv uses Python 3.11 (per CLAUDE.md) even though system Python is 3.12.3 | Environment Availability | If wrong: mediawikiapi 1.3 still works on 3.12; low risk |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `elasticsearch-dsl` as separate pip package | Merged into `elasticsearch` core at 8.18.0 | ES 8.18 (2024) | Do NOT pip install `elasticsearch-dsl` separately — already bundled |
| `wiki.page(title=...)` for all article fetches | `wiki.page(pageid=int_id, auto_suggest=False)` | Best practice established | Avoids redirect-resolution ambiguity and auto-suggest misfires |
| Raw `requests` to MediaWiki API for category walking | `mediawikiapi.category_members()` for simple cases; raw `requests` + `cmcontinue` loop for large categories (>500 members) | — | Hybrid approach gives simplicity for small categories, correctness for large ones |

**Deprecated/outdated:**
- `elasticsearch-dsl` (standalone pip install): Deprecated. Redirect to core client. Do not install separately — importing from it still works but is a dead-end.
- `html.parser` for large Wikipedia HTML pages: Functionally works but 2-4x slower than `lxml`; use `lxml` as the BS4 parser.
- `pymediawiki` (PyPI package `pymediawiki`): Different library from `mediawikiapi`. CLAUDE.md specifies `mediawikiapi` — do not substitute.

---

## Open Questions (RESOLVED)

1. **Which blog target is accessible from the developer's network?**
   - What we know: Hagerty and Car and Driver both returned non-200 on automated WebFetch; robots.txt confirms article scraping is not broadly blocked
   - What's unclear: Whether a browser-like User-Agent alone is sufficient, or TLS fingerprinting makes all four targets inaccessible without a headless browser
   - Recommendation: Wave 1 should include a manual inspection task — developer opens browser devtools, identifies article container selector, confirms accessibility with `requests` + User-Agent before building the parser
   - RESOLVED: Plan 02-04 Task 1 is a human-verify checkpoint that requires the developer to verify the target before implementation proceeds. Target selection is deferred to execution time per D-autonomy constraint. If all four targets fail manual inspection, the phase proceeds in Wikipedia-only mode (acceptable per phase success criterion — "at least one" blog OR documented Wikipedia-only completion).

2. **Are there enough infobox-equipped Wikipedia articles at depth=2 to reach 1,000+?**
   - What we know: `Category:Automobiles by manufacturer` and `Category:Car models` are large hierarchies with thousands of articles
   - What's unclear: The fraction of those articles that have infoboxes (estimate: 70-80% of car model articles have infoboxes, but unverified)
   - Recommendation: Early in implementation, run a sampling pass against 100 pages to measure infobox hit rate; adjust root categories if rate is below expectation
   - RESOLVED: Accepted as Assumption A3 (mitigated). Root categories and `max_depth` are configurable in `config/scraper.yaml` (Plan 02-01) — if depth=2 yields fewer than 1,000 articles, the developer adjusts `root_categories` or increases `max_depth` before re-running. No code change required; the YAML-driven design from D-03 absorbs this risk.

3. **Should the scraper normalize infobox field names for `manufacturer`, `production_start`, `production_end`?**
   - What we know: Wikipedia infobox field names vary across articles (`manufacturer` vs `Manufacturer` vs `produced by`); the `specs` field (flattened) stores raw key-value pairs
   - What's unclear: How reliable is the specific key name extraction for the SCHEMA-04 facet fields
   - Recommendation: Use `infobox.get("manufacturer") or infobox.get("Manufacturer") or ""` fallback chains; accept incomplete facet data gracefully rather than blocking indexing
   - RESOLVED: Plan 02-03 Task 1 uses multi-key fallback chains (e.g., `infobox.get("manufacturer") or infobox.get("Manufacturer") or ""` and `infobox.get("production") or infobox.get("years") or infobox.get("model years")`) rather than upfront normalization, keeping infobox data as-is in the `specs` flattened field and resolving synonyms at query time. Incomplete facet data is accepted gracefully — empty strings, not blocking indexing.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | CLI tool; no auth |
| V3 Session Management | No | Stateless CLI |
| V4 Access Control | No | Single-user local tool |
| V5 Input Validation | Yes | Validate `config/scraper.yaml` keys before use; reject non-integer `max_depth` values |
| V6 Cryptography | No | No secrets stored |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML config injection (arbitrary Python execution) | Tampering | Use `yaml.safe_load()` exclusively — never `yaml.load()` without Loader |
| Path traversal via `db_path` argument | Tampering | Validate `db_path` is within project directory before `sqlite3.connect()` |
| User-Agent header impersonation | — | Use honest User-Agent identifying NitroFind; do not impersonate browsers to bypass bot detection |
| ES index poisoning via unvalidated scraper input | Tampering | `dynamic: "false"` on index prevents field injection; strip HTML before indexing |

---

## Sources

### Primary (HIGH confidence)
- mediawikiapi 1.3 source on GitHub (lehinevych/MediaWikiAPI) — `category_members()`, `page()`, `WikipediaPage.infobox`, `WikipediaPage.pageid`, `WikipediaPage.content`
- MediaWiki API:Categorymembers (mediawiki.org) — pagination with `cmcontinue`, `cmtype`, `cmprop=ids|title`
- MediaWiki API:Etiquette (mediawiki.org) — User-Agent requirements, serial request recommendation, maxlag parameter
- elasticsearch-py 8.x helpers docs (elasticsearch-py.readthedocs.io) — `streaming_bulk()` parameters, action format, error handling
- Elasticsearch 8.19 API docs (elastic.co) — `indices.stats` response structure, `primaries.store.size_in_bytes`
- Existing project code: `nitrofind/es_schema.py`, `nitrofind/es_manager.py`, `requirements.txt` (Phase 1 outputs)

### Secondary (MEDIUM confidence)
- PyPI registry (2026-05-13) — mediawikiapi 1.3, beautifulsoup4 4.14.3, lxml 6.1.0, pyyaml 6.0.3, requests 2.34.1
- BeautifulSoup4 documentation — `get_text(separator, strip)` parameters
- Hagerty robots.txt (hagerty.com/robots.txt) — confirmed article paths not broadly disallowed
- en.wikipedia.org/wiki/Category:Cars — subcategory structure for root category selection

### Tertiary (LOW confidence — flagged as ASSUMED)
- Blog CSS selectors (A2): Not verified by direct HTML inspection
- 1,000+ infobox article count estimate (A3): Based on category size knowledge, not a measured API call
- Hagerty accessibility with User-Agent header (A1): Cannot confirm without live scraping attempt

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI; versions confirmed against registry
- Wikipedia API patterns: HIGH — verified against mediawikiapi source and official MediaWiki API docs
- ES bulk indexing patterns: HIGH — verified against elasticsearch-py 8.x docs and ES 8.19 API docs
- Blog CSS selectors: LOW — requires live HTML inspection at implementation time
- Blog accessibility (403 risk): LOW — multiple targets return connection errors; assume requires live testing

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 for stack/API findings; blog selector research should be re-validated immediately before implementation (site layouts change frequently)
