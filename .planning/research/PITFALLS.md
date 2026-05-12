# Domain Pitfalls

**Project:** NitroFind — offline automotive desktop search engine
**Domain:** Python scraper + local Elasticsearch node + PyQt native UI
**Researched:** 2026-05-12
**Confidence:** MEDIUM-HIGH (official Elasticsearch docs + community post-mortems verified)

---

## Critical Pitfalls

These mistakes cause rewrites, data loss, or an app that ships and immediately fails on end-user machines.

---

### Pitfall C-1: Elasticsearch 8 Security Autoconfiguration Blocks Localhost Connections

**What goes wrong:**
Elasticsearch 8.x ships with `xpack.security.enabled = true` and auto-generates a self-signed TLS certificate on first boot. The HTTP layer binds to `https://localhost:9200`, not `http://`. The Python `elasticsearch` client defaults to `http://` and gets a `ConnectionError` or `SSLError` — the node appears unreachable. Many tutorials still show `http://localhost:9200` which worked on Elasticsearch 7 but silently fails on 8.

**Why it happens:**
Elastic flipped the default to secure-by-default in v8 to reduce cloud misconfiguration incidents. Desktop apps were not the target, but they get the same behavior.

**Consequences:**
- App fails to connect at all on a fresh Elasticsearch 8 install
- Error message ("ConnectionError") is misleading — developers assume a port conflict instead of a TLS mismatch
- If developer disables TLS globally without understanding it, they may accidentally expose the node on public interfaces

**Prevention:**
In `elasticsearch.yml` for the embedded/local node, explicitly set:
```yaml
xpack.security.enabled: false
xpack.security.http.ssl.enabled: false
network.host: 127.0.0.1
```
This confines the node to loopback only (no security exposure) and allows plain HTTP. Document this in the setup script so users know what they are changing and why.

**Detection / Warning Signs:**
- `elasticsearch.exceptions.ConnectionError` on a fresh install despite ES process running
- `curl http://localhost:9200` returns connection refused; `curl https://localhost:9200 -k` succeeds
- Python log shows `SSLError: [SSL: WRONG_VERSION_NUMBER]`

**Phase to address:** Elasticsearch setup (Phase 1 / first milestone)

---

### Pitfall C-2: JVM Heap Misconfiguration Crashes or Starves the Host Machine

**What goes wrong:**
Elasticsearch's default behavior (v8+) is to auto-size heap at 50% of system RAM, capped at ~31 GB. On a developer machine with 8 GB RAM this means Elasticsearch claims 4 GB of heap — an aggressive default that works in a dedicated server but competes badly with the OS, the PyQt UI process, and any other app the user has open. On machines with 4 GB RAM, the JVM can barely start. On machines with 16 GB RAM, 8 GB heap is also too much for a desktop tool serving a 2 GB index.

**Why it happens:**
Default auto-sizing was tuned for dedicated nodes, not desktop apps sharing a machine with a browser and other processes.

**Consequences:**
- Elasticsearch kills itself with `OutOfMemoryError` under load
- Garbage collection pauses make search latency spike from <50 ms to several seconds
- Host machine becomes sluggish for everything else while ES holds 4–8 GB
- On low-RAM machines, ES process never starts at all

**Prevention:**
Pin heap to a fixed, modest value in `jvm.options`:
```
-Xms512m
-Xmx512m
```
For a 2 GB index with mostly read traffic and no shard replication, 512 MB heap is sufficient. Keep `-Xms` and `-Xmx` identical (prevents heap resizing pauses). Include a startup check that reads available system RAM and warns if it is below 2 GB.

**Detection / Warning Signs:**
- `[o.e.m.j.JvmGcMonitorService] [node] [gc][young][N][M] duration [Xs]` — GC pauses over 200 ms
- High JVM memory pressure in `GET /_nodes/stats/jvm`
- OS swap usage climbing after ES starts

**Phase to address:** Elasticsearch setup (Phase 1)

---

### Pitfall C-3: Storing Raw HTML Blows Through the 2 GB Cap Before Meaningful Content Is Indexed

**What goes wrong:**
A scraper that stores the full HTML response alongside (or instead of) extracted text inflates storage by 10–50x. A single Wikipedia article averages ~40 KB of HTML but only ~8 KB of plain text. Scraping 20,000 articles at 40 KB HTML = 800 MB of raw HTML alone, before any Elasticsearch overhead, field metadata, or blog articles are added. Add Car and Driver and Hagerty long-form articles (which can exceed 100 KB HTML each) and the 2 GB cap is breached during the first full scrape run.

**Why it happens:**
Early scraper prototypes often save the full response for debugging convenience ("I'll strip HTML later"). "Later" never comes, and the stored field makes it into the Elasticsearch document schema.

**Consequences:**
- Index exceeds 2 GB before covering the intended article set
- Re-indexing from scratch required — no incremental path
- Elasticsearch search on `_source` that includes raw HTML slows result retrieval significantly

**Prevention:**
Strip HTML to plain text at scrape time using `trafilatura` or `readability-lxml` before writing to the JSON output file. Never store raw HTML in the Elasticsearch document. Store only: clean body text, title, URL, metadata fields. If raw HTML is needed for debugging, write it to a separate `.html` file on disk that is gitignored and not indexed.

**Detection / Warning Signs:**
- First 100 scraped articles already exceed 5 MB in the JSON staging file
- `GET /_cat/indices?v` shows `store.size` growing faster than expected
- Any field in the mapping named `html`, `raw`, or `source_html`

**Phase to address:** Scraper design (Phase 2)

---

### Pitfall C-4: No URL Deduplication Leads to Duplicate Articles and Silent Index Bloat

**What goes wrong:**
Wikipedia automotive articles are heavily interlinked. A scraper that follows links naively will encounter the same article dozens of times through different entry points (e.g., "Ferrari 488" linked from "Ferrari", from "mid-engine sports car", from "2015 Geneva Motor Show"). Without deduplication, each encounter triggers a re-scrape and a re-index, bloating the article count and wasting the 2 GB budget on identical content. Automotive blogs compound this: Car and Driver frequently republishes evergreen content at new URLs ("Best sports cars 2024" → "Best sports cars 2025").

**Why it happens:**
URL-only deduplication misses canonical redirects (Wikipedia `?redirect=no` variations, UTM parameters on blog URLs). Content-hash deduplication is skipped as "over-engineering" in early iterations.

**Consequences:**
- Index contains 3–5x more documents than actual unique articles
- Relevance scoring breaks: the same article appears multiple times in results with different scores
- 2 GB cap reached with far less unique content than planned

**Prevention:**
Two-layer deduplication: (1) canonical URL normalization before fetching (strip query params, resolve redirects via HTTP 301/302 chain, normalize Wikipedia `/wiki/` paths to lowercase), (2) content fingerprint check (SHA-256 of cleaned body text) before writing to Elasticsearch — use `update` with `doc_as_upsert: true` and a deterministic `_id` derived from the canonical URL.

**Detection / Warning Signs:**
- Document count grows faster than expected relative to seed URLs visited
- `GET /articles/_search?q=title:"Ferrari 488"` returns more than one document
- Scraper log shows the same URL visited multiple times across different sessions

**Phase to address:** Scraper design (Phase 2)

---

### Pitfall C-5: Wikipedia Disambiguation and Non-Article Pages Enter the Index

**What goes wrong:**
Wikipedia's link graph contains many page types that are not encyclopedia articles: disambiguation pages (e.g., "Mustang (disambiguation)"), redirect pages, category pages (e.g., "Category:Sports cars"), portal pages, file pages, and template pages. All of these have valid `/wiki/` URLs. A scraper following links without namespace filtering will index "Category:German automobiles" as an article, polluting search results with meaningless content and wasting index space.

Disambiguation pages are particularly insidious: they contain lists of car names with no substantive content, but they look like articles at the HTTP level and return 200 OK.

**Why it happens:**
Developers test on a handful of known article URLs, miss the namespace problem entirely, and only discover it after a full scrape run returns thousands of garbage pages.

**Consequences:**
- Index contains hundreds of category, portal, and disambiguation pages
- Search results for "Mustang" return the disambiguation page ranked above actual articles
- Wasted 2 GB budget on non-content

**Prevention:**
Use the MediaWiki API (`action=query&prop=pageprops`) to check `disambiguation` in `pageprops` before indexing. Filter by namespace: only namespace 0 (main article namespace) should be indexed. Check for the `Disambiguation pages` category. For the `wikipedia` Python library, catch `wikipedia.DisambiguationError` and skip. For direct API calls, require `ns=0` on all `action=query` requests.

**Detection / Warning Signs:**
- Any indexed document with a title containing "Category:", "Portal:", "Template:", "File:", "Wikipedia:"
- Articles with unusually short body text (disambiguation pages average <500 characters)
- Title contains "(disambiguation)"

**Phase to address:** Scraper design (Phase 2)

---

### Pitfall C-6: Blocking the PyQt UI Thread with Synchronous Elasticsearch Queries

**What goes wrong:**
The most natural implementation of as-you-type search is to hook `textChanged` on the `QLineEdit` and call `es.search(...)` inline in the slot. `es.search()` is a synchronous HTTP call over localhost — typical latency is 5–50 ms. At 5 ms this is imperceptible; at 50 ms with 10 keystrokes per second, the UI thread is spending 500 ms/s blocked on network I/O. The application becomes visibly laggy; fast typists see the cursor stutter. If Elasticsearch is under load or warming up, a single call can take 200–500 ms and the UI freezes completely.

**Why it happens:**
Localhost feels "instant" so the synchronous pattern seems safe. It is not — HTTP overhead, JVM GC pauses, and query complexity make actual latency non-deterministic.

**Consequences:**
- UI freezes on every keystroke when ES is under any load
- Qt event loop starves, causing repaint delays and input queue buildup
- On Elasticsearch startup (slow JVM initialization), the first search call can block for several seconds

**Prevention:**
All Elasticsearch calls must run in a `QThread` (worker thread) and communicate results back to the UI thread via Qt signals. Use a `QTimer` with `setSingleShot(True)` and a 150–200 ms debounce window: reset the timer on every keystroke, only fire the query when the user pauses. This reduces query frequency from ~10/s to ~2–3/s with no perceived latency increase.

Pattern:
```python
# In QLineEdit.textChanged slot (UI thread):
self._debounce_timer.start(180)  # restart timer

# Timer timeout triggers (still UI thread):
def _on_debounce():
    self._search_worker.query.emit(self._search_box.text())

# Worker thread receives signal, runs es.search(), emits results back
```

**Detection / Warning Signs:**
- `es.search()` called directly in a Qt slot (grep for `es.search` or `client.search` in slot methods)
- UI cursor stutters or freezes when typing quickly
- Qt "The application is not responding" prompt on slow machines

**Phase to address:** Search UI (Phase 3 / UI milestone)

---

## Moderate Pitfalls

These cause significant quality or usability problems but do not require a full rewrite.

---

### Pitfall M-1: function_score Decay Functions Return 1.0 for Missing Fields

**What goes wrong:**
Elasticsearch's built-in decay functions (`gauss`, `exp`, `linear`) return a score of **1.0** (maximum) when the targeted field is missing from a document. For NitroFind, if `publish_date` is missing (common for scraped blog posts that don't expose a clear publication date), the decay function treating "distance from today" rewards those documents with the highest possible date score — the opposite of the intended behavior. Documents with no date rank as if they were published today.

**Why it happens:**
The Elasticsearch default was a design choice to avoid penalizing documents for missing data, but for freshness scoring the correct default should be 0 (or a mid-range neutral value), not 1.0.

**Consequences:**
- Undated articles score as highly as today's articles on the freshness signal
- The composite `function_score` is distorted; source authority signal is undermined by date noise
- Results appear to rank undated content above dated older content

**Prevention:**
Replace date decay functions with `script_score` for the freshness signal, where missing-field handling is explicit:
```python
{
  "script_score": {
    "script": {
      "source": """
        if (!doc.containsKey('publish_date') || doc['publish_date'].empty) {
          return 0.3;  // neutral penalty, not maximum
        }
        // decay logic here
      """
    }
  }
}
```
Alternatively, populate a `publish_date_score` field during indexing (0.0–1.0 normalized) and use `field_value_factor` with `missing: 0.3`.

**Detection / Warning Signs:**
- Articles without a `publish_date` field consistently appearing in the top 3 results
- Checking `explain=true` on a result and seeing `gauss` function returning `1.0` for a document with no date field

**Phase to address:** Relevance scoring (Phase 3 / scoring milestone)

---

### Pitfall M-2: Dynamic Mapping Creates Dual text+keyword Fields and Causes Mapping Explosion

**What goes wrong:**
Elasticsearch's default dynamic mapping creates both a `text` sub-field (for full-text search) and a `keyword` sub-field (for exact-match and aggregations) for every string field. For NitroFind's documents this is mostly fine for known fields, but if the scraper emits variable-structure JSON (e.g., per-article metadata keys from blog post frontmatter, Wikipedia infobox keys), each new key creates new mapping entries. At 1,000-field limit, Elasticsearch begins rejecting document writes with `illegal_argument_exception: Limit of total fields [1000] has been exceeded`.

**Why it happens:**
Scraper prototypes often emit raw infobox data (e.g., `"engine_displacement": "4.0L"`, `"wheelbase_mm": "2650"`) as top-level document fields. Wikipedia infobox schemas vary wildly between article types — a sports car, a muscle car, and a Formula 1 car have entirely different infobox keys.

**Consequences:**
- Index rejects writes after ~500 scraped articles that have varied infoboxes
- Re-mapping an existing index is not possible; full reindex required
- Slow cluster startup due to large mapping blob

**Prevention:**
Define an explicit, static mapping before indexing the first document. Use `dynamic: false` on the index to reject unmapped fields rather than silently creating new mappings. Consolidate variable infobox data into a single `specs` object with `type: flattened` — this stores arbitrary key-value pairs without exploding the field count.

**Detection / Warning Signs:**
- `PUT /articles/_doc/...` returns `mapper_parsing_exception` or `illegal_argument_exception` after many documents
- `GET /articles/_mapping` shows unexpectedly many fields
- Any field in the mapping named after a Wikipedia infobox key

**Phase to address:** Elasticsearch schema design (Phase 1)

---

### Pitfall M-3: Elasticsearch Startup Time Blocks the UI on App Launch

**What goes wrong:**
Elasticsearch's JVM takes 15–45 seconds to fully start on typical consumer hardware (spinning HDD: longer; SSD: 15–20 s). If the PyQt app starts Elasticsearch as a subprocess and then immediately tries to connect, the connection fails. Naive retry loops with no timeout freeze the UI on launch. If the app shows a blank window while waiting, users think it has crashed.

**Why it happens:**
Developers test on fast SSDs with warm JVM caches; end-user machines on HDDs (still common) take much longer.

**Consequences:**
- App appears dead for 30+ seconds on first launch
- Users force-quit and report the app is broken
- On Windows, slow Elasticsearch startup combined with Windows Defender scanning the JVM triggers even longer delays

**Prevention:**
Start Elasticsearch subprocess immediately on app launch (before showing the main window). Show a startup splash screen with a progress indicator polling `GET /_cluster/health?wait_for_status=yellow&timeout=60s`. Only replace the splash with the main UI when health status is `yellow` or `green`. Implement a 90-second timeout with a clear error dialog if ES fails to start. Cache the OS process handle to detect early crash vs slow start.

**Detection / Warning Signs:**
- Time from app launch to first usable search exceeds 5 seconds on an SSD
- Frequent "connection refused" errors in app logs during the first 30 seconds
- User reports on HDD machines seeing a blank or frozen window on launch

**Phase to address:** App startup and process management (Phase 3 / packaging milestone)

---

### Pitfall M-4: Scraping Automotive Blogs Without Respecting Rate Limits Gets the IP Blocked

**What goes wrong:**
Car and Driver, Road & Track, and Hagerty are commercial media sites running Cloudflare or Akamai WAF. Firing requests at full speed (no delay) will trigger rate limiting within seconds — typically an HTTP 429 or a 403 with a Cloudflare challenge page. The scraper receives what appears to be a valid 200 response containing an HTML challenge page instead of article content, and indexes the challenge text as article body.

**Why it happens:**
Default `requests` calls have no delay. One-off scraping against a personal test URL works fine; scraping hundreds of articles sequentially triggers rate limiting.

**Consequences:**
- IP gets banned (temporary or permanent) mid-scrape, leaving the database partially populated
- Challenge page HTML gets indexed as article content, poisoning relevance with noise
- No way to resume the scrape from where it stopped without a visited-URL checkpoint

**Prevention:**
(1) Use the MediaWiki API for all Wikipedia content — it is designed for programmatic access, has a documented rate limit of 200 requests/minute for non-authenticated bots, and returns structured data without HTML parsing. (2) For blog sites, add a randomized crawl delay of 2–5 seconds between requests, set a descriptive `User-Agent` header identifying the project, and respect `robots.txt` crawl-delay directives. (3) Implement a visited-URL checkpoint file so the scraper can resume after an interruption. (4) Validate each response: if body text is under 200 characters or contains "Cloudflare" or "CAPTCHA", discard and log as blocked.

**Detection / Warning Signs:**
- HTTP 429 status codes in scraper logs
- Scraped "articles" with body text under 300 characters
- Body text contains "checking your browser", "one more step", "ray ID"

**Phase to address:** Scraper robustness (Phase 2)

---

### Pitfall M-5: Wikipedia API Redirect Chains Cause Double-Indexing of the Same Article

**What goes wrong:**
Wikipedia uses redirects extensively. Searching for "Ferrari F40" may redirect to "Ferrari F40" (canonical), but the same article is also reachable via "F40 Ferrari", "Ferrari F40 (automobile)", and several other redirect titles. If the scraper seeds from category pages and link lists, it will encounter multiple redirect paths to the same canonical article, scrape it multiple times under different apparent titles, and index the same content with different `_id` values.

**Why it happens:**
The `wikipedia` Python library silently follows redirects and returns the canonical article, but does not expose the canonical title consistently — the `page.title` reflects the queried title, not the canonical one. Scripts using the page title as the document `_id` create duplicates.

**Consequences:**
- Same article indexed 2–5 times under different titles
- Relevance scoring rewards the duplicated article in proportion to duplicate count
- 2 GB budget wasted on duplicate content

**Prevention:**
Always use the `pageid` from the MediaWiki API as the Elasticsearch `_id`, not the title. Wikipedia page IDs are stable and canonical — all redirects to the same article share one `pageid`. Before indexing, call `action=query&redirects=1&titles=<title>` to resolve to the canonical `pageid`, then use that as the document ID. `es.index(index="articles", id=str(pageid), ...)` with `op_type="index"` will overwrite rather than duplicate.

**Detection / Warning Signs:**
- `GET /articles/_search?q=title:"Ferrari F40"` returns more than one document
- Multiple documents with very similar body text but different `_id` values
- `_id` values that look like article titles rather than numeric IDs

**Phase to address:** Scraper design (Phase 2)

---

## Minor Pitfalls

These cause friction or minor quality issues but are straightforward to fix once identified.

---

### Pitfall m-1: PyQt QListWidget for Search Results Cannot Handle 500+ Items Without Lag

**What goes wrong:**
`QListWidget` instantiates a real Qt widget for every item in the list. Adding 200+ search results causes a measurable paint delay (~100–300 ms) as Qt creates, measures, and lays out all widgets at once. If results are updated on every debounce tick, users typing quickly see brief visual freezes as the list is cleared and repopulated.

**Prevention:**
Use `QListView` with a `QAbstractListModel` instead of `QListWidget`. `QListView` renders only the visible rows (virtual rendering), regardless of total model size. Set `uniformItemSizes=True` if all result rows have the same height to enable Qt's batch layout optimization. Cap search results at 50 per page — Elasticsearch should also `size: 50` — so the model never holds more than 50 items at a time.

**Phase to address:** Search UI (Phase 3)

---

### Pitfall m-2: Elasticsearch function_score script_score Returns Negative or Zero Scores

**What goes wrong:**
Elasticsearch requires all document scores to be positive 32-bit floats. A `script_score` that can return 0 or negative values (e.g., a date freshness formula where old articles score negative) raises an error and the query fails entirely.

**Prevention:**
Clamp all `script_score` return values: `return Math.max(0.001, computedScore)`. Test with the oldest articles in the corpus and edge-case documents (missing fields, zero-length text).

**Phase to address:** Relevance scoring (Phase 3)

---

### Pitfall m-3: PyInstaller Cannot Bundle the Elasticsearch JVM — Distribution Requires a Separate ES Install

**What goes wrong:**
Elasticsearch is a Java application. PyInstaller bundles Python code and Python-native libraries but has no mechanism to bundle a JVM or a Java application. The app cannot be distributed as a single self-contained executable — the end user must separately install Elasticsearch (and Java) or the app must bundle a pre-extracted Elasticsearch directory alongside the Python executable.

**Prevention:**
Accept that NitroFind's distribution model is: (1) a Python executable (PyInstaller or Nuitka) for the UI and scraper, plus (2) a bundled Elasticsearch directory (pre-extracted, included in the installer). Use NSIS (Windows) or a shell script installer (Linux/macOS) to place the Elasticsearch directory in the app's data folder and set `ES_HOME` accordingly. Document this clearly in setup instructions. Do not attempt to have PyInstaller bundle the JVM — it will not work.

**Detection / Warning Signs:**
- Any design document that treats the app as a single `.exe` that "includes Elasticsearch"

**Phase to address:** Packaging and distribution (final phase)

---

### Pitfall m-4: Elasticsearch Index Becomes Read-Only When Disk Hits 85% Watermark

**What goes wrong:**
Elasticsearch has a disk-based shard allocation watermark. When disk usage reaches 85%, it stops allocating new shards. At 90%, it moves shards away from that node. In a single-node local setup the practical effect is that Elasticsearch silently puts the index into **read-only mode** when disk usage hits 85%. The scraper starts failing with `ClusterBlockException` on document writes, with no clear user-facing message.

**Prevention:**
In `elasticsearch.yml`, explicitly set:
```yaml
cluster.routing.allocation.disk.threshold_enabled: false
```
Or set the watermarks to more permissive values appropriate for a desktop machine. Alternatively, add a pre-scrape disk space check: warn and abort if free space is less than 5 GB before starting a scrape run.

**Detection / Warning Signs:**
- Scraper log shows `ClusterBlockException [blocked by: [FORBIDDEN/12/index read-only / allow delete (api)]]`
- `GET /_cluster/settings` shows watermark thresholds

**Phase to address:** Elasticsearch setup (Phase 1)

---

### Pitfall m-5: Wikipedia Infobox Data Is Inconsistent Across Article Types and Eras

**What goes wrong:**
Wikipedia automotive infobox templates differ by article type: "Automobile" infobox for production cars, "Infobox racing car" for motorsport, "Infobox engine" for engine articles. Field names, units, and presence vary. A scraper that assumes `infobox["manufacturer"]` always exists will throw `KeyError` on thousands of articles. Articles for pre-1950 vehicles often have minimal or no infobox at all.

**Prevention:**
Treat all infobox data as optional. Use `.get(key, None)` for every infobox field. Store extracted infobox fields in the `specs` flattened field (see Pitfall M-2), never as top-level document fields. The document schema should function correctly with zero infobox data.

**Phase to address:** Scraper design (Phase 2)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Elasticsearch initial setup | TLS autoconfiguration (C-1), JVM heap (C-2), disk watermark (m-4) | Configure `elasticsearch.yml` before first start |
| Index schema design | Dynamic mapping explosion (M-2) | Define explicit static mapping; `dynamic: false` |
| Wikipedia scraper | Disambiguation pages (C-5), redirect duplicates (M-5), infobox inconsistency (m-5) | Namespace filter + pageid as `_id` |
| Blog scraper | Rate limiting / IP block (M-4), raw HTML storage (C-3), deduplication (C-4) | Crawl delay + response validation + content hash |
| Relevance scoring | Decay missing-field behavior (M-1), negative scores (m-2), signal normalization | Use `script_score` for freshness; clamp all values |
| Search UI | Blocking UI thread (C-6), list widget performance (m-1) | QThread + debounce; QListView with model |
| App startup | Slow JVM startup (M-3) | Splash screen + health poll |
| Distribution / packaging | JVM not bundleable by PyInstaller (m-3) | Installer bundles pre-extracted Elasticsearch dir |

---

## Sources

- [High JVM memory pressure — Elastic Docs](https://www.elastic.co/docs/troubleshoot/elasticsearch/high-jvm-memory-pressure)
- [Managing and troubleshooting Elasticsearch memory — Elastic Blog](https://www.elastic.co/blog/managing-and-troubleshooting-elasticsearch-memory)
- [Elasticsearch heap size and JVM GC — Elasticsearch Labs](https://www.elastic.co/search-labs/blog/elasticsearch-heap-size-jvm-garbage-collection)
- [Translog corruption on killed process — elastic/elasticsearch #9699](https://github.com/elastic/elasticsearch/issues/9699)
- [Corrupt index after disk full — elastic/elasticsearch #18972](https://github.com/elastic/elasticsearch/issues/18972)
- [Troubleshoot data corruption — Elastic Docs](https://www.elastic.co/docs/troubleshoot/elasticsearch/corruption-troubleshooting)
- [Mapping explosion — Elastic Docs](https://www.elastic.co/docs/troubleshoot/elasticsearch/mapping-explosion)
- [3 ways to prevent mapping explosion — Elastic Blog](https://www.elastic.co/blog/3-ways-to-prevent-mapping-explosion-in-elasticsearch)
- [Function score query — Elasticsearch Reference](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-function-score-query)
- [Decay functions return 1.0 for missing field — elastic/elasticsearch #7788](https://github.com/elastic/elasticsearch/issues/7788)
- [Use PyQt's QThread to Prevent Freezing GUIs — Real Python](https://realpython.com/python-pyqt-qthread/)
- [Multithreading PyQt6 applications with QThreadPool — pythonguis.com](https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/)
- [Delay action to wait for user interaction (debounce) — Qt Wiki](https://wiki.qt.io/Delay_action_to_wait_for_user_interaction)
- [QListView and big database — Qt Centre](https://www.qtcentre.org/threads/59811-QListView-and-big-database-bad-performance)
- [How to Disable SSL/Auth of Elasticsearch — DEV Community](https://dev.to/wangpin34/how-to-disable-ssl-authencation-of-elasticsearch-46je)
- [Common Issues and Pitfalls — PyInstaller docs](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
- [Wikipedia-API Python wrapper — GitHub](https://github.com/martin-majlis/Wikipedia-API)
- [Web scraping access — MediaWiki](https://www.mediawiki.org/wiki/Web_scraping_access)
