"""
scripts/setup_es.py — NitroFind Elasticsearch configuration installer.

Copies config/elasticsearch.yml and config/jvm.options from the project repo
into the user's Elasticsearch 8.18 installation directory ($ES_HOME).

Usage:
    ES_HOME=/path/to/elasticsearch-8.18.0 python scripts/setup_es.py

Security: Validates ES_HOME is a real directory and that the ES binary exists
before performing any file copies (Security Domain V5 — path traversal mitigation,
T-01-01 in threat model).
"""

import os
import shutil
import sys


def main() -> None:
    # D-01: Locate ES via ES_HOME environment variable
    # D-02: Exit with clear error message if ES_HOME is not set
    es_home = os.environ.get("ES_HOME")
    if not es_home:
        print("ES_HOME is not set. Set it to your Elasticsearch 8.18 directory.")
        sys.exit(1)

    # Security Domain V5 / T-01-01: validate ES_HOME is a real directory
    # Prevents path traversal via ES_HOME=../../etc or other malicious values
    if not os.path.isdir(es_home):
        print(f"ES_HOME is not a valid directory: {es_home}")
        sys.exit(1)

    # Security Domain V5 / T-01-01: confirm the ES binary exists before writing
    # Prevents arbitrary binary path injection
    es_bin = os.path.join(es_home, "bin", "elasticsearch")
    if not os.path.isfile(es_bin):
        print(
            f"Elasticsearch binary not found at: {es_bin}\n"
            "Ensure ES_HOME points to a valid Elasticsearch 8.18 installation."
        )
        sys.exit(1)

    # Resolve config source directory relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_src = os.path.join(script_dir, "..", "config")

    es_config_dir = os.path.join(es_home, "config")

    # Copy elasticsearch.yml → $ES_HOME/config/elasticsearch.yml
    src_yml = os.path.join(config_src, "elasticsearch.yml")
    dst_yml = os.path.join(es_config_dir, "elasticsearch.yml")
    shutil.copy(src_yml, dst_yml)
    print(f"Copied elasticsearch.yml → {dst_yml}")

    # Create $ES_HOME/config/jvm.options.d/ if it doesn't exist
    jvm_options_dir = os.path.join(es_config_dir, "jvm.options.d")
    os.makedirs(jvm_options_dir, exist_ok=True)

    # Copy config/jvm.options → $ES_HOME/config/jvm.options.d/nitrofind.options
    src_jvm = os.path.join(config_src, "jvm.options")
    dst_jvm = os.path.join(jvm_options_dir, "nitrofind.options")
    shutil.copy(src_jvm, dst_jvm)
    print(f"Copied jvm.options → {dst_jvm}")

    print("ES configuration installed successfully.")


if __name__ == "__main__":
    main()
