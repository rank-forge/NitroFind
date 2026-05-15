"""
nitrofind.scraper.blogs — Automotive blog scraper for NitroFind.

Exports:
  BlogScraper  — fetches article lists and article pages from configured blog
                 targets, yields document dicts matching CAR_ARTICLES_MAPPING.

Requirement coverage:
  SCRP-02: fetches articles from automotive blogs using BS4 + requests
  L-05: body field contains plain text only (get_text + whitespace collapse)
  L-06: excerpt via make_excerpt (≤300 chars at word boundary)
  D-05: progress logging per target and per article
  D-06: skips URLs already in SQLite state

Anti-patterns avoided:
  Pitfall 3: honest User-Agent; HTTP 403 on listing → graceful skip + fallback chain;
             HTTP 403 on article → skip just that article (no browser impersonation)
  Pitfall 4: selectors come from config dict, not hardcoded — missing container
             triggers warning and None return (never indexes empty body)
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Generator, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from nitrofind.scraper.cleaner import make_excerpt
from nitrofind.scraper.state import SQLiteStateManager

logger = logging.getLogger(__name__)

HONEST_USER_AGENT = (
    "NitroFind/1.0 (nullsecurity1337@gmail.com; personal offline research tool)"
)


class BlogScraper:
    """Automotive blog scraper that yields document dicts for the ES car_articles index.

    Implements a fallback chain over enabled targets in config order (Pitfall 3):
    the first target whose listing page returns HTTP 200 is used; subsequent
    enabled targets are tried only if the previous one fails.

    Usage:
        with SQLiteStateManager("data/scraper_state.db") as state:
            scraper = BlogScraper(config=yaml_config, state=state)
            for doc in scraper.yield_documents():
                indexer.index_document(doc)
    """

    def __init__(self, config: dict, state: SQLiteStateManager) -> None:
        """Initialise the scraper from a parsed scraper.yaml config dict.

        Args:
            config: Parsed YAML config — must contain config["blogs"]["targets"].
            state:  SQLiteStateManager instance for D-06 deduplication.
        """
        self._targets = [
            t for t in config["blogs"]["targets"] if t.get("enabled")
        ]
        self._state = state
        self._rate_limit = float(config["blogs"].get("rate_limit_seconds", 1.0))
        self._session = requests.Session()
        # HONEST_USER_AGENT — no browser impersonation (Pitfall 3, RESEARCH.md security domain)
        self._session.headers["User-Agent"] = HONEST_USER_AGENT

    def yield_documents(self) -> Generator[dict, None, None]:
        """Generator: yield one document dict per successfully scraped article.

        Implements the fallback chain (Pitfall 3):
        - Iterate enabled targets in config order.
        - If listing fetch fails (HTTP error, connection error) → log warning, try next.
        - If listing fetch succeeds → fetch articles, then break (first-winner).
        - If no enabled target succeeds → log warning and return (Wikipedia-only mode).
        """
        if not self._targets:
            logger.warning("No blog targets enabled — skipping blog scraping")
            return

        yielded_any = False

        for target in self._targets:
            article_urls = self._fetch_article_urls(target)

            if article_urls is None:
                # Listing fetch failed — advance to next enabled target (Pitfall 3)
                logger.warning(
                    "Target %r listing unavailable, trying next", target["name"]
                )
                continue

            logger.info(
                "Target %r: discovered %d article URLs", target["name"], len(article_urls)
            )

            for url in article_urls:
                # D-06: skip already-indexed URLs before fetching
                if self._state.is_visited(url):
                    logger.debug("Skipping already-visited URL: %s", url)
                    continue

                doc = self._fetch_article(url, target)
                if doc is None:
                    continue

                # Record state BEFORE yield so state is durable if caller crashes (CR-01)
                self._state.mark_visited(url, target["name"])
                yield doc
                yielded_any = True
                time.sleep(self._rate_limit)

            # First successful target — stop the fallback chain
            break

        if not yielded_any:
            logger.warning(
                "All blog targets returned non-200 — Wikipedia-only mode"
            )

    def _fetch_article_urls(self, target: dict) -> Optional[list]:
        """Fetch the article listing page and return deduplicated article URLs.

        Returns:
            List of absolute article URLs (deduplicated, order preserved), or
            None if the listing request fails (HTTP error or connection error).
        """
        listing_url = target["article_list_url"]
        try:
            resp = self._session.get(listing_url, timeout=15)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            logger.warning(
                "HTTP %s fetching listing %s: %s",
                exc.response.status_code,
                listing_url,
                exc,
            )
            return None
        except requests.RequestException as exc:
            logger.warning(
                "Request failed for listing %s: %s: %s",
                listing_url,
                type(exc).__name__,
                exc,
            )
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.select(target["listing_selector"])

        urls = []
        for link in links:
            href = link.get("href")
            if href:
                urls.append(urljoin(target["base_url"], href))

        # Deduplicate while preserving order
        return list(dict.fromkeys(urls))

    def _fetch_article(self, url: str, target: dict) -> Optional[dict]:
        """Fetch a single article page, parse it, and return a document dict.

        Returns:
            Document dict with all required CAR_ARTICLES_MAPPING fields, or
            None if the fetch fails, the article container is absent (Pitfall 4),
            or the extracted body is suspiciously short (<100 chars).
        """
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            logger.warning(
                "HTTP %s fetching article %s: %s",
                exc.response.status_code,
                url,
                exc,
            )
            return None
        except requests.RequestException as exc:
            logger.warning(
                "Request failed for article %s: %s: %s",
                url,
                type(exc).__name__,
                exc,
            )
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noise elements before extracting text (RESEARCH.md Pattern 6)
        for noise_tag in soup.select("script, style, nav, footer, aside, .ad, .advertisement"):
            noise_tag.decompose()

        # Pitfall 4: selector may not match current HTML — always guard
        container = soup.select_one(target["article_selector"])
        if container is None:
            logger.warning(
                "Article container not found at %s (selector: %r)",
                url,
                target["article_selector"],
            )
            return None

        # L-05: plain text only — get_text removes all tags, regex collapses whitespace
        raw_text = container.get_text(separator=" ", strip=True)
        body_text = re.sub(r"\s+", " ", raw_text).strip()

        # Pitfall 4 warning sign: suspiciously short body means selector hit wrong element
        if len(body_text) < 100:
            logger.warning(
                "Skipping suspiciously short article (%d chars) at %s",
                len(body_text),
                url,
            )
            return None

        # Title: prefer <h1> inside container, fall back to <title> tag
        title_tag = container.select_one("h1") or soup.select_one("title")
        title = title_tag.get_text(strip=True) if title_tag else url

        url_slug = self._url_slug(url)
        source_domain = urlparse(target["base_url"]).netloc

        return {
            "title": title,
            "url": url,
            "source_domain": source_domain,
            "article_id": url_slug,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "body": body_text,
            "excerpt": make_excerpt(body_text),
            "word_count": len(body_text.split()),
            "has_infobox": False,
            "image_count": len(container.select("img")),
            "era_bucket": "Unknown",
        }

    def _url_slug(self, url: str) -> str:
        """Build a domain-scoped slug to guarantee uniqueness across blog targets (CR-03).

        Incorporates the source domain so two different blogs with the same final
        path segment produce distinct article_id values and do not overwrite each
        other in Elasticsearch.

        Falls back to a 16-char SHA-1 hex digest if the path has no segments.

        Examples:
            "https://www.hagerty.com/media/ferrari-308" -> "hagerty.com__ferrari-308"
            "https://www.hemmings.com/stories/ferrari-308" -> "hemmings.com__ferrari-308"
            "https://example.com/"                         -> sha1 hash prefix
        """
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        segments = [seg for seg in path.split("/") if seg]
        if segments:
            return f"{domain}__{segments[-1]}"
        # Fallback: stable hash of the full URL
        return hashlib.sha1(url.encode()).hexdigest()[:16]
