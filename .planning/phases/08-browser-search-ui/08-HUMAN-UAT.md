# Phase 8: Browser Search UI — Human UAT Checklist

**Purpose:** Manual smoke-test checklist for browser-side behaviors that cannot be automated
under the no-npm constraint (no jsdom, no Playwright). Run this checklist before marking
Phase 8 as complete.

## Setup

1. Start the server: `python main.py`
2. Wait for "Starting up…" to disappear from the search box (ES warmup complete).
3. Open http://localhost:5000 in a browser.

## Checklist

### SRCH-01: Debounced search (300ms)
- [ ] Type slowly in the search box (e.g., "ford mustang") — results appear after a ~300ms
  pause without pressing Enter. Results update while still typing. No button press required.

### SRCH-02: Result row content and excerpt highlighting
- [ ] Each result row shows the article title, source domain (e.g., "en.wikipedia.org"),
  and an excerpt. Query terms in the excerpt are displayed in bold.

### SRCH-03: Article view without new tab; back navigation
- [ ] Click a result row — the article text fills the page in place; no new browser tab opens.
- [ ] Click the "Back" button (arrow) — the results list returns showing the same query and
  filter selection that was active before opening the article.

### SRCH-04: Filters narrow results without clearing query
- [ ] Select a filter dropdown (e.g., era "1960s"), then type a query — results are filtered
  by the selected era.
- [ ] Retype a different query — the filter selection remains in place (not reset to "All").

### UIPL-01: Dark theme with teal accent
- [ ] The page loads with a dark off-black background (#0f1117 or similar). No bright white
  background visible. No neon glows. Teal accent color visible on highlighted elements.

### UIPL-02: Result count and query time line
- [ ] After searching, a line below the search box reads "N results (X.XXs)"
  (e.g., "42 results (0.08s)"). Zero results shows "No results".

### UIPL-03: Keyboard navigation
- [ ] In the results state: press ArrowDown — first result row is highlighted.
- [ ] Press ArrowDown/ArrowUp repeatedly — selection moves through result rows.
- [ ] Press Enter on a highlighted row — article view opens for that result.
- [ ] Press Escape — the search input is cleared and the view returns to the home state.

### ES Warmup Behavior (D-07)
- [ ] On a fresh app start (before ES is ready), the search box is disabled with
  "Starting up…" text visible below it. Once ES becomes healthy, the text fades out
  and the input becomes enabled automatically without a page reload.

---

**Pass Criteria:** All checkboxes above must be checked before proceeding to `/gsd-verify-work`.
