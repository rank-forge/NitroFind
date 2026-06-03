"""
nitrofind.server — Flask application, routes, and background ES startup machinery.

Exports:
  app                 — Flask WSGI application object
  state               — Shared mutable state dict (ready, process, es_health, doc_count,
                        index_size_bytes, es_client)
  start_es_background — Spawn daemon thread that starts ES subprocess and polls cluster health
  index               — GET / route: NitroFind placeholder HTML
  api_status          — GET /api/status route: 503 warmup guard / 200 health JSON
  api_search          — GET /api/search route: ranked full-text search with optional filters
  _result_to_api_dict — Serialize ArticleResult to the API-01 wire format

Requirement coverage:
  SRVR-02: Flask listens on localhost:5000; PORT overridable via env var
  SRVR-03: HTTP 503 {"status": "starting"} during ES warmup
  API-01:  GET /api/search returns JSON array with title, url, source_domain, excerpt, score, took_ms
  API-02:  GET /api/search accepts manufacturer, era_bucket, body_style filter params
  API-03:  GET /api/status returns JSON with es_health, doc_count, index_size_bytes
  API-04:  GET / serves NitroFind placeholder HTML

Security mitigations:
  T-06-05: 503 warmup guard checks state["ready"] before any ES client call
  T-06-06: GIL-safe single-writer state dict — no Lock needed for simple values
  T-06-07: Hard 180s monotonic deadline prevents poller from running forever
"""

import logging
import os
import subprocess
import threading
import time

from flask import Flask
from elasticsearch import Elasticsearch

from nitrofind.es_manager import ES_URL, shutdown_es  # noqa: F401 (shutdown_es re-exported for main.py)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

logger = logging.getLogger("nitrofind.server")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared mutable state (D-09: module-level dict, single writer, GIL-safe)
# ---------------------------------------------------------------------------

state: dict = {
    "ready": False,
    "process": None,        # subprocess.Popen | None
    "es_health": None,      # str | None: "green" | "yellow" | "red"
    "doc_count": 0,
    "index_size_bytes": 0,
    "es_client": None,      # Phase 7: Elasticsearch instance, set by _es_health_poller
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """GET / — NitroFind placeholder HTML (D-13)."""
    return "<h1>NitroFind</h1><p>Search UI coming in Phase 8.</p>"


@app.route("/api/status")
def api_status():
    """GET /api/status — 503 warmup guard / 200 health JSON (D-11, D-12).

    Returns HTTP 503 while state["ready"] is False to prevent ES client calls
    during startup (T-06-05 mitigation).
    """
    if not state["ready"]:
        return {"status": "starting"}, 503
    return {
        "status": "ok",
        "es_health": state["es_health"],
        "doc_count": state["doc_count"],
        "index_size_bytes": state["index_size_bytes"],
    }, 200


# ---------------------------------------------------------------------------
# ES subprocess helpers
# ---------------------------------------------------------------------------


def _start_es_process(es_home: str) -> subprocess.Popen:
    """Start the ES JVM as a child subprocess (Linux/WSL only — D-01).

    Returns a Popen object. Raises OSError if the binary is missing or not
    executable — the caller (_es_health_poller) catches this.
    """
    es_bin = os.path.join(es_home, "bin", "elasticsearch")
    return subprocess.Popen(
        [es_bin],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def _fetch_index_stats(client: Elasticsearch) -> tuple[int, int]:
    """Return (doc_count, size_in_bytes) from cat.indices.

    Returns (0, 0) on any error — called only after state["ready"] is True,
    so a failure here is non-fatal; the route falls back to zero values.

    Note: ES cat API uses "store.size" (dotted key) when h=["store.size"]
    is requested with bytes="b" (RESEARCH.md Pitfall 2).
    """
    try:
        result = client.cat.indices(
            index="car_articles",
            h=["docs.count", "store.size"],
            bytes="b",
            format="json",
        )
        if result:
            row = result[0]
            return int(row.get("docs.count") or 0), int(row.get("store.size") or 0)
    except Exception as exc:
        logger.warning("cat.indices failed: %s", exc)
    return 0, 0


def _es_health_poller(es_home: str) -> None:
    """Background thread target: start ES and poll until healthy (D-02..D-05).

    Flow:
      1. Start ES subprocess via _start_es_process().
      2. Poll cluster.health() every 2s for up to 180s (D-03, D-04).
      3. On green/yellow status (D-05): fetch index stats, set state["ready"] = True.
      4. On process exit or deadline expiry: log and return.

    Thread safety: state dict has a single writer (this function) and multiple
    readers (Flask route handlers). GIL makes simple value assignment atomic
    for bool/int/str — no Lock required (RESEARCH.md, T-06-06).
    """
    try:
        state["process"] = _start_es_process(es_home)
    except OSError as exc:
        logger.error("ES start failed: %s", exc)
        return  # state["process"] remains None — finally block guards against None (Pitfall 4)

    client = Elasticsearch(ES_URL, request_timeout=2)
    deadline = time.monotonic() + 180  # D-03: hard 180s deadline (T-06-07 mitigation)
    last_exc: Exception | None = None

    while time.monotonic() < deadline:
        if state["process"].poll() is not None:
            logger.error("ES process exited unexpectedly")
            return

        try:
            resp = client.cluster.health()
            if resp["status"] in ("green", "yellow"):  # D-05
                state["es_health"] = resp["status"]
                state["doc_count"], state["index_size_bytes"] = _fetch_index_stats(client)
                state["es_client"] = client  # Phase 7: single writer — GIL-safe (same rationale as ready flag, T-06-06)
                state["ready"] = True
                return
        except Exception as exc:
            last_exc = exc

        time.sleep(2)  # D-04: 2s poll interval

    logger.warning("ES did not become healthy within 180s. Last error: %s", last_exc)


def start_es_background(es_home: str) -> None:
    """Spawn the ES health-poller as a daemon thread (D-02, RESEARCH.md Pattern 2).

    daemon=True ensures the thread does not block process exit if the finally
    block in main.py runs before the poller completes (RESEARCH.md anti-pattern).
    """
    t = threading.Thread(target=_es_health_poller, args=(es_home,), daemon=True)
    t.start()
