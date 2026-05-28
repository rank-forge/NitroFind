# Phase 3: Search Logic & Relevance Scoring - Research

**Researched:** 2026-05-27
**Domain:** Elasticsearch 8.x function_score DSL, Python search layer architecture, PyQt6 threading
**Confidence:** HIGH

## Summary

Phase 3 builds the Python search layer that sits between Phase 2's indexed data and Phase 4's UI. The core deliverable is a `SearchEngine` class (or equivalent) in `nitrofind/search/` that: (1) translates a query string + optional filters into a `function_score` ES query, (2) executes that query on a background thread via `QRunnable`/`QThreadPool`, and (3) returns ranked `ArticleResult` dataclass objects with highlighted excerpt fragments.

The `function_score` configuration is fully locked by prior decisions: Gaussian decay on `published_at` (origin=now, scale=730d, decay=0.5 gives the ~2-year half-life), `field_value_factor` with `log1p` modifier on `word_count`, and a `weight` function conditioned on `has_infobox=true`. All three signals combine with `score_mode: sum` so a missing signal never zeroes a result; `boost_mode: multiply` lets BM25 text relevance act as a final multiplier. The critical pitfall is the `published_at` missing-field behavior: Elasticsearch decay functions return **1.0 (perfect score)** when the field is absent — not 0.5 — so articles without a date receive the maximum recency signal and distort ranking. The fix is a **two-function split**: one gauss function gated by `"filter": {"exists": {"field": "published_at"}}` (applied only to dated articles), and one `weight` function with the same filter negated to inject a configurable fallback score for undated articles.

For threading: the existing codebase uses `QThread` (subclass) for the ES health worker. The search layer should use `QThreadPool + QRunnable` instead — it is lighter weight, the pool manages thread reuse, and each user keystroke can submit a new `QRunnable` that cancels silently if a newer one arrives. The `Elasticsearch` client object is thread-safe and can be shared across runners via a reference passed at construction time.

**Primary recommendation:** Implement `nitrofind/search/` as a package with `engine.py` (SearchEngine class), `models.py` (ArticleResult dataclass), and `query_builder.py` (function_score dict construction). Wire ES calls via `QRunnable` workers that emit results through `WorkerSignals(QObject)` so results flow safely back to the Qt main thread.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| function_score query construction | Python/ES client | Elasticsearch server | Python builds the query dict; ES scores and ranks |
| Gaussian recency decay scoring | Elasticsearch server | — | Pure ES computation; Python only supplies params |
| has_infobox weight boost | Elasticsearch server | — | Computed inside function_score by ES, not Python |
| Missing-field fallback handling | Python (query design) | Elasticsearch server | Python must structure the two-function split; ES evaluates it |
| Background ES execution (thread safety) | Python (QThreadPool) | Qt signal/slot | QRunnable prevents GUI thread blocking |
| Result deserialization | Python (models.py) | — | Python unpacks ES response into ArticleResult |
| Highlight extraction | Python (models.py) | Elasticsearch server | ES returns highlighted fragments; Python stores them |
| Filter narrowing (manufacturer/era/style) | Elasticsearch server | Python (query_builder) | Python builds bool filter clauses; ES applies them |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| elasticsearch | 8.19.3 (installed) | Python ES client for all search calls | Already pinned in requirements.txt; thread-safe singleton |
| PyQt6 | 6.11.0 (installed) | QThreadPool + QRunnable for background ES execution | Already in stack; QRunnable lighter than QThread for search |
| dataclasses | stdlib | ArticleResult value object | No external dep; clean typed container |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type annotations on SearchEngine, ArticleResult | Always — project uses typed Python 3.11 |
| logging | stdlib | Structured debug output for query timing | Always — follow existing module logger pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| QRunnable / QThreadPool | QThread (subclass) | QThread is already used in es_manager.py; QRunnable preferred for short-lived tasks like search queries |
| Plain dict queries | elasticsearch-dsl Search object | DSL adds abstraction but function_score in DSL requires the same nested dict structure anyway; plain dicts are more readable and already used by the indexer |
| dataclass ArticleResult | TypedDict | dataclass gives `__post_init__` validation and default_factory for list fields |

**No new packages to install.** All required libraries are already in `requirements.txt`.

## Package Legitimacy Audit

No new packages are introduced in this phase. All libraries (elasticsearch==8.19.3, PyQt6==6.11.0) were vetted during Phases 1 and 2.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| elasticsearch | PyPI | 12+ yrs | Very high | github.com/elastic/elasticsearch-py | N/A (pre-vetted) | Approved |
| PyQt6 | PyPI | 4+ yrs | High | riverbankcomputing.com | N/A (pre-vetted) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
User query string + filters
        |
        v
  [query_builder.py]
  build_function_score_query()
  build_filter_clauses()
        |
        v
  [engine.py] SearchEngine
  .search(query, filters, callback)
        |
        v
  [QRunnable] SearchWorker
  (submitted to QThreadPool)
        |
        v
  Elasticsearch client (shared, thread-safe)
  client.search(index="car_articles", ...)
        |
        v
  ES response JSON (hits, scores, highlights)
        |
        v
  [models.py] ArticleResult deserialization
        |
        v
  WorkerSignals.results_ready.emit(List[ArticleResult])
        |
        v
  Qt main thread slot (Phase 4 UI consumer)
```

### Recommended Project Structure
```
nitrofind/
├── search/
│   ├── __init__.py         # exports SearchEngine, ArticleResult
│   ├── models.py           # ArticleResult dataclass
│   ├── query_builder.py    # build_function_score_query(), build_filter_clauses()
│   └── engine.py           # SearchEngine class with QRunnable workers
tests/
└── test_search/
    ├── __init__.py
    ├── test_models.py           # ArticleResult construction, highlight access
    ├── test_query_builder.py    # dict structure assertions, parameter coverage
    └── test_engine.py           # mock ES client, threading callback tests
```

### Pattern 1: function_score Query Dict — Complete Structure

**What:** The function_score query combining all three RLVN signals.
**When to use:** Every search call; constructed by `query_builder.build_function_score_query()`.

```python
# Source: elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-function-score-query.html
# [VERIFIED: official Elastic documentation]

def build_function_score_query(
    query_text: str,
    recency_weight: float = 1.5,
    length_weight: float = 1.0,
    infobox_weight: float = 0.5,
    missing_published_score: float = 0.3,
) -> dict:
    """Build the full function_score query dict for a text search."""

    # Base query: multi_match on title (boosted) and body
    base_query = {
        "multi_match": {
            "query": query_text,
            "fields": ["title^3", "body"],
            "type": "best_fields",
        }
    }

    return {
        "function_score": {
            "query": base_query,
            "functions": [
                # RLVN-01: Gaussian recency decay — only for dated articles
                # Filter avoids the 1.0-perfect-hit bug for missing published_at
                {
                    "filter": {"exists": {"field": "published_at"}},
                    "gauss": {
                        "published_at": {
                            "origin": "now",
                            "scale": "730d",   # 2-year scale → decay=0.5 at 2 years
                            "offset": "30d",   # no penalty within 30 days of today
                            "decay": 0.5,      # score halves at scale distance
                        }
                    },
                    "weight": recency_weight,
                },
                # Missing-field fallback: articles WITHOUT published_at get a fixed score
                # This is the workaround for the missing-field=1.0 bug [CITED: github.com/elastic/elasticsearch/issues/7788]
                {
                    "filter": {"bool": {"must_not": {"exists": {"field": "published_at"}}}},
                    "weight": missing_published_score,
                },
                # RLVN-02: log1p(word_count) modifier for article length signal
                {
                    "field_value_factor": {
                        "field": "word_count",
                        "modifier": "log1p",  # log1p handles word_count=0 safely
                        "factor": 1.0,
                        "missing": 1,          # fallback for missing word_count
                    },
                    "weight": length_weight,
                },
                # RLVN-03: boolean boost for articles with structured infobox
                {
                    "filter": {"term": {"has_infobox": True}},
                    "weight": infobox_weight,
                },
            ],
            "score_mode": "sum",       # RLVN-04: additive — missing signal ≠ zero result
            "boost_mode": "multiply",  # RLVN-04: BM25 text score acts as multiplier
        }
    }
```

**Gaussian decay math verification:**
- Formula: `score = exp(-0.5 * ((t - origin) / sigma)^2)` where sigma is derived from scale and decay
- With `scale=730d, decay=0.5`: an article published exactly 2 years ago scores 0.5 of maximum
- With `offset=30d`: articles within 30 days score at maximum (no decay)
- With `origin=now`: the decay is always calculated relative to the current time at query time [VERIFIED: official Elastic documentation]

### Pattern 2: Filter Clauses for Faceted Narrowing

**What:** Manufacturer, era_bucket, and body_style filters as bool filter context inside the function_score's wrapped query.
**When to use:** When user has selected sidebar filters (Phase 4 integration).

```python
# Source: elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-bool-query.html
# [VERIFIED: official Elastic documentation]

def build_filter_clauses(
    manufacturer: str | None = None,
    era_bucket: str | None = None,
    body_style: str | None = None,
) -> list[dict]:
    """Return a list of term filter dicts for the bool.filter context.

    These go inside the function_score's wrapped bool query as filter clauses,
    NOT as post_filter. This approach means filters affect both scoring and results.
    Use post_filter only if aggregations must show unfiltered counts (Phase 4 decision).
    """
    filters = []
    if manufacturer:
        filters.append({"term": {"manufacturer": manufacturer}})
    if era_bucket:
        filters.append({"term": {"era_bucket": era_bucket}})
    if body_style:
        filters.append({"term": {"body_style": body_style}})
    return filters


def build_search_body(
    query_text: str,
    filters: list[dict] | None = None,
    size: int = 20,
    from_: int = 0,
) -> dict:
    """Assemble the complete ES search request body dict.

    Filters are applied inside the function_score.query bool.filter context,
    so they gate which documents are scored — ES can cache filter results.
    """
    fs_query = build_function_score_query(query_text)

    if filters:
        # Wrap the function_score's base query in a bool with filter context
        inner_query = fs_query["function_score"]["query"]
        fs_query["function_score"]["query"] = {
            "bool": {
                "must": [inner_query],
                "filter": filters,
            }
        }

    return {
        "query": fs_query,
        "highlight": {
            "fields": {
                "title": {
                    "fragment_size": 150,
                    "number_of_fragments": 1,
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"],
                },
                "body": {
                    "fragment_size": 300,
                    "number_of_fragments": 2,
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"],
                },
            }
        },
        "size": size,
        "from": from_,
        "_source": [
            "title", "url", "source_domain", "excerpt",
            "published_at", "word_count", "has_infobox",
            "manufacturer", "era_bucket", "body_style",
        ],
    }
```

### Pattern 3: ArticleResult Dataclass

**What:** Typed container for a single search result, decoupled from the ES response dict.
**When to use:** Always — SearchEngine returns `List[ArticleResult]`.

```python
# Source: nitrofind conventions (models.py pattern following es_schema.py structure)
# [ASSUMED] — dataclass structure, not verified against external docs

from dataclasses import dataclass, field

@dataclass
class ArticleResult:
    """Single search result returned by SearchEngine.

    highlight_title: list of HTML-tagged title fragments from ES highlighter.
    highlight_body:  list of HTML-tagged body fragments from ES highlighter.
    Empty lists when ES returns no highlights for a field.
    """
    title: str
    url: str
    source_domain: str
    score: float
    excerpt: str = ""
    published_at: str | None = None
    word_count: int = 0
    has_infobox: bool = False
    manufacturer: str | None = None
    era_bucket: str | None = None
    body_style: str | None = None
    highlight_title: list[str] = field(default_factory=list)
    highlight_body: list[str] = field(default_factory=list)

    @classmethod
    def from_es_hit(cls, hit: dict) -> "ArticleResult":
        """Construct from a raw ES response hit dict."""
        src = hit.get("_source", {})
        highlights = hit.get("highlight", {})
        return cls(
            title=src.get("title", ""),
            url=src.get("url", ""),
            source_domain=src.get("source_domain", ""),
            score=hit.get("_score", 0.0),
            excerpt=src.get("excerpt", ""),
            published_at=src.get("published_at"),
            word_count=src.get("word_count", 0),
            has_infobox=src.get("has_infobox", False),
            manufacturer=src.get("manufacturer"),
            era_bucket=src.get("era_bucket"),
            body_style=src.get("body_style"),
            highlight_title=highlights.get("title", []),
            highlight_body=highlights.get("body", []),
        )
```

### Pattern 4: SearchEngine with QRunnable Worker

**What:** Thread-safe search engine using QThreadPool; callback pattern matches existing ESHealthWorker conventions in es_manager.py.
**When to use:** All ES search calls from any context (Phase 4 UI or CLI testing).

```python
# Source: pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/
# [CITED: pythonguis.com — QThreadPool QRunnable pattern]

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from elasticsearch import Elasticsearch
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class _SearchSignals(QObject):
    """Signals for communicating search results to the Qt main thread."""
    results_ready = pyqtSignal(list)      # list[ArticleResult]
    search_failed = pyqtSignal(str)       # error message


class _SearchWorker(QRunnable):
    """QRunnable that executes one ES search and emits results via signals."""

    def __init__(
        self,
        client: Elasticsearch,
        body: dict,
        signals: "_SearchSignals",
    ) -> None:
        super().__init__()
        self._client = client
        self._body = body
        self._signals = signals

    @pyqtSlot()
    def run(self) -> None:
        try:
            resp = self._client.search(
                index="car_articles",
                query=self._body["query"],
                highlight=self._body.get("highlight"),
                source=self._body.get("_source"),
                size=self._body.get("size", 20),
                from_=self._body.get("from", 0),
            )
            results = [
                ArticleResult.from_es_hit(hit)
                for hit in resp["hits"]["hits"]
            ]
            self._signals.results_ready.emit(results)
        except Exception as exc:
            logger.warning("Search failed: %s: %s", type(exc).__name__, exc)
            self._signals.search_failed.emit(str(exc))


class SearchEngine:
    """Runs Elasticsearch function_score queries on a background QThreadPool.

    Usage:
        engine = SearchEngine(client)
        engine.search("Ferrari 308", callback=self.on_results)
    """

    def __init__(self, client: Elasticsearch) -> None:
        self._client = client
        self._pool = QThreadPool.globalInstance()

    def search(
        self,
        query_text: str,
        filters: list[dict] | None = None,
        size: int = 20,
        callback: Callable[[list], None] | None = None,
        error_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Submit a search to the thread pool. Returns immediately (non-blocking).

        Results delivered via callback in the Qt main thread via signal/slot.
        """
        body = build_search_body(query_text, filters=filters, size=size)
        signals = _SearchSignals()
        if callback:
            signals.results_ready.connect(callback)
        if error_callback:
            signals.search_failed.connect(error_callback)
        worker = _SearchWorker(self._client, body, signals)
        self._pool.start(worker)
```

### Pattern 5: ES client.search() Flat Keyword API (8.x)

**What:** In elasticsearch-py 8.x the `body=` parameter is deprecated; pass all fields as top-level keyword arguments.

```python
# Source: elastic.co/guide/en/elasticsearch/client/python-api/8.19/migration.html
# [VERIFIED: official Elastic documentation]

# CORRECT (8.x flat API):
resp = client.search(
    index="car_articles",
    query={"function_score": {...}},
    highlight={"fields": {"title": {}, "body": {}}},
    source=["title", "url", "score"],
    size=20,
    from_=0,
)

# DEPRECATED (do not use):
resp = client.search(index="car_articles", body={"query": {...}})
```

### Anti-Patterns to Avoid

- **Calling client.search() on the Qt main thread:** Blocks the GUI; always submit via QRunnable.
- **Using body= parameter:** Deprecated in elasticsearch-py 8.x; use flat keyword API.
- **Relying on Gauss decay returning 0.5 for missing published_at:** ES returns 1.0 (perfect score) — always use the filter+exists split pattern for the recency function.
- **Using `log` modifier instead of `log1p`:** `log(0)` is undefined; `log1p` returns 0 safely for word_count=0.
- **Years/months in scale parameter:** Use `"730d"` not `"2y"` — year/month units are not supported in decay scale [CITED: github.com/elastic/elasticsearch/issues/19619].
- **Connecting signals AFTER starting the worker:** Race condition; connect before `pool.start(worker)`.
- **Creating a new QThreadPool per search:** Use `QThreadPool.globalInstance()` for automatic thread reuse.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 text relevance | Custom TF-IDF | multi_match query in function_score | ES BM25 is production-grade; hand-rolled scoring misses field norms, IDF across corpus |
| Score combination | Custom weighted sum | `score_mode: sum` + `boost_mode: multiply` | ES already implements this; wrong implementation order breaks additive guarantee |
| Highlighting | String substr matching | ES `highlight` parameter | ES uses Lucene tokenizer for accurate token boundaries; string matching splits on wrong boundaries |
| Thread pool | `threading.Thread` pool | `QThreadPool.globalInstance()` | Qt's pool integrates with Qt event loop and signal delivery; raw threads cannot emit Qt signals safely |
| Result pagination | Slice Python list | `from_` + `size` in ES query | ES does pagination server-side before returning; slicing Python results means fetching all docs |

**Key insight:** Every "hand-rolled" alternative requires reimplementing Lucene internals that ES already exposes through query DSL parameters.

## Common Pitfalls

### Pitfall 1: Missing published_at Returns Score 1.0 (Not 0.5)
**What goes wrong:** The Gaussian decay function treats a missing `published_at` field as if the value is 0 (the numeric origin), which for a date field means the article receives the maximum recency score of 1.0 — outranking all dated articles regardless of their actual publication date.
**Why it happens:** ES decay function spec: "If the numeric field is missing in the document, the function will return 1." [CITED: github.com/elastic/elasticsearch/issues/7788]
**How to avoid:** Use the two-function split: apply the gauss function only under `"filter": {"exists": {"field": "published_at"}}`, and add a separate `weight` function under `"filter": {"bool": {"must_not": {"exists": {...}}}}` that injects the desired fallback score (e.g., 0.3).
**Warning signs:** Searching produces results with no published_at in positions 1-3 when recent articles exist in the index.

### Pitfall 2: Using `body=` Parameter (Deprecated in 8.x)
**What goes wrong:** `client.search(body={"query": ...})` triggers a DeprecationWarning in 8.x and will break in 9.x.
**Why it happens:** elasticsearch-py 8.0 migrated to flat keyword API.
**How to avoid:** Pass `query=`, `highlight=`, `size=`, `from_=` as direct kwargs to `client.search()`.
**Warning signs:** "Passing transport options in the API method is deprecated" in logs.

### Pitfall 3: `log` Modifier Crashes on word_count = 0
**What goes wrong:** `field_value_factor` with `modifier: "log"` raises a scoring error when `word_count = 0` because `log(0)` is undefined.
**Why it happens:** Some indexed documents (blog stubs, redirect pages) may have zero or null word_count.
**How to avoid:** Use `modifier: "log1p"` which computes `log(1 + value)`, safe for value=0.
**Warning signs:** ES returns search errors or NaN scores; documents disappear from results.

### Pitfall 4: Year/Month Units Not Supported in Decay Scale
**What goes wrong:** Setting `"scale": "2y"` or `"scale": "24m"` raises an ES parsing error.
**Why it happens:** Decay functions only support day-level time units (`d`). [CITED: github.com/elastic/elasticsearch/issues/19619]
**How to avoid:** Use `"scale": "730d"` for a 2-year scale.
**Warning signs:** `SearchPhaseExecutionException: [...] Unknown time unit 'y'` at search time.

### Pitfall 5: Calling ES client from Qt Main Thread
**What goes wrong:** ES search blocks for 50-500ms; calling from the main thread freezes the UI during typing (Phase 4 regression).
**Why it happens:** `client.search()` is synchronous blocking I/O.
**How to avoid:** Always submit search via `QRunnable` through `QThreadPool.globalInstance()`. The SearchEngine.search() method must never be called in a way that blocks the calling thread.
**Warning signs:** UI input box freezes momentarily on each keystroke.

### Pitfall 6: Connecting Signals After pool.start()
**What goes wrong:** If the worker completes before signal connections are established, the `results_ready` signal fires but no slot receives it — results silently dropped.
**Why it happens:** QRunnable starts executing immediately on a free thread.
**How to avoid:** Follow the existing es_manager.py pattern: connect ALL signals to slots BEFORE calling `pool.start(worker)`.
**Warning signs:** Callback never fires even though search logs show success.

### Pitfall 7: Weight Tuning Locked at Defaults
**What goes wrong:** Hardcoded weights (recency=1.5, length=1.0, infobox=0.5) may not reflect the actual indexed data distribution — State.md explicitly flags this.
**Why it happens:** The literature-derived weights are starting points only.
**How to avoid:** Include a tuning checkpoint in the plan using `explain=True` on test queries to inspect individual function scores against real indexed data.
**Warning signs:** "Ferrari 308" Wikipedia article not in top 3; undated articles dominate results.

## Code Examples

### Verified: Accessing Highlights from ES Response

```python
# Source: elastic.co/guide/en/elasticsearch/reference/8.19/highlighting.html
# [VERIFIED: official Elastic documentation]

resp = client.search(
    index="car_articles",
    query={"match": {"body": "Ferrari"}},
    highlight={"fields": {"body": {"fragment_size": 300, "number_of_fragments": 2}}},
    size=5,
)
for hit in resp["hits"]["hits"]:
    score = hit["_score"]
    source = hit["_source"]
    # highlight may be absent if no matching fragments found in this field
    highlights = hit.get("highlight", {}).get("body", [])
    print(f"{score:.3f} — {source['title']}")
    for fragment in highlights:
        print(f"  ...{fragment}...")
```

### Verified: Gaussian Decay Parameters for 2-Year Half-Life

```python
# Source: elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-function-score-query.html
# [VERIFIED: official Elastic documentation]

# At scale=730d with decay=0.5:
#   article published today:      gauss score = 1.0
#   article published 1 year ago: gauss score ≈ 0.84
#   article published 2 years ago (= scale): gauss score = 0.5
#   article published 5 years ago: gauss score ≈ 0.10
#   article with NO published_at: WITHOUT the exists filter, gauss score = 1.0 (BUG)
#                                  WITH the exists filter + weight fallback: fixed fallback score

gauss_function = {
    "filter": {"exists": {"field": "published_at"}},
    "gauss": {
        "published_at": {
            "origin": "now",
            "scale": "730d",
            "offset": "30d",
            "decay": 0.5,
        }
    },
    "weight": 1.5,
}
```

### Verified: explain=True for Weight Tuning

```python
# Source: elastic.co/guide/en/elasticsearch/reference/8.19/search-search.html
# [VERIFIED: official Elastic documentation]

# Use during tuning to see individual function_score contributions per document
resp = client.search(
    index="car_articles",
    query=build_function_score_query("Ferrari 308"),
    explain=True,
    size=5,
)
for hit in resp["hits"]["hits"]:
    print(hit["_score"], hit["_source"]["title"])
    # hit["_explanation"] shows the full scoring tree
    if "_explanation" in hit:
        import json
        print(json.dumps(hit["_explanation"], indent=2)[:500])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `body=` dict parameter | Flat keyword args (`query=`, `highlight=`, etc.) | elasticsearch-py 8.0 | Must use flat API; body= deprecated |
| `elasticsearch-dsl` as standalone pip | Merged into `elasticsearch==8.x` core | 8.18.0 | No separate install; import from `elasticsearch` |
| `log` modifier for field_value_factor | `log1p` preferred for safety | Always | log(0) undefined; log1p(0)=0 safe |
| QThread subclass for all background tasks | QRunnable + QThreadPool for search | PyQt6 design guidance | QRunnable lighter; pool reuses threads for high-frequency calls |

**Deprecated/outdated:**
- `elasticsearch-dsl` standalone package: redirects to core; use `from elasticsearch import ...` directly
- `body=` kwarg in client.search(): raises DeprecationWarning; will break in 9.x

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ArticleResult` dataclass field layout | Code Examples / Pattern 3 | Planner tasks may need field additions if Phase 4 needs more fields |
| A2 | Weight defaults (recency=1.5, length=1.0, infobox=0.5) | Pattern 1 | Ranking may not satisfy success criteria until empirically tuned against real data |
| A3 | `multi_match` with `title^3, body` as base query type | Pattern 1 | Alternative: `bool` with separate `must` clauses; either works, multi_match is simpler |
| A4 | Highlight pre_tags/post_tags as `<b>`/`</b>` | Pattern 2 | Phase 4 may prefer `<em>` or custom markers; tags should be configurable |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions (RESOLVED)

1. **Weight empirical tuning checkpoint** — RESOLVED: Plans include test_recency_decay_active with explain=True; weight tuning is a post-execution validation step, not a plan blocker. Starting weights are implemented; empirical tuning follows from observing real scores against indexed data.

2. **Filter vs post_filter for Phase 4 sidebar** — RESOLVED: filter-inside-function_score used for Phase 3 (no aggregations needed); post_filter deferred to Phase 4 per recommendation.

3. **SearchEngine singleton vs per-request construction** — RESOLVED: Phase 3 scope only — SearchEngine constructed via mock client in tests; Phase 4 wires the singleton to main.py after on_es_ready().

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| elasticsearch-py | All search calls | Yes | 8.19.3 (verified via import) | — |
| PyQt6 | QRunnable/QThreadPool workers | Yes | 6.11.0 (in requirements.txt) | — |
| Elasticsearch server | Integration tests | Conditional | 8.x (requires ES_HOME) | Skip integration tests with `-m "not integration"` |

**Missing dependencies with no fallback:** None for unit tests.
**Missing dependencies with fallback:** Live ES server — integration tests skip gracefully if ES_HOME is not set (matching existing pattern in tests/test_scraper/test_indexer.py).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | pytest.ini (exists; markers defined) |
| Quick run command | `pytest tests/test_search/ -m "not integration" -x` |
| Full suite command | `pytest tests/test_search/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RLVN-01 | Gaussian decay function present in query dict with correct params | unit | `pytest tests/test_search/test_query_builder.py::test_recency_decay_in_query -x` | No — Wave 0 |
| RLVN-01 | Missing published_at receives fallback weight, not 1.0 | unit | `pytest tests/test_search/test_query_builder.py::test_missing_published_fallback -x` | No — Wave 0 |
| RLVN-01 | Dated article scores higher than undated article for same text | integration | `pytest tests/test_search/test_engine.py::test_recency_decay_active -m integration` | No — Wave 0 |
| RLVN-02 | field_value_factor with log1p modifier present in query | unit | `pytest tests/test_search/test_query_builder.py::test_length_signal_in_query -x` | No — Wave 0 |
| RLVN-02 | Long article outscores short article for same query | integration | `pytest tests/test_search/test_engine.py::test_length_signal_active -m integration` | No — Wave 0 |
| RLVN-03 | has_infobox weight function present with filter=True | unit | `pytest tests/test_search/test_query_builder.py::test_infobox_boost_in_query -x` | No — Wave 0 |
| RLVN-03 | Infobox article outscores non-infobox article for same query | integration | `pytest tests/test_search/test_engine.py::test_infobox_boost_active -m integration` | No — Wave 0 |
| RLVN-04 | score_mode=sum and boost_mode=multiply present in query | unit | `pytest tests/test_search/test_query_builder.py::test_score_and_boost_modes -x` | No — Wave 0 |
| RLVN-04 | SearchEngine.search() calls callback in non-main thread context | unit | `pytest tests/test_search/test_engine.py::test_search_returns_via_callback -x` | No — Wave 0 |
| SC-1 | "Ferrari 308" Wikipedia article in top 3 | integration + manual | `pytest tests/test_search/test_engine.py::test_ferrari_308_top3 -m integration` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_search/ -m "not integration" -x`
- **Per wave merge:** `pytest tests/ -m "not integration" -x`
- **Phase gate:** Full suite (including integration) green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_search/__init__.py` — package marker
- [ ] `tests/test_search/test_models.py` — ArticleResult construction, from_es_hit(), highlight field access
- [ ] `tests/test_search/test_query_builder.py` — dict structure assertions for all RLVN requirements
- [ ] `tests/test_search/test_engine.py` — mock ES client, callback delivery, integration tests
- [ ] `nitrofind/search/__init__.py` — package marker with exports

## Security Domain

`security_enforcement` is not explicitly set to false in config.json — default is enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not applicable — local app, no auth |
| V3 Session Management | No | Not applicable — no sessions |
| V4 Access Control | No | Local single-user desktop tool |
| V5 Input Validation | Yes | Query text sanitized via ES query DSL (parameterized) |
| V6 Cryptography | No | All data local; no encryption needed |

### Known Threat Patterns for Elasticsearch Query DSL

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| ES query injection (malicious query_text) | Tampering | Pass user text only to `"query"` field inside multi_match dict — never as raw DSL; ES client serializes the string safely |
| Unbounded result size (DOS via large size param) | Denial of Service | Cap `size` parameter at a maximum (e.g., 100) in build_search_body; reject or clamp larger values |
| Cross-index access | Information Disclosure | Always hard-code `index="car_articles"` in client.search() — never accept index name from user input |

**Note:** Because query text is always passed as a `query` string inside a typed `multi_match` DSL field — never interpolated into a raw JSON string or DSL path — injection risk is minimal. The ES Python client handles string escaping.

## Sources

### Primary (HIGH confidence)
- [Elastic docs: function_score query 8.19](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/query-dsl-function-score-query.html) — complete DSL syntax, score_mode/boost_mode options, decay parameters, filter-in-function pattern
- [Elastic docs: highlighting 8.19](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/highlighting.html) — fragment_size, number_of_fragments, pre/post tags, unified vs plain, response format
- [Elastic Python client migration guide 8.x](https://www.elastic.co/guide/en/elasticsearch/client/python-api/8.19/migration.html) — flat keyword API replacing body= parameter
- [pythonguis.com QThreadPool tutorial](https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/) — QRunnable + WorkerSignals pattern, thread-safe signal emission

### Secondary (MEDIUM confidence)
- [GitHub issue #7788: decay functions handle missing field as perfect hits](https://github.com/elastic/elasticsearch/issues/7788) — confirmed 1.0 behavior for missing fields in decay functions
- [GitHub issue #19619: year/month units not supported in scale](https://github.com/elastic/elasticsearch/issues/19619) — confirmed must use `730d` not `2y`
- [Elastic blog: function scoring introduction](https://www.elastic.co/blog/found-function-scoring) — decay math explanation

### Tertiary (LOW confidence)
- [Medium: Using Decay Function Gauss](https://medium.com/@andre.luiz1987/using-decay-function-gauss-elasticsearch-7379fac2e284) — practical example for recency scoring pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and verified in existing codebase
- Architecture: HIGH — function_score DSL verified against official 8.19 docs; QRunnable pattern verified against official PyQt6 docs
- Pitfalls: HIGH — missing-field behavior confirmed via official GitHub issue; year unit limitation confirmed via GitHub issue
- Weight values: LOW — explicitly flagged in State.md as needing empirical tuning

**Research date:** 2026-05-27
**Valid until:** 2026-08-27 (stable APIs — function_score DSL unchanged since ES 7.x)
