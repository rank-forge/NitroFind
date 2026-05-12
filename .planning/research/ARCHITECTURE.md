# Architecture Patterns

**Project:** NitroFind — Offline Automotive Desktop Search Engine
**Researched:** 2026-05-12
**Confidence:** HIGH (verified against official Elasticsearch 8.x docs, PyQt6 Riverbank docs, elasticsearch-py 8.x client docs)

---

## Recommended Architecture

NitroFind is a two-phase system: an offline **data pipeline** (scraper → indexer, run once) and an online **search runtime** (Elasticsearch node + PyQt UI, run always). These phases are architecturally separate and communicate only through the Elasticsearch index.

```
┌─────────────────────────────────────────────────────────────────────┐
│  DATA PIPELINE  (run once per database refresh)                     │
│                                                                     │
│  ┌──────────┐   NDJSON files    ┌──────────┐   bulk index API      │
│  │ Scraper  │ ─────────────────▶│ Indexer  │ ─────────────────────▶│
│  │          │  ./data/raw/*.json│          │                        │
│  └──────────┘                   └──────────┘                        │
│       │                              │                              │
│       ▼                              ▼                              │
│  scraper_state.db              (validation log)                     │
│  (SQLite, URL dedup)                                                │
└─────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────┐
                         │  Elasticsearch 8.x Node  │
                         │  localhost:9200           │
                         │  ./es_data/ (persisted)  │
                         └─────────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────┐
│  SEARCH RUNTIME  (runs while app is open)                           │
│                                       │                             │
│  ┌─────────────────────────────┐      │                             │
│  │  PyQt6 UI (main thread)     │      │                             │
│  │                             │      │                             │
│  │  SearchBar ──▶ QTimer       │      │                             │
│  │                  │ 300ms    │      │                             │
│  │                  ▼ debounce │      │                             │
│  │  QThreadPool ◀───────────── │      │                             │
│  │       │ (worker thread)     │      │                             │
│  │       ▼                     │      │                             │
│  │  SearchWorker ──────────────┼──────┘                             │
│  │       │  (ES HTTP call)     │                                    │
│  │       │ pyqtSignal          │                                    │
│  │       ▼                     │                                    │
│  │  ResultListWidget           │                                    │
│  │  FilterPanel                │                                    │
│  │  DetailView                 │                                    │
│  └─────────────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Does NOT touch |
|-----------|---------------|-------------------|----------------|
| `scraper/` | Fetch articles from Wikipedia and automotive blogs, output structured NDJSON | Writes to `./data/raw/`, reads/writes `scraper_state.db` | Elasticsearch directly |
| `indexer/` | Read NDJSON, validate, bulk-index into Elasticsearch | Reads `./data/raw/`, writes to ES via HTTP | UI, scraper |
| `search/` | Construct Elasticsearch queries (multi-match + function_score), execute, parse results | Elasticsearch HTTP on localhost:9200 | UI widgets directly |
| `ui/` | Render PyQt6 widgets, manage user interaction, dispatch search requests via worker threads | `search/` layer via pyqtSignal/QRunnable | Elasticsearch directly — never |
| `core/launcher.py` | App startup: start ES subprocess, poll health, open UI; app shutdown: stop ES subprocess | OS process (ES), PyQt6 app lifecycle | Indexing logic |
| `core/config.py` | Central constants: ES host, index name, heap settings path, data dirs | All other modules read from here | Nothing — read-only |

**Hard boundary:** The UI layer (`ui/`) must NEVER directly instantiate an `Elasticsearch` client or fire HTTP requests from the main thread. All search I/O goes through `search/` via a background `QRunnable`.

---

## Data Flow

### Phase 1: Data Pipeline (offline, one-shot)

```
Wikipedia MediaWiki API
Automotive blog HTML
        │
        ▼
scraper/wikipedia.py
scraper/blog_parsers/<domain>.py
        │
        │  Writes: ./data/raw/wikipedia.ndjson
        │          ./data/raw/caranddriver.ndjson
        │          etc.
        ▼
scraper_state.db (SQLite)
  → table: scraped_urls(url TEXT, scraped_at TEXT, status TEXT)
  → prevents re-fetching same URL on re-run
        │
        ▼
indexer/bulk_indexer.py
  → reads each NDJSON line
  → validates required fields (title, body, url, scraped_at, source_domain)
  → calls ES bulk API in batches of 200 documents
  → logs failed/skipped documents
        │
        ▼
Elasticsearch index: "car_articles"
```

### Phase 2: Search Runtime (live, per-keystroke)

```
User types in SearchBar
        │
        ▼ textChanged signal
QTimer (300ms single-shot, restarted on each keystroke)
        │
        ▼ timeout signal (fires only when user pauses typing)
SearchWorker(QRunnable).run()
        │
        ▼
search/query_builder.py
  → builds multi_match query (title^3, body, tags)
  → wraps in function_score with 4 scoring functions
  → adds any active filter terms (manufacturer, era, body_style)
        │
        ▼
elasticsearch-py client  →  HTTP GET localhost:9200/car_articles/_search
        │
        ▼
search/result_parser.py
  → parses ES response hits
  → extracts highlight snippets, scores, source fields
  → returns list[ArticleResult] dataclass
        │
        ▼ pyqtSignal("results_ready", list)  [emitted from worker thread]
        │
        ▼ [received on main thread]
ui/result_list.py   → clears and repopulates result list widget
ui/detail_view.py   → renders clicked article full text
```

### Filter Flow

Filter selections (manufacturer, era, body style) are `keyword` field term filters, not scored — they go into the `bool.filter` clause of the query (not `bool.must`), so they don't affect relevance scoring, only inclusion:

```json
{
  "bool": {
    "must": { "multi_match": { "query": "mustang", "fields": [...] } },
    "filter": [
      { "term": { "manufacturer": "ford" } },
      { "term": { "era": "1960s" } }
    ]
  }
}
```

---

## Elasticsearch: Local Node Management

### Architecture decision: Separate process, not embedded

Elasticsearch is a JVM process. It cannot be "embedded" in Python the way SQLite can. The correct model for NitroFind:

- Elasticsearch runs as a **separate OS process** (started via the ES shell/bat script).
- The Python app launches it at startup and terminates it at shutdown using `subprocess.Popen`.
- The Python app communicates with ES exclusively over HTTP on `localhost:9200`.

This is the only viable model. Attempting to bundle the JVM inside the Python app would produce a 500 MB+ artifact and break ES's internal path resolution.

### Startup and shutdown lifecycle (`core/launcher.py`)

```python
import subprocess
import time
import requests
import atexit
import os
import signal

ES_BIN = "./elasticsearch/bin/elasticsearch"   # path to ES binary
ES_PORT = 9200
HEALTH_TIMEOUT_SECONDS = 60
HEALTH_POLL_INTERVAL = 1.0

_es_process = None

def start_elasticsearch():
    global _es_process
    if _is_running():
        return  # already up from a previous session; don't start a second one

    _es_process = subprocess.Popen(
        [ES_BIN],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # On Windows, use creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    atexit.register(stop_elasticsearch)
    _wait_for_healthy()

def _wait_for_healthy():
    deadline = time.time() + HEALTH_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            r = requests.get(
                f"http://localhost:{ES_PORT}/_cluster/health",
                timeout=2
            )
            if r.json().get("status") in ("green", "yellow"):
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(HEALTH_POLL_INTERVAL)
    raise RuntimeError(
        f"Elasticsearch did not become healthy within {HEALTH_TIMEOUT_SECONDS}s"
    )

def _is_running():
    try:
        r = requests.get(f"http://localhost:{ES_PORT}/_cluster/health", timeout=1)
        return r.status_code == 200
    except Exception:
        return False

def stop_elasticsearch():
    global _es_process
    if _es_process and _es_process.poll() is None:
        _es_process.terminate()
        try:
            _es_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _es_process.kill()
    _es_process = None
```

**Key implementation notes:**
- `_is_running()` check at startup prevents launching a second ES instance if the user opens the app twice or ES is still shutting down.
- `atexit.register(stop_elasticsearch)` ensures ES is terminated even if the app crashes.
- On Windows, use `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` so that Ctrl+C in the terminal does not propagate to the ES subprocess unexpectedly.
- Poll `/_cluster/health` (not `/_cat/health`) — the health API returns JSON with a `status` field. Accept `"yellow"` (not just `"green"`) because a single-node cluster with replicas defaults to `yellow` (no replica shards). This is normal for a single-node setup.
- Startup takes 5–15 seconds on a cold JVM; the UI should display a loading screen during this window.

### Minimal `elasticsearch.yml` configuration

```yaml
cluster.name: nitrofind
node.name: nitrofind-local
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node   # disables multi-node bootstrap checks, required
xpack.security.enabled: false # no TLS, no auth tokens — safe for localhost-only
path.data: ./es_data
path.logs: ./es_logs
```

`discovery.type: single-node` is mandatory. Without it, ES attempts to form a cluster with other nodes and hangs on bootstrap checks. With it, the node starts immediately in single-node mode.

### JVM heap (`config/jvm.options.d/heap.options`)

```
-Xms512m
-Xmx1g
```

For a 2 GB index cap: 1 GB heap is sufficient. The ES recommendation is to give the heap 50% of available RAM but cap at ~31 GB (compressed OOP threshold). For a desktop app where the user may have 8–16 GB RAM, 1 GB heap prevents ES from starving the GUI process. Do not go below 512 MB — ES will struggle with complex function_score queries on large indices.

---

## Elasticsearch Index Schema

### Index name: `car_articles`

### Index settings

```python
INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,       # single node — no point in multiple shards
        "number_of_replicas": 0,     # single node — replicas would stay unassigned (yellow cluster)
        "analysis": {
            "analyzer": {
                "automotive_text": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "stop",          # removes "the", "a", "an", etc.
                        "snowball"       # English stemming: "engines" → "engin"
                    ]
                },
                "autocomplete_index": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "edge_ngram_filter"]
                },
                "autocomplete_search": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase"]
                }
            },
            "filter": {
                "edge_ngram_filter": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20
                }
            }
        }
    }
}
```

**Why `number_of_replicas: 0`:** A replica shard on a single-node cluster can never be assigned (no second node exists to hold it). The cluster would permanently sit at `yellow` health if replicas > 0. Setting replicas to 0 gets a `green` cluster on a single node.

**Why `edge_ngram_filter` on autocomplete:** The SearchBar fires on each keystroke. For short partial queries like "mus" to match "Mustang", edge n-grams at index time mean queries can use standard `match` without prefix queries (which are slower and don't support scoring).

### Mapping

```python
INDEX_MAPPINGS = {
    "mappings": {
        "properties": {
            # --- Identity ---
            "doc_id":       {"type": "keyword"},        # unique ID, used for dedup
            "url":          {"type": "keyword"},        # source URL, exact match only
            "source_domain":{"type": "keyword"},        # e.g. "wikipedia.org", "caranddriver.com"

            # --- Full-text search fields ---
            "title": {
                "type": "text",
                "analyzer": "automotive_text",
                "search_analyzer": "automotive_text",
                "fields": {
                    "raw":    {"type": "keyword"},               # for exact sort
                    "suggest":{"type": "text",
                               "analyzer": "autocomplete_index",
                               "search_analyzer": "autocomplete_search"}
                }
            },
            "body": {
                "type": "text",
                "analyzer": "automotive_text",
                "search_analyzer": "automotive_text"
                # body is NOT stored in _source by default; it IS stored —
                # we need it for the detail view. Leave store: true (default).
            },
            "summary": {       # first 2–3 sentences, for result snippet
                "type": "text",
                "analyzer": "automotive_text"
            },
            "tags": {
                "type": "keyword"   # exact match, used for filter aggregations
            },

            # --- Filter / facet fields (keyword — never analyzed) ---
            "manufacturer": {"type": "keyword"},    # "ford", "ferrari", "toyota"
            "era":          {"type": "keyword"},    # "1960s", "1970s", "modern"
            "body_style":   {"type": "keyword"},    # "coupe", "sedan", "convertible"
            "country":      {"type": "keyword"},    # "usa", "italy", "germany"

            # --- Scoring signal fields (numeric — used in function_score) ---
            "published_at": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis"
            },
            "domain_authority": {
                "type": "float"
                # Static score in [0.0, 1.0] assigned per source_domain at index time.
                # Values: wikipedia.org=1.0, caranddriver.com=0.85,
                #         roadandtrack.com=0.85, hagerty.com=0.80, hemmings.com=0.75
            },
            "word_count": {
                "type": "integer"
                # Proxy for article completeness. Computed at index time from body.
            },
            "image_count": {
                "type": "short"
                # Secondary completeness signal. Counted during scraping.
            },

            # --- Metadata ---
            "scraped_at":   {"type": "date"},
            "author":       {"type": "keyword"}     # exact, not analyzed
        }
    }
}
```

**Field design rationale:**

- `title.suggest` (edge_ngram): Enables partial-word matching on title during as-you-type without expensive prefix queries.
- `body` stored in `_source` (default): Required for the detail view to render full article text inside the app. If storage is tight, compress `body` before indexing (gzip → base64), store the result as a `keyword` field, and decompress on display. Only do this if approaching the 2 GB limit.
- `domain_authority` as a pre-computed `float`: Do NOT compute domain authority at query time via scripting. Assign it once per source domain in the indexer and store it in the document. This makes `field_value_factor` queries fast (no Painless script execution per-document).
- `word_count` as `integer`: Computed from `len(body.split())` in the indexer. Using `sqrt` modifier in `field_value_factor` prevents runaway scores from extremely long articles.
- Filter fields (`manufacturer`, `era`, `body_style`, `country`) as `keyword`: These go into `bool.filter` clauses (not scored), and must be exact-match. Analyzed `text` fields would break filtering.

---

## function_score: Multi-Signal Quality Ranking

### Design goal

NitroFind relevance = text match quality × (source authority + recency + completeness). The "PageRank-like" model means a highly relevant article from a well-known source that is recent and complete should outrank a marginal text match from a low-quality source.

### Query structure

```python
def build_search_query(query_text: str, filters: dict) -> dict:
    """
    Constructs the full Elasticsearch query body.
    filters: {"manufacturer": "ford", "era": "1960s"} — only keys present if selected.
    """
    # 1. Base text query
    text_query = {
        "multi_match": {
            "query": query_text,
            "fields": [
                "title^4",        # title matches worth 4x body matches
                "title.suggest^2",# partial title matches worth 2x
                "summary^2",      # summary matches worth 2x body
                "body"
            ],
            "type": "best_fields",
            "tie_breaker": 0.3,
            "minimum_should_match": "75%"
        }
    }

    # 2. Active filter terms (zero score impact — bool.filter not bool.must)
    filter_clauses = [
        {"term": {field: value}}
        for field, value in filters.items()
        if value
    ]

    # 3. Wrap in bool with filter
    base_query = {
        "bool": {
            "must": text_query,
            "filter": filter_clauses
        }
    } if filter_clauses else text_query

    # 4. function_score wrapper
    return {
        "function_score": {
            "query": base_query,
            "functions": [
                # Signal 1: Recency — gaussian decay on published_at
                # Articles published within 2 years get near-full score.
                # Older articles decay smoothly. Automotive content from the
                # 1960s is still relevant; don't use a short scale.
                {
                    "gauss": {
                        "published_at": {
                            "origin": "now",
                            "scale": "730d",    # 2 years = half-score threshold
                            "offset": "180d",   # no decay for last 6 months
                            "decay": 0.5
                        }
                    },
                    "weight": 1.5
                },

                # Signal 2: Domain authority — static float field [0.0, 1.0]
                # field_value_factor with modifier=none, factor=1.0
                # Wikipedia (1.0) beats Hemmings (0.75) directly.
                {
                    "field_value_factor": {
                        "field": "domain_authority",
                        "factor": 1.0,
                        "modifier": "none",
                        "missing": 0.5   # fallback for documents without this field
                    },
                    "weight": 2.0        # domain authority is the strongest signal
                },

                # Signal 3: Article length (completeness proxy)
                # sqrt modifier prevents runaway scores from very long articles.
                # A 2000-word article scores ~44; a 500-word stub scores ~22.
                # Diminishing returns past ~5000 words.
                {
                    "field_value_factor": {
                        "field": "word_count",
                        "factor": 0.01,     # scale down: 2000 words × 0.01 = 20
                        "modifier": "sqrt",
                        "missing": 1        # treat missing as stub (score = sqrt(0.01) ≈ 0.1)
                    },
                    "weight": 0.8
                },

                # Signal 4: Image count (secondary completeness / richness proxy)
                # An article with several images is likely more comprehensive.
                # ln1p prevents log(0) on articles with no images.
                {
                    "field_value_factor": {
                        "field": "image_count",
                        "factor": 1.0,
                        "modifier": "ln1p",  # ln(1 + image_count): 0→0, 5→1.79, 10→2.40
                        "missing": 0
                    },
                    "weight": 0.3
                }
            ],
            # How function scores combine with each other:
            # "sum" — adds all 4 signal scores. This means each signal contributes
            # additively. Use sum (not multiply) so that a zero in one signal
            # (e.g., no images) does not zero out the entire document score.
            "score_mode": "sum",
            # How the combined function score interacts with the text match score:
            # "multiply" — text relevance is a gating factor. A perfect quality score
            # on an irrelevant document still gets multiplied by the text score.
            # This preserves the intent: quality signals amplify, not replace, relevance.
            "boost_mode": "multiply",
            # Safety cap: prevent a single extremely-high-scoring outlier from
            # dominating when the text match is also perfect.
            "max_boost": 10.0
        }
    }
```

### Signal weight rationale

| Signal | Weight | Rationale |
|--------|--------|-----------|
| Domain authority | 2.0 | Strongest quality discriminator. Wikipedia is objectively more authoritative than an unknown blog. |
| Recency | 1.5 | Automotive articles about classic cars are perennially relevant; use a long scale (2 years) to avoid over-penalizing historical content. |
| Article length | 0.8 | Good proxy for depth, but long ≠ good; use sqrt to cap influence. |
| Image count | 0.3 | Weakest signal. A richly illustrated article is likely more complete, but images could be stock photos. |

### Score modes explained

- `score_mode: "sum"` (combining function scores): Sum means each signal contributes additively. The alternative `"multiply"` would make a zero image count (very common) zero out the entire quality score. Sum is the right choice here.
- `boost_mode: "multiply"` (function score × query score): Multiply means text relevance remains the primary filter. A car article with perfect quality signals but no text match with the query will score near zero. This matches the product intent: quality amplifies but does not override relevance.

### Gotchas

- **Scale units for date fields**: Must use Elasticsearch time units (`"730d"`, `"6M"`, `"2y"`) — not raw milliseconds or ISO strings. The `origin` for `gauss` on dates defaults to `"now"` and can be left as the string `"now"`.
- **`field_value_factor` with `modifier: "log"`**: Never use `log` (base 10) or `ln` on values that can be 0 — log(0) is undefined. Use `log1p` or `ln1p` instead. `word_count` with `sqrt` is safe because sqrt(0) = 0.
- **`missing` parameter**: Always specify `missing` on `field_value_factor` fields. Documents that were scraped before the field was added, or documents with incomplete metadata, will otherwise be excluded from function scoring entirely (they receive a score of 1.0 from the missing function, which can produce unexpected results).
- **Score normalization**: Decay functions return values in [0.0, 1.0]. `field_value_factor` returns raw field values multiplied by factor and modifier. They are on different scales. The `weight` parameter normalizes their contributions. Tune weights against real query results, not in theory.
- **`max_boost`**: Without `max_boost`, an article with perfect text match + maximum quality signals can produce a score that pushes all other results so far down they become invisible. `max_boost: 10.0` is a conservative starting cap; adjust after testing.

---

## PyQt UI: Communication with Elasticsearch

### Rule: Never query ES from the main thread

Elasticsearch HTTP calls take 5–50 ms. A PyQt main thread blocked for even 20 ms during an animation or layout operation will produce visible jank. All ES communication must happen in worker threads.

### Recommended pattern: QTimer debounce + QRunnable worker

This is lighter than `QThread.moveToThread()` for frequent short-lived tasks. `QThreadPool` manages a pool of reusable threads; `QRunnable` defines the task.

```python
from PyQt6.QtCore import QTimer, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt6.QtWidgets import QLineEdit

class SearchSignals(QObject):
    results_ready = pyqtSignal(list)    # list[ArticleResult]
    error_occurred = pyqtSignal(str)

class SearchWorker(QRunnable):
    def __init__(self, query_text: str, filters: dict, es_client):
        super().__init__()
        self.query_text = query_text
        self.filters = filters
        self.es_client = es_client
        self.signals = SearchSignals()

    def run(self):
        # This executes in a QThreadPool worker thread — never the GUI thread
        try:
            query_body = build_search_query(self.query_text, self.filters)
            response = self.es_client.search(
                index="car_articles",
                body=query_body,
                size=20
            )
            results = parse_results(response)
            self.signals.results_ready.emit(results)   # safe cross-thread signal
        except Exception as e:
            self.signals.error_occurred.emit(str(e))


class SearchBar(QLineEdit):
    def __init__(self, es_client, result_handler, parent=None):
        super().__init__(parent)
        self.es_client = es_client
        self.result_handler = result_handler

        # Debounce timer: fires 300ms after the user stops typing
        self._debounce = QTimer()
        self._debounce.setInterval(300)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._dispatch_search)
        self.textChanged.connect(self._debounce.start)  # each keystroke restarts timer

        self._thread_pool = QThreadPool.globalInstance()

    def _dispatch_search(self):
        query = self.text().strip()
        if not query:
            return
        worker = SearchWorker(query, self._active_filters(), self.es_client)
        worker.signals.results_ready.connect(self.result_handler)
        worker.setAutoDelete(True)
        self._thread_pool.start(worker)

    def _active_filters(self) -> dict:
        # Returns currently selected filter panel values
        # Implementation: read from shared filter state object
        return {}
```

### Why QRunnable over QThread subclassing

`QThread` subclassing is the legacy approach. The recommended Qt pattern (and what PyQt6 docs show) is `QObject.moveToThread()`, which is equivalent in power to `QRunnable` but more complex to set up correctly. `QRunnable` + `QThreadPool` is the right choice here because:
- Search requests are short-lived (50–200 ms each).
- The pool reuses threads, avoiding OS thread creation overhead per keystroke.
- `setAutoDelete(True)` handles cleanup automatically.
- The only limitation: `QRunnable` is not a `QObject`, so it cannot have signals. The `SearchSignals(QObject)` companion class bridges this — a standard pattern documented in PyQt6 official docs.

### Why 300ms debounce

Debounce at 300 ms means Elasticsearch is never queried faster than ~3 times per second regardless of typing speed. A 500 ms debounce feels sluggish; 100 ms fires too frequently and can queue up stale results. 300 ms is the standard value used in browser search implementations.

---

## Project Folder Structure

```
nitrofind/
├── pyproject.toml              # Poetry/pip project metadata, dependencies
├── README.md
│
├── elasticsearch/              # Elasticsearch 8.x distribution (downloaded separately)
│   ├── bin/elasticsearch       # ES startup script (gitignored — not committed)
│   ├── config/
│   │   ├── elasticsearch.yml   # minimal config (committed, templated)
│   │   └── jvm.options.d/
│   │       └── heap.options    # -Xms512m -Xmx1g
│   └── data/                   # ES index data (gitignored)
│
├── data/
│   ├── raw/                    # NDJSON scraper output (gitignored — too large)
│   │   ├── wikipedia.ndjson
│   │   ├── caranddriver.ndjson
│   │   └── hagerty.ndjson
│   └── scraper_state.db        # SQLite URL dedup state (gitignored)
│
├── nitrofind/                  # Main Python package
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # ES_HOST, INDEX_NAME, DATA_DIR, ES_BIN_PATH, etc.
│   │   ├── launcher.py         # start_elasticsearch(), stop_elasticsearch()
│   │   └── models.py           # ArticleResult dataclass, ScrapeRecord dataclass
│   │
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── wikipedia.py        # MediaWiki API fetcher → structured dict
│   │   ├── blog_parsers/
│   │   │   ├── __init__.py
│   │   │   ├── caranddriver.py
│   │   │   ├── roadandtrack.py
│   │   │   ├── hagerty.py
│   │   │   └── hemmings.py
│   │   ├── state.py            # SQLite scraper_state.db read/write
│   │   └── runner.py           # Orchestrates all scrapers, writes NDJSON
│   │
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── schema.py           # INDEX_SETTINGS and INDEX_MAPPINGS dicts
│   │   ├── bulk_indexer.py     # reads NDJSON, calls ES bulk API
│   │   └── setup.py            # create_index(), delete_index(), check_size()
│   │
│   ├── search/
│   │   ├── __init__.py
│   │   ├── client.py           # Elasticsearch client singleton
│   │   ├── query_builder.py    # build_search_query(text, filters) → dict
│   │   └── result_parser.py    # parse ES response → list[ArticleResult]
│   │
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py      # QMainWindow, layout, widget composition
│       ├── search_bar.py       # QLineEdit + QTimer debounce + QRunnable dispatch
│       ├── filter_panel.py     # QListWidget / QComboBox for facet filters
│       ├── result_list.py      # QListWidget showing search result cards
│       ├── detail_view.py      # QTextBrowser rendering full article body
│       └── workers.py          # SearchWorker(QRunnable), SearchSignals(QObject)
│
├── scripts/
│   ├── run_scraper.py          # CLI entry: python scripts/run_scraper.py
│   └── run_indexer.py          # CLI entry: python scripts/run_indexer.py
│
└── main.py                     # App entry: start ES, open QApplication, show window
```

**Why this structure:**

- `nitrofind/core/` is imported by all other modules; it has no imports from `scraper/`, `indexer/`, `search/`, or `ui/`. Dependency direction: `core` ← everything else. This makes `core/config.py` and `core/models.py` the only shared state.
- `scraper/` and `indexer/` are pipeline-only and are never imported by `ui/`. They run as CLI scripts via `scripts/`. This enforces the hard boundary between pipeline and runtime.
- `search/` is the only module that `ui/` imports from. The `search/client.py` singleton holds the `Elasticsearch` instance, which the UI worker threads receive by reference (thread-safe for read operations like search).
- `main.py` is the single entry point for the GUI app. It calls `launcher.start_elasticsearch()`, waits for health, then starts the `QApplication`. This keeps startup sequencing explicit and visible.

---

## Suggested Build Order

Dependencies flow from infrastructure → data → search logic → UI. Each phase is independently testable before the next begins.

| Order | Component | Deliverable | Tests Before Moving On |
|-------|-----------|-------------|------------------------|
| 1 | `core/config.py` + `core/models.py` | Config constants, dataclasses | Import cleanly, no side effects |
| 2 | `core/launcher.py` | ES starts, health check passes, ES stops | Run manually: `python -c "from nitrofind.core.launcher import start_elasticsearch; start_elasticsearch()"` |
| 3 | `indexer/schema.py` + `indexer/setup.py` | Index created in ES with correct mappings | `GET /car_articles/_mapping` matches schema |
| 4 | `scraper/wikipedia.py` | Wikipedia articles scraped to NDJSON | Sample 10 car articles, validate JSON fields |
| 5 | `scraper/blog_parsers/` | Each blog domain parses correctly | Sample 5 articles per domain, validate fields |
| 6 | `indexer/bulk_indexer.py` | 100+ documents indexed into ES | Query ES directly: `GET /car_articles/_count` |
| 7 | `search/query_builder.py` + `search/result_parser.py` | Queries return scored results | Interactive Python session against local ES with real data |
| 8 | `ui/workers.py` | SearchWorker executes query in background thread | Unit test: mock ES client, verify signal fires with results |
| 9 | `ui/search_bar.py` + `ui/result_list.py` | Typing produces results | Manual smoke test: app opens, search returns results |
| 10 | `ui/filter_panel.py` + `ui/detail_view.py` | Filtering narrows results; clicking shows full article | Manual smoke test: filter by manufacturer, click result |
| 11 | Full pipeline integration | Scrape → index → search → display | End-to-end: fresh index, 500+ articles, search for "ferrari 308" |

**Critical dependency:** Steps 1–3 must be complete before any scraper or UI work begins. The schema (step 3) defines what fields the scraper must produce (steps 4–5) and what the query builder can reference (step 7). Schema changes after data is indexed require a full re-index.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Querying Elasticsearch from the main thread

**What:** `self.es_client.search(...)` called directly in a button click handler or `textChanged` slot.
**Why bad:** ES HTTP calls block the main thread. The UI freezes for 20–200 ms per query. At 300+ queries per minute during active typing, the app becomes unresponsive.
**Instead:** Always dispatch through `QRunnable` → `QThreadPool`. Emit results back via `pyqtSignal`.

### Anti-Pattern 2: Dynamic mapping (no explicit schema)

**What:** Let Elasticsearch infer field types from the first document indexed.
**Why bad:** ES infers `word_count` as `long`, not `integer`; infers dates as `text` if the format is unrecognized; creates `keyword` sub-fields automatically for all `text` fields, bloating index size. Most critically: dynamic mapping cannot know that `domain_authority` should be `float` — it would be inferred as `float` from the first document but `keyword` if the first document happens to have it as a string. Explicit mapping eliminates this entire class of bugs.
**Instead:** Always define explicit mappings via `indexer/schema.py` before indexing any data.

### Anti-Pattern 3: Storing `body` outside Elasticsearch

**What:** Storing the full article text in a separate SQLite table or file system, with only a reference key in ES.
**Why bad:** The detail view needs to display full article text. If body is not in ES `_source`, every result click requires a second database lookup. ES already stores `_source` efficiently with LZ4 compression. Two storage systems for the same content violates the single-source-of-truth principle.
**Instead:** Store the full body in ES `_source`. If the 2 GB limit is approached, compress body text in the indexer before writing, and decompress it in `result_parser.py` after retrieval.

### Anti-Pattern 4: Starting Elasticsearch inside `QApplication.__init__`

**What:** Embedding `start_elasticsearch()` inside the Qt application constructor.
**Why bad:** ES startup takes 5–15 seconds. If the ES startup is synchronous on the main thread, the app window never appears and the OS marks it as "not responding" on Windows.
**Instead:** Show a minimal splash screen first (or a loading dialog), then start ES in `main.py` before `app.exec()`, OR move ES startup to a QThread with a progress signal feeding the splash screen.

### Anti-Pattern 5: `number_of_replicas: 1` on a single-node cluster

**What:** Using the ES default (1 replica) on a single-node cluster.
**Why bad:** The replica shard can never be assigned (no second node), so the cluster sits permanently at `yellow` health. Health checks that only accept `green` will loop until timeout. The app will appear to never start.
**Instead:** Set `number_of_replicas: 0` in `INDEX_SETTINGS`. Single-node clusters with zero replicas achieve `green` health immediately.

### Anti-Pattern 6: Running `function_score` with `score_mode: "multiply"` when signals can be zero

**What:** Using `score_mode: "multiply"` to combine the 4 quality signals.
**Why bad:** An article with zero images (`image_count: 0`) would have `field_value_factor` return 0, and 0 × everything = 0 for that article's quality score regardless of how authoritative or recent it is.
**Instead:** Use `score_mode: "sum"`. Each signal adds its contribution independently. A zero image count contributes 0 to the sum, not a product collapse.

---

## Scalability Considerations

These are informational only — NitroFind is a single-user desktop app. The numbers show where the architecture would need to change for other use cases.

| Concern | At current scale (2 GB / ~50K docs) | At 10× scale (20 GB) | At cloud scale |
|---------|--------------------------------------|----------------------|----------------|
| Index shards | 1 shard is fine | Still 1 shard (ES single-node) | Would need sharding |
| Heap size | 512 MB–1 GB heap | 2–4 GB heap | Cluster mode |
| function_score speed | Sub-10ms per query | Sub-50ms (more docs to score) | Would need caching layer |
| Worker threads | Global QThreadPool (default: CPU cores) | Same | N/A (desktop) |
| Concurrent users | 1 (single-user desktop) | N/A | Would need ES cluster |

For NitroFind's constraints (2 GB, single user, offline), the architecture above is already at the right scale. The main performance risk is ES startup time (5–15s cold start), not query speed.

---

## Sources

- Elasticsearch 8.19 function_score query reference: https://www.elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-function-score-query.html
- Elasticsearch 8.19 mapping field types: https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-types.html
- Elasticsearch 8.19 analyzer configuration: https://www.elastic.co/guide/en/elasticsearch/reference/8.19/analyzer.html
- Elasticsearch function scoring guide (Elastic blog): https://www.elastic.co/blog/found-function-scoring
- Elasticsearch cluster health API: https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-health.html
- elasticsearch-py 8.x DSL docs: https://elasticsearch-py.readthedocs.io/en/stable/
- PyQt6 QThread worker object pattern: https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtcore/qthread.html
- PyQt6 QRunnable multithreading guide: https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/
- PyQt QTimer debounce pattern: https://gist.github.com/chipolux/a600d2a31b6811d553651822f89c9e39
- python-elasticsearch-runner subprocess management reference: https://github.com/comperiosearch/python-elasticsearch-runner/blob/master/elasticsearch_runner/runner.py
- Elasticsearch discovery.type single-node: https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-discovery-settings.html
- Elasticsearch JVM heap settings: https://www.elastic.co/docs/reference/elasticsearch/jvm-settings
- Python project structure 2024/2025: https://realpython.com/python-application-layouts/
