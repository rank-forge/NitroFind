---
status: complete
phase: 01-infrastructure-schema-foundation
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md]
started: 2026-05-13T14:00:00.000Z
updated: 2026-05-13T15:00:00.000Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 8
name: Error State and Retry
expected: |
  [testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running Elasticsearch process. Start `python main.py` from scratch (with ES_HOME set). The app boots without errors — loading window appears immediately, ES health polling runs, and the main window appears after ES reaches a healthy state. A `curl http://localhost:9200/_cluster/health` returns live JSON with status green or yellow.
result: pass

### 2. Dependency Lockfile Reproducibility
expected: In a fresh virtual environment, `pip install -r requirements.txt` completes with no version conflicts. Every runtime package (elasticsearch, PyQt6, qt-material, requests) is pinned to an exact version. Running `pytest tests/test_lockfile.py -q` shows 3 passed, 0 failed.
result: pass

### 3. ES Configuration Setup Script
expected: With ES_HOME set to a valid ES 8.x directory, `python scripts/setup_es.py` prints "ES configuration installed." and exits 0. With ES_HOME unset (`ES_HOME= python scripts/setup_es.py`), it prints a clear error message to stderr and exits non-zero — no raw Python traceback shown.
result: pass

### 4. Launch — Loading Window Appearance
expected: Running `python main.py` immediately shows a frameless ~360×240 dark window. It displays "NitroFind" text in large semibold style, a teal rotating arc spinner, and "Starting search engine…" label below. No Retry or Quit buttons are visible during this initial loading phase.
result: pass

### 5. ES Startup and Main Window Transition
expected: After Elasticsearch reaches healthy status (within ~180s), the loading window closes and a "NitroFind — Ready" stub window (minimum 800×600) appears with "Search engine ready." centered inside. Dark theme is consistent across both windows — no white or light-colored regions appear.
result: pass

### 6. Index Schema Correctness
expected: While the app is running (after the main window appears), `curl -s http://localhost:9200/car_articles/_mapping` returns JSON for the `car_articles` index. The mapping contains all required fields (title, body, excerpt, url, source_domain, article_id, scraped_at, published_at, word_count, image_count, has_infobox, manufacturer, body_style, era_bucket, country_of_origin, production_start, production_end, specs). The `"dynamic"` setting is `"false"`.
result: pass

### 7. Clean Shutdown — No Orphan JVM
expected: Closing the app (× button) exits without hanging. Immediately after exit, `ps aux | grep elasticsearch` shows no running Elasticsearch or Java processes that belong to NitroFind (the subprocess started by main.py is gone).
result: pass

### 8. Error State and Retry
expected: Starting the app with an invalid ES_HOME (`ES_HOME=/nonexistent python main.py`) shows a user-friendly error message inside the loading window — not a raw Python traceback or JVM log. Retry and Quit buttons are visible. Clicking Retry resets the window to the loading spinner state. Clicking Quit exits the application cleanly.
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

