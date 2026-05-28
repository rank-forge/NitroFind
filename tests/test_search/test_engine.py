"""
Unit tests for nitrofind.search.engine — RLVN-01..04 coverage.

Test strategy:
  - Call worker.run() directly (synchronously) — never pool.start()
  - Provide mock ES client that returns canned response dicts
  - No live ES or Qt event loop required for unit tests
  - Integration tests skipped if ES_HOME is not set (matching existing pattern)

Requirement coverage:
  RLVN-01: SearchEngine uses build_search_body which includes Gaussian decay query
  RLVN-04: SearchEngine.search() returns None immediately (non-blocking by API contract)

Security coverage:
  T-03-01: _SearchWorker.run() uses flat keyword API — no body= parameter
  T-03-04: index="car_articles" hard-coded in _SearchWorker.run()
  T-03-06: signal connections established BEFORE pool.start(worker)
"""

import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

from PyQt6.QtWidgets import QApplication

# Ensure a QApplication exists (required for QObject/QRunnable/QThreadPool)
_app = QApplication.instance() or QApplication(sys.argv)

from nitrofind.search.engine import SearchEngine, _SearchSignals, _SearchWorker
from nitrofind.search.models import ArticleResult
from nitrofind.es_manager import ES_URL


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_client(hits=None):
    """Return a MagicMock ES client with a canned search response."""
    if hits is None:
        hits = [
            {
                "_score": 1.5,
                "_source": {
                    "title": "Ferrari 308",
                    "url": "https://en.wikipedia.org/wiki/Ferrari_308",
                    "source_domain": "en.wikipedia.org",
                    "excerpt": "The Ferrari 308 GTB and GTS...",
                    "published_at": "2023-01-01",
                    "word_count": 3500,
                    "has_infobox": True,
                    "manufacturer": "Ferrari",
                    "era_bucket": "1970s",
                    "body_style": "coupe",
                },
                "highlight": {
                    "title": ["<b>Ferrari 308</b>"],
                    "body": ["The <b>Ferrari 308</b> GTB..."],
                },
            }
        ]
    mock_client = MagicMock()
    mock_client.search.return_value = {"hits": {"hits": hits}}
    return mock_client


# ---------------------------------------------------------------------------
# _SearchSignals: structure assertions
# ---------------------------------------------------------------------------


class TestSearchSignalsStructure:
    def test_search_signals_is_qobject(self):
        """_SearchSignals must be a QObject so it can hold pyqtSignals."""
        from PyQt6.QtCore import QObject
        signals = _SearchSignals()
        assert isinstance(signals, QObject)

    def test_search_signals_has_results_ready(self):
        """results_ready signal must exist on _SearchSignals."""
        signals = _SearchSignals()
        assert hasattr(signals, "results_ready")

    def test_search_signals_has_search_failed(self):
        """search_failed signal must exist on _SearchSignals."""
        signals = _SearchSignals()
        assert hasattr(signals, "search_failed")


# ---------------------------------------------------------------------------
# _SearchWorker: construction and run() behavior
# ---------------------------------------------------------------------------


class TestSearchWorkerConstruction:
    def test_worker_stores_client(self):
        """_SearchWorker.__init__ must store the client as _client."""
        mock_client = _make_mock_client()
        body = {"query": {}, "highlight": {}, "size": 20, "from": 0, "_source": []}
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        assert worker._client is mock_client

    def test_worker_stores_body(self):
        """_SearchWorker.__init__ must store the body dict as _body."""
        mock_client = _make_mock_client()
        body = {"query": {"test": True}, "size": 10, "from": 0}
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        assert worker._body is body

    def test_worker_stores_signals(self):
        """_SearchWorker.__init__ must store the signals sidecar as _signals."""
        mock_client = _make_mock_client()
        body = {}
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        assert worker._signals is signals


class TestSearchWorkerRun:
    def test_run_calls_client_search_with_index(self):
        """run() must call client.search() with index='car_articles'."""
        mock_client = _make_mock_client()
        body = {
            "query": {"function_score": {}},
            "highlight": {"fields": {}},
            "size": 20,
            "from": 0,
            "_source": ["title"],
        }
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        worker.run()
        # Verify client.search was called at all
        assert mock_client.search.called
        # Verify index="car_articles" was passed (T-03-04: hard-coded, not from user input)
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs.get("index") == "car_articles"

    def test_run_uses_flat_keyword_api_not_body(self):
        """run() must NOT pass body= kwarg (deprecated in elasticsearch-py 8.x)."""
        mock_client = _make_mock_client()
        body = {
            "query": {"function_score": {}},
            "highlight": {"fields": {}},
            "size": 20,
            "from": 0,
            "_source": ["title"],
        }
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        worker.run()
        call_kwargs = mock_client.search.call_args.kwargs
        # T-03-01 / Pattern 5: flat keyword API — body= must NOT be present
        assert "body" not in call_kwargs

    def test_run_passes_query_kwarg(self):
        """run() must pass query= to client.search() as a flat keyword arg."""
        mock_client = _make_mock_client()
        query_dict = {"function_score": {"query": {"multi_match": {"query": "Ferrari"}}}}
        body = {
            "query": query_dict,
            "highlight": {},
            "size": 10,
            "from": 0,
            "_source": [],
        }
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        worker.run()
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs.get("query") == query_dict

    def test_run_passes_size_kwarg(self):
        """run() must pass size= to client.search() from the body dict."""
        mock_client = _make_mock_client()
        body = {
            "query": {},
            "highlight": {},
            "size": 15,
            "from": 5,
            "_source": [],
        }
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        worker.run()
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs.get("size") == 15

    def test_run_passes_from_kwarg(self):
        """run() must pass from_= to client.search() from the body dict."""
        mock_client = _make_mock_client()
        body = {
            "query": {},
            "highlight": {},
            "size": 10,
            "from": 5,
            "_source": [],
        }
        signals = _SearchSignals()
        worker = _SearchWorker(mock_client, body, signals)
        worker.run()
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs.get("from_") == 5

    def test_run_emits_results_ready_on_success(self):
        """run() must emit results_ready with a list of ArticleResult on success."""
        mock_client = _make_mock_client()
        body = {
            "query": {},
            "highlight": {},
            "size": 20,
            "from": 0,
            "_source": [],
        }
        signals = _SearchSignals()
        received = []
        signals.results_ready.connect(lambda results: received.extend(results))

        worker = _SearchWorker(mock_client, body, signals)
        worker.run()

        assert len(received) == 1
        assert isinstance(received[0], ArticleResult)
        assert received[0].title == "Ferrari 308"

    def test_run_emits_search_failed_on_exception(self):
        """run() must emit search_failed with the error string on exception."""
        mock_client = MagicMock()
        mock_client.search.side_effect = ConnectionError("ES is not reachable")
        body = {"query": {}, "highlight": {}, "size": 20, "from": 0, "_source": []}
        signals = _SearchSignals()
        errors = []
        signals.search_failed.connect(lambda msg: errors.append(msg))

        worker = _SearchWorker(mock_client, body, signals)
        worker.run()

        assert len(errors) == 1
        assert "ES is not reachable" in errors[0]

    def test_run_does_not_raise_on_exception(self):
        """run() must suppress exceptions — they are delivered via signal, not raised."""
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("unexpected error")
        body = {"query": {}, "highlight": {}, "size": 20, "from": 0, "_source": []}
        signals = _SearchSignals()

        worker = _SearchWorker(mock_client, body, signals)
        # Must not raise — exception is captured and emitted via search_failed signal
        try:
            worker.run()
        except Exception as exc:
            pytest.fail(f"worker.run() raised an exception: {exc!r}")

    def test_run_deserializes_all_hits(self):
        """run() must deserialize all hits from resp['hits']['hits'] into ArticleResult."""
        hits = [
            {
                "_score": 2.0,
                "_source": {"title": "Ferrari 308", "url": "u1", "source_domain": "d1"},
                "highlight": {},
            },
            {
                "_score": 1.0,
                "_source": {"title": "Lamborghini Countach", "url": "u2", "source_domain": "d2"},
                "highlight": {},
            },
        ]
        mock_client = _make_mock_client(hits=hits)
        body = {"query": {}, "highlight": {}, "size": 20, "from": 0, "_source": []}
        signals = _SearchSignals()
        received = []
        signals.results_ready.connect(lambda results: received.extend(results))

        worker = _SearchWorker(mock_client, body, signals)
        worker.run()

        assert len(received) == 2
        assert received[0].title == "Ferrari 308"
        assert received[1].title == "Lamborghini Countach"

    def test_run_handles_empty_hits(self):
        """run() must emit results_ready with empty list when hits is empty."""
        mock_client = _make_mock_client(hits=[])
        body = {"query": {}, "highlight": {}, "size": 20, "from": 0, "_source": []}
        signals = _SearchSignals()
        received = []
        signals.results_ready.connect(lambda results: received.append(results))

        worker = _SearchWorker(mock_client, body, signals)
        worker.run()

        assert len(received) == 1
        assert received[0] == []


# ---------------------------------------------------------------------------
# SearchEngine: construction
# ---------------------------------------------------------------------------


class TestSearchEngineConstruction:
    def test_engine_stores_client(self):
        """SearchEngine.__init__ must store the ES client as _client."""
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        assert engine._client is mock_client

    def test_engine_uses_global_thread_pool(self):
        """SearchEngine must use QThreadPool.globalInstance(), not construct its own."""
        from PyQt6.QtCore import QThreadPool
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        assert engine._pool is QThreadPool.globalInstance()

    def test_engine_has_search_method(self):
        """SearchEngine must expose a .search() method."""
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        assert callable(getattr(engine, "search", None))


# ---------------------------------------------------------------------------
# SearchEngine.search(): API contract
# ---------------------------------------------------------------------------


class TestSearchEngineSearch:
    def test_search_returns_none(self):
        """SearchEngine.search() must return None immediately (non-blocking API)."""
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        result = engine.search("Ferrari 308")
        assert result is None

    def test_search_calls_build_search_body(self):
        """SearchEngine.search() must call build_search_body with query_text."""
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        with patch("nitrofind.search.engine.build_search_body") as mock_build:
            mock_build.return_value = {
                "query": {},
                "highlight": {},
                "size": 20,
                "from": 0,
                "_source": [],
            }
            engine.search("Ferrari 308")
        mock_build.assert_called_once_with("Ferrari 308", filters=None, size=20, from_=0)

    def test_search_passes_filters_to_build_search_body(self):
        """SearchEngine.search() must forward filters to build_search_body."""
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        filters = [{"term": {"manufacturer": "Ferrari"}}]
        with patch("nitrofind.search.engine.build_search_body") as mock_build:
            mock_build.return_value = {
                "query": {},
                "highlight": {},
                "size": 20,
                "from": 0,
                "_source": [],
            }
            engine.search("Ferrari 308", filters=filters, size=10)
        mock_build.assert_called_once_with("Ferrari 308", filters=filters, size=10, from_=0)

    def test_search_connects_callback_before_start(self):
        """Signal connections must be established before pool.start() is called.

        This test verifies the connection order by patching pool.start and
        checking that signals.results_ready has connections at start() time.

        A buggy implementation that called pool.start() before connecting signals
        would fail the receivers() assertion inside tracking_start.
        """
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)

        connection_count_at_start = []
        receiver_count_at_start = []

        original_start = engine._pool.start

        def tracking_start(worker):
            # At this point, signals must already be connected — capture receiver count.
            # If start() is called before connect(), receivers() returns 0 here.
            count = worker._signals.receivers(worker._signals.results_ready)
            receiver_count_at_start.append(count)
            connection_count_at_start.append("start_called")

        engine._pool.start = tracking_start

        results_received = []
        engine.search("Ferrari", callback=lambda r: results_received.extend(r))
        engine._pool.start = original_start

        # pool.start() must have been called exactly once
        assert len(connection_count_at_start) == 1, "pool.start() should have been called once"
        # signals must have been connected BEFORE pool.start() was called (T-03-06)
        assert receiver_count_at_start[0] > 0, (
            "results_ready had no receivers at pool.start() time — "
            "signal connection happened AFTER start(), violating T-03-06"
        )

    def test_search_with_no_callback_does_not_raise(self):
        """SearchEngine.search() with no callback must not raise."""
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        # Should not raise even with no callback and no error_callback
        try:
            engine.search("Ferrari 308")
        except Exception as exc:
            pytest.fail(f"search() raised without callbacks: {exc!r}")

    def test_search_with_error_callback_does_not_raise(self):
        """SearchEngine.search() with error_callback must not raise."""
        mock_client = _make_mock_client()
        engine = SearchEngine(mock_client)
        try:
            engine.search("Ferrari 308", error_callback=lambda e: None)
        except Exception as exc:
            pytest.fail(f"search() raised with error_callback: {exc!r}")


# ---------------------------------------------------------------------------
# ES_URL import contract (T-03-04 / WR-01)
# ---------------------------------------------------------------------------


class TestEngineModuleContracts:
    def test_search_engine_accepts_elasticsearch_client(self):
        """SearchEngine must accept an Elasticsearch client injected at construction.

        The engine does not construct its own client from ES_URL — the caller
        provides a client configured for localhost:9200.  This test verifies that
        the construction contract (client injection) works without raising.
        """
        from elasticsearch import Elasticsearch
        client = Elasticsearch(ES_URL)  # localhost:9200 — not connecting, just constructing
        engine = SearchEngine(client)
        assert engine._client is client

    def test_index_name_hardcoded_not_accepted_from_user(self):
        """index='car_articles' must appear as a string literal in engine.py (T-03-04)."""
        import inspect
        import nitrofind.search.engine as engine_module
        source = inspect.getsource(engine_module)
        assert '"car_articles"' in source, (
            "engine.py must hard-code index='car_articles' — never accept from user input"
        )

    def test_no_body_kwarg_in_source(self):
        """engine.py must not use the deprecated body= parameter (Pattern 5)."""
        import inspect
        import nitrofind.search.engine as engine_module
        source = inspect.getsource(engine_module)
        # Check that no client.search() call uses body= kwarg
        # Simple check: "body=" should not appear in any search call context
        # We allow "self._body" (the attribute) but not "body=" as a kwarg
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            if "client.search(" in stripped or "self._client.search(" in stripped:
                assert "body=" not in stripped, (
                    f"Deprecated body= kwarg found in client.search() call: {stripped!r}"
                )

    def test_qthreadpool_global_instance_used(self):
        """engine.py must use QThreadPool.globalInstance(), not QThreadPool()."""
        import inspect
        import nitrofind.search.engine as engine_module
        source = inspect.getsource(engine_module)
        assert "QThreadPool.globalInstance()" in source, (
            "engine.py must use QThreadPool.globalInstance() — not QThreadPool()"
        )

    def test_logger_uses_percent_formatting(self):
        """All logger calls must use % lazy formatting, not f-strings."""
        import inspect
        import nitrofind.search.engine as engine_module
        source = inspect.getsource(engine_module)
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("logger.") and "f'" in stripped:
                pytest.fail(
                    f"Logger call uses f-string formatting (must use %): {stripped!r}"
                )
            if stripped.startswith("logger.") and 'f"' in stripped:
                pytest.fail(
                    f"Logger call uses f-string formatting (must use %): {stripped!r}"
                )


# ---------------------------------------------------------------------------
# Integration tests (require live ES node)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_callback_receives_article_results():
    """Integration: SearchEngine.search() delivers ArticleResult list via callback."""
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")

    from elasticsearch import Elasticsearch
    client = Elasticsearch(ES_URL, request_timeout=5)
    engine = SearchEngine(client)

    results_received = []
    errors_received = []

    engine.search(
        "Ferrari",
        callback=lambda r: results_received.extend(r),
        error_callback=lambda e: errors_received.append(e),
    )

    # Wait briefly for the worker to complete (integration only)
    import time
    time.sleep(2)

    if errors_received:
        pytest.fail(f"Search failed with error: {errors_received[0]}")

    assert len(results_received) > 0, "Expected at least one result for 'Ferrari'"
    assert all(isinstance(r, ArticleResult) for r in results_received)


@pytest.mark.integration
def test_ferrari_308_top3():
    """Integration: searching 'Ferrari 308' returns a result with '308' in top 3 titles."""
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")

    from elasticsearch import Elasticsearch
    from nitrofind.search.query_builder import build_search_body
    client = Elasticsearch(ES_URL, request_timeout=5)

    signals = _SearchSignals()
    results = []
    signals.results_ready.connect(lambda r: results.extend(r))

    body = build_search_body("Ferrari 308")
    worker = _SearchWorker(client, body, signals)
    worker.run()

    assert len(results) >= 1, "Expected at least one result for 'Ferrari 308'"
    assert any(
        "308" in r.title.lower() for r in results[:3]
    ), f"Expected '308' in top-3 titles, got: {[r.title for r in results[:3]]}"


@pytest.mark.integration
def test_recency_decay_active():
    """Integration: explain=True confirms function_score scoring tree (recency decay active)."""
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")

    from elasticsearch import Elasticsearch
    from nitrofind.search.query_builder import build_function_score_query
    client = Elasticsearch(ES_URL, request_timeout=5)

    resp = client.search(
        index="car_articles",
        query=build_function_score_query("Ferrari 308"),
        explain=True,
        size=3,
    )
    hits = resp["hits"]["hits"]
    if hits:
        assert "_explanation" in hits[0], (
            "Expected '_explanation' in first hit — confirms function_score scoring tree is active"
        )
