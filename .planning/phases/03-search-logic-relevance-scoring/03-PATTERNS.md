# Phase 3: Search Logic & Relevance Scoring - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 8 (4 source + 4 test)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `nitrofind/search/__init__.py` | package-init | — | `nitrofind/scraper/__init__.py` | exact |
| `nitrofind/search/models.py` | model | transform | `nitrofind/es_schema.py` | role-match |
| `nitrofind/search/query_builder.py` | utility | request-response | `nitrofind/scraper/indexer.py` (`build_action`) | role-match |
| `nitrofind/search/engine.py` | service | request-response | `nitrofind/es_manager.py` (`ESHealthWorker`) | role-match |
| `tests/test_search/__init__.py` | package-init | — | `tests/test_scraper/__init__.py` | exact |
| `tests/test_search/test_models.py` | test | transform | `tests/test_scraper/test_indexer.py` | role-match |
| `tests/test_search/test_query_builder.py` | test | request-response | `tests/test_scraper/test_indexer.py` | role-match |
| `tests/test_search/test_engine.py` | test | request-response | `tests/test_es_manager.py` | exact |

---

## Pattern Assignments

### `nitrofind/search/__init__.py` (package-init)

**Analog:** `nitrofind/scraper/__init__.py`

**Core pattern** (line 1):
```python
# NitroFind scraper package
```

The search package `__init__.py` follows the same minimal comment-only convention. Unlike the scraper package, the search `__init__.py` should re-export the public API per RESEARCH.md:

```python
# NitroFind search package
from nitrofind.search.engine import SearchEngine
from nitrofind.search.models import ArticleResult

__all__ = ["SearchEngine", "ArticleResult"]
```

---

### `nitrofind/search/models.py` (model, transform)

**Analog:** `nitrofind/es_schema.py`

**Module docstring pattern** (`es_schema.py` lines 1–15):
```python
"""
nitrofind.es_schema — Elasticsearch index schema for NitroFind.

Exports:
  CAR_ARTICLES_MAPPING  — full mapping dict for the car_articles index
  ensure_index          — idempotent index creation (Pattern 3)

Requirement coverage:
  SCHEMA-01: core identity fields
  ...
"""
```

**Imports pattern** (`es_schema.py` lines 17–18):
```python
from elasticsearch import Elasticsearch
```

For `models.py`, the imports are stdlib only:
```python
from __future__ import annotations
from dataclasses import dataclass, field
```

**Core pattern** — field layout mirrors `es_schema.py` `CAR_ARTICLES_MAPPING.properties` (`es_schema.py` lines 20–51). Every field in `ArticleResult` maps 1-to-1 to a property in the ES mapping:

| ArticleResult field | ES mapping property | ES type |
|---------------------|---------------------|---------|
| `title` | `title` | text |
| `url` | `url` | keyword |
| `source_domain` | `source_domain` | keyword |
| `published_at` | `published_at` | date |
| `word_count` | `word_count` | integer |
| `has_infobox` | `has_infobox` | boolean |
| `manufacturer` | `manufacturer` | keyword |
| `era_bucket` | `era_bucket` | keyword |
| `body_style` | `body_style` | keyword |

**`from_es_hit` classmethod pattern** — mirrors `BulkIndexer.index_all()` destructuring of ES response dicts (`indexer.py` lines 118–144). Use `.get()` with safe defaults throughout; never assume a key is present in an ES hit.

---

### `nitrofind/search/query_builder.py` (utility, request-response)

**Analog:** `nitrofind/scraper/indexer.py`

**Module docstring pattern** (`indexer.py` lines 1–22):
```python
"""
nitrofind.scraper.indexer — Elasticsearch bulk indexer with size guard.

Exports:
  BulkIndexer       — wraps streaming_bulk; ...
  build_action      — builds a streaming_bulk action dict ...

Requirement coverage:
  SCRP-03: ...
  SCRP-04: ...

Anti-patterns avoided:
  Per-document client.index() calls — use streaming_bulk exclusively (Pattern 3)
  ...
"""
```

Follow the same structure: `Exports:`, `Requirement coverage:`, `Anti-patterns avoided:` sections.

**Logger pattern** (`indexer.py` line 31):
```python
logger = logging.getLogger(__name__)
```

**Module constants pattern** (`indexer.py` lines 37–38):
```python
SIZE_HALT_BYTES: int = 1_800_000_000  # 1.8 GB — SCRP-04 halt threshold
CHECK_EVERY_N_DOCS: int = 100         # Check index size after every N successful docs
```

Apply to `query_builder.py` constants:
```python
DEFAULT_RECENCY_WEIGHT: float = 1.5
DEFAULT_LENGTH_WEIGHT: float = 1.0
DEFAULT_INFOBOX_WEIGHT: float = 0.5
DEFAULT_MISSING_PUBLISHED_SCORE: float = 0.3
MAX_RESULT_SIZE: int = 100  # security: cap unbounded size requests
```

**Free-function pattern** (`indexer.py` `build_action`, lines 45–61) — pure functions that accept typed args and return dicts:
```python
def build_action(doc: dict) -> dict:
    """Build a streaming_bulk action dict with _id set from doc['article_id'].

    ...
    """
    action = {"_index": "car_articles", "_id": doc["article_id"]}
    action.update(doc)
    return action
```

`query_builder.py` functions follow this exact style: short docstring, typed args, return `dict`.

**ES flat keyword API** (NEVER use `body=`). All `client.search()` calls pass fields as top-level kwargs:
```python
# CORRECT — elasticsearch-py 8.x flat API (from RESEARCH.md Pattern 5)
resp = client.search(
    index="car_articles",
    query=self._body["query"],
    highlight=self._body.get("highlight"),
    source=self._body.get("_source"),
    size=self._body.get("size", 20),
    from_=self._body.get("from", 0),
)
# WRONG — deprecated body= parameter
resp = client.search(index="car_articles", body={"query": {...}})
```

---

### `nitrofind/search/engine.py` (service, request-response)

**Analog:** `nitrofind/es_manager.py` (`ESHealthWorker`)

**Module docstring pattern** (`es_manager.py` lines 1–19):
```python
"""
nitrofind.es_manager — Elasticsearch subprocess lifecycle manager.

Exports:
  validate_es_home   — ...
  shutdown_es        — ...
  ESHealthWorker     — QThread worker: starts ES, polls health, emits signals

Requirement coverage:
  INFRA-02: ...
  INFRA-04: ...

Security mitigations:
  T-02-01 (path traversal): ...
  T-02-02 (shell injection): ...
"""
```

**Imports pattern** (`es_manager.py` lines 21–29):
```python
import os
import signal
import subprocess
import sys
import time

from PyQt6.QtCore import QThread, pyqtSignal
from elasticsearch import Elasticsearch
```

For `engine.py`, the imports are:
```python
import logging
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from elasticsearch import Elasticsearch

from nitrofind.search.models import ArticleResult
from nitrofind.search.query_builder import build_search_body

logger = logging.getLogger(__name__)
```

**Signals class pattern** (`es_manager.py` lines 124–126) — define signals as class attributes on a `QObject` subclass (NOT on `QRunnable`, which cannot hold signals):
```python
es_ready = pyqtSignal()       # zero-arg
es_failed = pyqtSignal(str)   # reason string
```

For `engine.py`, mirror this with:
```python
class _SearchSignals(QObject):
    results_ready = pyqtSignal(list)   # list[ArticleResult]
    search_failed = pyqtSignal(str)    # error message string
```

**QThread worker `run()` pattern** (`es_manager.py` lines 138–172):
```python
def run(self) -> None:
    """...Blocking — designed to run in a QThread (call via start(), not run()
    directly, in production)..."""
    ...
    try:
        resp = client.cluster.health()
        if resp["status"] in ("green", "yellow"):
            self.es_ready.emit()
            return
    except Exception as exc:
        last_exc = exc  # track for deadline message; not swallowed silently

    time.sleep(2)
```

For `engine.py` `_SearchWorker.run()` (QRunnable, decorated with `@pyqtSlot()`):
```python
@pyqtSlot()
def run(self) -> None:
    try:
        resp = self._client.search(...)
        results = [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]
        self._signals.results_ready.emit(results)
    except Exception as exc:
        logger.warning("Search failed: %s: %s", type(exc).__name__, exc)
        self._signals.search_failed.emit(str(exc))
```

**Signal connection order** (`es_manager.py` lines 118–122, docstring pattern and test enforcement in `test_es_manager.py` lines 99–106):
```python
# ALWAYS connect signals BEFORE start():
worker = ESHealthWorker(es_home)
worker.es_ready.connect(on_es_ready)      # connect BEFORE start()
worker.es_failed.connect(on_es_failed)
worker.start()
```

For `SearchEngine.search()` the same order applies:
```python
signals = _SearchSignals()
if callback:
    signals.results_ready.connect(callback)   # connect BEFORE pool.start()
if error_callback:
    signals.search_failed.connect(error_callback)
worker = _SearchWorker(self._client, body, signals)
self._pool.start(worker)                      # start AFTER connecting
```

**Logger warning format** (`es_manager.py` line 164, `indexer.py` line 127):
```python
logger.warning("Bulk index error: %s", info)                     # indexer.py
logger.warning("Search failed: %s: %s", type(exc).__name__, exc) # engine.py pattern
```

Both use `%`-style lazy formatting (never f-strings in logger calls).

---

### `tests/test_search/__init__.py` (package-init)

**Analog:** `tests/test_scraper/__init__.py`

The file is empty (zero bytes). Copy exactly:
```python

```

---

### `tests/test_search/test_models.py` (test, transform)

**Analog:** `tests/test_scraper/test_indexer.py`

**Module docstring pattern** (`test_indexer.py` lines 1–14):
```python
"""
Unit + integration tests for nitrofind.scraper.indexer — SCRP-03, SCRP-04 coverage.

Test strategy:
  - Unit: mock streaming_bulk and indices.stats to test halt logic
  - Integration: marked @pytest.mark.integration; requires live ES node

Requirement coverage:
  SCRP-03: ...
  SCRP-04: ...

Anti-patterns avoided:
  Pitfall 8: size check uses primaries.store.size_in_bytes (not total)
"""
```

**Import pattern** (`test_indexer.py` lines 16–21):
```python
import os
from unittest.mock import MagicMock, patch

import pytest

from nitrofind.scraper.indexer import BulkIndexer, build_action, SIZE_HALT_BYTES, CHECK_EVERY_N_DOCS
```

**Test function naming pattern** (`test_indexer.py` lines 28, 39, 52, 64):
```python
def test_build_action_sets_id_from_article_id():
def test_build_action_includes_all_doc_fields():
def test_module_constants():
def test_index_size_bytes_reads_primaries():
```

Pattern: `test_<thing being tested>_<expected behavior>()`. Apply to `test_models.py`:
```python
def test_article_result_construction_required_fields():
def test_article_result_highlight_fields_default_empty_list():
def test_from_es_hit_extracts_source_fields():
def test_from_es_hit_extracts_highlight_fragments():
def test_from_es_hit_missing_fields_use_defaults():
```

---

### `tests/test_search/test_query_builder.py` (test, request-response)

**Analog:** `tests/test_scraper/test_indexer.py`

**Section separator pattern** (`test_indexer.py` lines 26, 50, 62, 86):
```python
# ---------------------------------------------------------------------------
# SCRP-03: document ID deduplication
# ---------------------------------------------------------------------------
```

Apply the same separator pattern, one section per RLVN requirement:
```python
# ---------------------------------------------------------------------------
# RLVN-01: Gaussian recency decay signal
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# RLVN-02: field_value_factor length signal
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# RLVN-03: has_infobox weight boost
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# RLVN-04: score_mode and boost_mode
# ---------------------------------------------------------------------------
```

**Dict structure assertion pattern** (`test_indexer.py` lines 33–36):
```python
assert action["_index"] == "car_articles"
assert action["_id"] == "12345"
assert action["title"] == "Ferrari 308"
```

For query builder tests, assert against the returned dict structure:
```python
query = build_function_score_query("Ferrari")
assert "function_score" in query
functions = query["function_score"]["functions"]
assert query["function_score"]["score_mode"] == "sum"
assert query["function_score"]["boost_mode"] == "multiply"
```

---

### `tests/test_search/test_engine.py` (test, request-response)

**Analog:** `tests/test_es_manager.py`

**Module docstring pattern** (`test_es_manager.py` lines 1–13):
```python
"""
Unit tests for nitrofind.es_manager — INFRA-02, INFRA-03, INFRA-04 coverage.

Test strategy:
  - Call worker.run() directly (synchronously) — never worker.start()
  - Patch subprocess.Popen and nitrofind.es_manager.Elasticsearch
  - No live ES or Qt event loop required

Requirement coverage:
  INFRA-02: ...
  INFRA-04: ...
"""
```

**Mock client + patch pattern** (`test_es_manager.py` lines 87–106):
```python
ready_calls = []
failed_calls = []

mock_client = MagicMock()
mock_client.cluster.health.return_value = mock_health_resp

with patch("nitrofind.es_manager.subprocess.Popen", return_value=mock_process), \
     patch("nitrofind.es_manager.Elasticsearch", return_value=mock_client):

    worker = ESHealthWorker("/fake/es_home")
    worker.es_ready.connect(lambda: ready_calls.append(True))
    worker.es_failed.connect(lambda reason: failed_calls.append(reason))
    worker.run()

assert len(ready_calls) == 1
```

Apply to `test_engine.py` — replace `Elasticsearch` patch with mock that returns canned ES response:
```python
mock_client = MagicMock()
mock_client.search.return_value = {
    "hits": {
        "hits": [
            {"_score": 1.5, "_source": {"title": "Ferrari 308", "url": "...", ...}, "highlight": {}}
        ]
    }
}
```

**Integration test skip pattern** (`test_indexer.py` lines 149–152):
```python
@pytest.mark.integration
def test_deduplication_no_duplicate_docs():
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")
```

Apply verbatim to all integration-marked tests in `test_engine.py`.

**Signal callback collection pattern** (`test_es_manager.py` lines 89–90):
```python
ready_calls = []
failed_calls = []
```

For engine tests, collect results via callback list:
```python
results_received = []
errors_received = []

engine.search("Ferrari 308", callback=lambda r: results_received.extend(r))
```

---

## Shared Patterns

### Logger Declaration
**Source:** `nitrofind/scraper/indexer.py` line 31, `nitrofind/es_manager.py` (implicit — uses `time` not logging, but `indexer.py` shows the canonical form)
**Apply to:** `engine.py`, `query_builder.py`
```python
import logging
logger = logging.getLogger(__name__)
```

### Logger Call Format (% lazy formatting, never f-strings)
**Source:** `nitrofind/scraper/indexer.py` lines 127, 134, 139–143
**Apply to:** All `logger.*()` calls in `engine.py` and `query_builder.py`
```python
logger.warning("Bulk index error: %s", info)
logger.info("Indexed %d docs; index size %.2f MB", doc_count, size / 1e6)
logger.warning(
    "Index size %.2f GB reached halt threshold. "
    "Halting scraper. SCRP-04 size guard triggered.",
    size / 1e9,
)
```

### ES URL Import
**Source:** `nitrofind/scraper/indexer.py` line 29
**Apply to:** `engine.py`
```python
from nitrofind.es_manager import ES_URL  # single source of truth (WR-01)
```

### Signal Connection Before Start
**Source:** `nitrofind/es_manager.py` docstring lines 118–122, enforced by `test_es_manager.py` lines 102–106
**Apply to:** `engine.py` `SearchEngine.search()` method
```python
# Connect ALL signals BEFORE pool.start(worker) — race condition if reversed
signals = _SearchSignals()
signals.results_ready.connect(callback)
signals.search_failed.connect(error_callback)
worker = _SearchWorker(...)
self._pool.start(worker)  # LAST
```

### Exception Logging Pattern
**Source:** `nitrofind/scraper/indexer.py` lines 145–149
**Apply to:** `engine.py` `_SearchWorker.run()`
```python
except Exception as exc:
    logger.warning(
        "Bulk indexing failed: %s: %s", type(exc).__name__, exc
    )
    raise
```

For `engine.py`, suppress + emit instead of re-raise (signal delivers the error to UI):
```python
except Exception as exc:
    logger.warning("Search failed: %s: %s", type(exc).__name__, exc)
    self._signals.search_failed.emit(str(exc))
```

### Index Name Hard-Coded Constant
**Source:** `nitrofind/scraper/indexer.py` line 59, `nitrofind/es_schema.py` line 62
**Apply to:** `engine.py` `_SearchWorker.run()`
```python
# Always hard-code index name — never accept from user input (security: cross-index access)
client.search(index="car_articles", ...)
```

### MagicMock + Patch Pattern in Tests
**Source:** `tests/test_es_manager.py` lines 16–18, 99–101
**Apply to:** All test files in `tests/test_search/`
```python
from unittest.mock import MagicMock, patch

with patch("nitrofind.search.engine.Elasticsearch", return_value=mock_client):
    ...
```

### Integration Test Mark + Skip
**Source:** `tests/test_scraper/test_indexer.py` lines 149–152
**Apply to:** `tests/test_search/test_engine.py` integration tests
```python
@pytest.mark.integration
def test_ferrari_308_top3():
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")
```

---

## No Analog Found

All files have analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `/mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind/nitrofind/`, `/mnt/c/Users/Leonardo/Desktop/codes/Claude/NitroFind/tests/`
**Files scanned:** 8 (es_manager.py, es_schema.py, scraper/indexer.py, scraper/__init__.py, ui/main_window.py, test_es_manager.py, test_scraper/test_indexer.py, nitrofind/__init__.py)
**Pattern extraction date:** 2026-05-27
