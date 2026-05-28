---
phase: 04-desktop-ui
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - nitrofind/search/engine.py
  - nitrofind/search/models.py
  - nitrofind/search/query_builder.py
  - nitrofind/ui/filter_sidebar.py
  - nitrofind/ui/main_window.py
  - nitrofind/ui/result_delegate.py
  - tests/test_search/test_engine.py
  - tests/test_search/test_models.py
  - tests/test_search/test_query_builder.py
  - tests/test_ui/__init__.py
  - tests/test_ui/test_filter_sidebar.py
  - tests/test_ui/test_main_window.py
  - tests/test_ui/test_result_delegate.py
  - main.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Reviewed the complete Phase 4 desktop UI implementation — search engine thread pool integration, data models, query builder, filter sidebar, main window, result delegate, and tests. The search and model layers are well-structured, with solid security mitigations documented and implemented. The critical defect is in `main_window.py`: `QCheckBox.stateChanged` (which emits an `int`) is wired directly to `QTimer.start` (which accepts an optional `int msec` argument), silently overriding the 300 ms debounce interval on every checkbox interaction. This corruption is permanent — once a user checks a filter checkbox, all subsequent text-change debounce fires are broken for the session. Four warnings cover unescaped article content in the detail pane, an incomplete UI-SPEC implementation (missing empty-results label), the stale-result guard not covering error callbacks, and a fragile `int()` conversion in models. Two info items cover a `noqa` suppressant that is no longer needed and a test coverage gap.

## Critical Issues

### CR-01: `stateChanged` int argument permanently corrupts the debounce timer interval

**File:** `nitrofind/ui/main_window.py:227-232`

**Issue:** `QCheckBox.stateChanged` emits an `int` (0 = unchecked, 2 = checked) as its argument. `QTimer.start()` is overloaded: `start()` restarts with the stored interval, but `start(msec: int)` restarts with a *new* interval and **also replaces the stored interval**. Connecting `stateChanged` to `timer.start` therefore passes the checkbox state value as the millisecond argument. Checking a box calls `start(2)` — the timer fires after 2 ms instead of 300 ms, and permanently changes the stored interval to 2 ms. All subsequent `textChanged -> timer.start()` (no-arg) calls then also fire with 2 ms, eliminating debounce for the rest of the session. Unchecking calls `start(0)`, making the timer fire immediately (Qt processes `start(0)` as a zero-delay timeout) and permanently stores 0 ms. This is confirmed by live PyQt6 testing:

```
timer.setInterval(300)
timer.start(2)     # simulate checkbox check
timer.interval()   # → 2   (300 ms gone, permanently)
timer.start()      # no-arg restart after textChanged
timer.interval()   # → 2   (still 2 ms — debounce is dead)
```

The debounce timer corruption means each keystroke after the first checkbox interaction fires an immediate ES query, creating a rapid burst of queries on every typed character — effectively a self-inflicted denial-of-service against the ES node, and defeating the entire purpose of SRCH-01.

**Fix:** Connect with a no-argument lambda or `lambda _: self._debounce_timer.start()` so the state integer is discarded:

```python
# Replace lines 227-232 in main_window.py:
for cb in self._filter_sidebar.manufacturer_checks.values():
    cb.stateChanged.connect(lambda _: self._debounce_timer.start())
for cb in self._filter_sidebar.era_checks.values():
    cb.stateChanged.connect(lambda _: self._debounce_timer.start())
for cb in self._filter_sidebar.body_style_checks.values():
    cb.stateChanged.connect(lambda _: self._debounce_timer.start())
```

This calls `start()` with no arguments (restart with the stored 300 ms interval) regardless of the checkbox state value. The `lambda _:` pattern discards the emitted int while keeping the connection.

---

## Warnings

### WR-01: Unescaped article content inserted into `setHtml` in detail pane

**File:** `nitrofind/ui/main_window.py:411-415`

**Issue:** `_show_result_detail` builds HTML by f-string-interpolating `result.title`, `result.source_domain`, `result.url`, and `body_text` directly into a `setHtml` call without HTML-escaping. Article content scraped from the web can contain angle brackets, ampersands, or partial HTML tags (e.g., a title like `"Ferrari <i>308</i>"` or a URL with `&amp;` entities). Qt Rich Text's HTML parser is lenient — malformed tags from article content can break the rendered layout, swallow subsequent content, or introduce unexpected visual structure. Although `QTextBrowser` does not execute JavaScript and `setOpenLinks(False)` blocks navigation, Qt's HTML subset still parses enough markup that injected `<img>`, `<table>`, or block-level tags in `body_text` can corrupt the detail pane rendering.

**Fix:** HTML-escape the untrusted fields before interpolation:

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

Note: `result.url` should be escaped but also consider whether it should be rendered as a clickable link. If so, use `escape()` on the display text but keep the raw URL in the `href` attribute.

The same concern applies to `_result_to_html` in `result_delegate.py` lines 94-96, where `result.source_domain` is interpolated unescaped. Highlight fragments (`highlight_title`, `highlight_body`) intentionally contain `<b>` tags from ES and should not be escaped — only the plain-text fallback fields need escaping.

---

### WR-02: UI-SPEC "Empty result list label" is not implemented

**File:** `nitrofind/ui/main_window.py:326-333`

**Issue:** The module docstring explicitly lists the copywriting contract for the empty result state (line 17):

```
Empty result list label: "No articles match your search.\nTry different keywords or adjust filters."
```

When `_on_results` is called with an empty list, the code sets `status_label` to `"No results"` (correct) but then sets the detail pane back to `"Select a result to read the article."` — which is semantically the *initial idle state* message, not the *no-results state* message. The actual empty-results label `"No articles match your search..."` is never displayed anywhere. The result list is simply empty with no in-list feedback. This means the spec-required empty state guidance is silently absent from the UI.

**Fix:** In the no-results branch, display the specified label, e.g., by adding a `QLabel` overlay on the result list, or by inserting a disabled placeholder item:

```python
if not results:
    self._status_label.setText("No results")
    # Show the copywriting-contract empty-state message in the result area
    placeholder = QListWidgetItem(
        "No articles match your search.\nTry different keywords or adjust filters."
    )
    placeholder.setFlags(Qt.ItemFlag.NoItemFlags)  # non-selectable
    self._result_list.addItem(placeholder)
    # Reset detail pane to idle message
    self._detail_pane.setHtml(
        "<p style='color:#80cbc4;font-size:10pt;margin-top:32px;text-align:center'>"
        "Select a result to read the article."
        "</p>"
    )
    return
```

---

### WR-03: Stale-result guard does not cover `error_callback` — a slow failed search can overwrite a newer success

**File:** `nitrofind/ui/main_window.py:303`

**Issue:** The stale-result guard (`_current_seq`) is applied to the success callback via the captured `s=seq` lambda (line 302), but `error_callback=self._on_search_error` is passed as a direct method reference with no sequence check (line 303). If search #1 fails slowly and search #2 succeeds quickly, the sequence is:

1. Search #1 dispatched (seq=1), search #2 dispatched (seq=2, _current_seq=2)
2. Search #2 succeeds → `_on_results` called with seq=2 — guard passes, results shown
3. Search #1 fails → `_on_search_error` called — no guard, overwrites status label with "Search failed. Check Elasticsearch connection."

The user now sees a success result list but a "Search failed" status label, which is confusing and incorrect.

**Fix:** Capture the sequence number for the error callback as well:

```python
self._current_seq += 1
seq = self._current_seq

def _error_cb(msg: str, s: int = seq) -> None:
    if s != self._current_seq:
        return  # stale error — discard
    self._on_search_error(msg)

self._engine.search(
    query,
    filters=self._filter_sidebar.collect_filters(),
    callback=lambda results, took, s=seq: self._on_results(results, took, s),
    error_callback=_error_cb,
)
```

---

### WR-04: `int()` conversion in `from_es_hit` will raise `ValueError` on non-numeric `word_count`

**File:** `nitrofind/search/models.py:77`

**Issue:** `word_count = int(raw_word_count) if raw_word_count is not None else 0` will raise `ValueError` if the ES document has a `word_count` field with a non-integer value (e.g., the string `"unknown"` or a float stored as a string). Similarly, `float(raw_score)` on line 75 will raise `ValueError` if `_score` is a non-numeric string. While the ES mapping should enforce the correct type, schema evolution or index corruption can produce unexpected values. A `ValueError` in `from_es_hit` will propagate through `_SearchWorker.run()`'s list comprehension, get caught by the broad `except Exception`, and emit `search_failed` — the user sees an error for what may be a single malformed document, losing all other valid hits.

**Fix:** Wrap the conversions in a try/except or use a safe helper:

```python
def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

# In from_es_hit:
score = _safe_float(hit.get("_score"), 0.0)
word_count = _safe_int(src.get("word_count"), 0)
```

---

## Info

### IN-01: `noqa: F401` suppression on `ArticleResult` import is unnecessary

**File:** `nitrofind/ui/main_window.py:61`

**Issue:** The comment `# noqa: F401 (used in type hints)` was appropriate when `ArticleResult` was used only in string-form annotations. At runtime, `ArticleResult` is referenced directly in non-string type annotations at lines 382, 396, and 399 (`result: ArticleResult = ...` and `def _show_result_detail(self, result: ArticleResult)`). With `from __future__ import annotations` at line 40, all annotations are lazily evaluated strings, so `ArticleResult` is not actually needed at runtime — but flake8/ruff should already see the inline usages and not flag F401. The suppression comment creates misleading noise suggesting the import would otherwise be flagged as unused.

**Fix:** Remove the `# noqa: F401` comment. If a linter does flag it, the correct fix is to keep the import as-is (it is used in annotations) rather than suppress the warning.

---

### IN-02: Test suite does not cover the debounce corruption scenario (no assertion on `timer.interval()` after checkbox interaction)

**File:** `tests/test_ui/test_main_window.py`

**Issue:** No test verifies that `_debounce_timer.interval()` remains 300 ms after a filter checkbox is checked or unchecked. The existing `test_debounce_timer_interval` (Test 1) only checks the initial timer configuration. `test_filter_preserved_on_retype` (Test 5) exercises the filter checkbox but does not assert on the timer interval. The debounce corruption described in CR-01 would not be caught by the current test suite.

**Fix:** Add a test that checks the timer interval is unchanged after checkbox interaction:

```python
def test_filter_checkbox_does_not_corrupt_debounce_interval(qtbot, monkeypatch):
    window, _ = _make_window(qtbot, monkeypatch)
    assert window._debounce_timer.interval() == 300  # initial

    window._filter_sidebar.manufacturer_checks["Ferrari"].setChecked(True)
    assert window._debounce_timer.interval() == 300, (
        "Checking a filter checkbox must not change the debounce timer interval"
    )

    window._filter_sidebar.manufacturer_checks["Ferrari"].setChecked(False)
    assert window._debounce_timer.interval() == 300, (
        "Unchecking a filter checkbox must not change the debounce timer interval"
    )
```

---

_Reviewed: 2026-05-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
