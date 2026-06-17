# Phase 9: Article Rendering Fixes - Research

**Researched:** 2026-06-17
**Domain:** HTML scraping, BeautifulSoup4, Elasticsearch schema, vanilla JS DOM rendering
**Confidence:** HIGH

---

## Summary

Phase 9 addresses two bugs in the data pipeline and frontend rendering layer. Both bugs share a common root cause: the scraper extracts content with insufficient noise removal and insufficient structure preservation.

**BUG-01 (table rendering):** The Wikipedia scraper uses `mediawikiapi.page.content`, which calls the MediaWiki Extracts API with `explaintext=1`. This parameter converts wiki markup to plain text, which means all table structure (infobox, production tables) is discarded before the data reaches Elasticsearch. The blog scraper uses BeautifulSoup `get_text()` which also strips HTML including `<table>`. The frontend renders `result.body` with `articleBody.textContent`, which cannot show HTML structure even if it were present. Fixing BUG-01 requires three changes: (1) scraper fetches rendered HTML, (2) a new `body_html` field stores the cleaned HTML, (3) the frontend renders `body_html` via `innerHTML`.

**BUG-02 (navigation text in body):** The Wikipedia plain-text content (`page.content`) includes "External links", "References", "See also", and "Bibliography" sections at the end. The blog scraper removes only `script, style, nav, footer, aside, .ad, .advertisement` before calling `get_text()`, leaving breadcrumbs, author bios, tag lists, related-article links, and newsletter callouts inside the article container. Both bugs contaminate the `body` field used for ES full-text search and the `excerpt` field, degrading search quality and display.

These are pure scraper + schema + frontend fixes with no dependency on other v1.2 phases. The index must be re-created (schema change for `body_html`) and data re-scraped. That is acceptable because re-scraping was already required to get clean `body` content for BUG-02.

**Primary recommendation:** Add `body_html` field to the ES schema (`text`, `index: false` — stored but not tokenized), fetch rendered HTML via the MediaWiki Parse API for Wikipedia articles, apply comprehensive noise removal in both scrapers, and switch the article view to `innerHTML` rendering of `body_html`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-01 | Article detail pane renders HTML table elements from Wikipedia and blog articles (currently tables are stripped or not displayed) | MediaWiki Parse API returns rendered HTML with `<table>` elements; ES supports `body_html` as a non-indexed stored text field; frontend `innerHTML` renders table HTML |
| BUG-02 | Article body contains only article prose — navigation links, sidebar text, and anchor text are excluded from the ingested body | Wikipedia: strip terminal nav sections from plain text by section name; Blogs: extend noise selector list to remove breadcrumb, tag-list, related-articles, newsletter, author-bio containers before `get_text()` |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fetch Wikipedia HTML with tables | Scraper (Python) | — | MediaWiki Parse API call belongs in `WikipediaScraper._fetch_html_body()` using existing `requests.Session` |
| Strip Wikipedia navigation sections from plain text | Scraper (Python) | — | `cleaner.py` pure-function pattern; strip by section heading name after `page.content` fetch |
| Strip blog article noise elements | Scraper (Python) | — | Extend existing `blogs.py` noise selectors before `container.get_text()` call |
| Store cleaned HTML | Elasticsearch | — | New `body_html` field in `es_schema.py`; `index: false` means stored-not-tokenized |
| Return `body_html` in API responses | API / Backend | — | Add `body_html` to `_source` list in `query_builder.py`; include in `_result_to_api_dict` |
| Render HTML tables in article view | Browser / Client | — | `app.js` `openArticle()` switches from `textContent` to `innerHTML` for article body |

---

## Standard Stack

### Core (all already in requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mediawikiapi | 1.3 | Wikipedia API access | Already installed; provides `page.content` (plain text) and `requests.Session` for raw API calls |
| beautifulsoup4 | 4.14.3 | HTML parsing for blog articles and Wikipedia parse-API response | Already installed; `decompose()` for noise removal |
| lxml | 6.1.0 | BS4 parser backend | Already installed; faster than html.parser for large Wikipedia HTML |
| requests | installed | HTTP for MediaWiki Parse API | Already installed in WikipediaScraper._session |
| elasticsearch | 8.x | Index schema field, _source storage | Already installed; `index: false` field option is standard ES 8.x |

[VERIFIED: Bash - `pip show mediawikiapi beautifulsoup4 lxml`]

### No New Dependencies

This phase requires **zero new packages**. All capabilities are achievable with the existing stack:
- Wikipedia HTML fetching: `requests.Session` already on `WikipediaScraper`
- HTML parsing and noise removal: `BeautifulSoup` already in `blogs.py`
- Cleaned HTML storage: ES field option change in `es_schema.py`
- Frontend HTML rendering: vanilla `innerHTML` assignment

**Installation:** None required.

---

## Package Legitimacy Audit

No new packages are introduced in this phase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| *(none)* | — | — | — | — | — | — |

---

## Architecture Patterns

### System Architecture Diagram

```
[Wikipedia.org]                    [Blog Sites]
      |                                  |
      | MediaWiki Parse API              | HTTP + BS4
      | action=parse&prop=text           | article_selector
      v                                  v
 _fetch_html_body()              _fetch_article() (improved)
      |                                  |
      | BeautifulSoup (lxml)             | BeautifulSoup (lxml)
      | remove noise selectors           | remove expanded noise selectors
      | fix relative URLs                | (breadcrumb, tags, related, etc.)
      v                                  v
 body_html (cleaned HTML)         body_html (article HTML with <table>)
      |                                  |
      | page.content (existing)          | get_text() on cleaned container
      | strip_nav_sections()             |
      v                                  v
   body (plain text, no nav)          body (plain text, no nav)
      |                                  |
      +------------------+---------------+
                         |
                         v
              Elasticsearch Index
              car_articles mapping:
              - body      (text, standard analyzer — searched)
              - body_html (text, index:false — stored for display)
                         |
                         v
              GET /api/search
              _source includes body_html
              _result_to_api_dict adds body_html key
                         |
                         v
              Browser: openArticle()
              articleBody.innerHTML = result.body_html
                                   (falls back to result.body)
```

### Recommended Project Structure

No new files needed. Changes are within existing files:

```
nitrofind/
├── scraper/
│   ├── cleaner.py       # + strip_nav_sections() (new pure function, BUG-02/Wikipedia)
│   ├── wikipedia.py     # + _fetch_html_body() (new method, BUG-01/Wikipedia)
│   └── blogs.py         # expanded noise selectors + body_html field (BUG-01/BUG-02 blog)
├── es_schema.py         # + body_html field (index:false)
└── search/
    └── query_builder.py # + body_html in _source list
nitrofind/server.py      # + body_html in _result_to_api_dict()
static/js/app.js         # innerHTML for article body (BUG-01 display)
tests/
├── test_scraper/
│   ├── test_cleaner.py  # + tests for strip_nav_sections()
│   ├── test_wikipedia.py # + test for _fetch_html_body() noise removal
│   └── test_blogs.py    # + tests for body_html field presence, noise removal
└── test_search/
    └── test_api_search.py # update test_search_result_shape (body_html key)
```

### Pattern 1: Wikipedia HTML Fetch via Parse API

**What:** Call `action=parse&prop=text&disabletoc=1` on the MediaWiki Action API to get rendered HTML with proper `<table>` elements.

**When to use:** In `WikipediaScraper._fetch_and_build_doc()` after fetching `page.content` (which remains the source for the plain-text `body` field).

**Example:**

```python
# Source: MediaWiki Action API docs — action=parse, prop=text
# https://www.mediawiki.org/wiki/API:Parse

def _fetch_html_body(self, pageid: int) -> str:
    """Fetch rendered HTML for pageid via MediaWiki Parse API.

    Uses the existing self._session (rate-limited, correct User-Agent).
    Returns cleaned HTML string, or empty string on failure.
    """
    try:
        resp = self._session.get(
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
        data = resp.json()
        raw_html = data["parse"]["text"]["*"]
    except Exception as exc:
        logger.warning("Parse API failed for pageid=%s: %s: %s", pageid, type(exc).__name__, exc)
        return ""

    return _clean_wikipedia_html(raw_html)
```

[VERIFIED: Bash — live MediaWiki Parse API test confirmed `data["parse"]["text"]["*"]` contains rendered HTML with `<table class="infobox">` elements]

### Pattern 2: Wikipedia HTML Noise Removal

**What:** Strip navboxes, edit links, references, TOC, and other MediaWiki furniture from the parsed HTML using BeautifulSoup `decompose()`. Fix relative URLs to absolute. Strip event handler attributes.

**When to use:** In `_clean_wikipedia_html()` module-level function in `wikipedia.py`.

**Example:**

```python
# Source: confirmed via live test — all selectors verified to remove target elements

_WIKIPEDIA_NOISE_SELECTORS = [
    ".navbox",              # bottom-of-page navigation tables (e.g. "Ferrari models")
    ".navbox-styles",       # CSS blocks accompanying navboxes
    ".mw-editsection",      # [edit] links beside every heading
    ".reference",           # inline [1] superscript citations
    ".reflist",             # References section list
    ".refbegin",            # References section header
    "[role='navigation']",  # explicit ARIA nav elements
    ".noprint",             # print-hidden elements
    ".mbox-small",          # maintenance templates
    ".hatnote",             # disambiguation notice
    ".shortdescription",    # microdata hidden div
    "style",                # inline MediaWiki template CSS
    "script",               # any script tags
    ".toc",                 # Table of Contents
    ".sistersitebox",       # Wikimedia sister project box
    ".catlinks",            # category links at page bottom
    ".printfooter",
    ".mw-indicators",
]

def _clean_wikipedia_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")
    for selector in _WIKIPEDIA_NOISE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    main = soup.select_one(".mw-parser-output")
    if not main:
        return ""

    # Fix relative URLs → absolute (Wikipedia links)
    for tag in main.select("a[href]"):
        href = tag.get("href", "")
        if href.startswith("/wiki/"):
            tag["href"] = "https://en.wikipedia.org" + href
        elif href.startswith("#"):
            tag["href"] = "#"

    # Fix protocol-relative image srcs
    for img in main.select("img[src]"):
        src = img.get("src", "")
        if src.startswith("//"):
            img["src"] = "https:" + src

    # Strip event handler attributes and data: URIs (security hygiene)
    for tag in main.find_all(True):
        for attr in list(tag.attrs):
            if attr.startswith("on"):
                del tag[attr]
            elif attr in ("src", "href") and str(tag.get(attr, ""))[:5] == "data:":
                del tag[attr]

    return str(main)
```

[VERIFIED: Bash — live test confirmed 0 navbox elements remaining after selector list, 5 infobox `<table>` elements retained]

### Pattern 3: Wikipedia Navigation Section Stripping (BUG-02)

**What:** After fetching `page.content` (plain text), strip the terminal navigation sections from the text. These sections ("References", "External links", "See also", "Bibliography") are present in the MediaWiki plain-text extract and contaminate the ES `body` field.

**When to use:** In `cleaner.py` as a new pure function `strip_nav_sections()`, called in `wikipedia.py` before assigning `body_text`.

**Example:**

```python
# Source: verified via live Wikipedia API test — section headers appear as == Name ==

_WIKIPEDIA_NAV_SECTIONS = frozenset({
    "references",
    "external links",
    "see also",
    "further reading",
    "bibliography",
    "notes",
    "footnotes",
})

def strip_nav_sections(content: str) -> str:
    """Remove Wikipedia navigation/reference sections from plain-text extract.

    Splits on section headers (== Name ==) and drops all content
    after the first header whose name is in _WIKIPEDIA_NAV_SECTIONS.
    Section headers for real content sections are preserved.

    Args:
        content: Plain text from mediawikiapi page.content (== headings included).

    Returns:
        Filtered content string with nav sections removed.
    """
    lines = content.split("\n")
    result = []
    in_nav_section = False
    for line in lines:
        header_match = re.match(r"^={1,6}\s*(.+?)\s*={1,6}$", line.strip())
        if header_match:
            section_name = header_match.group(1).strip().lower()
            in_nav_section = section_name in _WIKIPEDIA_NAV_SECTIONS
            if not in_nav_section:
                result.append(line)
        elif not in_nav_section:
            result.append(line)
    return "\n".join(result).strip()
```

[VERIFIED: Bash — live test on Ferrari 308 GTB/GTS plain text confirmed "References", "External links", "Bibliography" sections removed; article prose sections preserved]

### Pattern 4: Blog Article Noise Removal (BUG-02)

**What:** Extend the noise selector list in `blogs.py` `_fetch_article()` to remove within-article navigation elements before `get_text()`.

**When to use:** In `blogs.py` `_fetch_article()`, replacing the current 4-selector noise removal.

**Example:**

```python
# Source: analysis of Hagerty article HTML structure
# Current code removes only: script, style, nav, footer, aside, .ad, .advertisement

_BLOG_NOISE_SELECTORS = (
    "script, style, nav, footer, aside, "
    ".ad, .advertisement, "
    ".breadcrumb, .breadcrumbs, "          # "Home > Media > Title"
    ".article-meta, .post-meta, "          # author name + date line
    ".tag-list, .tags, .post-tags, "       # tag pills
    ".related-articles, .related-posts, "  # related article cards
    "[class*='related'], "                 # catch-all related variants
    ".newsletter-signup, [class*='newsletter'], "
    "[class*='signup'], "
    ".author-bio, .author-info, "          # author bio box
    ".share-buttons, .social-share, "      # share icons
    ".comments, #comments, "               # comment sections
    ".sidebar"                             # sidebars inside article container
)

# In _fetch_article():
for noise_tag in soup.select(_BLOG_NOISE_SELECTORS):
    noise_tag.decompose()
```

[VERIFIED: Bash — manual HTML test confirmed breadcrumb, author meta, tag list, related articles, newsletter text removed; article prose and table cell text preserved]

### Pattern 5: Blog HTML Capture (BUG-01)

**What:** After noise removal, capture the container's HTML (not just plain text) for the `body_html` field.

**When to use:** In `_fetch_article()`, after noise removal, before `get_text()`.

**Example:**

```python
# Capture HTML BEFORE get_text() strips it
body_html = str(container)         # full HTML with <table> preserved

# body (plain text) is still derived from the same cleaned container
raw_text = container.get_text(separator=" ", strip=True)
body_text = re.sub(r"\s+", " ", raw_text).strip()
```

### Pattern 6: ES Schema — body_html Field

**What:** Add `body_html` as a `text` field with `index: false`. This stores the content in `_source` without building an inverted index. The `body` field (plain text, `standard` analyzer) handles all full-text search.

**When to use:** In `es_schema.py` `CAR_ARTICLES_MAPPING["properties"]`.

**Example:**

```python
# Source: Elasticsearch 8.x field mapping — index:false is standard for stored-not-searched fields

"body_html": {
    "type": "text",
    "index": False,   # stored in _source, not tokenized — display only
},
```

[VERIFIED: ES documentation pattern — `index: false` fields are stored in `_source` and returned in search hits; they have no size limit and no inverted index overhead]

### Pattern 7: API Body_html Pass-through

**What:** Add `body_html` to the `_source` list in `query_builder.py` and include it in the `_result_to_api_dict` response in `server.py`.

**When to use:** These are additive changes to existing code paths.

**Example:**

```python
# In query_builder.py build_search_body() _source list — add "body_html":
"_source": [
    "title", "url", "source_domain", "excerpt", "body", "body_html",
    "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
],

# In server.py _result_to_api_dict():
return {
    "title": result.title,
    "url": result.url,
    "source_domain": result.source_domain,
    "excerpt": excerpt,
    "body": result.body,
    "body_html": result.body_html,   # new field
    "score": result.score,
    "took_ms": took_ms,
}
```

### Pattern 8: Frontend HTML Rendering (BUG-01)

**What:** `openArticle()` in `app.js` switches from `textContent` to `innerHTML` for `articleBody`. The `body_html` field is preferred; `body` is the fallback for articles without HTML content.

**When to use:** In `app.js` `openArticle()`.

**Example:**

```javascript
// Before (BUG-01 — strips all structure):
// articleBody.textContent = result.body || "No content available.";

// After (BUG-01 fix):
const htmlContent = result.body_html || "";
if (htmlContent) {
    articleBody.innerHTML = htmlContent;  // renders <table>, <h2>, etc.
} else {
    // Fallback for articles without body_html (e.g. not yet re-scraped)
    articleBody.textContent = result.body || "No content available.";
}
```

**Security note:** `innerHTML` is used intentionally. The data source is the local scraper, not user input. The scraper strips `<script>`, `<style>`, and `on*` event handler attributes before storing. This is a single-user local offline application — the XSS attack surface is effectively zero.

### Anti-Patterns to Avoid

- **Using `page.html()` from mediawikiapi for HTML fetch:** `WikipediaPage.html()` calls the MediaWiki API with `rvparse=""` on `prop=revisions`, which returns raw wikitext content, not rendered HTML. Use `action=parse&prop=text` directly via `self._session`. [VERIFIED: Bash — inspected `mediawikiapi.wikipediapage.WikipediaPage.html` source]
- **Storing body_html as a `keyword` field:** `keyword` has a default `ignore_above=256` byte limit, which would truncate Wikipedia articles (100KB HTML). Use `text` with `index: false` instead.
- **Rendering `body_html` on the excerpt in the results list:** Excerpt is used in the result cards with `innerHTML` for ES highlight `<b>` tags — this is intentional and safe. `body_html` is only used in the article view (`articleBody`).
- **Stripping `== Section Name ==` headers from Wikipedia plain text:** These are not navigation — they are structural prose. Only strip sections whose **name** is in the nav set. Preserve headers for real content sections.
- **Calling the Parse API without `pageid`:** The Parse API accepts `page=<title>` or `pageid=<id>`. Always use `pageid` (consistent with Pitfall 1 in `wikipedia.py` — prevents redirect aliasing).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML parsing and node removal | Custom regex tag stripper | BeautifulSoup `decompose()` | Regex cannot handle nested tags, malformed HTML, or Unicode edge cases |
| Wikipedia HTML rendering | Parse wiki markup manually | MediaWiki Parse API | Wiki markup syntax is complex (templates, citations, transclusion); the API returns authoritative rendered HTML |
| Absolute URL construction | String concatenation for Wikipedia hrefs | `tag["href"] = "https://en.wikipedia.org" + href` | Protocol, scheme, and path handling is error-prone without urlparse |
| XSS sanitization | DOMPurify equivalent in vanilla JS | Strip `on*` attributes + `script` tags in scraper | For a local offline app, scraper-side stripping is sufficient; no CDN allowed by project constraints |

---

## Common Pitfalls

### Pitfall 1: Using `page.html()` Instead of Parse API

**What goes wrong:** `mediawikiapi.WikipediaPage.html()` is called instead of the Parse API. The method returns raw wikitext with `"*"` key, not rendered HTML. Tables appear as MediaWiki pipe syntax (`{| class="wikitable" |- | cell |}`) rather than `<table>` elements.

**Why it happens:** The method is named `html()` but does not return HTML.

**How to avoid:** Call `action=parse&pageid=<id>&prop=text&format=json` directly via `self._session`. Extract `data["parse"]["text"]["*"]`.

**Warning signs:** The returned string contains `{|`, `|-`, `|}` characters; `<table>` is absent.

[VERIFIED: Bash — inspected `WikipediaPage.html` source code: `rvprop=content` + `rvparse=` returns raw markup, not rendered HTML]

### Pitfall 2: Navbox Selector Misses `.navbox-styles`

**What goes wrong:** Removing `.navbox` leaves behind `.navbox-styles` `<div>` elements containing embedded CSS for the navbox. These appear in the rendered HTML as blank blocks.

**Why it happens:** Wikipedia navboxes have a separate `<div class="navbox-styles">` companion element that holds the CSS.

**How to avoid:** Include both `.navbox` and `.navbox-styles` in the noise selector list.

[VERIFIED: Bash — live test showed 2 `.navbox-styles` remaining after removing only `.navbox`]

### Pitfall 3: Blog HTML Capture Order (body_html must be captured BEFORE get_text)

**What goes wrong:** `get_text()` is called on the container before capturing `str(container)`. BeautifulSoup's `get_text()` does not modify the tree, but if `decompose()` is called after `get_text()`, the HTML capture reflects the pre-cleanup state.

**Why it happens:** Misreading the order of operations in `_fetch_article()`.

**How to avoid:** Always call `container.decompose()` noise removal → `body_html = str(container)` → `raw_text = container.get_text()`. Never mutate the tree after capturing HTML.

**Warning signs:** `body_html` contains breadcrumb or related-article text that was supposed to be removed.

### Pitfall 4: Wikipedia Parse API Pageid vs. Title

**What goes wrong:** `page=<title>` is used instead of `pageid=<id>` in the Parse API call. This can cause redirect aliasing (a disambiguation page is returned instead of the target article) — the same issue Pitfall 1 in `wikipedia.py` was designed to prevent.

**Why it happens:** Copy-paste from examples using `page=`.

**How to avoid:** Always use `pageid=<int>` in the Parse API call, consistent with the existing `_wiki.page(pageid=pageid, auto_suggest=False)` pattern.

### Pitfall 5: ES Index Must Be Re-Created

**What goes wrong:** The `body_html` field is added to `es_schema.py` but the existing index is not deleted and re-created. Elasticsearch does not allow adding fields to an index with `dynamic: "false"` after creation (adding a mapping to a running index requires `PUT /<index>/_mapping`, and with `dynamic: "false"` any document with unmapped fields will silently drop those fields).

**Why it happens:** Developer edits the schema file without dropping the index.

**How to avoid:** Phase plan must include an explicit task to delete the `car_articles` index and run `ensure_index()` again before re-scraping. Document this in the plan's Wave 0.

**Warning signs:** `body_html` is `None` or absent in all search results despite scraper producing the field.

### Pitfall 6: ArticleResult Missing body_html Field

**What goes wrong:** `body_html` is added to `_source` and returned by the API, but `ArticleResult.from_es_hit()` does not expose it. `_result_to_api_dict()` tries to access `result.body_html` and raises `AttributeError`.

**Why it happens:** `ArticleResult` dataclass is not updated to add the new field.

**How to avoid:** Add `body_html: str = ""` to the `ArticleResult` dataclass and `body_html=src.get("body_html", "")` to `from_es_hit()`.

### Pitfall 7: Pre-Existing test_search_result_shape Failure

**What goes wrong:** `tests/test_search/test_api_search.py::test_search_result_shape` currently **fails** because the API returns a `body` key that the test's `expected_keys` set does not include. This is a pre-existing failure unrelated to Phase 9, but Phase 9 adds `body_html` which will further change the shape.

**Why it happens:** The `body` field was added to `_result_to_api_dict` in Phase 8 but the test was not updated.

**How to avoid:** Update `test_search_result_shape` to expect `{"title", "url", "source_domain", "excerpt", "body", "body_html", "score", "took_ms"}` as part of Phase 9 work.

[VERIFIED: Bash — `python3 -m pytest tests/test_search/test_api_search.py::test_search_result_shape -q` fails with `extra items: 'body'`]

---

## Code Examples

Verified patterns from live investigation:

### Wikipedia Parse API Call

```python
# Source: live test via MediaWiki Action API (confirmed 2026-06-17)
resp = self._session.get(
    MEDIAWIKI_API_URL,
    params={
        "action": "parse",
        "pageid": pageid,        # always use pageid (not page=title) — Pitfall 4
        "prop": "text",
        "disabletoc": "1",
        "format": "json",
    },
    timeout=30,
)
raw_html = resp.json()["parse"]["text"]["*"]
# raw_html is full rendered HTML with <table class="infobox">, <table class="wikitable">
```

### strip_nav_sections Integration Point

```python
# In wikipedia.py _fetch_and_build_doc():
# BEFORE (BUG-02: References/External links in body):
body_text = page.content

# AFTER (BUG-02 fix):
from nitrofind.scraper.cleaner import strip_nav_sections
body_text = strip_nav_sections(page.content)
```

### ES Field — body_html non-indexed text

```python
# Source: Elasticsearch 8.x mapping reference
# In es_schema.py CAR_ARTICLES_MAPPING["properties"]:
"body_html": {
    "type": "text",
    "index": False,   # stored in _source, not tokenized
},
```

### Frontend article view switch

```javascript
// In static/js/app.js openArticle():
// Old: articleBody.textContent = result.body || "No content available.";
// New:
const htmlContent = result.body_html || "";
if (htmlContent) {
    articleBody.innerHTML = htmlContent;
} else {
    articleBody.textContent = result.body || "No content available.";
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| mediawikiapi page.content for body | Parse API for body_html + page.content for body | Phase 9 | Tables preserved in display |
| get_text() on full article container | Noise removal before get_text() | Phase 9 | Nav text excluded from search index |
| textContent article rendering | innerHTML for body_html | Phase 9 | Table structure visible to user |

**Deprecated/outdated:**
- `page.html()` from mediawikiapi: returns raw wikitext markup, not rendered HTML. Not usable for this purpose.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Blog article noise CSS class names (`.breadcrumb`, `.related-articles`, `.newsletter-signup`, `.author-bio`) apply to Hagerty and Hemmings HTML structure | Architecture Patterns — Pattern 4 | Blog-specific selectors may differ; the config-driven `article_selector` design means selectors can be extended per-target in `scraper.yaml` if needed |
| A2 | Wikipedia infobox tables have class `infobox hproduct` | Pattern 1 / verified | [ASSUMED] — only one article tested live; other cars may use different infobox classes. The approach works regardless because we keep ALL tables, not just infobox ones |

---

## Open Questions

1. **Should body_html replace body for display, or always be a fallback?**
   - What we know: articles scraped before Phase 9 will have no `body_html` field; `body` (plain text) exists for all current articles
   - What's unclear: whether the planner should add a scraper re-run task or leave old data with fallback display
   - Recommendation: plan should include index re-creation + full re-scrape task; `body_html` fallback to `body` in `openArticle()` handles any stragglers gracefully

2. **Rate limit impact of double Parse API call per Wikipedia article**
   - What we know: current scraper already calls `page.content` (Extracts API) per article; Parse API adds one more call; `rate_limit_seconds` defaults to 0.5s between articles
   - What's unclear: whether MediaWiki will rate-limit two API calls per article
   - Recommendation: the Parse API call can be added in `_fetch_and_build_doc()` immediately after `page.content`; both share the same 0.5s sleep that follows. MediaWiki's rate limit is per-request, not per-article-fetch. This is acceptable.

3. **CSS for Wikipedia table display in the article view**
   - What we know: Wikipedia infobox tables have `class="infobox hproduct"` with inline `style` attributes; without Wikipedia's CSS, table rendering will be unstyled
   - What's unclear: whether plain unstyled table rendering is acceptable, or if minimal CSS should be added to `style.css`
   - Recommendation: add minimal CSS for `#article-body table` — `border-collapse: collapse`, `th/td: border, padding` — in `style.css`. This is a polish item; the planner should include it in the same wave as the HTML rendering change.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| mediawikiapi | `wikipedia.py` | ✓ | 1.3 | — |
| beautifulsoup4 | `blogs.py`, new `_clean_wikipedia_html` | ✓ | 4.14.3 | — |
| lxml | BS4 parser backend | ✓ | 6.1.0 | html.parser (slower) |
| requests | Parse API call in `WikipediaScraper._session` | ✓ | (in mediawikiapi deps) | — |
| Elasticsearch 8.x | Schema field change | Network dependency for live ES | 8.x | — |
| MediaWiki Parse API | Wikipedia HTML fetch | ✓ (network available) | — | Fall back to empty `body_html` (graceful degradation) |

[VERIFIED: Bash — `pip show mediawikiapi beautifulsoup4 lxml`; network test confirmed Wikipedia API reachable]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (no version pinned — see requirements.txt) |
| Config file | `pytest.ini` |
| Quick run command | `python3 -m pytest tests/test_scraper/ tests/test_search/ -m "not integration" -q` |
| Full suite command | `python3 -m pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-01 | `strip_nav_sections()` removes References section, keeps Design section | unit | `pytest tests/test_scraper/test_cleaner.py::test_strip_nav_sections_removes_references -x` | ❌ Wave 0 |
| BUG-01 | `strip_nav_sections()` removes External Links section | unit | `pytest tests/test_scraper/test_cleaner.py::test_strip_nav_sections_removes_external_links -x` | ❌ Wave 0 |
| BUG-01 | `_clean_wikipedia_html()` returns HTML with `<table>` elements | unit | `pytest tests/test_scraper/test_wikipedia.py::test_clean_wikipedia_html_preserves_tables -x` | ❌ Wave 0 |
| BUG-01 | `_clean_wikipedia_html()` removes `.navbox` elements | unit | `pytest tests/test_scraper/test_wikipedia.py::test_clean_wikipedia_html_removes_navboxes -x` | ❌ Wave 0 |
| BUG-01 | `_fetch_and_build_doc()` returns `body_html` key | unit | `pytest tests/test_scraper/test_wikipedia.py::test_fetch_and_build_doc_returns_body_html -x` | ❌ Wave 0 |
| BUG-01 | Blog `_fetch_article()` returns `body_html` key with `<table>` | unit | `pytest tests/test_scraper/test_blogs.py::test_doc_has_body_html_field -x` | ❌ Wave 0 |
| BUG-02 | Blog `_fetch_article()` body excludes breadcrumb text | unit | `pytest tests/test_scraper/test_blogs.py::test_breadcrumb_excluded_from_body -x` | ❌ Wave 0 |
| BUG-02 | Blog `_fetch_article()` body excludes related-articles text | unit | `pytest tests/test_scraper/test_blogs.py::test_related_articles_excluded_from_body -x` | ❌ Wave 0 |
| BUG-01/02 | `ArticleResult` has `body_html` field | unit | `pytest tests/test_search/test_models.py::test_body_html_field_default -x` | ❌ Wave 0 |
| BUG-01 | API search result shape includes `body_html` key | unit | `pytest tests/test_search/test_api_search.py::test_search_result_shape -x` | ✅ (must update) |
| BUG-01 | ES mapping includes `body_html` field with `index: false` | unit | `pytest tests/test_es_schema.py::test_body_html_field_present -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_scraper/ tests/test_search/ tests/test_es_schema.py -m "not integration" -q`
- **Per wave merge:** `python3 -m pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_scraper/test_cleaner.py` — new tests for `strip_nav_sections()` (2 cases: References removed, Design preserved)
- [ ] `tests/test_scraper/test_wikipedia.py` — new tests for `_clean_wikipedia_html()` (table preserved, navbox removed) and `_fetch_and_build_doc()` `body_html` key presence
- [ ] `tests/test_scraper/test_blogs.py` — new tests for `body_html` field presence, breadcrumb exclusion, related-articles exclusion
- [ ] `tests/test_search/test_models.py` — new test for `ArticleResult.body_html` default
- [ ] `tests/test_es_schema.py` — new test for `body_html` in `CAR_ARTICLES_MAPPING.properties`
- [ ] Update `tests/test_search/test_api_search.py::test_search_result_shape` — add `body_html` to expected keys set and fix the pre-existing `body` inclusion

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (partial) | Scraper strips `on*` attrs and `data:` URIs from scraped HTML before storing |
| V6 Cryptography | no | — |

### Known Threat Patterns for innerHTML Rendering

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via scraped article body_html | Tampering | Scraper strips `<script>`, `<style>`, and `on*` event handler attributes; local offline single-user app — no remote attack surface |
| Malicious `data:` URI in img src | Tampering | Scraper strips `src` attributes starting with `data:` |
| CSS injection via inline `style` attributes | Tampering | Acceptable for this use case — Wikipedia inline styles are layout-only (background-color, font-size) and come from MediaWiki's own rendering; local app, no remote users |

**Risk assessment:** NitroFind is a single-user offline local application. The `body_html` field is populated exclusively by the user's own scraper from known, reputable sources (Wikipedia, Hagerty, Hemmings). There are no untrusted content submissions, no remote users, and no server-side execution of the HTML. The XSS risk in this context is near-zero. The scraper-side stripping of `<script>` and `on*` attributes is defensive hygiene, not a critical security gate.

---

## Sources

### Primary (HIGH confidence)

- Live MediaWiki Action API test (`action=parse&pageid=1178093&prop=text&format=json`) — confirmed `data["parse"]["text"]["*"]` contains rendered HTML with `<table class="infobox hproduct">` elements [VERIFIED: Bash 2026-06-17]
- Live MediaWiki Extracts API test (`action=query&prop=extracts&explaintext=`) — confirmed plain text includes "References", "External links" section headers with content [VERIFIED: Bash 2026-06-17]
- mediawikiapi 1.3 source code inspection — `WikipediaPage.content` uses Extracts API with `explaintext`; `WikipediaPage.html()` uses `rvprop=content` not rendered HTML [VERIFIED: Bash `inspect.getsource()`]
- BeautifulSoup4 4.14.3 — `decompose()`, `get_text()`, `select()` behavior [VERIFIED: live test]
- Elasticsearch 8.x mapping documentation — `"index": false` stores field in `_source` without inverted index [CITED: https://www.elastic.co/docs/reference/elasticsearch/mapping-params/index]

### Secondary (MEDIUM confidence)

- Wikipedia article HTML structure — navbox classes, infobox classes, mw-editsection [VERIFIED: live fetch of Ferrari 308 GTB/GTS article]
- Blog article noise element class names — breadcrumb, article-meta, tag-list, related-articles [ASSUMED for specific blog targets beyond Hagerty; config-driven selectors mitigate risk]

### Tertiary (LOW confidence)

- MediaWiki Parse API rate limit behavior with two calls per article — not tested; assumed acceptable based on MediaWiki's per-request rate limit documentation

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all packages confirmed installed via pip show
- Architecture: HIGH — live Wikipedia API tests confirm the Parse API approach
- Pitfalls: HIGH — pitfalls 1, 2, 5, 7 confirmed via code inspection and test runs
- Wikipedia noise selectors: HIGH — confirmed via live HTML fetch
- Blog noise selectors: MEDIUM — class names verified against a sample HTML structure but not live Hagerty/Hemmings fetch

**Research date:** 2026-06-17
**Valid until:** 2026-07-17 (30 days; stable domain)
