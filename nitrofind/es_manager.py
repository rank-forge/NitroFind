"""
nitrofind.es_manager — Elasticsearch subprocess lifecycle utilities (Linux/WSL only).

Exports:
  resolve_es_home    — returns ES_HOME from environment variable
  inject_es_config   — writes elasticsearch.yml + jvm.options.d into ES dir
  validate_es_home   — validates ES_HOME path before exec (T-02-01, T-02-02)
  shutdown_es        — POSIX graceful ES shutdown helper (INFRA-03)
  _es_binary_path    — returns the ES binary path (Linux-only)

Requirement coverage:
  INFRA-03: shutdown_es terminates ES gracefully via SIGTERM;
            falls back to kill() after 10s timeout

Security mitigations:
  T-02-01 (path traversal): validate_es_home enforces isdir + isfile before exec
  T-02-02 (shell injection): Popen command is a list literal — no shell=True
"""

import os
import shutil
import subprocess

from elasticsearch import Elasticsearch


# ---------------------------------------------------------------------------
# Module-level constant — single source of truth for ES URL (WR-01)
# ---------------------------------------------------------------------------

ES_URL = "http://localhost:9200"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_es_home() -> str | None:
    """Return ES_HOME from environment variable (dev/WSL mode).

    Returns None if ES_HOME is unset; validate_es_home() will raise ValueError
    on None.
    """
    return os.environ.get("ES_HOME")


# ---------------------------------------------------------------------------
# Config injection
# ---------------------------------------------------------------------------

def inject_es_config(es_home: str, config_src_dir: str) -> None:
    """Copy NitroFind's elasticsearch.yml and jvm.options into the ES config dir.

    Idempotent: overwrites both files on every call, ensuring the NitroFind-controlled
    config is always in place before the ES subprocess is started.
    Calling this function twice produces identical results; the second call is safe.

    Writes:
      {es_home}/config/elasticsearch.yml    <- from {config_src_dir}/elasticsearch.yml
      {es_home}/config/jvm.options.d/nitrofind.options  <- from {config_src_dir}/jvm.options

    Creates jvm.options.d/ via os.makedirs(..., exist_ok=True) if it does not exist.

    # Source: elastic.co/guide/en/elasticsearch/reference/8.19/advanced-configuration.html
    #         (jvm.options.d/ file semantics and ES_JAVA_OPTS caveat)
    """
    es_config = os.path.join(es_home, "config")

    # Create config/ and jvm.options.d/ before any writes (CR-02: makedirs must
    # precede shutil.copy so config/ is created even when es_home is bare).
    jvm_dir = os.path.join(es_config, "jvm.options.d")
    os.makedirs(jvm_dir, exist_ok=True)

    # Write elasticsearch.yml (xpack.security.* = false — PKG-01 Pitfall 3 mitigation)
    shutil.copy(
        os.path.join(config_src_dir, "elasticsearch.yml"),
        os.path.join(es_config, "elasticsearch.yml"),
    )

    # Write jvm.options.d/nitrofind.options (heap + perf tuning)
    shutil.copy(
        os.path.join(config_src_dir, "jvm.options"),
        os.path.join(jvm_dir, "nitrofind.options"),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _es_binary_path(es_home: str) -> str:
    """Return the ES binary path (Linux/WSL only)."""
    return os.path.join(es_home, "bin", "elasticsearch")


def validate_es_home(es_home: str | None) -> str:
    """Validate that es_home is a real directory containing an ES binary.

    Raises ValueError with descriptive messages on failure.
    Returns es_home unchanged on success.

    Security: T-02-01 — prevents arbitrary binary execution via malicious ES_HOME.
    """
    if not es_home:
        raise ValueError(
            "ES_HOME is not set. Set it to your Elasticsearch 8.18 directory."
        )
    if not os.path.isdir(es_home):
        raise ValueError(f"ES_HOME is not a directory: {es_home}")

    es_bin = _es_binary_path(es_home)
    if not os.path.isfile(es_bin):
        raise ValueError(f"Elasticsearch binary not found at: {es_bin}")

    return es_home


# ---------------------------------------------------------------------------
# Shutdown helper (INFRA-03)
# ---------------------------------------------------------------------------

def shutdown_es(process: subprocess.Popen) -> None:
    """Gracefully terminate the Elasticsearch subprocess (POSIX only).

    Sends SIGTERM via process.terminate(), then waits up to 10 seconds.
    Falls back to process.kill() if ES does not exit within that window.

    Idempotent: returns immediately if process has already exited.
    """
    if process.poll() is not None:
        return  # already exited

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
