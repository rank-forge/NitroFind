"""
scripts/scraper.py — NitroFind data pipeline CLI entrypoint.

Fetches automotive articles from Wikipedia (MediaWiki API) and/or blog targets
(BeautifulSoup4 + requests), cleans and indexes them into the local
Elasticsearch car_articles index.

Usage:
    python scripts/scraper.py [--wikipedia | --blogs | --all] [--config PATH]

Defaults: --all (scrape both Wikipedia and configured blog targets).

Security:
  - Config loaded with yaml.safe_load (never yaml.load — T-02-01 mitigation)
  - ES reachability validated before any scrape begins
  - SQLite state DB constrained to project directory (path traversal guard)
"""

import argparse
import logging
import os
import sys

import yaml
from elasticsearch import Elasticsearch

from nitrofind.es_manager import ES_URL
from nitrofind.es_schema import ensure_index

INDEX_NAME = "car_articles"
from nitrofind.scraper.blogs import BlogScraper
from nitrofind.scraper.indexer import BulkIndexer, build_action
from nitrofind.scraper.state import SQLiteStateManager
from nitrofind.scraper.wikipedia import WikipediaScraper

# ---------------------------------------------------------------------------
# Module-level logger and constants
# ---------------------------------------------------------------------------

logger = logging.getLogger("nitrofind.scraper.cli")

DEFAULT_CONFIG_PATH = "config/scraper.yaml"
STATE_DB_PATH = "data/scraper_state.db"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    """Configure logging.basicConfig at INFO level to stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _load_config(config_path: str) -> dict:
    """Load scraper config from YAML file using yaml.safe_load (T-02-01).

    Exits 1 on FileNotFoundError or YAML parse error.
    NEVER calls bare yaml.load — only yaml.safe_load.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        sys.stderr.write(f"Config file not found: {config_path}\n")
        sys.exit(1)
    except yaml.YAMLError as exc:
        sys.stderr.write(f"Failed to parse {config_path}: {exc}\n")
        sys.exit(1)


def _create_client() -> Elasticsearch:
    """Create Elasticsearch client and validate reachability via client.info().

    Exits 1 if ES is unreachable, logging the exception type and message.
    Uses request_timeout=5 (T-02-21 DoS mitigation).
    """
    client = Elasticsearch(ES_URL, request_timeout=5)
    try:
        client.info()
    except Exception as exc:
        sys.stderr.write(
            f"Cannot reach Elasticsearch at {ES_URL}: {type(exc).__name__}: {exc}\n"
        )
        sys.exit(1)
    return client


def _ensure_data_dir() -> None:
    """Create data/ directory if it does not exist."""
    os.makedirs("data", exist_ok=True)


def _run_wikipedia(
    config: dict, state: SQLiteStateManager, client: Elasticsearch
) -> int:
    """Scrape Wikipedia and index into car_articles. Returns doc count indexed."""
    logger.info("Starting Wikipedia scrape...")
    scraper = WikipediaScraper(config, state)
    actions = (build_action(doc) for doc in scraper.yield_documents())
    indexer = BulkIndexer(client, state)
    count = indexer.index_all(actions)
    logger.info("Wikipedia scrape complete: %d documents indexed", count)
    return count


def _run_blogs(
    config: dict, state: SQLiteStateManager, client: Elasticsearch
) -> int:
    """Scrape configured blog targets and index into car_articles. Returns doc count."""
    logger.info("Starting blog scrape...")
    scraper = BlogScraper(config, state)
    actions = (build_action(doc) for doc in scraper.yield_documents())
    indexer = BulkIndexer(client, state)
    count = indexer.index_all(actions)
    logger.info("Blog scrape complete: %d documents indexed", count)
    return count


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. Returns argparse.Namespace."""
    parser = argparse.ArgumentParser(
        description="NitroFind data pipeline scraper",
        prog="scraper.py",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--wikipedia",
        action="store_true",
        help="Scrape only Wikipedia",
    )
    group.add_argument(
        "--blogs",
        action="store_true",
        help="Scrape only configured blog targets",
    )
    group.add_argument(
        "--all",
        dest="all_sources",
        action="store_true",
        help="Scrape both Wikipedia and blogs (default)",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to scraper config YAML (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and rebuild the car_articles index before scraping — required after a schema change",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: parse args, validate ES, run scraper(s), exit 0 on success.

    Returns 0 on success (including SCRP-04 size-halt), 1 on error.
    Wraps execution in try/except to surface unexpected failures cleanly
    per es_manager.py convention (log with type name, return 1).
    """
    _setup_logging()
    try:
        args = _parse_args(argv)

        # D-04: default to --all when no flag is given
        if not (args.wikipedia or args.blogs or args.all_sources):
            args.all_sources = True

        config = _load_config(args.config)
        client = _create_client()

        # --recreate: drop and rebuild the index to apply schema changes (Pitfall 5)
        if args.recreate:
            logger.warning(
                "Dropping car_articles index for re-creation (--recreate flag set)"
            )
            client.indices.delete(index=INDEX_NAME, ignore_unavailable=True)

        ensure_index(client)
        _ensure_data_dir()

        total = 0
        with SQLiteStateManager(STATE_DB_PATH) as state:
            if args.wikipedia or args.all_sources:
                total += _run_wikipedia(config, state, client)
            if args.blogs or args.all_sources:
                total += _run_blogs(config, state, client)

        logger.info("Scraper run complete: %d total documents indexed", total)
        return 0

    except SystemExit:
        # Re-raise SystemExit from _load_config / _create_client (already logged)
        raise
    except Exception as exc:
        logger.error(
            "Scraper run failed: %s: %s", type(exc).__name__, exc
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
