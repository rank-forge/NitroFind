---
phase: 04-desktop-ui
reviewed: 2026-05-28T12:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - tests/test_ui/__init__.py
  - nitrofind/search/models.py
  - nitrofind/search/query_builder.py
  - tests/test_search/test_models.py
  - tests/test_search/test_engine.py
  - tests/test_search/test_query_builder.py
  - nitrofind/ui/result_delegate.py
  - nitrofind/ui/filter_sidebar.py
  - tests/test_ui/test_result_delegate.py
  - tests/test_ui/test_filter_sidebar.py
  - tests/test_ui/test_main_window.py
  - nitrofind/ui/main_window.py
  - main.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-28T12:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the complete Phase 4 desktop UI implementation: search engine thread-pool integration (`engine.py`), data models, query builder, filter sidebar, main window, result delegate, entry point (`main.py`), and their test suites. The search and model layers are sound — security mitigations for injection, cross-index access, and result-size caps are correctly implemented and well-tested.

Two blockers are present. First, `QCheckBox.stateChanged` (emits `int`) is connected directly to `QTimer.start` (overloaded: `start(msec: int)` permanently replaces the stored interval), so every checkbox interaction permanently destroys the 300 ms debounce, confirmed by live PyQt6 testing. Second, the stale-result guard (`_current_seq`) is not incremented on the empty-query path, meaning an in-flight search result can repopulate the result list after the user has already cleared the search bar — the guard is bypassed.

Four warnings cover: raw article content inserted unescaped into `setHtml`; the error callback having no sequence guard; a `ValueError`-unsafe type conversion in `from_es_hit`; and `BODY_STYLES` filter constants that can never match Wikipedia-scraped data. Three info items cover a missing UI-SPEC empty-results label, a fragile time-based wait in a stale-result test, and an unnecessary `noqa` comment.

## Critical Issues

### CR-01: `stateChanged` integer passed to `QTimer.start()` permanently corrupts the debounce interval

**File:** `nitrofind/ui/main_window.py:227-232`

**Issue:** `QCheckBox.stateChanged` emits an `int` (0 = unchecked, 2 = checked in PyQt6). `QTimer.start()` is overloaded: the no-argument form `start()` restarts with the stored interval, but `start(msec: int)` restarts with a new interval **and permanently replaces the stored interval**. Lines 227-232 connect `stateChanged` directly to `self._debounce_timer.start`:

```python
for cb in self._filter_sidebar.manufacturer_checks.values():
    cb.stateChanged.connect(self._debounce_timer.start)
```

When a user checks a box, Qt delivers `start(2)` — the timer fires after 2 ms and sets the stored interval to 2 ms. When a user unchecks a box, Qt delivers `start(0)`, making the timer a zero-delay timer permanently. Subsequent no-argument `start()` calls from `textChanged` then fire with the corrupted interval. Confirmed by runtime test:

```
timer.setInterval(300)
timer.start(2)      # simulate checkbox check
timer.interval()    # → 2   (300 ms permanently gone)
timer.start(0)      # simulate uncheck
timer.interval()    # → 0   (now fires immediately)
timer.start()       # next textChanged no-arg restart
timer.interval()    # → 0   (debounce is dead)
```

Every keystroke after the first checkbox interaction fires an immediate ES query, creating a query burst on every typed character and defeating SRCH-01 entirely for the rest of the session.

**Fix:** Discard the emitted integer with a no-argument lambda:

```python
for cb in self._filter_sidebar.manufacturer_checks.values():
    cb.stateChanged.connect(lambda _: self._debounce_timer.start())
for cb in self._filter_sidebar.era_checks.values():
    cb.stateChanged.connect(lambda _: self._debounce_timer.start())
for cb in self._filter_sidebar.body_style_checks.values():
    cb.stateChanged.connect(lambda _: self._debounce_timer.start())
```

`lambda _: self._debounce_timer.start()` calls `start()` with no arguments (restarts with the stored 300 ms) regardless of the checkbox state value.

---

### CR-02: Stale-result guard is bypassed when the user clears the search bar

**File:** `nitrofind/ui/main_window.py:286-290`

**Issue:** `_current_seq` is incremented **only** in the non-empty query branch (line 293). The empty-query branch (lines 286-290) clears the result list and resets the title but returns without incrementing `_current_seq`. This leaves the sequence counter at its last dispatched value.

Scenario:
1. User types "Ferrari" → `_current_seq` becomes 1, search dispatched with `seq=1`
2. User presses Escape → `_execute_search` runs with empty query → clears result list → **`_current_seq` stays at 1** → returns
3. Ferrari search result returns → `_on_results(results, took, seq=1)` → check: `1 == _current_seq (1)` → **guard passes** → result list is repopulated even though the search bar is now empty

The user now sees results for a search they explicitly cancelled, contradicting their intent and the T-04-05 stale-result protection.

**Fix:** Increment `_current_seq` in the empty-query branch as well, so any in-flight search result is treated as stale after the bar is cleared:

```python
def _execute_search(self) -> None:
    query = self._search_bar.text().strip()
    if not query:
        self._current_seq += 1   # invalidate any in-flight search
        self._result_list.clear()
        self._status_label.setText("")
        self.setWindowTitle("NitroFind — Ready")
        return
    # ... rest unchanged
```

---

## Warnings

### WR-01: Unescaped article content interpolated into `setHtml` in the detail pane

**File:** `nitrofind/ui/main_window.py:411-415`

**Issue:** `_show_result_detail` builds HTML by f-string-interpolating `result.title`, `result.source_domain`, `result.url`, and `body_text` directly into a `setHtml` call without HTML-escaping:

```python
self._detail_pane.setHtml(
    f"<h2 style='font-size:14pt'>{result.title}</h2>"
    f"<p style='color:#80cbc4;font-size:9pt'>{result.source_domain} · {result.url}</p>"
    f"<hr>"
    f"<p style='font-size:10pt;line-height:1.5'>{body_text}</p>"
)
```

Article content scraped from Wikipedia and automotive blogs can contain angle brackets, ampersands, and partial HTML tags — e.g., a title like `"Ferrari <i>308</i>"` or body text with `<table>` markup. Qt Rich Text's HTML parser is lenient; injected block-level tags (`<table>`, `<img>`, `<ul>`) in `body_text` can corrupt the detail pane layout or swallow following content. While `QTextBrowser` does not execute JavaScript and `setOpenLinks(False)` prevents navigation, the Qt HTML subset parses enough markup that unescaped content causes visual defects in practice. The same issue exists in `result_delegate.py` lines 94-96 for `result.source_domain` (the plain-text fallback path).

**Fix:** HTML-escape untrusted fields. Highlight fragments from ES (`highlight_title`, `highlight_body`) are intentionally tagged with `<b>` and must not be escaped; plain-text fallback fields must be escaped:

```python
from html import escape

def _show_result_detail(self, result: ArticleResult) -> None:
    if result is None:
        return
    body_text = result.body if result.body else result.excerpt
    self._detail_pane.setHtml(
        f"<h2 style='font-size:14pt'>{escape(result.title)}</h2>"
        f"<p style='color:#80cbc4;font-size:9pt'>"
        f"{escape(result.source_domain)} · {escape(result.url)}</p>"
        f"<hr>"
        f"<p style='font-size:10pt;line-height:1.5'>{escape(body_text)}</p>"
    )
```

In `result_delegate.py` line 95, `result.source_domain` should also use `escape()`.

---

### WR-02: Error callback has no sequence guard — stale error can overwrite a newer success

**File:** `nitrofind/ui/main_window.py:303`

**Issue:** The stale-result guard captures `seq` in the success callback lambda (line 302) but `error_callback` is passed as a direct method reference with no sequence check:

```python
callback=lambda results, took, s=seq: self._on_results(results, took, s),
error_callback=self._on_search_error,   # no seq guard
```

If search #1 is slow and fails while search #2 has already succeeded:
1. Search #2 succeeds → `_on_results` with seq=2 passes guard → results shown
2. Search #1 fails → `_on_search_error` called → no guard → status label overwritten with "Search failed. Check Elasticsearch connection."

The user sees a valid result list with a false error status label.

**Fix:** Wrap the error callback with the same sequence guard:

```python
seq = self._current_seq

def _guarded_error(msg: str, s: int = seq) -> None:
    if s != self._current_seq:
        return
    self._on_search_error(msg)

self._engine.search(
    query,
    filters=self._filter_sidebar.collect_filters(),
    callback=lambda results, took, s=seq: self._on_results(results, took, s),
    error_callback=_guarded_error,
)
```

---

### WR-03: `BODY_STYLES` filter constants use title-case values that will never match Wikipedia scraped data

**File:** `nitrofind/ui/filter_sidebar.py:89-98`

**Issue:** `BODY_STYLES` contains title-cased values: `"Coupe"`, `"Sedan"`, `"Convertible"`, etc. These are used in ES `term` filter queries — exact, case-sensitive keyword matches. Wikipedia infobox data for `body_style` is stored as raw scraped text (e.g., `"2-door coupe"`, `"4-door saloon"`, `"3-door hatchback"`). The term query `{"term": {"body_style": "Coupe"}}` will never match any Wikipedia-originated document because the scraped values are lower-cased multi-word strings. This means every body-style filter selection silently returns 0 results. The manufacturer filter has the same risk: raw infobox values like `"Ferrari S.p.A."` will not match the sidebar's `"Ferrari"`. The era_bucket filter is correctly aligned (computed as `"1960s"`, `"1970s"` etc. by `compute_era_bucket` in `cleaner.py`).

**Fix:** Either (a) normalize `body_style` in the scraper to a controlled vocabulary during indexing, or (b) normalize `BODY_STYLES` values to match the actual indexed format. Since scraper normalization is the appropriate place for this:

```python
# In nitrofind/scraper/wikipedia.py — normalize body_style before indexing:
raw_body_style = (infobox.get("body_style") or infobox.get("Body style") or "").lower()
BODY_STYLE_MAP = {
    "coupe": "Coupe", "coupé": "Coupe", "2-door": "Coupe",
    "sedan": "Sedan", "saloon": "Sedan",
    "convertible": "Convertible", "cabriolet": "Convertible", "roadster": "Convertible",
    "suv": "SUV", "crossover": "SUV",
    "hatchback": "Hatchback",
    "wagon": "Wagon", "estate": "Wagon",
    "pickup": "Pickup", "truck": "Pickup",
    "van": "Van",
}
body_style = next((v for k, v in BODY_STYLE_MAP.items() if k in raw_body_style), "")
```

---

### WR-04: `int()` and `float()` conversions in `from_es_hit` raise `ValueError` on malformed data

**File:** `nitrofind/search/models.py:75-77`

**Issue:**

```python
raw_score = hit.get("_score")
score = float(raw_score) if raw_score is not None else 0.0
raw_word_count = src.get("word_count")
word_count = int(raw_word_count) if raw_word_count is not None else 0
```

Both `float()` and `int()` raise `ValueError` if the value is a non-numeric string (e.g., `"unknown"`, `""`, or a string representation of a malformed number). `int()` additionally raises `TypeError` on incompatible types and `ValueError` on floats passed as strings (`int("3.5")` raises). A `ValueError` from a single malformed document propagates through the list comprehension in `_SearchWorker.run()`, gets caught by the broad `except Exception`, and causes `search_failed` to fire — the user sees an error and loses all other valid hits for that query. The ES mapping should prevent this, but schema evolution and index corruption are real operational risks.

**Fix:** Use a safe conversion helper:

```python
def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))  # handles "3.5" → 3 gracefully
    except (TypeError, ValueError):
        return default

# In from_es_hit:
score = _safe_float(hit.get("_score"), 0.0)
word_count = _safe_int(src.get("word_count"), 0)
```

---

## Info

### IN-01: UI-SPEC empty-results label is documented but never rendered

**File:** `nitrofind/ui/main_window.py:17` (docstring), `nitrofind/ui/main_window.py:326-333` (implementation)

**Issue:** The module docstring copywriting contract specifies:

```
Empty result list label: "No articles match your search.\nTry different keywords or adjust filters."
```

The `_on_results` no-results branch sets `status_label` to `"No results"` (correct per UIPL-02) but resets the detail pane to the idle-state message `"Select a result to read the article."` The in-list empty-state label is never shown anywhere. The result list is simply empty with no guidance to the user about why there are no results or what to try next. The copywriting contract string is dead documentation.

**Fix:** Display the specified empty-state label in the result list area, either as a disabled placeholder item or an overlay `QLabel`. A simple approach:

```python
if not results:
    self._status_label.setText("No results")
    placeholder = QListWidgetItem(
        "No articles match your search.\nTry different keywords or adjust filters."
    )
    placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
    self._result_list.addItem(placeholder)
    return
```

---

### IN-02: `qtbot.wait(50)` in stale-result test is a time-based wait that can be flaky

**File:** `tests/test_ui/test_main_window.py:529`

**Issue:** `test_stale_results_discarded` uses `qtbot.wait(50)` after clearing the search bar to prevent the debounce timer from firing on the cleared text before the second query is typed:

```python
window._search_bar.clear()
# Give the debounce timer a moment to not fire on the cleared text
qtbot.wait(50)
```

The test relies on the 50 ms sleep being less than the 300 ms debounce timer, which is true under normal conditions but can fail on an overloaded CI system where thread scheduling delays make `wait(50)` take longer and the timer fires unexpectedly. The RESEARCH.md explicitly calls out time-based waits as an anti-pattern (Pitfall documented in 04-RESEARCH.md).

**Fix:** Instead of a time-based wait, directly call `_execute_search()` to flush the empty-query path synchronously before dispatching the second search, or use `window._debounce_timer.stop()` to explicitly cancel the timer after clearing:

```python
window._search_bar.clear()
window._debounce_timer.stop()  # cancel timer explicitly — no time dependency
callback_2 = _trigger_search_and_capture_callback(qtbot, window, engine_mock, "porsche")
```

---

### IN-03: `noqa: F401` suppression on `ArticleResult` import is misleading

**File:** `nitrofind/ui/main_window.py:61`

**Issue:** Line 61 reads:

```python
from nitrofind.search.models import ArticleResult  # noqa: F401 (used in type hints)
```

With `from __future__ import annotations` at line 40, all annotations are lazily-evaluated strings, so `ArticleResult` is not needed at runtime. However, the import IS referenced in inline annotations at lines 382, 396, and 410 (`result: ArticleResult = ...` and `def _show_result_detail(self, result: ArticleResult)`). A linter that understands `from __future__ import annotations` will not flag this import as unused because it recognizes the annotation-only usage. The `# noqa: F401` suppression therefore silently hides any future actual unused import on this line and adds incorrect explanatory noise.

**Fix:** Remove the `# noqa: F401` comment. If the linter does flag F401 on this specific import, the correct response is to keep the import (it is semantically used) rather than suppress the warning.

---

_Reviewed: 2026-05-28T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
