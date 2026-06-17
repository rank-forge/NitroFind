# Phase 9: Article Rendering Fixes - Pattern Map

**Mapped:** 2026-06-17
**Files analyzed:** 9 (modified files only — no new files this phase)
**Analogs found:** 9 / 9

---

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `nitrofind/scraper/cleaner.py` | utility | transform | itself (new pure function alongside existing ones) | exact |
| `nitrofind/scraper/wikipedia.py` | scraper | file-I/O + request-response | itself + `blogs.py` noise removal | exact |
| `nitrofind/scraper/blogs.py` | scraper | request-response | itself | exact |
| `nitrofind/es_schema.py` | config | CRUD | itself | exact |
| `nitrofind/search/query_builder.py` | service | request-response | itself | exact |
| `nitrofind/search/models.py` | model | transform | itself | exact |
| `nitrofind/server.py` | service | request-response | itself | exact |
| `static/js/app.js` | component | request-response | itself | exact |
| `tests/test_scraper/test_cleaner.py` | test | transform | itself + `test_wikipedia.py` | exact |
| `tests/test_scraper/test_wikipedia.py` | test | request-response | itself | exact |
| `tests/test_scraper/test_blogs.py` | test | request-response | itself | exact |
| `tests/test_search/test_models.py` | test | transform | itself | exact |
| `tests/test_search/test_api_search.py` | test | request-response | itself | exact |
| `tests/test_es_schema.py` | test | CRUD | itself | exact |

---

## Pattern Assignments

### `nitrofind/scraper/cleaner.py` (utility, transform)

**Change:** Add `strip_nav_sections()` pure function. No changes to existing functions.

**Analog:** Same file — existing pure functions `make_excerpt`, `compute_era_bucket`, `parse_year`.

**Imports pattern** (lines 1-21 of `cleaner.py`):
```python
"""
nitrofind.scraper.cleaner — Text cleaning and field derivation utilities.

Exports:
  make_excerpt       — ...
  strip_nav_sections — removes Wikipedia navigation/reference sections from plain text
  ...
"""

import re
from typing import Optional
```

**Core pure-function pattern** — copy the module-docstring export list convention and function signature style (lines 23-33 of `cleaner.py`):
```python
def make_excerpt(body_text: str) -> str:
    """Return ≤300-char excerpt ending on a word boundary (L-06, Pitfall 7).
    ...
    """
    if len(body_text) <= 300:
        return body_text
    return body_text[:300].rsplit(" ", 1)[0]
```

**New function to add** — `strip_nav_sections()`. Place after `parse_year` at the end of the module, following the same documentation pattern. Module-level constant pattern copied from `_BODY_STYLE_MAP` in `wikipedia.py` (lines 293-316):
```python
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

---

### `nitrofind/scraper/wikipedia.py` (scraper, request-response)

**Change:** Add `_fetch_html_body()` method and `_clean_wikipedia_html()` module-level function; call `strip_nav_sections()` on `page.content` in `_fetch_and_build_doc()`; add `body_html` key to returned doc.

**Analog:** Same file — existing `_get_category_members_raw()` uses identical `self._session.get(..., timeout=30).json()` pattern.

**Imports to add** (lines 28-35 of `wikipedia.py` — add `BeautifulSoup` and `strip_nav_sections`):
```python
# Existing:
from nitrofind.scraper.cleaner import compute_era_bucket, make_excerpt, parse_year
# Change to:
from nitrofind.scraper.cleaner import compute_era_bucket, make_excerpt, parse_year, strip_nav_sections
from bs4 import BeautifulSoup
```

**`_session.get()` error-handling pattern** (lines 199-244 of `wikipedia.py` — `_get_category_members_raw`):
```python
try:
    data = self._session.get(
        MEDIAWIKI_API_URL, params=params, timeout=30
    ).json()
    ...
except Exception as exc:
    logger.warning(
        "MediaWiki API failure for %r (no results collected): %s: %s",
        category_title,
        type(exc).__name__,
        exc,
    )
    return []
```

**New `_fetch_html_body()` method** — copy `_get_category_members_raw` error-handling shape, use `self._session.get()`:
```python
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
                "pageid": pageid,      # always pageid — Pitfall 4 (not page=title)
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

**Module-level noise constant + `_clean_wikipedia_html()` function** — place before the `WikipediaScraper` class, following the `MEDIAWIKI_API_URL` constant:
```python
_WIKIPEDIA_NOISE_SELECTORS = [
    ".navbox", ".navbox-styles",   # Pitfall 2: must include both
    ".mw-editsection",
    ".reference", ".reflist", ".refbegin",
    "[role='navigation']",
    ".noprint", ".mbox-small", ".hatnote", ".shortdescription",
    "style", "script", ".toc",
    ".sistersitebox", ".catlinks", ".printfooter", ".mw-indicators",
]

def _clean_wikipedia_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")
    for selector in _WIKIPEDIA_NOISE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    main = soup.select_one(".mw-parser-output")
    if not main:
        return ""

    for tag in main.select("a[href]"):
        href = tag.get("href", "")
        if href.startswith("/wiki/"):
            tag["href"] = "https://en.wikipedia.org" + href
        elif href.startswith("#"):
            tag["href"] = "#"

    for img in main.select("img[src]"):
        src = img.get("src", "")
        if src.startswith("//"):
            img["src"] = "https:" + src

    for tag in main.find_all(True):
        for attr in list(tag.attrs):
            if attr.startswith("on"):
                del tag[attr]
            elif attr in ("src", "href") and str(tag.get(attr, ""))[:5] == "data:":
                del tag[attr]

    return str(main)
```

**`_fetch_and_build_doc()` body_text change** (lines 278 and 321-349 of `wikipedia.py`):
```python
# Line 278 — BUG-02 fix: strip nav sections from plain text
# BEFORE:
body_text = page.content
# AFTER:
body_text = strip_nav_sections(page.content)

# BUG-01: fetch HTML body
body_html = self._fetch_html_body(pageid)

# In the returned doc dict — add body_html key after "body":
doc = {
    ...
    "body": body_text,
    "body_html": body_html,    # new field — stored HTML with <table> elements
    "excerpt": make_excerpt(body_text),
    ...
}
```

---

### `nitrofind/scraper/blogs.py` (scraper, request-response)

**Change:** Expand noise selector list; capture `body_html` before `get_text()`.

**Analog:** Same file — existing `_fetch_article()` at lines 245-321.

**Existing noise removal pattern** (line 276 of `blogs.py`):
```python
for noise_tag in soup.select("script, style, nav, footer, aside, .ad, .advertisement"):
    noise_tag.decompose()
```

**Replacement — expanded noise selector** (move to module-level constant, BUG-02 fix):
```python
# Module level (before BlogScraper class):
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

# In _fetch_article(), replace the current noise removal line (line 276):
for noise_tag in soup.select(_BLOG_NOISE_SELECTORS):
    noise_tag.decompose()
```

**Body capture order pattern** (lines 289-291 of `blogs.py` — Pitfall 3: HTML BEFORE get_text):
```python
# BEFORE (current):
raw_text = container.get_text(separator=" ", strip=True)
body_text = re.sub(r"\s+", " ", raw_text).strip()

# AFTER (BUG-01 fix — capture HTML first, then get_text):
body_html = str(container)          # full HTML with <table> preserved — BEFORE get_text
raw_text = container.get_text(separator=" ", strip=True)
body_text = re.sub(r"\s+", " ", raw_text).strip()
```

**Returned doc dict** — add `body_html` key (lines 309-321 of `blogs.py`):
```python
return {
    ...
    "body": body_text,
    "body_html": body_html,    # new field
    "excerpt": make_excerpt(body_text),
    ...
}
```

---

### `nitrofind/es_schema.py` (config, CRUD)

**Change:** Add `body_html` field to `CAR_ARTICLES_MAPPING["properties"]`.

**Analog:** Same file — existing field entries at lines 37-50.

**Existing field pattern** (lines 37-39 of `es_schema.py`):
```python
"body":    {"type": "text", "analyzer": "standard"},
"excerpt": {"type": "keyword"},  # Pitfall 5: keyword not text — display-only, no analysis
```

**New field to add** — after `"excerpt"`, before `# SCHEMA-04`:
```python
"body_html": {
    "type": "text",
    "index": False,   # stored in _source, not tokenized — display only (anti-pattern: NOT keyword)
},
```

**Note on index re-creation:** The index must be deleted and `ensure_index()` re-run before re-scraping. `dynamic: "false"` silently drops unmapped fields — no mapping update is possible in-place.

---

### `nitrofind/search/models.py` (model, transform)

**Change:** Add `body_html: str = ""` field to `ArticleResult` dataclass and `body_html=src.get("body_html", "")` to `from_es_hit()`.

**Analog:** Same file — `body: str = ""` field added in Phase 4 (W0-EXT-01), lines 74 and 115.

**Existing body field pattern** (lines 74 and 115 of `models.py`):
```python
# Dataclass field (line 74):
body: str = ""          # W0-EXT-01: full article text for SRCH-03 detail pane

# from_es_hit mapping (line 115):
body=src.get("body", ""),  # W0-EXT-01
```

**New field — copy this pattern exactly, adding after `body`:**
```python
# Dataclass field:
body_html: str = ""     # Phase 9: rendered HTML with <table> for article view

# from_es_hit mapping — add after body= line:
body_html=src.get("body_html", ""),
```

---

### `nitrofind/search/query_builder.py` (service, request-response)

**Change:** Add `"body_html"` to the `_source` list in `build_search_body()`.

**Analog:** Same file — `_source` list at lines 241-245 of `query_builder.py`.

**Existing `_source` pattern** (lines 241-245 of `query_builder.py`):
```python
"_source": [
    "title", "url", "source_domain", "excerpt", "body",
    "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
],
```

**After change — append `"body_html"` to the first line:**
```python
"_source": [
    "title", "url", "source_domain", "excerpt", "body", "body_html",
    "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
],
```

---

### `nitrofind/server.py` (service, request-response)

**Change:** Add `"body_html": result.body_html` to `_result_to_api_dict()` return dict.

**Analog:** Same file — `_result_to_api_dict()` at lines 95-120 of `server.py`.

**Existing return dict pattern** (lines 112-120 of `server.py`):
```python
return {
    "title": result.title,
    "url": result.url,
    "source_domain": result.source_domain,
    "excerpt": excerpt,
    "body": result.body,
    "score": result.score,
    "took_ms": took_ms,
}
```

**After change — add `body_html` after `body`:**
```python
return {
    "title": result.title,
    "url": result.url,
    "source_domain": result.source_domain,
    "excerpt": excerpt,
    "body": result.body,
    "body_html": result.body_html,   # Phase 9: HTML for article view rendering
    "score": result.score,
    "took_ms": took_ms,
}
```

---

### `static/js/app.js` (component, request-response)

**Change:** Switch `openArticle()` from `textContent` to `innerHTML` for `articleBody`; prefer `body_html`, fall back to `body`.

**Analog:** Same file — existing `innerHTML` usage for `excerpt` at line 146 of `app.js`:
```javascript
excerpt.innerHTML = r.excerpt || "";      // innerHTML ONLY — ES highlight <b> tags (D-10)
```

**Existing `openArticle()` body assignment** (lines 161-165 of `app.js`):
```javascript
function openArticle(result) {
  articleTitle.textContent  = result.title;
  articleSource.textContent = result.source_domain;
  articleBody.textContent   = result.body || "No content available."; // textContent — Pitfall 3
  transitionTo("article");
}
```

**After change — BUG-01 fix:**
```javascript
function openArticle(result) {
  articleTitle.textContent  = result.title;                        // textContent
  articleSource.textContent = result.source_domain;                // textContent
  const htmlContent = result.body_html || "";
  if (htmlContent) {
    articleBody.innerHTML = htmlContent;     // renders <table>, <h2>, etc. (Phase 9)
  } else {
    // Fallback for articles without body_html (scraped before Phase 9)
    articleBody.textContent = result.body || "No content available.";
  }
  transitionTo("article");
}
```

**Security note:** `innerHTML` is intentional here. The scraper strips `<script>`, `<style>`, and `on*` event handler attributes before storing. This is a local single-user offline application — same rationale as the existing `excerpt.innerHTML` at line 146.

---

## Test File Patterns

### `tests/test_scraper/test_cleaner.py` (test, transform)

**Change:** Add tests for `strip_nav_sections()`. Import the new function.

**Analog:** Same file — existing pure-function test pattern (lines 23-103 of `test_cleaner.py`).

**Import line to update** (line 16 of `test_cleaner.py`):
```python
# BEFORE:
from nitrofind.scraper.cleaner import make_excerpt, compute_era_bucket, parse_year
# AFTER:
from nitrofind.scraper.cleaner import make_excerpt, compute_era_bucket, parse_year, strip_nav_sections
```

**Test structure pattern** — copy from existing test block (lines 76-88 of `test_cleaner.py`):
```python
def test_era_bucket_from_year():
    """L-07: compute_era_bucket returns correct decade label for valid years."""
    assert compute_era_bucket(1965) == "1960s"
```

**New tests to add** — no mocks needed (pure function):
```python
def test_strip_nav_sections_removes_references():
    """BUG-02: strip_nav_sections removes the 'References' section from Wikipedia plain text."""
    content = (
        "== Design ==\n"
        "The car has a V8 engine.\n"
        "== References ==\n"
        "* [1] Some reference\n"
        "* [2] Another reference\n"
    )
    result = strip_nav_sections(content)
    assert "References" not in result
    assert "Design" in result
    assert "V8 engine" in result


def test_strip_nav_sections_removes_external_links():
    """BUG-02: strip_nav_sections removes 'External links' section."""
    content = "== Performance ==\nFast.\n== External links ==\nhttps://example.com\n"
    result = strip_nav_sections(content)
    assert "External links" not in result
    assert "https://example.com" not in result
    assert "Performance" in result
    assert "Fast." in result


def test_strip_nav_sections_preserves_content_headings():
    """BUG-02: strip_nav_sections keeps real content sections like 'Design', 'Engine'."""
    content = "== Design ==\nBody text.\n== Engine ==\nPower specs.\n"
    result = strip_nav_sections(content)
    assert "Design" in result
    assert "Body text." in result
    assert "Engine" in result
    assert "Power specs." in result


def test_strip_nav_sections_empty_input():
    """strip_nav_sections returns empty string for empty input."""
    assert strip_nav_sections("") == ""
```

---

### `tests/test_scraper/test_wikipedia.py` (test, request-response)

**Change:** Add tests for `_clean_wikipedia_html()` and `_fetch_and_build_doc()` `body_html` key presence.

**Analog:** Same file — existing mock patterns at lines 83-138 (`test_fetch_and_build_doc_returns_full_doc_for_infobox_page`).

**Mock page construction pattern** (lines 106-127 of `test_wikipedia.py`):
```python
def test_fetch_and_build_doc_returns_full_doc_for_infobox_page():
    mock_page = MagicMock()
    mock_page.pageid = 12345
    mock_page.title = "Ferrari 308"
    mock_page.content = "A real plain text body about Ferrari 308"
    mock_page.infobox = {"manufacturer": "Ferrari", "production": "1975 to 1985"}

    mock_wiki = MagicMock()
    mock_wiki.page.return_value = mock_page

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)
        doc = scraper._fetch_and_build_doc(pageid=12345)

    assert doc is not None
    assert doc["body"] == "A real plain text body about Ferrari 308"
```

**New tests to add:**
```python
# Test 1: _clean_wikipedia_html preserves <table> and removes .navbox
from nitrofind.scraper.wikipedia import _clean_wikipedia_html

def test_clean_wikipedia_html_preserves_tables():
    """BUG-01: _clean_wikipedia_html returns HTML string containing <table> elements."""
    raw_html = (
        '<div class="mw-parser-output">'
        '<table class="infobox hproduct"><tr><td>Ferrari</td></tr></table>'
        '<p>Article body.</p>'
        '</div>'
    )
    result = _clean_wikipedia_html(raw_html)
    assert "<table" in result
    assert "Ferrari" in result


def test_clean_wikipedia_html_removes_navboxes():
    """BUG-01: _clean_wikipedia_html removes .navbox elements (Pitfall 2: also removes .navbox-styles)."""
    raw_html = (
        '<div class="mw-parser-output">'
        '<p>Article body.</p>'
        '<div class="navbox">navigation stuff</div>'
        '<div class="navbox-styles">CSS stuff</div>'
        '</div>'
    )
    result = _clean_wikipedia_html(raw_html)
    assert "navigation stuff" not in result
    assert "CSS stuff" not in result
    assert "Article body." in result


def test_clean_wikipedia_html_empty_on_no_mw_parser_output():
    """_clean_wikipedia_html returns empty string when .mw-parser-output is absent."""
    result = _clean_wikipedia_html("<div>no parser output wrapper</div>")
    assert result == ""


# Test 2: _fetch_and_build_doc returns body_html key
def test_fetch_and_build_doc_returns_body_html():
    """BUG-01: _fetch_and_build_doc returns a doc dict with 'body_html' key."""
    mock_page = MagicMock()
    mock_page.pageid = 12345
    mock_page.title = "Ferrari 308"
    mock_page.url = "https://en.wikipedia.org/wiki/Ferrari_308"
    mock_page.content = "A real plain text body about Ferrari 308"
    mock_page.images = []
    mock_page.infobox = {"manufacturer": "Ferrari", "production": "1975 to 1985"}

    mock_wiki = MagicMock()
    mock_wiki.page.return_value = mock_page
    mock_state = MagicMock()
    mock_state.is_visited.return_value = False

    with patch("nitrofind.scraper.wikipedia.MediaWikiAPI", return_value=mock_wiki), \
         patch("nitrofind.scraper.wikipedia.WikipediaScraper._fetch_html_body", return_value="<div>html</div>"):
        scraper = WikipediaScraper(config=SAMPLE_CONFIG, state=mock_state)
        doc = scraper._fetch_and_build_doc(pageid=12345)

    assert doc is not None
    assert "body_html" in doc
```

---

### `tests/test_scraper/test_blogs.py` (test, request-response)

**Change:** Add tests for `body_html` field presence, breadcrumb exclusion, related-articles exclusion.

**Analog:** Same file — `test_doc_has_correct_shape()` at lines 216-244 and `test_extract_plain_text_removes_html_tags()` at lines 182-208.

**Helper pattern** (lines 54-82 of `test_blogs.py`):
```python
_VALID_ARTICLE_HTML = (
    "<html><body>"
    "<article class='post'>"
    "<h1>Test Title</h1>"
    "<p>Real body text about Ferrari ...</p>"
    "</article>"
    "</body></html>"
)
```

**New HTML fixtures and tests to add:**
```python
_ARTICLE_WITH_NOISE_HTML = (
    "<html><body>"
    "<article class='post'>"
    "<div class='breadcrumb'>Home > Media > Article</div>"
    "<h1>Test Title</h1>"
    "<p>Real body text about Ferrari that is sufficiently long to clear the "
    "100-char threshold for the test of valid article content.</p>"
    "<div class='related-articles'>Related: Other car article</div>"
    "<div class='newsletter-signup'>Subscribe to our newsletter</div>"
    "</article>"
    "</body></html>"
)


def test_doc_has_body_html_field():
    """BUG-01: _fetch_article returns doc with 'body_html' key containing HTML."""
    scraper = _make_scraper()
    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(text=_VALID_ARTICLE_HTML)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]
    doc = scraper._fetch_article("https://www.hagerty.com/media/ferrari-history", target)

    assert doc is not None
    assert "body_html" in doc, f"Expected 'body_html' key in doc; got keys: {set(doc.keys())}"
    assert "<" in doc["body_html"], "body_html should contain HTML tags"


def test_breadcrumb_excluded_from_body():
    """BUG-02: breadcrumb text is not included in body (plain text) field."""
    scraper = _make_scraper()
    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(text=_ARTICLE_WITH_NOISE_HTML)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]
    doc = scraper._fetch_article("https://www.hagerty.com/media/ferrari-noise", target)

    assert doc is not None
    assert "Home > Media > Article" not in doc["body"], (
        f"Breadcrumb text found in body: {doc['body']!r}"
    )


def test_related_articles_excluded_from_body():
    """BUG-02: related-articles text is not included in body (plain text) field."""
    scraper = _make_scraper()
    mock_session = MagicMock()
    mock_session.headers = {}
    mock_session.get.return_value = _make_mock_response(text=_ARTICLE_WITH_NOISE_HTML)
    scraper._session = mock_session

    target = _SAMPLE_CONFIG["blogs"]["targets"][0]
    doc = scraper._fetch_article("https://www.hagerty.com/media/ferrari-noise", target)

    assert doc is not None
    assert "Related: Other car article" not in doc["body"], (
        f"Related-articles text found in body: {doc['body']!r}"
    )
```

---

### `tests/test_search/test_models.py` (test, transform)

**Change:** Add `body_html` to the `expected_fields` set in `test_article_result_all_fields()` and add a dedicated `body_html` default test.

**Analog:** Same file — `test_article_result_body_default_empty_string()` at lines 160-163 (the `body` field precedent from W0-EXT-01).

**Existing body field test pattern** (lines 160-163 and 166-190 of `test_models.py`):
```python
def test_article_result_body_default_empty_string():
    """ArticleResult.body defaults to empty string (W0-EXT-01)."""
    r = ArticleResult(title="x", url="y", source_domain="z", score=1.0)
    assert r.body == ""
```

**Update `test_article_result_all_fields`** (line 57-67 of `test_models.py`):
```python
# BEFORE:
expected_fields = {
    "title", "url", "source_domain", "score",
    "excerpt", "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
    "highlight_title", "highlight_body",
    "body",
}
# AFTER — add "body_html":
expected_fields = {
    "title", "url", "source_domain", "score",
    "excerpt", "published_at", "word_count", "has_infobox",
    "manufacturer", "era_bucket", "body_style",
    "highlight_title", "highlight_body",
    "body", "body_html",
}
```

**New test to add** — copy exact structure from `test_article_result_body_default_empty_string`:
```python
def test_body_html_field_default():
    """ArticleResult.body_html defaults to empty string (Phase 9)."""
    r = ArticleResult(title="x", url="y", source_domain="z", score=1.0)
    assert r.body_html == ""


def test_article_result_body_html_from_es_hit():
    """from_es_hit populates body_html from _source and falls back to empty string when missing."""
    hit_with_body_html = {
        "_score": 1.0,
        "_source": {
            "title": "T", "url": "U", "source_domain": "D",
            "body_html": "<div><table><tr><td>Spec</td></tr></table></div>",
        },
    }
    r = ArticleResult.from_es_hit(hit_with_body_html)
    assert r.body_html == "<div><table><tr><td>Spec</td></tr></table></div>"

    hit_no_body_html = {
        "_score": 1.0,
        "_source": {"title": "T", "url": "U", "source_domain": "D"},
    }
    r2 = ArticleResult.from_es_hit(hit_no_body_html)
    assert r2.body_html == ""
```

---

### `tests/test_search/test_api_search.py` (test, request-response)

**Change:** Update `test_search_result_shape` to fix the pre-existing `body` omission and add `body_html`.

**Analog:** Same file — `test_search_result_shape` at lines 111-119.

**Current (broken) assertion** (line 117 of `test_api_search.py`):
```python
assert set(item.keys()) == {"title", "url", "source_domain", "excerpt", "score", "took_ms"}
```

**Fixed assertion — add `body` (pre-existing gap) and `body_html` (Phase 9):**
```python
assert set(item.keys()) == {
    "title", "url", "source_domain", "excerpt", "body", "body_html", "score", "took_ms"
}
```

**Mock ES hit fixture update** — the fixture at lines 40-56 (`client_with_search`) must include `body_html` in `_source` for the assertion to pass:
```python
"_source": {
    "title": "Ford Mustang",
    "url": "https://en.wikipedia.org/wiki/Ford_Mustang",
    "source_domain": "en.wikipedia.org",
    "excerpt": "The Ford Mustang is a pony car.",
    "body": "Full text.",
    "body_html": "<p>Full text.</p>",   # add this
},
```

---

### `tests/test_es_schema.py` (test, CRUD)

**Change:** Add assertion for `body_html` field with `index: False`.

**Analog:** Same file — existing assertion block at lines 41-44 (`test_mapping_has_required_fields`).

**Existing field assertion pattern** (lines 41-44 of `test_es_schema.py`):
```python
# SCHEMA-03: full text + display excerpt
assert "body" in props
assert props["body"]["type"] == "text"
assert "excerpt" in props
assert props["excerpt"]["type"] == "keyword"
```

**New assertion to add** — after the `excerpt` check:
```python
def test_body_html_field_present():
    """Phase 9 / BUG-01: body_html field exists with type text and index=False."""
    props = CAR_ARTICLES_MAPPING["properties"]
    assert "body_html" in props, "body_html field missing from CAR_ARTICLES_MAPPING"
    assert props["body_html"]["type"] == "text"
    assert props["body_html"]["index"] is False, (
        f"body_html must have index=False (not tokenized); got {props['body_html'].get('index')!r}"
    )
```

---

## Shared Patterns

### Exception + logger.warning pattern
**Source:** `nitrofind/scraper/wikipedia.py` lines 220-233 and 263-267
**Apply to:** `_fetch_html_body()` new method, `_clean_wikipedia_html()` function
```python
except Exception as exc:
    logger.warning(
        "MediaWiki API failure for %r (no results collected): %s: %s",
        category_title,
        type(exc).__name__,
        exc,
    )
    return []   # or "" for string-returning functions
```

### `decompose()` noise removal pattern
**Source:** `nitrofind/scraper/blogs.py` line 276
**Apply to:** `_clean_wikipedia_html()` and expanded `_fetch_article()` noise loop
```python
for noise_tag in soup.select("script, style, nav, footer, ..."):
    noise_tag.decompose()
```

### `src.get("field", default)` dataclass field mapping
**Source:** `nitrofind/search/models.py` lines 107-124 (`from_es_hit`)
**Apply to:** `body_html` field in `from_es_hit`
```python
body_html=src.get("body_html", ""),
```

### Module docstring `Exports:` convention
**Source:** Every file in `nitrofind/scraper/` and `nitrofind/search/`
**Apply to:** Update `cleaner.py` module docstring when adding `strip_nav_sections`

---

## No Analog Found

All files in this phase are modifications to existing files. No truly new file lacks an analog. The `_clean_wikipedia_html()` function is technically new but lives in `wikipedia.py` alongside existing scraper patterns.

---

## Metadata

**Analog search scope:** `nitrofind/scraper/`, `nitrofind/search/`, `nitrofind/`, `static/js/`, `tests/`
**Files scanned:** 14 source + test files read in full
**Pattern extraction date:** 2026-06-17
