"""
nitrofind.scraper.wikipedia — Wikipedia article scraper for NitroFind.

Exports:
  WikipediaScraper  — walks category trees via MediaWiki Action API, fetches
                      and filters articles by infobox presence, yields document
                      dicts matching CAR_ARTICLES_MAPPING schema.

Requirement coverage:
  SCRP-01: fetches articles from Wikipedia using MediaWiki API (not raw HTML)
  SCRP-03: uses MediaWiki page ID (str(pageid)) as ES document _id for deduplication
  D-01: category tree walk to configurable max_depth (default 2)
  D-02: infobox filter — skips articles where page.infobox is falsy (empty dict or None)
  D-03: root categories loaded from config["wikipedia"]["root_categories"], not hardcoded
  D-05: progress logging to stdout via logging.INFO
  D-06: skips page IDs already recorded in SQLiteStateManager

Anti-patterns avoided:
  Pitfall 1: uses pageid kwarg + auto_suggest=False (not title) to prevent redirect
             aliasing and disambiguation page misfires
  Pitfall 2: uses `if not page.infobox:` (falsy check) not `if page.infobox is None:`
             because mediawikiapi returns {} (empty dict) when no infobox is present
  Pitfall 6: visited_categories set scoped to each yield_documents() call prevents
             infinite recursion through cyclic Wikipedia category trees
"""

import logging
import time
from datetime import datetime, timezone
from typing import Generator, Optional

import requests
from mediawikiapi import MediaWikiAPI

from nitrofind.scraper.cleaner import compute_era_bucket, make_excerpt, parse_year
from nitrofind.scraper.state import SQLiteStateManager

logger = logging.getLogger(__name__)

MEDIAWIKI_API_URL = "https://en.wikipedia.org/w/api.php"


class WikipediaScraper:
    """Walks Wikipedia category trees and yields document dicts for car articles.

    Fetches pages using the MediaWiki Action API (via mediawikiapi + raw requests)
    and filters out pages that lack an infobox. Integrates with SQLiteStateManager
    to skip already-visited pageids across interrupted runs (D-06).

    Usage:
        scraper = WikipediaScraper(config=config, state=state_manager)
        for doc in scraper.yield_documents():
            # doc is a dict conforming to CAR_ARTICLES_MAPPING
            indexer.index(doc)
    """

    def __init__(self, config: dict, state: SQLiteStateManager) -> None:
        """Initialise the scraper.

        Args:
            config: Full project config dict. The wikipedia sub-section is
                    accessed via config["wikipedia"].
            state:  SQLiteStateManager instance for D-06 skip-if-visited tracking.
        """
        self._config = config["wikipedia"]
        self._state = state

        # MediaWikiAPI client — set honest User-Agent (MediaWiki etiquette, T-02-10)
        self._wiki = MediaWikiAPI()
        self._wiki.config.user_agent = self._config["user_agent"]

        # requests.Session for raw MediaWiki Action API calls (pagination, cmcontinue)
        self._session = requests.Session()
        self._session.headers["User-Agent"] = self._config["user_agent"]

        self._rate_limit = float(self._config.get("rate_limit_seconds", 0.5))
        self._max_depth = int(self._config["max_depth"])

    def yield_documents(self) -> Generator[dict, None, None]:
        """Walk all root categories and yield document dicts for eligible articles.

        Generator pattern: callers consume docs one at a time and can chain with
        build_action() + BulkIndexer.index_all() in scripts/scraper.py (Plan 05).

        Yields:
            dict conforming to CAR_ARTICLES_MAPPING.properties — only fields
            defined in the mapping are included.
        """
        # Pitfall 6: per-call set — prevents cyclic category recursion
        visited_categories: set[str] = set()

        # Phase 1: collect all page IDs from category tree walk
        all_pageids: list[int] = []
        for root_category in self._config["root_categories"]:
            pageids = self._walk_category(
                category_title=root_category,
                depth=0,
                visited_categories=visited_categories,
            )
            all_pageids.extend(pageids)

        logger.info(
            "Category walk complete: %d total article IDs found across %d root categories",
            len(all_pageids),
            len(self._config["root_categories"]),
        )

        # Phase 2: fetch, filter, and yield each page
        yielded_count = 0
        for pageid in all_pageids:
            # D-06: skip pageids already recorded in SQLite state
            if self._state.is_visited(str(pageid)):
                logger.debug("Skipping already-indexed pageid=%s", pageid)
                continue

            doc = self._fetch_and_build_doc(pageid)
            if doc is None:
                continue

            # Record state BEFORE yield so state is durable even if the caller
            # crashes mid-batch and never returns control to this generator (CR-01)
            self._state.mark_visited(str(pageid), "wikipedia")
            yield doc
            yielded_count += 1

            if yielded_count % 50 == 0:
                logger.info("Progress: %d documents yielded so far", yielded_count)

            # MediaWiki etiquette: serial requests with rate limit
            time.sleep(self._rate_limit)

        logger.info("yield_documents complete: %d documents yielded", yielded_count)

    def _walk_category(
        self,
        category_title: str,
        depth: int,
        visited_categories: set[str],
    ) -> list[int]:
        """Return article pageids within category tree up to self._max_depth.

        Pitfall 6: visited_categories set prevents cyclic category recursion.
        Returns [] immediately if category_title is already in visited_categories.

        Args:
            category_title:     Wikipedia category name (e.g. "Category:Sports cars")
            depth:              Current recursion depth (0 = root)
            visited_categories: Shared set of already-visited category titles

        Returns:
            List of integer page IDs for articles in this subtree.
        """
        # Pitfall 6: cycle guard — return immediately if already seen
        if category_title in visited_categories:
            return []
        visited_categories.add(category_title)

        # Get article-type members (cmtype="page" excludes subcategories and files)
        page_ids = self._get_category_members_raw(category_title, cmtype="page")
        logger.info(
            "Category %r: %d article IDs (depth=%d)", category_title, len(page_ids), depth
        )

        # Recurse into subcategories if we haven't hit the depth limit
        if depth < self._max_depth:
            subcat_titles = self._get_category_members_raw(
                category_title, cmtype="subcat", return_titles=True
            )
            for subcat_title in subcat_titles:
                child_ids = self._walk_category(
                    category_title=subcat_title,
                    depth=depth + 1,
                    visited_categories=visited_categories,
                )
                page_ids.extend(child_ids)

        return page_ids

    def _get_category_members_raw(
        self,
        category_title: str,
        cmtype: str,
        return_titles: bool = False,
    ) -> list:
        """Fetch all category members using raw MediaWiki Action API with pagination.

        Uses cmcontinue token loop to exhaust all members in large categories
        (>500 members) that mediawikiapi.category_members() would truncate.

        Args:
            category_title: Wikipedia category name
            cmtype:         "page" for articles, "subcat" for subcategories
            return_titles:  If True, return list of title strings; else list of int pageids

        Returns:
            List of int pageids (default) or list of str titles (if return_titles=True).
            Returns [] on API error.
        """
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category_title,
            "cmtype": cmtype,
            "cmprop": "ids|title",
            "cmlimit": 500,
            "format": "json",
        }
        results = []
        first_page_fetched = False
        try:
            while True:
                data = self._session.get(
                    MEDIAWIKI_API_URL, params=params, timeout=30
                ).json()
                results.extend(data["query"]["categorymembers"])
                first_page_fetched = True
                if not data.get("continue"):
                    break
                params["cmcontinue"] = data["continue"]["cmcontinue"]
                time.sleep(self._rate_limit)
        except Exception as exc:
            if not first_page_fetched:
                # Category unreachable before any results were collected
                logger.warning(
                    "MediaWiki API failure for %r (no results collected): %s: %s",
                    category_title,
                    type(exc).__name__,
                    exc,
                )
                return []
            else:
                # Network died mid-pagination — results list is truncated (WR-02)
                logger.error(
                    "MediaWiki API failure for %r mid-pagination after %d results "
                    "(results are PARTIAL — category walk is incomplete): %s: %s",
                    category_title,
                    len(results),
                    type(exc).__name__,
                    exc,
                )
                # Return whatever was collected so the partial list is still usable

        if return_titles:
            return [item["title"] for item in results]
        return [item["pageid"] for item in results]

    def _fetch_and_build_doc(self, pageid: int) -> Optional[dict]:
        """Fetch a Wikipedia page by pageid and build a document dict.

        Applies D-02 infobox filter: returns None for pages without an infobox.
        Uses Pitfall 1 mitigation: pageid kwarg + auto_suggest=False.

        Args:
            pageid: Integer Wikipedia page ID (from category walk)

        Returns:
            Document dict conforming to CAR_ARTICLES_MAPPING.properties, or None
            if the page should be skipped (no infobox, fetch failure).
        """
        # Pitfall 1: use pageid + auto_suggest=False to prevent redirect aliasing
        try:
            page = self._wiki.page(pageid=pageid, auto_suggest=False)
        except Exception as exc:
            logger.warning(
                "Failed to fetch pageid=%s: %s: %s", pageid, type(exc).__name__, exc
            )
            return None

        # D-02 + Pitfall 2: falsy check handles both {} (empty dict) and None.
        # mediawikiapi raises AttributeError on some pages when _infobox is unset.
        try:
            infobox = page.infobox
        except AttributeError:
            return None
        if not infobox:
            return None

        body_text = page.content  # plain text — mediawikiapi strips wiki markup (L-05)

        # Multi-key fallback chain for production year (RESEARCH.md Open Question 3)
        raw_production = (
            str(infobox.get("production") or "")
            or str(infobox.get("years") or "")
            or str(infobox.get("model years") or "")
        )
        production_start = parse_year(raw_production)
        production_end = parse_year(str(infobox.get("production_end") or ""))

        # WR-03: normalize raw body_style infobox value to the controlled vocabulary
        # used by FilterSidebar.BODY_STYLES. Wikipedia infobox values like "2-door coupe"
        # or "4-door saloon" are lowercase multi-word strings; the ES term query for
        # filter selections like "Coupe" or "Sedan" would never match without this mapping.
        _BODY_STYLE_MAP = {
            "coupe": "Coupe",
            "coupé": "Coupe",
            "2-door": "Coupe",
            "sedan": "Sedan",
            "saloon": "Sedan",
            "convertible": "Convertible",
            "cabriolet": "Convertible",
            "roadster": "Convertible",
            "suv": "SUV",
            "crossover": "SUV",
            "hatchback": "Hatchback",
            "wagon": "Wagon",
            "estate": "Wagon",
            "pickup": "Pickup",
            "truck": "Pickup",
            "van": "Van",
        }
        raw_body_style = (
            str(infobox.get("body_style") or infobox.get("Body style") or "").lower()
        )
        normalized_body_style = next(
            (v for k, v in _BODY_STYLE_MAP.items() if k in raw_body_style), ""
        )

        # Build document — ONLY include fields from CAR_ARTICLES_MAPPING.properties
        # Extra keys are silently dropped by dynamic:"false" but the contract is to send
        # only mapped fields (Pitfall 5 defence)
        doc = {
            # SCHEMA-01: core identity
            "title": page.title,
            "url": page.url,
            "source_domain": "en.wikipedia.org",
            "article_id": str(page.pageid),       # L-03; SCRP-03 deduplication key
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            # SCHEMA-02: relevance scoring
            "word_count": len(body_text.split()),
            "has_infobox": True,
            "image_count": len(page.images) if page.images else 0,
            # SCHEMA-03: full-text body + excerpt
            "body": body_text,
            "excerpt": make_excerpt(body_text),    # L-06: <=300 chars at word boundary
            # SCHEMA-04: automotive facet fields
            "manufacturer": str(
                infobox.get("manufacturer") or infobox.get("Manufacturer") or ""
            ),
            "production_start": production_start,  # int or None — ES accepts null
            "production_end": production_end,
            "body_style": normalized_body_style,  # WR-03: normalized to BODY_STYLES vocab
            "era_bucket": compute_era_bucket(production_start),  # L-07
            "country_of_origin": str(
                infobox.get("origin") or infobox.get("country") or ""
            ),
            # L-02: flatten values to strings to avoid ES mapping conflicts from
            # nested dicts or mixed types in the raw infobox (WR-04)
            "specs": {k: str(v) for k, v in infobox.items()},
        }

        return doc
