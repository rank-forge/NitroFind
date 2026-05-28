"""
nitrofind.search.engine — QThreadPool-based search engine for NitroFind.

Exports:
  SearchEngine  — submits _SearchWorker instances to QThreadPool.globalInstance()

Requirement coverage:
  RLVN-01: recency decay executed via ES function_score (built by query_builder.py)
  RLVN-02: length signal (log1p field_value_factor) executed via ES
  RLVN-03: infobox boost (weight function) executed via ES
  RLVN-04: score/boost modes (score_mode=sum, boost_mode=multiply) via ES

Security mitigations:
  T-03-01 (query injection): query_text passed to build_search_body which places it
           inside multi_match "query" string value — never interpolated as raw DSL key
  T-03-04 (cross-index): index="car_articles" hard-coded as string literal in
           _SearchWorker.run() — never derived from user input
  T-03-05 (unbounded size): build_search_body clamps size to MAX_RESULT_SIZE (100)
           before body reaches _SearchWorker — engine layer receives pre-clamped body
  T-03-06 (signal race condition): signals connected BEFORE pool.start(worker)
           in SearchEngine.search() — enforced by code structure
"""

import logging
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from elasticsearch import Elasticsearch

from nitrofind.es_manager import ES_URL  # single source of truth (WR-01)
from nitrofind.search.models import ArticleResult
from nitrofind.search.query_builder import build_search_body

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signals sidecar (QRunnable cannot hold pyqtSignal; QObject sidecar required)
# ---------------------------------------------------------------------------


class _SearchSignals(QObject):
    """Signals for communicating search results to the Qt main thread.

    Must be a QObject subclass (not defined on _SearchWorker) because
    QRunnable does not inherit QObject and cannot hold pyqtSignal attributes.
    """

    results_ready = pyqtSignal(list)   # list[ArticleResult] — emitted on success
    search_failed = pyqtSignal(str)    # error message string — emitted on exception


# ---------------------------------------------------------------------------
# QRunnable worker — executes one ES search per submission
# ---------------------------------------------------------------------------


class _SearchWorker(QRunnable):
    """QRunnable that executes one ES search query and emits results via signals.

    Submitted to QThreadPool.globalInstance() by SearchEngine.search().
    Each user search creates a new worker; the pool manages thread reuse.

    Args:
        client:  Shared Elasticsearch client (thread-safe; injected at construction
                 time — never constructed inside run() to avoid per-query overhead).
        body:    Search body dict from build_search_body() with keys:
                 "query", "highlight", "_source", "size", "from".
        signals: _SearchSignals sidecar instance — results and errors flow
                 to the Qt main thread via its pyqtSignal slots.
    """

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
        """Execute the ES search query and emit results via signals.

        Uses the flat keyword API (no body= parameter) as required by
        elasticsearch-py 8.x. index="car_articles" is hard-coded (T-03-04).

        On success: emits signals.results_ready with list[ArticleResult].
        On exception: logs warning with % formatting and emits signals.search_failed.
        """
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


# ---------------------------------------------------------------------------
# SearchEngine — public API consumed by Phase 4 UI
# ---------------------------------------------------------------------------


class SearchEngine:
    """Runs Elasticsearch function_score queries on a background QThreadPool.

    ES client is injected at construction time and shared across all workers.
    Each call to search() submits a new _SearchWorker to QThreadPool.globalInstance();
    the pool manages thread reuse automatically.

    Usage (Phase 4 main.py pattern):
        engine = SearchEngine(client)
        engine.search("Ferrari 308", callback=self.on_results, error_callback=self.on_error)
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

        Results are delivered via callback in the Qt main thread via signal/slot.
        Signal connections are established BEFORE pool.start(worker) to prevent
        the race condition where a fast worker emits before connections are made
        (T-03-06 mitigation — Pitfall 6 from RESEARCH.md).

        Args:
            query_text:     User's search text. Forwarded to build_search_body as
                            the multi_match query string (never interpolated as DSL).
            filters:        Optional list of term filter dicts from build_filter_clauses.
            size:           Number of results requested. Clamped by build_search_body
                            to MAX_RESULT_SIZE (100) before reaching the worker.
            callback:       Called with list[ArticleResult] on success. Optional.
            error_callback: Called with error message string on failure. Optional.

        Returns:
            None — always returns immediately; results arrive via callback.
        """
        body = build_search_body(query_text, filters=filters, size=size)
        signals = _SearchSignals()

        # Connect ALL signals BEFORE pool.start(worker) — race condition if reversed.
        # (T-03-06: Pitfall 6 — fast workers can emit before connections are established)
        if callback:
            signals.results_ready.connect(callback)
        if error_callback:
            signals.search_failed.connect(error_callback)

        worker = _SearchWorker(self._client, body, signals)
        self._pool.start(worker)  # LAST — after all signal connections
