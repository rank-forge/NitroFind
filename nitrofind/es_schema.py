"""
nitrofind.es_schema — Elasticsearch index schema for NitroFind.

Exports:
  CAR_ARTICLES_MAPPING  — full mapping dict for the car_articles index
  ensure_index          — idempotent index creation (Pattern 3)

Requirement coverage:
  SCHEMA-01: core identity fields
  SCHEMA-02: relevance scoring fields
  SCHEMA-03: full-text body + display excerpt
  SCHEMA-04: automotive facet fields
  L-02: flattened specs field (prevents mapping explosion)
  T-02-04: dynamic: "false" blocks attacker-injected field types
"""

from elasticsearch import Elasticsearch

INDEX_REQUEST_TIMEOUT_SECONDS = 180

# Full mapping definition (Pattern 3, SCHEMA-01..04, D-08/D-09, L-02)
CAR_ARTICLES_MAPPING = {
    "dynamic": "false",  # Pitfall 6: string not boolean; T-02-04: blocks field injection
    "properties": {
        # SCHEMA-01: core identity fields
        "title":         {"type": "text", "analyzer": "standard"},
        "url":           {"type": "keyword"},
        "source_domain": {"type": "keyword"},
        "article_id":    {"type": "keyword"},
        "scraped_at":    {"type": "date"},

        # SCHEMA-02: relevance scoring fields
        "published_at":  {"type": "date"},
        "word_count":    {"type": "integer"},
        "has_infobox":   {"type": "boolean"},
        "image_count":   {"type": "integer"},
        "hero_image_url": {"type": "keyword"},

        # SCHEMA-03: full plain-text body + 300-character display excerpt
        "body":          {"type": "text", "analyzer": "standard"},
        "excerpt":       {"type": "keyword"},  # Pitfall 5: keyword not text — display-only, no analysis
        "body_html":     {                     # Phase 9 / BUG-01: stored-not-tokenized display HTML
            "type": "text",
            "index": False,   # stored in _source, not tokenized — NOT keyword (ignore_above would truncate)
        },

        # SCHEMA-04: automotive facet fields
        "manufacturer":       {"type": "keyword"},
        "production_start":   {"type": "integer"},
        "production_end":     {"type": "integer"},
        "body_style":         {"type": "keyword"},
        "era_bucket":         {"type": "keyword"},  # D-09: decade label e.g. "1960s"
        "country_of_origin":  {"type": "keyword"},

        # L-02: flattened prevents mapping explosion from varied infobox shapes
        "specs":              {"type": "flattened"},
    }
}


def _allocation_explain_summary(client: Elasticsearch) -> str:
    """Return a compact shard-allocation diagnostic string for car_articles."""
    try:
        explain = client.options(
            request_timeout=INDEX_REQUEST_TIMEOUT_SECONDS,
        ).cluster.allocation_explain(
            index="car_articles",
            shard=0,
            primary=True,
        )
    except Exception as exc:
        return f"allocation_explain_unavailable={type(exc).__name__}: {exc}"

    unassigned = explain.get("unassigned_info") or {}
    reason = unassigned.get("reason")
    details = unassigned.get("details")
    current_state = explain.get("current_state")
    return (
        "allocation_explain="
        f"current_state={current_state!r}, "
        f"reason={reason!r}, "
        f"details={details!r}"
    )


def ensure_index(client: Elasticsearch) -> None:
    """Create the car_articles index idempotently.

    Uses ignore_status=[400] (Pattern 3) so calling this twice raises no exception —
    a 400 ResourceAlreadyExistsException is silently swallowed.
    """
    client.options(
        ignore_status=[400],
        request_timeout=INDEX_REQUEST_TIMEOUT_SECONDS,
    ).indices.create(
        index="car_articles",
        mappings=CAR_ARTICLES_MAPPING,
        settings={"number_of_shards": 1, "number_of_replicas": 0},
    )
    health = client.options(
        request_timeout=INDEX_REQUEST_TIMEOUT_SECONDS,
    ).cluster.health(
        index="car_articles",
        wait_for_status="yellow",
        wait_for_active_shards=1,
        timeout="120s",
    )
    if health.get("timed_out") or health.get("status") == "red":
        detail = _allocation_explain_summary(client)
        raise RuntimeError(
            "car_articles index is not ready: "
            f"status={health.get('status')!r}, "
            f"timed_out={health.get('timed_out')!r}, "
            f"{detail}"
        )
