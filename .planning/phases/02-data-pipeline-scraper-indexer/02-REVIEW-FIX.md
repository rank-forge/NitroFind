---
phase: 02-data-pipeline-scraper-indexer
fixed_at: 2026-05-15T00:00:00Z
review_path: .planning/phases/02-data-pipeline-scraper-indexer/02-REVIEW.md
iteration: 1
findings_in_scope: 11
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-05-15T00:00:00Z
**Source review:** .planning/phases/02-data-pipeline-scraper-indexer/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 11 (5 Critical + 6 Warning)
- Fixed: 11
- Skipped: 0

## Fixed Issues

### CR-01: `mark_visited` called after `yield` — state never persists on caller crash

**Files modified:** `nitrofind/scraper/wikipedia.py`, `nitrofind/scraper/blogs.py`
**Commit:** 9b54b02
**Applied fix:** Moved `self._state.mark_visited(...)` to execute before `yield doc` in both files. State is now recorded before transferring control to the caller, so if the caller crashes mid-batch and never resumes the generator, the document is not re-scraped on the next run.

---

### CR-02: Path-traversal guard bypassable via same-prefix directory names

**Files modified:** `nitrofind/scraper/state.py`
**Commit:** ee24908
**Applied fix:** Replaced the fragile `str(resolved).startswith(str(cwd_resolved) + os.sep)` check with `resolved.is_relative_to(cwd_resolved)` (Python 3.9+). This handles case-insensitive Windows paths, trailing separators, and same-prefix directory name collisions correctly. Also removed the now-unused `import os`.

---

### CR-03: `_url_slug()` produces colliding `article_id` values across domains

**Files modified:** `nitrofind/scraper/blogs.py`, `tests/test_scraper/test_blogs.py`
**Commit:** 269ed8f
**Applied fix:** `_url_slug()` now incorporates the source domain (netloc minus `www.`) into the slug: `f"{domain}__{segments[-1]}"`. This ensures two different blog targets with the same final path segment produce distinct `article_id` values and do not silently overwrite each other in Elasticsearch. Updated test assertion from `"ferrari-history"` to `"hagerty.com__ferrari-history"`.

---

### CR-04: `_index_size_bytes()` raises unhandled `KeyError` when index is absent

**Files modified:** `nitrofind/scraper/indexer.py`
**Commit:** e2eecac
**Applied fix:** Wrapped the deep dict access in a `try/except KeyError` that returns `0`. Prevents an unhandled exception from killing the entire scraper run on the first size check before any document has been written (or when the index was deleted between runs).

---

### CR-05: Personal email address hardcoded in production source

**Files modified:** `nitrofind/scraper/blogs.py`, `config/scraper.yaml`, `tests/test_scraper/test_blogs.py`
**Commit:** 3d672d8
**Applied fix:** Removed the `HONEST_USER_AGENT` constant containing the personal email address. The `BlogScraper` now reads `config["blogs"].get("user_agent", _DEFAULT_USER_AGENT)` where `_DEFAULT_USER_AGENT = "NitroFind/1.0 (offline automotive research tool)"` contains no personal information. Added a `user_agent` key under `blogs` in `scraper.yaml` with a generic value and a comment instructing users to supply their own contact address. Updated the test to import `_DEFAULT_USER_AGENT` instead of `HONEST_USER_AGENT` and assert against the config-driven value.

---

### WR-01: `yield_documents` fallback chain breaks after first successful listing even when zero articles yield

**Files modified:** `nitrofind/scraper/blogs.py`
**Commit:** 639f386
**Applied fix:** Introduced a `target_yielded` boolean that tracks whether the current target yielded at least one document. The `break` now fires only when `target_yielded` is `True`. When a listing returns 200 but zero articles are harvested (all visited or all `None`), the code logs a warning and continues to the next target rather than silently stopping the fallback chain.

---

### WR-02: `_get_category_members_raw` silently swallows network failures and returns empty list

**Files modified:** `nitrofind/scraper/wikipedia.py`
**Commit:** 94a857d
**Applied fix:** Added a `first_page_fetched` flag inside the pagination loop. When the exception is caught: if no pages were fetched yet (category truly unreachable), logs WARNING and returns `[]` as before. If pages were already collected (mid-pagination failure), logs ERROR noting the results are PARTIAL and returns whatever was collected so the category walk is not silently truncated to empty.

---

### WR-03: `compute_era_bucket` treats negative years as valid

**Files modified:** `nitrofind/scraper/cleaner.py`
**Commit:** 89fb5fb
**Applied fix:** Added bounds check `production_start < 1900 or production_start > 2099` to the guard condition. Values outside the valid automotive range (including negative years) now return `"Unknown"` instead of producing nonsensical strings like `"-510s"`. Updated docstring with additional examples.

---

### WR-04: `_fetch_and_build_doc` stores raw infobox dict in `specs` field without sanitisation

**Files modified:** `nitrofind/scraper/wikipedia.py`
**Commit:** 7853636
**Applied fix:** Changed `"specs": infobox` to `"specs": {k: str(v) for k, v in infobox.items()}`. All infobox values are flattened to strings before indexing, preventing ES mapping conflict errors from nested dicts, lists, or mixed types in the raw infobox data.

---

### WR-05: `_load_config` opens the config file without explicit encoding

**Files modified:** `scripts/scraper.py`
**Commit:** daffac7
**Applied fix:** Added `encoding="utf-8"` to the `open(config_path, "r")` call. Prevents `UnicodeDecodeError` on Windows when the YAML config contains non-ASCII characters (e.g., category names with accented characters).

---

### WR-06: `test_main_uses_yaml_safe_load` test is a static source scan, not a behavioural test

**Files modified:** `tests/test_scraper/test_cli.py`
**Commit:** 45c21e5
**Applied fix:** Replaced the source-text string scan with an AST walk using `ast.parse()` and `ast.walk()`. The test now verifies that `yaml.safe_load(...)` is actually called as a function (not just present in a comment) and that `yaml.load(...)` is never called (catching alias patterns like `load = yaml.load; load(fh)`). The behavioural test `test_main_uses_yaml_safe_load` (evil YAML payload) is preserved unchanged.

---

## Test Results

After all fixes: `python3 -m pytest tests/ -q --tb=short -m "not integration"` — **60 passed, 3 deselected in 0.78s**. No regressions.

---

_Fixed: 2026-05-15T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
