"""
main.py — NitroFind Flask lifecycle entry point (v1.1).

Validates ES_HOME, injects NitroFind config, starts Elasticsearch as a
background daemon thread, then runs the Flask dev server on 127.0.0.1:PORT.
A try/finally block shuts down the ES subprocess on Ctrl+C (SRVR-04).

Security mitigations:
  T-06-01: host="127.0.0.1" — never 0.0.0.0 (WSL-only, no external access)
  T-06-02: debug=False, use_reloader=False — prevents duplicate ES JVM spawn
  T-06-03: PORT env var wrapped in try/except ValueError — exits 1 on bad value
  T-06-08: try/finally calls shutdown_es None-guarded — no orphaned ES JVM
"""

import logging
import os
import sys

from nitrofind.es_manager import inject_es_config, resolve_es_home, validate_es_home, shutdown_es
from nitrofind.server import app, start_es_background, state

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("nitrofind.main")


def main() -> None:
    """NitroFind Flask lifecycle entry point.

    Validates ES_HOME, injects ES config, starts the background ES health
    poller, then runs Flask on 127.0.0.1:PORT. A try/finally terminates the
    ES subprocess on KeyboardInterrupt or any unhandled exception.
    """
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    es_home_raw = resolve_es_home()

    # Resolve config source relative to main.py location (no frozen/PyInstaller branch)
    config_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

    if es_home_raw:
        try:
            inject_es_config(es_home_raw, config_src)
        except OSError as exc:
            logger.warning("inject_es_config failed: %s", exc)

    try:
        es_home = validate_es_home(es_home_raw)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)

    start_es_background(es_home)

    # T-06-03: reject non-integer PORT before binding
    try:
        port = int(os.environ.get("PORT", 5000))
    except ValueError:
        sys.stderr.write(
            f"Invalid PORT value: {os.environ.get('PORT')!r} — must be an integer.\n"
        )
        sys.exit(1)

    # D-06: Flask lifecycle with SIGINT-safe finally shutdown (T-06-08)
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    finally:
        if state["process"] is not None:
            shutdown_es(state["process"])


if __name__ == "__main__":
    main()
