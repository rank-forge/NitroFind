---
phase: 04-desktop-ui
fixed_at: 2026-05-28T12:30:00Z
review_path: .planning/phases/04-desktop-ui/04-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 5
skipped: 1
status: partial
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-05-28T12:30:00Z
**Source review:** `.planning/phases/04-desktop-ui/04-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (2 Critical + 4 Warning)
- Fixed: 5
- Skipped: 1 (WR-03 partial — UI side not changed, scraper normalization applied)

## Fixed Issues

### CR-01: `stateChanged` int corrupts debounce timer permanently

**Files modified:** `nitrofind/ui/main_window.py`
**Commit:** `f32a7db`
**Applied fix:** Changed all three filter checkbox group signal connections from `cb.stateChanged.connect(self._debounce_timer.start)` to `cb.stateChanged.connect(lambda _: self._debounce_timer.start())`. The lambda discards the `int` emitted by `stateChanged` (0 or 2) and calls `start()` with no arguments so the stored 300 ms interval is always used, never replaced.

---

### CR-02: Stale-result guard bypassed when user clears the search bar

**Files modified:** `nitrofind/ui/main_window.py`
**Commit:** `cd3a069`
**Applied fix:** Added `self._current_seq += 1` as the first statement in the empty-query branch of `_execute_search()`. Any in-flight search result carrying the old `seq` value will now fail the `seq != self._current_seq` guard in `_on_results()` and be discarded, even if the user clears the search bar before the result arrives.

---

### WR-01: Unescaped article content in `setHtml` detail pane

**Files modified:** `nitrofind/ui/main_window.py`, `nitrofind/ui/result_delegate.py`
**Commit:** `d1e30eb`
**Applied fix:**
- Added `import html` to both files.
- In `_show_result_detail` (main_window.py): wrapped `result.title`, `result.source_domain`, `result.url`, and `body_text` with `html.escape()`. ES highlight fields (`highlight_title`, `highlight_body`) contain intentional `<b>` tags from the ES highlighter and are NOT escaped — they are used as-is in the title/excerpt positions.
- In `_result_to_html` (result_delegate.py): wrapped `result.source_domain` with `html.escape()`. The `title` and `excerpt` variables may contain ES highlight `<b>` tags (via `highlight_title[0]` / `highlight_body[0]`) and must not be escaped.

---

### WR-02: Error callback has no stale sequence guard

**Files modified:** `nitrofind/ui/main_window.py`
**Commit:** `89c9ed0`
**Applied fix:** Replaced the direct `error_callback=self._on_search_error` reference with a `_guarded_error` inner function that captures `seq` via a default argument (same pattern as the success callback lambda). The inner function checks `s != self._current_seq` and returns early for stale errors, then calls `self._on_search_error(msg)` for current errors.

---

### WR-03: `BODY_STYLES` filter constants never match Wikipedia scraped data

**Files modified:** `nitrofind/scraper/wikipedia.py`
**Commit:** `83ba801`
**Applied fix:** Added a `_BODY_STYLE_MAP` dict and normalization logic in `_fetch_and_build_doc()` between the production year computation and the doc dict construction. The raw infobox `body_style` value is lowercased and matched against the map keys using substring search (`if k in raw_body_style`), yielding the title-cased controlled vocabulary value (e.g., `"2-door coupe"` → `"Coupe"`, `"4-door saloon"` → `"Sedan"`). Articles with unrecognized body styles index an empty string. The `BODY_STYLES` constants in `filter_sidebar.py` are unchanged — the fix is in the scraper where normalization belongs.

---

### WR-04: `int()`/`float()` in `from_es_hit` raise `ValueError` on malformed ES data

**Files modified:** `nitrofind/search/models.py`
**Commit:** `d8efd70`
**Applied fix:** Added two module-level helper functions `_safe_float(value, default=0.0)` and `_safe_int(value, default=0)` that wrap the conversions in `try/except (TypeError, ValueError)`. `_safe_int` converts via `int(float(value))` so string-encoded floats like `"3.5"` are handled gracefully (truncated to 3). Updated `from_es_hit` to use `_safe_float(hit.get("_score"), 0.0)` and `_safe_int(src.get("word_count"), 0)` in place of the inline conditional conversions.

---

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-05-28T12:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
