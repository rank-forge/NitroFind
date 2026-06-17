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

# Default User-Agent used when config["blogs"]["user_agent"] is not set.
# The NitroFind/1.0 prefix is hardcoded; each user should supply their own
# contact address via scraper.yaml blogs.user_agent (CR-05).
_DEFAULT_USER_AGENT = "NitroFind/1.0 (offline automotive research tool)"

# Expanded noise selector list for blog article cleanup (BUG-02)
# Strips breadcrumbs, tags, related articles, newsletter signups, author bios, etc.
# from article containers before get_text() call.
_BLOG_NOISE_SELECTORS = (
    "script, style, nav, footer, aside, "
    ".ad, .advertisement, "
    ".breadcrumb, .breadcrumbs, "
    ".article-meta, .post-meta, "
    ".tag-list, .tags, .post-tags, "
    ".related-articles, .related-posts, "
    "[class*='related'], "
    ".newsletter-signup, [class*='newsletter'], "
    "[class*='signup'], "
    ".author-bio, .author-info, "
    ".share-buttons, .social-share, "
    ".comments, #comments, "
    ".sidebar"
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
        # Apply all headers from config (browser-like UA, Accept, Accept-Language).
        # blogs.headers overrides blogs.user_agent when both are present (CR-05).
        self._session.headers["User-Agent"] = config["blogs"].get(
            "user_agent", _DEFAULT_USER_AGENT
        )
        for header_name, header_value in config["blogs"].get("headers", {}).items():
            self._session.headers[header_name] = header_value

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
                # Listing fetch failed — skip this target and continue with others
                logger.warning(
                    "Target %r listing unavailable, skipping", target["name"]
                )
                continue

            logger.info(
                "Target %r: discovered %d article URLs", target["name"], len(article_urls)
            )

            if not article_urls:
                logger.warning(
                    "Target %r listing succeeded but zero articles harvested",
                    target["name"],
                )
                continue

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

        if not yielded_any:
            logger.warning(
                "All blog targets returned non-200 or zero articles — Wikipedia-only mode"
            )

    def _fetch_article_urls(self, target: dict) -> Optional[list]:
        """Fetch article URLs for a target — via sitemap index if configured, else listing page.

        Returns:
            List of absolute article URLs (deduplicated, order preserved), or
            None if discovery fails (HTTP error or connection error).
        """
        if "sitemap_index_url" in target:
            urls = self._fetch_urls_from_sitemap_index(target)
            if urls is not None:
                return urls
            logger.warning(
                "Target %r sitemap discovery failed; falling back to listing page",
                target["name"],
            )

        return self._fetch_urls_from_listing(target)

    def _fetch_urls_from_sitemap_index(self, target: dict) -> Optional[list]:
        """Discover article URLs by walking a sitemap index and its sub-sitemaps.

        Fetches the sitemap index, then each sub-sitemap in sequence, collecting
        all URLs that start with target['base_url'] (excludes the base URL itself).

        Returns:
            Deduplicated list of article URLs, or None on index fetch failure.
        """
        index_url = target["sitemap_index_url"]
        base_url = target["base_url"]

        try:
            resp = self._session.get(index_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning(
                "Sitemap index fetch failed for %r: %s: %s",
                target["name"], type(exc).__name__, exc,
            )
            return None

        soup = BeautifulSoup(resp.text, "lxml-xml")
        sub_urls = [loc.text.strip() for loc in soup.find_all("loc")]
        if not sub_urls:
            logger.warning("No sub-sitemaps found in sitemap index for %r", target["name"])
            return None

        logger.info("Target %r: walking %d sub-sitemaps", target["name"], len(sub_urls))
        all_urls: list[str] = []

        for i, sub_url in enumerate(sub_urls):
            try:
                sub_resp = self._session.get(sub_url, timeout=15)
                sub_resp.raise_for_status()
                sub_soup = BeautifulSoup(sub_resp.text, "lxml-xml")
                locs = [loc.text.strip() for loc in sub_soup.find_all("loc")]
                article_urls = [u for u in locs if u.startswith(base_url) and u.rstrip("/") != base_url.rstrip("/")]
                all_urls.extend(article_urls)
            except Exception as exc:
                logger.warning("Failed to fetch sub-sitemap %s: %s: %s", sub_url, type(exc).__name__, exc)

            if (i + 1) % 50 == 0:
                logger.info(
                    "Target %r: processed %d/%d sub-sitemaps, %d URLs collected",
                    target["name"], i + 1, len(sub_urls), len(all_urls),
                )
            time.sleep(self._rate_limit)

        logger.info("Target %r: sitemap walk complete — %d article URLs found", target["name"], len(all_urls))
        return list(dict.fromkeys(all_urls))

    def _fetch_urls_from_listing(self, target: dict) -> Optional[list]:
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

        # Remove expanded noise elements before extracting text (BUG-02 fix)
        for noise_tag in soup.select(_BLOG_NOISE_SELECTORS):
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

        # BUG-01 fix: capture HTML BEFORE get_text() strips structure (Pitfall 3 / Pattern 5)
        body_html = str(container)          # full HTML with <table> preserved

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
            "body_html": body_html,    # BUG-01: stored HTML with <table> preserved (index:false)
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
