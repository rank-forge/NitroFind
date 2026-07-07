"""
nitrofind.scraper.indexer — Elasticsearch bulk indexer with size guard.

Exports:
  BulkIndexer       — wraps streaming_bulk; checks index size every N docs; halts at 1.8 GB
  build_action      — builds a streaming_bulk action dict with _id for deduplication
  SIZE_HALT_BYTES   — halt threshold: 1.8 GB (SCRP-04)
  CHECK_EVERY_N_DOCS — size check interval: every 100 successfully indexed docs

Requirement coverage:
  SCRP-03: _id set to article_id (str(pageid) for Wikipedia) for ES deduplication
  SCRP-04: halts and logs warning containing 'Halting scraper' + 'SCRP-04' before
           car_articles index exceeds 1.8 GB
  L-03: ES document _id = str(page.pageid) for Wikipedia articles
  L-04: index size capped at 1.8 GB to stay within the 2 GB project constraint

Anti-patterns avoided:
  Per-document client.index() calls — use streaming_bulk exclusively (Pattern 3)
  Pitfall 8: size check uses primaries.store.size_in_bytes (not total) to avoid
             double-counting replica shards on a single-node setup
  Hardcoded 'http://localhost:9200' — always import ES_URL from es_manager
"""

import logging

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

from nitrofind.es_manager import ES_URL  # single source of truth (WR-01)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants (SCRP-04, L-04)
# ---------------------------------------------------------------------------

SIZE_HALT_BYTES: int = 1_800_000_000  # 1.8 GB — SCRP-04 halt threshold
CHECK_EVERY_N_DOCS: int = 100         # Check index size after every N successful docs


# ---------------------------------------------------------------------------
# Free function: build_action (SCRP-03, L-03, Pattern 4)
# ---------------------------------------------------------------------------

def build_action(doc: dict) -> dict:
    """Build a streaming_bulk action dict with _id set from doc['article_id'].

    Sets _id to doc['article_id'] so that indexing the same document twice is
    an upsert (no duplicate created in car_articles index) — SCRP-03.

    Args:
        doc: Document dict matching CAR_ARTICLES_MAPPING.properties fields.
             Must contain 'article_id' key (str(pageid) for Wikipedia, URL slug
             for blogs — per L-03).

    Returns:
        Action dict with '_index', '_id', and all fields from doc merged in.
    """
    action = {"_index": "car_articles", "_id": doc["article_id"]}
    action.update(doc)
    return action


def _bulk_item_id(info: dict) -> str | None:
    """Return the Elasticsearch document id from a streaming_bulk item response."""
    if not isinstance(info, dict):
        return None
    for item in info.values():
        if isinstance(item, dict) and item.get("_id"):
            return str(item["_id"])
    return None


# ---------------------------------------------------------------------------
# BulkIndexer class (SCRP-03, SCRP-04, Pattern 3)
# ---------------------------------------------------------------------------

class BulkIndexer:
    """Streams document actions into Elasticsearch using streaming_bulk.

    Checks the car_articles index size every CHECK_EVERY_N_DOCS successfully
    indexed documents. If the size reaches SIZE_HALT_BYTES (1.8 GB), logs a
    WARNING containing the literals 'Halting scraper' and 'SCRP-04', and
    returns early — the generator is abandoned (SCRP-04).

    Per-action errors (ok=False from streaming_bulk) are logged as warnings
    and skipped; they do not increment the doc counter.

    Usage:
        indexer = BulkIndexer(client=Elasticsearch(ES_URL), state=state_manager)
        total = indexer.index_all(build_action(doc) for doc in scraped_docs)
    """

    def __init__(self, client: Elasticsearch, state) -> None:
        """Initialize BulkIndexer.

        Args:
            client: Elasticsearch 8.x client instance.
            state:  SQLiteStateManager (or None) for visit-tracking.
                    Stored but not used directly by BulkIndexer — provided for
                    Plan 05 CLI to access via the same object.
        """
        self._client = client
        self._state = state

    def index_all(self, actions_generator) -> int:
        """Stream actions into Elasticsearch. Returns total successfully indexed doc count.

        Iterates over streaming_bulk results. On each successful doc:
          - increments doc_count
          - every CHECK_EVERY_N_DOCS docs: checks index size via _index_size_bytes()
          - if size >= SIZE_HALT_BYTES: logs WARNING with 'Halting scraper' + 'SCRP-04'
            and returns doc_count immediately (generator abandoned)

        Per-action failures (ok=False) are logged at WARNING level and skipped.

        Unexpected ES exceptions (e.g. connection failure) are caught, logged, and
        re-raised so the Plan 05 CLI can report the error and exit cleanly.

        Args:
            actions_generator: Iterable of action dicts (from build_action()).

        Returns:
            Integer count of successfully indexed documents.
        """
        doc_count = 0
        try:
            for ok, info in streaming_bulk(
                self._client,
                actions_generator,
                chunk_size=100,
                raise_on_error=False,
                raise_on_exception=False,
            ):
                if not ok:
                    # Follow es_manager.py convention: log type name in warning
                    logger.warning("Bulk index error: %s", info)
                    continue

                doc_count += 1
                doc_id = _bulk_item_id(info)
                if doc_id and self._state is not None:
                    self._state.mark_visited(doc_id, "car_articles")
                if doc_count % CHECK_EVERY_N_DOCS == 0:
                    size = self._index_size_bytes()
                    logger.info(
                        "Indexed %d docs; index size %.2f MB",
                        doc_count,
                        size / 1e6,
                    )
                    if size >= SIZE_HALT_BYTES:
                        logger.warning(
                            "Index size %.2f GB reached halt threshold. "
                            "Halting scraper. SCRP-04 size guard triggered.",
                            size / 1e9,
                        )
                        return doc_count
        except Exception as exc:
            logger.warning(
                "Bulk indexing failed: %s: %s", type(exc).__name__, exc
            )
            raise

        return doc_count

    def _index_size_bytes(self) -> int:
        """Return the primary shard store size of car_articles index in bytes.

        Pitfall 8: accesses primaries.store.size_in_bytes — NOT total.store —
        to avoid double-counting on single-node setups where total == 2 * primaries
        when replicas exist (even with replicas=0, the key path must be consistent).
        """
        stats = self._client.indices.stats(index="car_articles", metric="store")
        try:
            return stats["indices"]["car_articles"]["primaries"]["store"]["size_in_bytes"]
        except KeyError:
            # Index absent or stats response incomplete — treat as 0 bytes (CR-04)
            return 0
