# Feature Landscape

**Domain:** Offline automotive desktop encyclopedia / search tool
**Researched:** 2026-05-12
**Sources:** Zeal/Dash UX analysis, Kiwix offline reader patterns, automotive database schemas (Teoalida, Automobile-Catalog, Wikipedia Infobox Automobile template), Elasticsearch function_score documentation, search UX best practices, automotive era classification standards, PyQt instant search patterns

---

## Table Stakes

Features users expect. Missing = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| As-you-type instant search | Every modern search tool (browser, Spotlight, Alfred) sets this expectation; Zeal and Kiwix both do it | Medium | Debounce at 150-200ms; cancel in-flight Elasticsearch queries when a new keystroke arrives |
| Results visible within ~300ms of last keystroke | Users abandon searches if nothing happens within ~1 second; "no feedback = broken" perception | Medium | Local Elasticsearch node should easily meet this; measure round-trip in early milestones |
| Match highlighting in result snippets | Users need to see WHY a result matched — Zeal's biggest UI complaint is lack of context on multi-docset results | Low | Elasticsearch highlight API; wrap matched terms in `<em>` tags rendered in the snippet |
| Full article text rendered inline | Enthusiasts want to read, not be redirected; Kiwix renders inline, Dash renders inline — it is the expected pattern | High | PyQt QWebEngineView or QTextBrowser for HTML rendering inside the app |
| Sidebar filter panel alongside search | Car databases (Automobile-Catalog, AutoEvolution) all offer faceted filters; users expect to narrow by make, era, style without retyping | High | Filters must apply additively (AND logic); each filter change re-executes the current search |
| Zero-results messaging | Search UX best practice: empty results with no explanation feels like a crash | Low | Show "No results for '[query]' — try removing filters or broadening search" |
| Keyboard navigable result list | Power users expect Arrow + Enter to select results without touching the mouse; Zeal fails this in older versions | Low | QListView with standard arrow-key focus cycling |
| Dark mode | Kiwix added dark mode after user demand; reference tools used at night/long sessions need it | Low | Qt StyleSheet; two themes (light/dark), toggled in settings |
| Persistent filter state across searches | Filters should NOT reset when the user types a new query; resetting breaks browsing flow | Low | Hold filter widget state in memory; only reset on explicit "Clear filters" action |
| Readable article typography | Long-form content requires good line length, spacing, and font size; reference apps that ignore this drive users away | Low | Set max content width ~720px, line-height 1.6, default 16px system serif or sans-serif |

---

## Filter Taxonomy

Sidebar filters automotive enthusiasts expect, sourced from Wikipedia Infobox Automobile template (used on ~9,200 Wikipedia car pages), Automobile-Catalog, and Teoalida databases.

### Primary Filters (must have in MVP)

| Filter | Values / Facet Type | Source Authority |
|--------|---------------------|-----------------|
| Manufacturer | Multi-select list (Toyota, Ford, Ferrari, etc.) | Wikipedia infobox `manufacturer` field |
| Production Era | Range buckets: Pre-War (pre-1946), Vintage/Classic (1946-1972), Malaise Era (1973-1989), Modern (1990-2009), Contemporary (2010+) | Collector community standards (CCCA, VSCC); ranges are fuzzy — buckets are better than exact year range sliders for browsing |
| Body Style | Multi-select: Sedan, Coupe, Convertible, Hatchback, Station Wagon, Fastback, Roadster, SUV/Crossover, Muscle Car | Wikipedia Car Body Style taxonomy; 26 current + 13 historic styles catalogued |
| Country of Origin | Multi-select: USA, Germany, Italy, Japan, UK, France, Sweden, etc. | Wikipedia infobox `assembly` field normalized to country |
| Source Domain | Multi-select: Wikipedia, Hagerty, Car and Driver, Hemmings, Road & Track | NitroFind-specific; lets users prefer primary vs enthusiast-blog sources |

### Secondary Filters (add in later milestones)

| Filter | Values / Facet Type | Notes |
|--------|---------------------|-------|
| Engine Type | Gasoline, Diesel, Electric, Hybrid | Wikipedia infobox `engine` field; too granular for MVP filter but valuable for enthusiasts |
| Drivetrain / Layout | FWD, RWD, AWD, 4WD | Wikipedia infobox `drivetrain` field |
| Engine Configuration | Inline-4, V6, V8, V12, Flat-6, Rotary | Wikipedia infobox `engine` — high cardinality; use multi-select not dropdown |
| Article Source Quality | High / Medium / Low (derived from Elasticsearch `_score`) | Exposes the relevance model to users; transparent and differentiating |

### Do NOT build as filters

- Exact year slider (too granular; era buckets work better for browsing without an exact car in mind)
- Price / valuation (out of scope; dynamic market data)
- Color / trim (too car-specific; search handles this better than a filter)

---

## Document Data Fields

Each article document indexed in Elasticsearch must carry these fields to support both full-text search and filtered browsing.

### Identity Fields (required for search and display)

| Field | Type | Purpose | Source |
|-------|------|---------|--------|
| `title` | text (analyzed) + keyword | Primary search target; displayed as result heading | Wikipedia article title / blog post title |
| `body_text` | text (analyzed) | Full article content for FTS | Scraped and cleaned body |
| `summary` | text (analyzed) | 2-3 sentence lead for result snippet | First paragraph of article or `og:description` |
| `url` | keyword | Canonical source link (offline reference only) | Scraped URL |
| `source_domain` | keyword | e.g. `en.wikipedia.org`, `hagerty.com` | Derived from URL |

### Facet Fields (required for sidebar filters)

| Field | Type | Purpose | Source |
|-------|------|---------|--------|
| `manufacturer` | keyword (multi-value) | Manufacturer filter facet | Wikipedia infobox `manufacturer`; normalized to canonical name |
| `production_start` | integer | Era bucket calculation | Wikipedia infobox `production` — extract start year |
| `production_end` | integer | Era bucket; null = still in production | Wikipedia infobox `production` — extract end year |
| `era_bucket` | keyword | Pre-computed era label for filter | Derived from `production_start` at index time |
| `body_style` | keyword (multi-value) | Body style filter facet | Wikipedia infobox `body_style`; normalized to canonical values |
| `country_of_origin` | keyword | Country filter facet | Wikipedia infobox `assembly` first token |
| `drivetrain` | keyword | Drivetrain filter | Wikipedia infobox `drivetrain` or `layout` |
| `engine_config` | keyword (multi-value) | Engine type filter | Wikipedia infobox `engine` — parsed |

### Relevance Scoring Fields (required for function_score)

| Field | Type | Purpose | Scoring Use |
|-------|------|---------|-------------|
| `published_date` | date | Publication/last-edit date for freshness decay | Gauss/exp decay function in function_score |
| `article_length_chars` | integer | Proxy for completeness; short articles penalized | field_value_factor with log modifier |
| `inbound_link_count` | integer | Wikipedia "linked from" count; PageRank proxy | field_value_factor; only meaningful for Wikipedia articles |
| `domain_authority_tier` | integer (1-5) | Manual tier assigned per source domain at scrape time | Weight function in function_score |
| `has_infobox` | boolean | Wikipedia articles with a structured infobox are more complete | Weight boost if true |
| `image_count` | integer | Illustrated articles are typically more complete | field_value_factor with sqrt modifier |

### Display-Only Fields (not searched, shown in detail view)

| Field | Type | Purpose |
|-------|------|---------|
| `raw_html` | stored-only (not indexed) | Full rendered article HTML for the detail pane |
| `infobox_data` | object | Structured key-value pairs from Wikipedia infobox for spec panel |
| `featured_image_url` | keyword | Thumbnail for result card |

---

## Relevance Signals: Source Quality Ranking

NitroFind ranks by article authority, not car performance. Signals recommended based on Elasticsearch function_score documentation and information retrieval literature.

### Signal Hierarchy

| Signal | Type | ES Function | Weight Rationale |
|--------|------|-------------|-----------------|
| BM25 text relevance | Dynamic (per query) | Base query score | Full-text match quality — always the primary signal |
| Domain authority tier | Static | `weight` per tier | Wikipedia tier-1 (5), Hagerty/Car&Driver tier-2 (4), enthusiast blogs tier-3 (3), unknown tier-0 (1) |
| Article completeness | Static | `field_value_factor` with `log1p` modifier on `article_length_chars` | Long articles have more depth; log prevents very long articles dominating |
| Freshness | Static | `gauss` decay on `published_date`; half-life = 3 years | Older articles still valid (1969 Camaro facts don't expire) but more recently edited = likelier to be correct |
| Has structured infobox | Static | `weight` boost of 1.2 | Wikipedia infobox = structured, verified data |
| Inbound link count | Static | `field_value_factor` with `sqrt` modifier | Authority signal; Wikipedia-only; sqrt prevents mega-articles drowning everything |
| score_mode | — | `sum` | Additive combination of all function scores |
| boost_mode | — | `multiply` | Multiply combined function score with BM25 base score |

### Signals NOT to use

- Click-through rate — no telemetry in an offline app
- User ratings — single-user tool, no social signals
- Price signals — NitroFind is an encyclopedia, not a market
- AI embeddings — explicitly out of scope per PROJECT.md

---

## Differentiators

Features that set NitroFind apart. Not universally expected, but valued and memorable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Transparent relevance tier display | Show which source domain (Wikipedia vs. Hagerty vs. Hemmings) each result comes from via a badge in the result card | Low | Domain badge (`[W]`, `[H]`, `[C&D]`) in result card; filter by source domain in sidebar |
| Era bucket browsing | Browse all articles in "Malaise Era 1973-1989" with one click — no competitor does this as a first-class filter | Low | Requires `era_bucket` field pre-computed at index time; maps to distinct cultural periods enthusiasts care about |
| Infobox spec panel | Wikipedia infobox data displayed as a structured sidebar in the article detail view (not buried in prose) | Medium | Parse `infobox_data` object; render as key-value table next to article body |
| Offline-first with no ads, no account | Core differentiator vs. web alternatives; state this clearly in the app | None | Product positioning, not a feature to build |
| Query history (session-only) | Arrow-up to recall previous queries; common in shells and browser address bars; rare in encyclopedia apps | Low | In-memory list; no persistence across launches to keep it simple |
| Keyboard shortcut for search focus | Ctrl+L or Ctrl+K to focus the search bar from anywhere in the app; Zeal uses Alt+Space for global hotkey | Low | Common in browser paradigm; essential for keyboard-first power users |

---

## Anti-Features

Things to deliberately NOT build. Each one has a real cost and kills the product's core promise.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Background indexer that runs on startup | Windows Search Indexer and GNOME Tracker are despised for this exact behavior; stealth resource consumption destroys trust | Indexing is a one-shot scraper operation done before ship; Elasticsearch data is static at search time |
| Startup delay > 2 seconds | Zeal is criticized for sluggish startup; Kiwix Electron variant is described as "slow to open"; users equate startup time with app quality | Keep Elasticsearch node startup async in the background; show the UI shell immediately with a subtle "connecting..." indicator |
| Blocking UI during any operation | Searching, loading articles, applying filters — all must remain non-blocking; PyQt main thread must never wait on Elasticsearch | Use Qt signals/slots with worker threads for all Elasticsearch calls |
| Floating search result window | Forces users to alt-tab to read; breaks reading flow | Inline split-pane layout: results on left, article on right — standard reference app pattern |
| Auto-update / phone-home | The offline-first promise is the product's core value; any network call at search time breaks it | Manual scraper re-run to refresh database; no auto-update mechanism |
| Spelling autocorrect on search | Automotive terms (Bugatti Veyron, Koenigsegg Agera, Alfa Romeo Giulietta) are routinely flagged by generic spell-checkers; wrong autocorrect = wrong results | Use fuzzy matching (`fuzziness: AUTO` in Elasticsearch) for tolerance WITHOUT auto-replacing the query |
| Complex saved-search / tag system | Out of scope per PROJECT.md; adds UI complexity that distracts from core search loop | If user wants to "save" something, they can bookmark in their OS; NitroFind is a search tool, not a notes app |
| Paginated results with numbered pages | "Page 2" is a signal that ranking failed; enthusiasts should find their car on the first load | Show top 20 results; allow scroll-to-load more; never use page numbers |
| Settings sprawl | Zeal's UI complaint thread cites confusing options; too many settings signals lack of product opinions | Expose only: light/dark theme, font size, number of results per query. Everything else is baked in. |
| Per-article database sync | Syncing individual articles on-demand implies network dependency; blurs offline-first promise | All content is pre-scraped; the database is a complete snapshot |

---

## Feature Dependencies

```
Full-text search (BM25)
  -> Elasticsearch schema with analyzed text fields
  -> Scraper outputs normalized JSON
  -> Document fields: title, body_text, summary

Sidebar filters
  -> Elasticsearch schema with keyword facet fields
  -> Scraper normalizes manufacturer, body_style, country_of_origin at ingest
  -> era_bucket pre-computed at index time from production_start

function_score relevance ranking
  -> domain_authority_tier assigned per source at scrape config time
  -> article_length_chars, inbound_link_count, has_infobox stored as numeric fields
  -> published_date stored as ES date type for decay functions

Article detail view (inline rendering)
  -> raw_html stored in ES (stored-only, not analyzed)
  -> infobox_data stored as ES object for spec panel rendering
  -> PyQt QWebEngineView or QTextBrowser to render HTML

Era bucket filter
  -> production_start integer field
  -> Era bucket mapping applied at index time (not query time)

Match highlighting
  -> Elasticsearch Highlight API on title and summary fields
  -> Rendered in result card via Qt rich text
```

---

## MVP Recommendation

### Must ship in MVP (phase 1-2)

1. As-you-type search with 150-200ms debounce and match highlighting
2. Result list: title + source domain badge + 2-line summary snippet
3. Inline article detail pane (split-pane layout, right side)
4. Sidebar filters: Manufacturer, Era bucket, Body Style, Country of Origin, Source Domain
5. Dark/light theme toggle
6. Keyboard navigation: Ctrl+L for search focus, Arrow+Enter for result selection, Escape to clear
7. function_score with all five static signals configured from day one (domain tier, length, freshness, infobox, inbound links)

### Defer to later milestones

- Engine type and drivetrain filters (secondary filters; requires reliable scraper field extraction)
- Infobox spec panel in detail view (requires clean infobox_data parsing; render prose first)
- Query history (session-only arrow-up recall) — low effort but not core
- Article source quality badge in results ("High / Medium / Low" derived from score) — requires score calibration after real data is indexed

---

## Sources

- [Zeal — Offline Documentation Browser](https://zealdocs.org/) — UX patterns, keyboard navigation, dark mode history
- [Zeal GitHub Issues — UI complaints thread](https://github.com/zealdocs/zeal/issues/1336) — real user pain points
- [Kiwix — Wikipedia on Wikipedia](https://en.wikipedia.org/wiki/Kiwix) — offline reader feature set
- [Search UX Best Practices — Pencil & Paper](https://www.pencilandpaper.io/articles/search-ux) — instant search, filtering, anti-patterns
- [In-app instant search UX: debounce, cache, relevance — Koder.ai](https://koder.ai/blog/instant-in-app-search-ux) — 150-200ms debounce standard, request cancellation
- [Wikipedia Template:Infobox automobile](https://en.wikipedia.org/wiki/Template:Infobox_automobile) — canonical automotive data field taxonomy (35+ fields)
- [Wikipedia — Car body style](https://en.wikipedia.org/wiki/Car_body_style) — 26 current + 13 historic body style categories
- [Elasticsearch — function_score query reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-function-score-query.html) — gauss/exp/linear decay, field_value_factor, weight, score_mode, boost_mode
- [Elasticsearch — Static scoring signals](https://www.elastic.co/guide/en/elasticsearch/reference/current/static-scoring-signals.html) — PageRank and URL length as archetypal static quality signals
- [Elasticsearch function_score queries — OneUptime Blog](https://oneuptime.com/blog/post/2026-01-30-elasticsearch-function-score-queries/view) — recency, popularity, quality indicator signal patterns
- [Automobile-Catalog](https://www.automobile-catalog.com/) — comprehensive field taxonomy reference (dimensions, power, torque, displacement, transmission)
- [Teoalida Car Database](https://www.teoalida.com/cardatabase/) — body styles, model/trim/engine field taxonomy
- [Classic car era definitions — PreWarCar.com](https://www.prewarcar.com/the-meaning-of-vintage-classics-prewar) — vintage/classic/pre-war year range conventions
- [Classic car era — American Collectors Insurance](https://americancollectors.com/articles/vintage-vs-classic-vs-antique-cars/) — antique/vintage/classic/modern classic definitions
- [PyQt instant search bar — PyPI](https://pypi.org/project/pyqt-instant-search-bar/) — PyQt implementation patterns for real-time search
- [GNOME Tracker resource abuse — MakeUseOf](https://www.makeuseof.com/gnome-tracker-was-silently-making-linux-system-worse-whole-time/) — background indexer anti-pattern evidence
