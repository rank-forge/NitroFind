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

        # SCHEMA-03: full plain-text body + 300-character display excerpt
        "body":          {"type": "text", "analyzer": "standard"},
        "excerpt":       {"type": "keyword"},  # Pitfall 5: keyword not text — display-only, no analysis

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


def ensure_index(client: Elasticsearch) -> None:
    """Create the car_articles index idempotently.

    Uses ignore_status=[400] (Pattern 3) so calling this twice raises no exception —
    a 400 ResourceAlreadyExistsException is silently swallowed.
    """
    client.options(ignore_status=[400]).indices.create(
        index="car_articles",
        mappings=CAR_ARTICLES_MAPPING,
        settings={"number_of_shards": 1, "number_of_replicas": 0},
    )
