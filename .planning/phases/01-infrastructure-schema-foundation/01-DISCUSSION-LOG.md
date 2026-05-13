# Phase 1: Infrastructure & Schema Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 1-Infrastructure & Schema Foundation
**Areas discussed:** ES binary location, Startup architecture, Loading screen design, era_bucket vocabulary

---

## ES Binary Location

| Option | Description | Selected |
|--------|-------------|----------|
| ES_HOME env var | Developer sets ES_HOME in shell/dotenv pointing to ES directory. Phase 5 sets it via launcher. Consistent across dev and packaged. | ✓ |
| Config file | A config.toml or .env file in the project root holds the es_home path. Easy to commit a template; actual path gitignored. | |
| Relative ./elasticsearch-8.18/ | App looks for ES in a predictable relative directory next to the project root. Simple but brittle if ES is installed elsewhere. | |

**User's choice:** ES_HOME env var

---

| Option | Description | Selected |
|--------|-------------|----------|
| Crash with clear error message | Print "ES_HOME is not set. Set it to your Elasticsearch 8.18 directory." and exit. Fails fast, obvious to diagnose. | ✓ |
| Fall back to PATH search | Try `which elasticsearch` / `shutil.which` as a secondary attempt before failing. Handles brew/apt installs. | |
| Fall back to ./elasticsearch-8.18/ | Try a relative default path before giving up. Silent fallback — easier to set up but less explicit. | |

**User's choice:** Crash with clear error message (if ES_HOME not set)

---

| Option | Description | Selected |
|--------|-------------|----------|
| $ES_HOME/bin/elasticsearch | Standard ES directory layout — works with official tar.gz distribution and Phase 5 bundling. | ✓ |
| You decide | Claude picks the path derivation based on ES 8.18 standard layout. | |

**User's choice:** $ES_HOME/bin/elasticsearch

---

## Startup Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Single main.py + background thread | QApplication starts immediately, shows loading window, QThread boots ES and polls health. Window transitions to search UI when ES is ready. One Python process, clean Qt threading. | ✓ |
| Thin launch.py + splash, then main app | launch.py shows a splash, starts ES, waits for health, then opens the main PyQt window. Two-stage startup. | |
| You decide | Claude picks the startup architecture based on Qt best practices. | |

**User's choice:** Single main.py + background thread

---

| Option | Description | Selected |
|--------|-------------|----------|
| aboutToQuit signal + terminate/wait | Connect QApplication.aboutToQuit to a handler that calls process.terminate(), then process.wait(timeout=10). Falls back to kill() if ES doesn't stop. | ✓ |
| atexit handler | Register an atexit function that terminates ES. Simpler but misses cases where the app is force-killed. | |
| You decide | Claude picks the shutdown mechanism. | |

**User's choice:** aboutToQuit signal + terminate/wait (with kill() fallback)

---

| Option | Description | Selected |
|--------|-------------|----------|
| GET /_cluster/health, 2s interval, 60s timeout | Simple requests loop in QThread. Emits signal when status is green or yellow. Matches 60-second criterion in success criteria. | ✓ |
| GET /_cluster/health with exponential backoff | Start at 1s, double each retry up to 10s. More polite for slow hardware but harder to show accurate progress. | |
| You decide | Claude picks the health check polling strategy. | |

**User's choice:** GET /_cluster/health, 2s interval, 60s timeout

---

## Loading Screen Design

| Option | Description | Selected |
|--------|-------------|----------|
| Loading window with spinner + status text | Small window with NitroFind name, animated spinner, status line "Starting search engine...". Transitions to main window when ES is ready. | ✓ |
| Qt splash screen (QSplashScreen) | Borderless image overlay before main window. Simple but no status text or spinner. | |
| Main window + disabled search bar + spinner inline | Show full main window immediately but with search bar grayed out. User sees layout right away. | |

**User's choice:** Loading window with spinner + status text

---

| Option | Description | Selected |
|--------|-------------|----------|
| Simple single message | Just "Starting search engine..." throughout. Clean and honest. | ✓ |
| Step-by-step messages | "Launching Elasticsearch..." → "Waiting for node..." → "Ready!". More informative but requires tracking ES startup stages. | |
| You decide | Claude picks status messaging. | |

**User's choice:** Simple single message: "Starting search engine..."

---

| Option | Description | Selected |
|--------|-------------|----------|
| Replace spinner with error message + Retry button | Loading window shows "Failed to start search engine" with Retry and Quit buttons. Non-destructive, user can recover. | ✓ |
| Dialog popup over loading screen | Modal error dialog appears explaining the failure with options to retry or quit. | |
| You decide | Claude picks the error handling for startup failure. | |

**User's choice:** Replace spinner with error message + Retry button (inline in loading window)

---

## era_bucket Vocabulary

| Option | Description | Selected |
|--------|-------------|----------|
| Decade strings: "1920s", "1960s", "2020s" | Scraper derives from production_start year with simple math. Neutral, sortable. Filter sidebar shows decade labels. | ✓ |
| Named automotive eras | "Pre-war", "Golden Age", "Muscle Era", "Malaise Era", etc. More evocative but requires a mapping table and edge cases. | |
| Integer decade: 1920, 1960, 2020 | Sortable numerically; UI formats as display labels. Same simplicity as decade strings but stored as integer. | |

**User's choice:** Decade strings ("1920s", "1960s", "2020s")

---

| Option | Description | Selected |
|--------|-------------|----------|
| keyword | Exact-match filtering. Perfect for filter sidebar aggregations. | ✓ |
| text + keyword sub-field | Adds full-text search on era label. Unnecessary for exact-match filtering. | |

**User's choice:** keyword field type

---

| Option | Description | Selected |
|--------|-------------|----------|
| "Unknown" | Explicit null-like value. Filter sidebar can include or exclude it. Clear intent. | ✓ |
| null / omit the field | Don't store era_bucket if year is missing. Cleaner mapping but null-handling required. | |
| You decide | Claude picks the missing-value strategy. | |

**User's choice:** Store "Unknown" for missing production_start

---

## Claude's Discretion

No areas delegated to Claude — user selected explicit options for all questions.

## Deferred Ideas

None — discussion stayed within Phase 1 scope.
