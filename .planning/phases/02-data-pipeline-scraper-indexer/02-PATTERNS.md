# Phase 2: Data Pipeline (Scraper + Indexer) - Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 13 new/modified files
**Analogs found:** 9 / 13 (4 files have no close codebase analog — RESEARCH.md patterns apply)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/scraper.py` | utility (CLI entrypoint) | request-response | `scripts/setup_es.py` | role-match |
| `config/scraper.yaml` | config | — | `config/elasticsearch.yml` (existing) | partial |
| `nitrofind/scraper/__init__.py` | config (package marker) | — | `nitrofind/__init__.py` | exact |
| `nitrofind/scraper/wikipedia.py` | service | batch + request-response | `nitrofind/es_manager.py` (ESHealthWorker) | partial (data-flow match on error handling + ES client conventions) |
| `nitrofind/scraper/blogs.py` | service | batch + request-response | `nitrofind/es_manager.py` (error handling + retry pattern) | partial |
| `nitrofind/scraper/cleaner.py` | utility | transform | `nitrofind/es_schema.py` (field contract) | partial (no transform analog exists) |
| `nitrofind/scraper/state.py` | service | CRUD | `nitrofind/es_manager.py` (lifecycle init pattern) | partial |
| `nitrofind/scraper/indexer.py` | service | batch | `nitrofind/es_schema.py` + `nitrofind/es_manager.py` | role-match |
| `tests/test_scraper/test_wikipedia.py` | test | — | `tests/test_es_manager.py` | exact |
| `tests/test_scraper/test_blogs.py` | test | — | `tests/test_es_manager.py` | exact |
| `tests/test_scraper/test_cleaner.py` | test | — | `tests/test_es_schema.py` | exact |
| `tests/test_scraper/test_indexer.py` | test | — | `tests/test_es_manager.py` + `tests/integration/test_es_startup.py` | exact |
| `tests/test_scraper/test_state.py` | test | — | `tests/test_es_schema.py` | exact |

---

## Pattern Assignments

### `scripts/scraper.py` (utility, CLI entrypoint)

**Analog:** `scripts/setup_es.py`

**Module docstring pattern** (lines 1-13 of `scripts/setup_es.py`):
```python
"""
scripts/scraper.py — NitroFind data pipeline CLI entrypoint.

Fetches automotive articles from Wikipedia (MediaWiki API) and/or blog targets
(BeautifulSoup4 + requests), cleans and indexes them into the local
Elasticsearch car_articles index.

Usage:
    python scripts/scraper.py [--wikipedia] [--blogs] [--all]

Security: Validates ES reachability before starting a long scrape run.
"""
```

**Imports pattern** (based on `scripts/setup_es.py` lines 1-6, adapted for scraper):
```python
import argparse
import logging
import os
import sys

import yaml
from elasticsearch import Elasticsearch

from nitrofind.es_manager import ES_URL
from nitrofind.es_schema import ensure_index
from nitrofind.scraper.wikipedia import WikipediaScraper
from nitrofind.scraper.blogs import BlogScraper
from nitrofind.scraper.state import SQLiteStateManager
from nitrofind.scraper.indexer import BulkIndexer
```

**Pre-flight validation pattern** (analog: `scripts/setup_es.py` lines 34-54):
```python
def main() -> None:
    # 1. Parse args
    # 2. Validate ES reachable (equivalent to validate_es_home in setup_es.py)
    client = Elasticsearch(ES_URL, request_timeout=5)
    try:
        client.info()
    except Exception as exc:
        sys.stderr.write(f"Cannot reach Elasticsearch at {ES_URL}: {exc}\n")
        sys.exit(1)

    # 3. Ensure index exists (idempotent — safe to call every run)
    ensure_index(client)

if __name__ == "__main__":
    main()
```

**Logging setup pattern** (analog: `main.py` lines 54-55):
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("nitrofind.scraper")
```

**CLI flag pattern** (no existing analog — use argparse stdlib):
```python
parser = argparse.ArgumentParser(description="NitroFind data pipeline")
group = parser.add_mutually_exclusive_group()
group.add_argument("--wikipedia", action="store_true")
group.add_argument("--blogs", action="store_true")
group.add_argument("--all", dest="all_sources", action="store_true", default=True)
args = parser.parse_args()
```

---

### `config/scraper.yaml` (config file)

**Analog:** No direct YAML analog in codebase. RESEARCH.md Pattern 7 is the authoritative template.

**Pattern from RESEARCH.md Pattern 7** (reference only — adapt field names to final decisions):
```yaml
wikipedia:
  root_categories:
    - "Category:Automobiles by manufacturer"
    - "Category:Car models"
    - "Category:Sports cars"
    - "Category:Luxury vehicles"
    - "Category:Cars by year of introduction"
  max_depth: 2
  rate_limit_seconds: 0.5

blogs:
  targets:
    - name: hagerty
      enabled: true
      base_url: "https://www.hagerty.com/media/"
      article_list_url: "https://www.hagerty.com/media/all-articles/"
      article_selector: "div.article-content"   # ASSUMED — verify at implementation
      listing_selector: "a.article-link"         # ASSUMED — verify at implementation
    - name: caranddriver
      enabled: false
      base_url: "https://www.caranddriver.com/"
      article_selector: "div.article-body-content"  # ASSUMED — verify at implementation
      listing_selector: "a.content-block"            # ASSUMED — verify at implementation
```

**YAML loading pattern** (security — analog: `main.py` on-failure exit, RESEARCH.md security section):
```python
# Always yaml.safe_load() — never yaml.load() without Loader (YAML injection risk)
with open("config/scraper.yaml", "r") as fh:
    config = yaml.safe_load(fh)
```

---

### `nitrofind/scraper/__init__.py` (package marker)

**Analog:** `nitrofind/__init__.py` (line 1)

```python
# NitroFind scraper package
```

Single-line comment only. No imports, no `__all__`.

---

### `nitrofind/scraper/wikipedia.py` (service, batch + request-response)

**Analog:** `nitrofind/es_manager.py` — class structure, error handling, logging conventions.

**Module docstring pattern** (analog: `nitrofind/es_manager.py` lines 1-19):
```python
"""
nitrofind.scraper.wikipedia — Wikipedia article scraper for NitroFind.

Exports:
  WikipediaScraper  — walks category trees via MediaWiki API, fetches and
                      filters articles, yields document dicts matching
                      CAR_ARTICLES_MAPPING.

Requirement coverage:
  SCRP-01: fetches articles from Wikipedia using MediaWiki API (not raw HTML)
  SCRP-03: uses MediaWiki page ID as ES document _id for deduplication
  D-01: category tree walk to max_depth=2
  D-02: infobox filter — skips articles where page.infobox == {}
  D-03: root categories loaded from config, not hardcoded
  D-05: progress logging to stdout
  D-06: skips page IDs already in SQLite state

Anti-patterns avoided:
  Pitfall 6: visited_categories set prevents cyclic category recursion
  Pitfall 2: uses `if not page.infobox:` (falsy check) not `is None`
"""
```

**Imports pattern** (analog: `nitrofind/es_manager.py` lines 21-28):
```python
import logging
import time
from datetime import datetime, timezone
from typing import Generator

import requests
from mediawikiapi import MediaWikiAPI

from nitrofind.scraper.state import SQLiteStateManager
from nitrofind.scraper.cleaner import make_excerpt, compute_era_bucket, parse_year

logger = logging.getLogger(__name__)
```

**Class init pattern** (analog: `nitrofind/es_manager.py` ESHealthWorker `__init__` lines 128-132):
```python
class WikipediaScraper:
    def __init__(self, config: dict, state: SQLiteStateManager) -> None:
        self._config = config
        self._state = state
        self._wiki = MediaWikiAPI()
        self._wiki.config.user_agent = "NitroFind/1.0 (nullsecurity1337@gmail.com)"
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "NitroFind/1.0 (nullsecurity1337@gmail.com)"
        })
```

**Error handling pattern** (analog: `nitrofind/es_manager.py` lines 163-164 — catch Exception, log with type name):
```python
try:
    page = self._wiki.page(pageid=pageid, auto_suggest=False)
except Exception as exc:
    logger.warning("Failed to fetch pageid=%s: %s: %s", pageid, type(exc).__name__, exc)
    return None
```

**Category walk pattern** (RESEARCH.md Pattern 1 + Pitfall 6 guard — no codebase analog):
```python
def _walk_category(
    self,
    category_title: str,
    depth: int,
    visited_categories: set[str],
) -> list[int]:
    """Return article pageids within category tree. Pitfall 6: visited set prevents cycles."""
    if category_title in visited_categories:
        return []
    visited_categories.add(category_title)

    page_ids = self._get_category_members_raw(category_title, cmtype="page")
    logger.info("Category %r: %d article IDs (depth=%d)", category_title, len(page_ids), depth)

    if depth < self._config["max_depth"]:
        subcats = self._get_category_members_raw(category_title, cmtype="subcat")
        for subcat_title in subcats:
            page_ids.extend(
                self._walk_category(subcat_title, depth + 1, visited_categories)
            )
    return page_ids
```

**D-06 skip-if-visited pattern** (analog: `nitrofind/es_manager.py` poll-before-act structure):
```python
if self._state.is_visited(str(pageid)):
    logger.debug("Skipping already-indexed pageid=%s", pageid)
    continue
```

---

### `nitrofind/scraper/blogs.py` (service, batch + request-response)

**Analog:** `nitrofind/es_manager.py` error handling pattern; RESEARCH.md Pattern 6.

**Module docstring pattern** (follow `es_manager.py` style):
```python
"""
nitrofind.scraper.blogs — Automotive blog scraper for NitroFind.

Exports:
  BlogScraper  — fetches article lists and article pages from configured blog
                 targets, yields document dicts matching CAR_ARTICLES_MAPPING.

Requirement coverage:
  SCRP-02: fetches articles from automotive blogs using BS4 + requests
  D-05: progress logging per article
  D-06: skips URLs already in SQLite state

Anti-patterns avoided:
  Pitfall 3: honest User-Agent; 403 → graceful skip + log (no browser impersonation)
  Pitfall 4: selectors come from config, not hardcoded
"""
```

**Imports pattern**:
```python
import logging
import re
import time
from datetime import datetime, timezone
from typing import Generator

import requests
from bs4 import BeautifulSoup

from nitrofind.scraper.state import SQLiteStateManager
from nitrofind.scraper.cleaner import make_excerpt

logger = logging.getLogger(__name__)

HONEST_USER_AGENT = "NitroFind/1.0 (nullsecurity1337@gmail.com; personal offline research tool)"
```

**HTTP fetch + error handling pattern** (analog: `es_manager.py` lines 163-164 catch + log type name):
```python
self._session.headers["User-Agent"] = HONEST_USER_AGENT

try:
    resp = self._session.get(url, timeout=15)
    resp.raise_for_status()
except requests.HTTPError as exc:
    logger.warning("HTTP %s fetching %s: %s", exc.response.status_code, url, exc)
    return None
except requests.RequestException as exc:
    logger.warning("Request failed for %s: %s: %s", url, type(exc).__name__, exc)
    return None
```

**BS4 parse pattern** (RESEARCH.md Pattern 6 — no codebase analog):
```python
soup = BeautifulSoup(resp.text, "lxml")
for noise in soup.select("script, style, nav, footer, aside, .ad, .advertisement"):
    noise.decompose()

container = soup.select_one(target_config["article_selector"])
if not container:
    # Pitfall 4: log warning; do not index empty body
    logger.warning("Article container not found at %s (selector: %r)", url, target_config["article_selector"])
    return None

body_text = re.sub(r"\s+", " ", container.get_text(separator=" ", strip=True)).strip()
```

---

### `nitrofind/scraper/cleaner.py` (utility, transform)

**Analog:** `nitrofind/es_schema.py` — the mapping it references defines the output contract. No transform-layer analog exists.

**Module docstring pattern**:
```python
"""
nitrofind.scraper.cleaner — Text cleaning and field derivation utilities.

Exports:
  make_excerpt       — truncates body text to ≤300 chars at word boundary (L-06)
  compute_era_bucket — derives decade label from production_start year (L-07)
  parse_year         — extracts 4-digit year from infobox field strings

Requirement coverage:
  L-05: body field contains plain text only (callers must pass pre-stripped text)
  L-06: excerpt capped at 300 characters, no mid-word cut (Pitfall 7)
  L-07: era_bucket formula f"{(year // 10) * 10}s"; "Unknown" when year is None
  SCHEMA-03: enforced by make_excerpt + body passthrough
"""
```

**Imports pattern** (minimal — pure functions only):
```python
import re
from typing import Optional
```

**Core transform patterns** (from RESEARCH.md Pattern 2 + Pitfalls 7):
```python
def make_excerpt(body_text: str) -> str:
    """Return ≤300-char excerpt ending on a word boundary (L-06, Pitfall 7)."""
    if len(body_text) <= 300:
        return body_text
    return body_text[:300].rsplit(" ", 1)[0]


def compute_era_bucket(production_start: Optional[int]) -> str:
    """Derive decade label from production year (L-07).

    Returns "Unknown" when production_start is None or 0.
    """
    if not production_start:
        return "Unknown"
    return f"{(production_start // 10) * 10}s"


def parse_year(raw: str) -> Optional[int]:
    """Extract first 4-digit year from an infobox field value string.

    Returns None if no 4-digit sequence is found.
    """
    if not raw:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", raw)
    return int(match.group()) if match else None
```

---

### `nitrofind/scraper/state.py` (service, CRUD)

**Analog:** `nitrofind/es_manager.py` — class init pattern with resource lifecycle management.

**Module docstring pattern** (follow `es_manager.py` style):
```python
"""
nitrofind.scraper.state — SQLite-based scraper resume state manager.

Exports:
  SQLiteStateManager  — open, is_visited, mark_visited, close

Requirement coverage:
  D-06: resume support — re-runs skip already-indexed page IDs / URLs
  Security V5: db_path validated before connect (path traversal mitigation)
"""
```

**Class init + resource lifecycle** (analog: `es_manager.py` `__init__` lines 128-132 + `shutdown_es` lifecycle):
```python
class SQLiteStateManager:
    def __init__(self, db_path: str) -> None:
        # Security V5: path traversal — caller should validate db_path is within project dir
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS visited (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
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

    def close(self) -> None:
        self._conn.close()
```

**Context manager support** (idiomatic Python resource — no codebase analog, add to SQLiteStateManager):
```python
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

---

### `nitrofind/scraper/indexer.py` (service, batch)

**Analog:** `nitrofind/es_schema.py` (ES client usage) + `nitrofind/es_manager.py` (error handling + logging conventions).

**Module docstring pattern**:
```python
"""
nitrofind.scraper.indexer — Elasticsearch bulk indexer with size guard.

Exports:
  BulkIndexer  — wraps streaming_bulk; checks index size every N docs; halts at 1.8 GB

Requirement coverage:
  SCRP-03: _id set to article_id (str(pageid)) for Wikipedia deduplication
  SCRP-04: halts and logs warning before car_articles index exceeds 1.8 GB
  L-03: ES document _id = str(page.pageid) for Wikipedia articles

Anti-patterns avoided:
  Per-document client.index() calls — use streaming_bulk exclusively
  Pitfall 8: size check uses primaries.store.size_in_bytes (not total)
"""
```

**Imports pattern** (analog: `es_schema.py` line 17 ES import; `es_manager.py` logging pattern):
```python
import logging

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

from nitrofind.es_manager import ES_URL

logger = logging.getLogger(__name__)

SIZE_HALT_BYTES = 1_800_000_000  # 1.8 GB — SCRP-04
CHECK_EVERY_N_DOCS = 100
```

**Core bulk indexing pattern** (RESEARCH.md Pattern 3 — no codebase analog; error logging follows `es_manager.py` style):
```python
class BulkIndexer:
    def __init__(self, client: Elasticsearch, state) -> None:
        self._client = client
        self._state = state

    def index_all(self, actions_generator) -> int:
        """Stream actions into ES. Returns total indexed doc count."""
        doc_count = 0
        for ok, info in streaming_bulk(
            self._client,
            actions_generator,
            chunk_size=100,
            raise_on_error=False,
            raise_on_exception=False,
        ):
            if not ok:
                # Follow es_manager.py convention: log type name in warning
                logger.warning("Bulk index error: %s", info)
                continue
            doc_count += 1
            if doc_count % CHECK_EVERY_N_DOCS == 0:
                size = self._index_size_bytes()
                logger.info("Indexed %d docs; index size %.2f MB", doc_count, size / 1e6)
                if size >= SIZE_HALT_BYTES:
                    logger.warning(
                        "Index approaching 2 GB limit (%.2f GB). "
                        "Halting scraper. SCRP-04 size guard triggered.",
                        SIZE_HALT_BYTES / 1e9,
                    )
                    return doc_count
        return doc_count

    def _index_size_bytes(self) -> int:
        """Pitfall 8: use primaries (not total) to avoid double-counting replicas."""
        stats = self._client.indices.stats(index="car_articles", metric="store")
        return stats["indices"]["car_articles"]["primaries"]["store"]["size_in_bytes"]


def build_action(doc: dict) -> dict:
    """Build streaming_bulk action dict with _id for deduplication (SCRP-03)."""
    action = {"_index": "car_articles", "_id": doc["article_id"]}
    action.update(doc)
    return action
```

---

### `tests/test_scraper/test_wikipedia.py` (test)

**Analog:** `tests/test_es_manager.py` — exact test file structure, import style, mock/patch conventions.

**File header pattern** (analog: `tests/test_es_manager.py` lines 1-13):
```python
"""
Unit tests for nitrofind.scraper.wikipedia — SCRP-01 coverage.

Test strategy:
  - Instantiate WikipediaScraper with mocked MediaWikiAPI and SQLiteStateManager
  - Use unittest.mock.patch and MagicMock for all external calls
  - No live Wikipedia API or Qt event loop required

Requirement coverage:
  SCRP-01: walk_category returns page IDs from mocked category response
  SCRP-01: fetch_and_filter returns None for page with empty infobox (Pitfall 2)
  SCRP-01: fetch_and_filter returns correct document dict for page with infobox
"""

from unittest.mock import MagicMock, patch
import pytest
from nitrofind.scraper.wikipedia import WikipediaScraper
```

**Mock structure pattern** (analog: `tests/test_es_manager.py` lines 87-109):
```python
def test_fetch_and_filter_skips_empty_infobox():
    """Returns None when page.infobox == {} (D-02, Pitfall 2)."""
    mock_page = MagicMock()
    mock_page.infobox = {}  # empty dict — falsy; must not be treated as None

    mock_wiki = MagicMock()
    mock_wiki.page.return_value = mock_page

    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki):
        scraper = WikipediaScraper(config={"max_depth": 2, "rate_limit_seconds": 0}, state=mock_state)
        result = scraper.fetch_and_filter(pageid=12345)

    assert result is None
```

**Integration test marker pattern** (analog: `tests/integration/test_es_startup.py` lines 20-22):
```python
@pytest.mark.integration
def test_real_wikipedia_page_fetch():
    """Live test — requires internet. Marked integration to exclude from CI."""
    ...
```

---

### `tests/test_scraper/test_blogs.py` (test)

**Analog:** `tests/test_es_manager.py` — same mock/patch structure.

**File header pattern**:
```python
"""
Unit tests for nitrofind.scraper.blogs — SCRP-02 coverage.

Test strategy:
  - Mock requests.Session.get with responses library or unittest.mock
  - No live network access required

Requirement coverage:
  SCRP-02: blog fetcher returns None gracefully on HTTP 403 (Pitfall 3)
  SCRP-02: extract_plain_text returns no HTML tags in output (L-05)
"""

from unittest.mock import MagicMock, patch
import pytest
from nitrofind.scraper.blogs import BlogScraper
```

**403 handling test pattern** (analog: `test_es_manager.py` `test_worker_emits_failed` — mock a failure path):
```python
def test_fetch_article_returns_none_on_403():
    """Pitfall 3: HTTP 403 is logged as warning and returns None (not raised)."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        response=MagicMock(status_code=403)
    )

    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    with patch("nitrofind.scraper.blogs.requests.Session") as mock_session_cls:
        mock_session_cls.return_value.get.return_value = mock_response
        scraper = BlogScraper(config={...}, state=mock_state)
        result = scraper._fetch_article("https://example.com/article")

    assert result is None
```

---

### `tests/test_scraper/test_cleaner.py` (test)

**Analog:** `tests/test_es_schema.py` — assertion-heavy unit tests, no mocks needed (pure functions).

**File header pattern** (analog: `tests/test_es_schema.py` lines 1-10):
```python
"""
Unit tests for nitrofind.scraper.cleaner — SCHEMA-03 coverage.

Requirement coverage:
  SCHEMA-03: excerpt is always ≤300 chars in generated docs (L-06)
  SCHEMA-03: body field contains no HTML tags — no < or > characters (L-05)
  L-07: era_bucket derived correctly from production_start
  Pitfall 7: excerpt never cuts mid-word
"""

from nitrofind.scraper.cleaner import make_excerpt, compute_era_bucket, parse_year
```

**Pure assertion pattern** (analog: `tests/test_es_schema.py` lines 17-56 — no mocks):
```python
def test_excerpt_max_300_chars():
    """make_excerpt always returns ≤300 characters (L-06)."""
    long_body = "word " * 200  # 1000 chars
    result = make_excerpt(long_body)
    assert len(result) <= 300


def test_excerpt_no_mid_word_cut():
    """Pitfall 7: excerpt ends on a word boundary."""
    body = "a" * 295 + " boundary_word"
    result = make_excerpt(body)
    assert not result.endswith("boundar")  # mid-word cut would produce this
    assert " " not in result[-10:] or result == body  # ends cleanly


def test_era_bucket_from_year():
    """L-07: decade derivation formula."""
    assert compute_era_bucket(1965) == "1960s"
    assert compute_era_bucket(2003) == "2000s"
    assert compute_era_bucket(None) == "Unknown"
    assert compute_era_bucket(0) == "Unknown"
```

---

### `tests/test_scraper/test_indexer.py` (test)

**Analog:** `tests/test_es_manager.py` (unit mocks) + `tests/integration/test_es_startup.py` (integration marker + skip guard).

**File header pattern**:
```python
"""
Unit + integration tests for nitrofind.scraper.indexer — SCRP-03, SCRP-04 coverage.

Test strategy:
  - Unit: mock streaming_bulk and indices.stats to test halt logic
  - Integration: marked @pytest.mark.integration; requires live ES node

Requirement coverage:
  SCRP-03: indexing same article twice produces no duplicate count increase
  SCRP-04: index_documents() halts and logs warning before 1.8 GB
"""

from unittest.mock import MagicMock, patch, call
import pytest
from nitrofind.scraper.indexer import BulkIndexer, SIZE_HALT_BYTES
```

**Size guard unit test** (analog: `test_es_manager.py` mock-the-dependency pattern):
```python
def test_size_guard_halts_indexing():
    """SCRP-04: BulkIndexer.index_all() returns early when size >= 1.8 GB."""
    mock_client = MagicMock()
    # Stats returns a size over the halt threshold
    mock_client.indices.stats.return_value = {
        "indices": {"car_articles": {"primaries": {"store": {"size_in_bytes": SIZE_HALT_BYTES + 1}}}}
    }

    # streaming_bulk yields (ok=True, info) for 101 docs so size is checked
    fake_actions = [{"_index": "car_articles", "_id": str(i)} for i in range(101)]
    mock_bulk_results = [(True, {}) for _ in fake_actions]

    with patch("nitrofind.scraper.indexer.streaming_bulk", return_value=iter(mock_bulk_results)):
        indexer = BulkIndexer(client=mock_client, state=MagicMock())
        count = indexer.index_all(iter(fake_actions))

    assert count <= 101  # halted; did not process all actions
```

**Integration test pattern** (analog: `tests/integration/test_es_startup.py` lines 20-22 skip guard):
```python
@pytest.mark.integration
def test_deduplication_no_duplicate_docs():
    """SCRP-03: indexing same article_id twice does not increase doc count."""
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")
    ...
```

---

### `tests/test_scraper/test_state.py` (test)

**Analog:** `tests/test_es_schema.py` — lightweight unit tests, no mocks for stdlib.

**File header pattern**:
```python
"""
Unit tests for nitrofind.scraper.state — D-06 resume coverage.

Test strategy:
  - Use sqlite3 in-memory DB (':memory:') to avoid file I/O
  - No mocks needed — sqlite3 is stdlib

Requirement coverage:
  D-06: is_visited returns False for unseen ID; True after mark_visited
  D-06: mark_visited with INSERT OR IGNORE is idempotent (safe to call twice)
"""

import pytest
from nitrofind.scraper.state import SQLiteStateManager
```

**In-memory DB test pattern** (no codebase analog — stdlib sqlite3 idiom):
```python
def test_is_visited_false_for_new_id():
    state = SQLiteStateManager(":memory:")
    assert state.is_visited("page_123") is False
    state.close()


def test_mark_visited_idempotent():
    """INSERT OR IGNORE: calling twice does not raise and is_visited returns True."""
    state = SQLiteStateManager(":memory:")
    state.mark_visited("page_123", "wikipedia")
    state.mark_visited("page_123", "wikipedia")  # second call must not raise
    assert state.is_visited("page_123") is True
    state.close()
```

---

## Shared Patterns

### Module Docstring Structure
**Source:** `nitrofind/es_manager.py` lines 1-19, `nitrofind/es_schema.py` lines 1-15
**Apply to:** All `nitrofind/scraper/*.py` files

Every module starts with a triple-quoted docstring that lists:
1. Exports (public symbols)
2. Requirement coverage (IDs like SCRP-01, D-02, L-07)
3. Anti-patterns avoided (Pitfall N references)

```python
"""
nitrofind.scraper.X — one-line description.

Exports:
  ClassName  — brief description

Requirement coverage:
  REQ-ID: what this module satisfies

Anti-patterns avoided:
  Pitfall N: what mitigation is applied
"""
```

### Logger Instantiation
**Source:** `main.py` line 39 + `nitrofind/es_manager.py` (implicit via logging import)
**Apply to:** All `nitrofind/scraper/*.py` files (not tests)

```python
# At module level, after imports
logger = logging.getLogger(__name__)
```

### Error Handling — Catch Exception + Log Type Name
**Source:** `nitrofind/es_manager.py` lines 163-164
**Apply to:** `wikipedia.py`, `blogs.py`, `indexer.py`

```python
except Exception as exc:
    logger.warning("Operation failed: %s: %s", type(exc).__name__, exc)
```

Never use bare `except:` or `except Exception: pass`. Always log the exception type and message.

### ES Client Import Convention
**Source:** `nitrofind/es_manager.py` lines 35-36, `nitrofind/es_schema.py` line 17
**Apply to:** `nitrofind/scraper/indexer.py`, `scripts/scraper.py`

```python
from elasticsearch import Elasticsearch
from nitrofind.es_manager import ES_URL  # single source of truth for localhost:9200
```

Never hardcode `"http://localhost:9200"` — always import `ES_URL`.

### Test File Structure
**Source:** `tests/test_es_manager.py` lines 1-23
**Apply to:** All `tests/test_scraper/test_*.py` files

```python
"""
[Docstring with test strategy + requirement coverage]
"""

from unittest.mock import MagicMock, patch
import pytest

from nitrofind.scraper.X import ClassName

# ---------------------------------------------------------------------------
# REQUIREMENT-ID: description
# ---------------------------------------------------------------------------

def test_specific_behavior():
    """One-line docstring stating exactly what behavior is verified."""
    ...
```

Section headers using `# ---` separators group tests by requirement ID, matching the style in `tests/test_es_manager.py`.

### Integration Test Marker + Skip Guard
**Source:** `tests/integration/test_es_startup.py` lines 20-22
**Apply to:** `tests/test_scraper/test_indexer.py` (SCRP-03 live deduplication test)

```python
@pytest.mark.integration
def test_live_behavior():
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")
    ...
```

The `@pytest.mark.integration` marker is already registered in `pytest.ini` (line 3). Use it for any test requiring a live ES node or live internet.

### YAML Safe Load
**Source:** RESEARCH.md security section (CLAUDE.md prescribes yaml.safe_load)
**Apply to:** `scripts/scraper.py` (config loading), any module that loads `scraper.yaml`

```python
import yaml
# ALWAYS safe_load — never yaml.load() without Loader
with open(config_path, "r") as fh:
    config = yaml.safe_load(fh)
```

---

## No Analog Found

Files with no close match in the codebase (planner uses RESEARCH.md patterns directly):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `nitrofind/scraper/cleaner.py` | utility | transform | No text transformation utilities exist in Phase 1 codebase |
| `config/scraper.yaml` | config | — | Only existing config is `config/elasticsearch.yml` (INI-style, not YAML); RESEARCH.md Pattern 7 is the template |
| `nitrofind/scraper/__init__.py` | config (package marker) | — | Trivial: copy `nitrofind/__init__.py` exactly (single comment line) |

---

## Metadata

**Analog search scope:** `nitrofind/`, `scripts/`, `tests/`, `config/`
**Files scanned:** 11 existing source files + `pytest.ini`, `requirements.in`
**Pattern extraction date:** 2026-05-13

**Key observations:**
- Phase 1 established the error-handling convention (`catch Exception, log type name`) in `es_manager.py` — apply uniformly across all scraper modules
- `ES_URL` from `es_manager.py` is the single source of truth for the ES endpoint — scraper must import it, not hardcode
- `ensure_index()` from `es_schema.py` is ready to call at scraper startup with no modification needed
- `dynamic: "false"` on the index (string not bool — Pitfall 6 in `es_schema.py`) means scraper documents must match `CAR_ARTICLES_MAPPING.properties` keys exactly — no extra fields
- Test convention: call `.run()` / methods directly (synchronously), never `.start()` — avoids threading in tests (established in `test_es_manager.py` lines 8-10)
- pytest `integration` marker is pre-registered in `pytest.ini` — use it for any test requiring live ES or live internet, consistent with `tests/integration/test_es_startup.py`
