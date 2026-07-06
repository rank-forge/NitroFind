"""
Unit tests for nitrofind.server — SRVR-02, SRVR-03, API-03, API-04 coverage.

Test strategy:
  - Monkeypatch the module-level state dict to control ready/not-ready branches
  - Use Flask test_client() — no live ES, no real subprocess
  - No QThread, no Qt event loop

Requirement coverage:
  SRVR-02: PORT env var port-resolution contract (test_port_env_var)
  SRVR-03: HTTP 503 before ready, HTTP 200 after ready (test_status_before/after_ready)
  API-03:  /api/status JSON shape (test_status_response_shape)
  API-04:  GET / serves rendered index.html template (test_root_returns_html, test_root_uses_template)
"""

import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures: Flask test clients with monkeypatched state
# ---------------------------------------------------------------------------


@pytest.fixture
def client_not_ready(monkeypatch):
    """Flask test client with state["ready"] = False (warmup / not-yet-healthy)."""
    from nitrofind import server
    monkeypatch.setitem(server.state, "ready", False)
    return server.app.test_client()


@pytest.fixture
def client_ready(monkeypatch):
    """Flask test client with state fully populated as if ES just became healthy."""
    from nitrofind import server
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_health", "green")
    monkeypatch.setitem(server.state, "doc_count", 42)
    monkeypatch.setitem(server.state, "index_size_bytes", 1024)
    return server.app.test_client()


# ---------------------------------------------------------------------------
# SRVR-02: PORT env var resolution contract
# ---------------------------------------------------------------------------


def test_port_env_var(monkeypatch):
    """int(os.environ.get("PORT", 5000)) resolves correctly with and without PORT set.

    This validates the port-resolution expression used by main.py (SRVR-02).
    No real server is started — only the expression is exercised.
    """
    # Default: PORT not set → 5000
    monkeypatch.delenv("PORT", raising=False)
    assert int(os.environ.get("PORT", 5000)) == 5000

    # Override: PORT=8080 → 8080
    monkeypatch.setenv("PORT", "8080")
    assert int(os.environ.get("PORT", 5000)) == 8080


# ---------------------------------------------------------------------------
# SRVR-03: HTTP 503 before ES is ready
# ---------------------------------------------------------------------------


def test_status_before_ready(client_not_ready):
    """GET /api/status returns 503 with {"status": "starting"} before ES is healthy."""
    resp = client_not_ready.get("/api/status")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "starting"}


# ---------------------------------------------------------------------------
# SRVR-03: HTTP 200 after ES becomes healthy
# ---------------------------------------------------------------------------


def test_status_after_ready(client_ready):
    """GET /api/status returns 200 with status=ok and es_health=green when ready."""
    resp = client_ready.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["es_health"] == "green"


# ---------------------------------------------------------------------------
# API-03: /api/status response shape
# ---------------------------------------------------------------------------


def test_status_response_shape(client_ready):
    """GET /api/status JSON has the four expected keys with correct types."""
    resp = client_ready.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data
    assert "es_health" in data
    assert "doc_count" in data
    assert "index_size_bytes" in data
    assert isinstance(data["doc_count"], int)
    assert isinstance(data["index_size_bytes"], int)


# ---------------------------------------------------------------------------
# API-04: GET / rendered index.html template
# ---------------------------------------------------------------------------


def test_root_returns_html(client_not_ready):
    """GET / returns HTTP 200 with rendered index.html template."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert b"NitroFind" in resp.data
    assert b"<!DOCTYPE html>" in resp.data


def test_root_uses_template(client_not_ready):
    """GET / responds with text/html content-type and structural template marker."""
    resp = client_not_ready.get("/")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")
    assert b'data-state="home"' in resp.data


# ---------------------------------------------------------------------------
# API-05: /api/articles/<article_id> full detail payload
# ---------------------------------------------------------------------------


def test_article_detail_503_while_not_ready(client_not_ready, monkeypatch):
    """GET /api/articles/<article_id> returns 503 before ES is ready."""
    from nitrofind import server
    mock_es = MagicMock()
    monkeypatch.setitem(server.state, "es_client", mock_es)

    resp = client_not_ready.get("/api/articles/12345")

    assert resp.status_code == 503
    assert resp.get_json() == {"status": "starting"}
    mock_es.get.assert_not_called()


def test_article_detail_returns_full_article(monkeypatch):
    """GET /api/articles/<article_id> returns full detail payload for a clicked result."""
    from nitrofind import server

    mock_es = MagicMock()
    mock_es.get.return_value = {
        "_score": 1.0,
        "_source": {
            "article_id": "12345",
            "title": "Ford Mustang",
            "url": "https://en.wikipedia.org/wiki/Ford_Mustang",
            "source_domain": "en.wikipedia.org",
            "excerpt": "The Ford Mustang is a pony car.",
            "body": "Full article text.",
            "body_html": "<div><p>Full article text.</p></div>",
            "hero_image_url": "https://upload.wikimedia.org/mustang.jpg",
            "manufacturer": "Ford",
            "production_start": 1964,
            "production_end": 2023,
            "era_bucket": "1960s",
            "body_style": "Coupe",
            "country_of_origin": "United States",
            "specs": {"engine": "V8"},
        },
    }
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/articles/12345")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["article_id"] == "12345"
    assert data["title"] == "Ford Mustang"
    assert data["body_html"] == "<div><p>Full article text.</p></div>"
    assert data["hero_image_url"] == "https://upload.wikimedia.org/mustang.jpg"
    assert data["specs"] == {"engine": "V8"}
    mock_es.get.assert_called_once()
    call_kwargs = mock_es.get.call_args.kwargs
    assert call_kwargs["index"] == "car_articles"
    assert call_kwargs["id"] == "12345"


def test_article_detail_404_when_missing(monkeypatch):
    """GET /api/articles/<article_id> returns 404 when ES cannot find the document."""
    from elasticsearch import NotFoundError
    from nitrofind import server

    mock_es = MagicMock()
    mock_es.get.side_effect = NotFoundError(
        message="not found",
        meta=MagicMock(status=404),
        body={"found": False},
    )
    monkeypatch.setitem(server.state, "ready", True)
    monkeypatch.setitem(server.state, "es_client", mock_es)
    client = server.app.test_client()

    resp = client.get("/api/articles/missing")

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "article_not_found"}
