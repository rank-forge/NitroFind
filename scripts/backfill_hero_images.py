"""
scripts/backfill_hero_images.py — populate hero_image_url on already-indexed
car_articles documents without re-running the full scraper.

For each indexed document missing the hero_image_url field, re-fetches only
the article's rendered HTML (Wikipedia Parse API) and extracts the same
best-effort hero image the live scraper now captures for new articles,
then writes it back with a partial ES update. Existing article fields
(body, specs, etc.) are left untouched.

Usage:
    python scripts/backfill_hero_images.py [--limit N] [--config PATH]

Idempotent: documents are matched with `must_not: exists hero_image_url`,
so articles with no extractable image are written back with "" to mark
them as processed and are skipped on subsequent runs.
"""

import argparse
import logging
import sys
import time

import requests
import yaml
from elasticsearch import Elasticsearch

from nitrofind.es_manager import ES_URL
from nitrofind.scraper.wikipedia import MEDIAWIKI_API_URL, _best_hero_image_url

logger = logging.getLogger("nitrofind.scripts.backfill_hero_images")

INDEX_NAME = "car_articles"
DEFAULT_CONFIG_PATH = "config/scraper.yaml"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _create_client() -> Elasticsearch:
    client = Elasticsearch(ES_URL, request_timeout=30)
    try:
        client.options(request_timeout=5).info()
    except Exception as exc:
        sys.stderr.write(f"Cannot reach Elasticsearch at {ES_URL}: {type(exc).__name__}: {exc}\n")
        sys.exit(1)
    return client


def _ensure_hero_image_mapping(client: Elasticsearch) -> None:
    """Add hero_image_url to the mapping if missing (dynamic:"false" would silently drop it)."""
    mapping = client.indices.get_mapping(index=INDEX_NAME)
    props = mapping[INDEX_NAME]["mappings"].get("properties", {})
    if "hero_image_url" not in props:
        client.indices.put_mapping(index=INDEX_NAME, properties={"hero_image_url": {"type": "keyword"}})
        logger.info("Added hero_image_url to car_articles mapping")


def _iter_docs_missing_hero_image(client: Elasticsearch, page_size: int = 100):
    """Yield hits (with article_id + source_domain in _source) lacking hero_image_url."""
    query = {"bool": {"must_not": [{"exists": {"field": "hero_image_url"}}]}}
    resp = client.search(
        index=INDEX_NAME,
        query=query,
        size=page_size,
        scroll="2m",
        source=["article_id", "source_domain"],
    )
    scroll_id = resp.get("_scroll_id")
    hits = resp["hits"]["hits"]
    try:
        while hits:
            yield from hits
            resp = client.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp.get("_scroll_id")
            hits = resp["hits"]["hits"]
    finally:
        if scroll_id:
            client.options(ignore_status=404).clear_scroll(scroll_id=scroll_id)


def _fetch_wikipedia_hero_image(session: requests.Session, pageid: int) -> str:
    """Fetch rendered HTML for pageid via MediaWiki Parse API and extract hero image."""
    try:
        resp = session.get(
            MEDIAWIKI_API_URL,
            params={
                "action": "parse",
                "pageid": pageid,
                "prop": "text",
                "disabletoc": "1",
                "format": "json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw_html = resp.json()["parse"]["text"]["*"]
    except Exception as exc:
        logger.warning("Parse API failed for pageid=%s: %s: %s", pageid, type(exc).__name__, exc)
        return ""
    return _best_hero_image_url(raw_html)


def _load_config(config_path: str) -> dict:
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        sys.stderr.write(f"Config file not found: {config_path}\n")
        sys.exit(1)
    except yaml.YAMLError as exc:
        sys.stderr.write(f"Failed to parse {config_path}: {exc}\n")
        sys.exit(1)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill hero_image_url on already-indexed car_articles documents",
        prog="backfill_hero_images.py",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of documents to process (omit to process all matching documents)",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to scraper config YAML, used for rate_limit_seconds and user_agent (default: {DEFAULT_CONFIG_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    try:
        args = _parse_args(argv)
        config = _load_config(args.config)
        wiki_config = config["wikipedia"]
        rate_limit = float(wiki_config.get("rate_limit_seconds", 0.5))

        client = _create_client()
        _ensure_hero_image_mapping(client)

        session = requests.Session()
        session.headers["User-Agent"] = wiki_config["user_agent"]

        processed = 0
        updated = 0
        skipped_non_wikipedia = 0

        for hit in _iter_docs_missing_hero_image(client):
            if args.limit is not None and processed >= args.limit:
                break

            doc_id = hit["_id"]
            src = hit["_source"]

            if src.get("source_domain") != "en.wikipedia.org":
                # No blog documents are indexed as of this writing; blog backfill
                # would need each target's article_selector from config to locate
                # the article container, same as BlogScraper._fetch_article.
                skipped_non_wikipedia += 1
                processed += 1
                continue

            try:
                pageid = int(src.get("article_id", ""))
            except (TypeError, ValueError):
                processed += 1
                continue

            hero_url = _fetch_wikipedia_hero_image(session, pageid)
            client.update(index=INDEX_NAME, id=doc_id, doc={"hero_image_url": hero_url})
            if hero_url:
                updated += 1

            processed += 1
            if processed % 50 == 0:
                logger.info("Progress: %d processed, %d updated with an image", processed, updated)

            time.sleep(rate_limit)

        logger.info(
            "Backfill complete: %d processed, %d updated with an image, %d skipped (non-Wikipedia)",
            processed, updated, skipped_non_wikipedia,
        )
        return 0

    except SystemExit:
        raise
    except Exception as exc:
        logger.error("Backfill run failed: %s: %s", type(exc).__name__, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
