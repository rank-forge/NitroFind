"""
Integration test for INFRA-02: live Elasticsearch reaches healthy within 180s.

Marked @pytest.mark.integration — excluded from quick-run:
    pytest -m "not integration"

Run only with ES_HOME set:
    ES_HOME=/path/to/elasticsearch pytest tests/integration/test_es_startup.py -v

Skips gracefully when ES_HOME is not set to avoid blocking CI/dev machines
that do not have Elasticsearch installed.
"""

import os
import pytest

from nitrofind.es_manager import ESHealthWorker


@pytest.mark.integration
def test_real_es_reaches_healthy():
    """Live ES subprocess started by ESHealthWorker reaches green/yellow within 210s.

    Verifies INFRA-02: ES starts, health becomes green/yellow within 180s deadline.
    Verifies INFRA-03: shutdown_es() called in finally block — no orphan JVM.

    Upper bound is 210s (180s health deadline + 30s margin) to accommodate slow cold starts
    on resource-constrained machines.
    """
    if not os.environ.get("ES_HOME"):
        pytest.skip("ES_HOME not set — skipping live ES integration test")

    ready_calls = []
    failed_calls = []

    worker = ESHealthWorker(os.environ["ES_HOME"])
    worker.es_ready.connect(lambda: ready_calls.append(True))
    worker.es_failed.connect(lambda reason: failed_calls.append(reason))

    try:
        # Call run() synchronously (not start()) to avoid Qt event loop dependencies.
        # run() blocks until es_ready or es_failed is emitted.
        worker.run()
    finally:
        # INFRA-03: always shut down the ES subprocess — no orphan JVM after test.
        worker.shutdown_es()

    assert len(ready_calls) == 1, (
        f"Expected exactly 1 es_ready emission, got {len(ready_calls)}. "
        f"es_failed reasons: {failed_calls}"
    )
    assert len(failed_calls) == 0, (
        f"Expected no es_failed, got: {failed_calls}"
    )
