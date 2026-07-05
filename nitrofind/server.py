"""
nitrofind.server — Flask application, routes, and background ES startup machinery.

Exports:
  app                 — Flask WSGI application object
  state               — Shared mutable state dict (ready, process, es_health, doc_count,
                        index_size_bytes, es_client)
  start_es_background — Spawn daemon thread that starts ES subprocess and polls cluster health
  index               — GET / route: serves rendered index.html search UI
  api_status          — GET /api/status route: 503 warmup guard / 200 health JSON
  api_search          — GET /api/search route: ranked full-text search with optional filters and pagination
  _result_to_api_dict — Serialize ArticleResult to the per-item wire format (7 keys, no took_ms)

Requirement coverage:
  SRVR-02: Flask listens on localhost:5000; PORT overridable via env var
  SRVR-03: HTTP 503 {"status": "starting"} during ES warmup
  API-01:  GET /api/search returns JSON wrapper {results, total, took_ms, page} with per-item keys title, url, source_domain, excerpt, body, body_html, score
  API-02:  GET /api/search accepts manufacturer, era_bucket, body_style filter params
  API-03:  GET /api/status returns JSON with es_health, doc_count, index_size_bytes
  API-04:  GET / serves rendered index.html search UI

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

from flask import Flask, jsonify, render_template, request
from elasticsearch import Elasticsearch

from nitrofind.es_manager import ES_URL, shutdown_es  # noqa: F401 (shutdown_es re-exported for main.py)
from nitrofind.search.models import ArticleResult
from nitrofind.search.query_builder import build_search_body, build_filter_clauses

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

logger = logging.getLogger("nitrofind.server")

_pkg_dir = os.path.dirname(os.path.abspath(__file__))

# SORT-02: allowlist for sort param (T-10-SORT mitigation — unknown values coerced to None)
_VALID_SORTS: frozenset[str] = frozenset({"relevance", "date", "size"})
# PAGE-01: number of results per page (matches frontend pageSize constant)
PAGE_SIZE: int = 10
app = Flask(
    __name__,
    template_folder=os.path.join(_pkg_dir, "..", "templates"),
    static_folder=os.path.join(_pkg_dir, "..", "static"),
)

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
    """GET / — NitroFind search UI (Phase 8)."""
    return render_template("index.html")


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


def _result_to_api_dict(result: ArticleResult) -> dict:
    """Serialize one ArticleResult to the API-01 wire format.

    Excerpt selection: use highlight_body[0] if ES returned a highlighted
    fragment (contains <b> tags), otherwise fall back to plain _source excerpt.
    This satisfies API-01's requirement that the excerpt contain ES highlight
    tags when a match exists.

    Note: took_ms is no longer per-item — it now lives on the wrapper response
    (PAGE-02). The wrapper response has keys: results, total, took_ms, page.

    Args:
        result:   ArticleResult instance from ArticleResult.from_es_hit().

    Returns:
        dict with keys: title, url, source_domain, excerpt, body, body_html, score.
    """
    excerpt = result.highlight_body[0] if result.highlight_body else result.excerpt
    return {
        "title": result.title,
        "url": result.url,
        "source_domain": result.source_domain,
        "excerpt": excerpt,
        "body": result.body,
        "body_html": result.body_html,   # Phase 9: HTML for article view rendering
        "score": result.score,
    }


def _safe_int_param(raw: str | None) -> int | None:
    """Coerce string query param to int, returning None on error.

    Tampering mitigation T-11-02: raw user strings never reach an ES range
    clause — only validated int values pass through.

    Args:
        raw: Raw query param string (e.g. "1960"), or None if param absent.

    Returns:
        int on success; None if raw is falsy or not a valid integer.
    """
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@app.route("/api/search")
def api_search():
    """GET /api/search — ranked full-text search with optional filters and pagination.

    Requirement coverage:
      API-01: returns JSON wrapper {results, total, took_ms, page} with per-item keys
              title, url, source_domain, excerpt, body, body_html, score
      API-02: accepts manufacturer, era_bucket, body_style filter params
      SRVR-03: returns 503 while state["ready"] is False
      PAGE-01: page param maps to from_ offset (from_ = (page-1) * PAGE_SIZE)
      PAGE-02: total key exposes hits.total.value for pagination UI

    Security mitigations:
      T-07-01: q placed in multi_match.query value only — never interpolated as DSL key
      T-07-02: filter params placed in term filter value fields via build_filter_clauses()
      T-07-03: index="car_articles" is a hard-coded literal — never derived from user input
      T-07-04: size clamped to MAX_RESULT_SIZE by build_search_body()
      T-07-05: blank q guard returns [] before any ES call (prevents multi_match BadRequestError)
      T-07-07: 503 guard runs before any state["es_client"] access
      T-12-01: page param coerced via _safe_int_param — raw string never reaches ES
      T-12-02: page=0 clamped to 1 via max(1, ...); very large page yields ES 400 caught by try/except
    """
    if not state["ready"]:
        return {"status": "starting"}, 503

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    filters = build_filter_clauses(
        manufacturer=request.args.get("manufacturer") or None,
        era_bucket=request.args.get("era_bucket") or None,
        body_style=request.args.get("body_style") or None,
        year_from=_safe_int_param(request.args.get("year_from")),
        year_to=_safe_int_param(request.args.get("year_to")),
        country=request.args.get("country") or None,
    )
    # SORT-02: read sort param with allowlist (T-10-SORT mitigation)
    sort = request.args.get("sort") or None
    if sort not in _VALID_SORTS:
        sort = None  # unknown value → treat as relevance (silently coerced)

    # PAGE-01: read page param; non-integer or zero → clamp to 1 (T-12-01, T-12-02)
    page = max(1, _safe_int_param(request.args.get("page")) or 1)
    from_value = (page - 1) * PAGE_SIZE

    body = build_search_body(q, filters=filters, sort=sort, size=PAGE_SIZE, from_=from_value)

    try:
        resp = state["es_client"].search(
            index="car_articles",
            query=body["query"],
            sort=body.get("sort"),        # SORT-02: None → ES default _score desc; list → field sort
            highlight=body.get("highlight"),
            source=body.get("_source"),   # 'source' not '_source' — known naming difference (Pitfall 1)
            size=body.get("size", PAGE_SIZE),
            from_=body.get("from", 0),
        )
    except Exception as exc:
        logger.warning("Search error: %s: %s", type(exc).__name__, exc)
        return {"error": "search_failed"}, 500

    took_ms = resp.get("took", 0)
    total = resp["hits"]["total"]["value"]  # PAGE-02: true hit count across all pages
    results = [ArticleResult.from_es_hit(hit) for hit in resp["hits"]["hits"]]
    return jsonify({
        "results": [_result_to_api_dict(r) for r in results],
        "total": total,
        "took_ms": took_ms,
        "page": page,
    })


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
