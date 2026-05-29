"""
Unit tests for nitrofind.es_manager.inject_es_config — PKG-01 coverage.

Test strategy:
  - Use tmp_path to build a fake ES home directory with config/ subdirectory
  - Create fake source config files (elasticsearch.yml, jvm.options) using write_text()
  - Call inject_es_config() and assert files were written to expected destinations
  - No live ES or subprocess required

Requirement coverage:
  PKG-01: inject_es_config writes elasticsearch.yml to {es_home}/config/elasticsearch.yml
  PKG-01: inject_es_config writes jvm.options to {es_home}/config/jvm.options.d/nitrofind.options
  PKG-01: inject_es_config creates jvm.options.d/ if it does not exist
  PKG-01: inject_es_config is idempotent (second call overwrites first, no exception)
"""

import pytest

from nitrofind.es_manager import inject_es_config


# ---------------------------------------------------------------------------
# File write tests
# ---------------------------------------------------------------------------

def test_writes_elasticsearch_yml(tmp_path):
    """inject_es_config writes elasticsearch.yml to {es_home}/config/elasticsearch.yml."""
    es_home = tmp_path / "elasticsearch-8.18.0"
    (es_home / "config").mkdir(parents=True)
    config_src = tmp_path / "config_src"
    config_src.mkdir()

    yml_content = "network.host: 127.0.0.1\nxpack.security.enabled: false\n"
    (config_src / "elasticsearch.yml").write_text(yml_content)
    (config_src / "jvm.options").write_text("-Xms512m\n-Xmx512m\n")

    inject_es_config(str(es_home), str(config_src))

    dst = es_home / "config" / "elasticsearch.yml"
    assert dst.exists(), "elasticsearch.yml was not written to es_home/config/"
    assert dst.read_text() == yml_content


def test_writes_jvm_options_to_options_d(tmp_path):
    """inject_es_config writes jvm.options to {es_home}/config/jvm.options.d/nitrofind.options."""
    es_home = tmp_path / "elasticsearch-8.18.0"
    (es_home / "config").mkdir(parents=True)
    config_src = tmp_path / "config_src"
    config_src.mkdir()

    jvm_content = "-Xms512m\n-Xmx512m\n"
    (config_src / "elasticsearch.yml").write_text("network.host: 127.0.0.1\n")
    (config_src / "jvm.options").write_text(jvm_content)

    inject_es_config(str(es_home), str(config_src))

    dst = es_home / "config" / "jvm.options.d" / "nitrofind.options"
    assert dst.exists(), "nitrofind.options was not written to jvm.options.d/"
    assert dst.read_text() == jvm_content


def test_creates_jvm_options_d_if_missing(tmp_path):
    """inject_es_config creates jvm.options.d/ if it does not already exist."""
    es_home = tmp_path / "elasticsearch-8.18.0"
    (es_home / "config").mkdir(parents=True)
    # Deliberately do NOT pre-create jvm.options.d/
    config_src = tmp_path / "config_src"
    config_src.mkdir()

    (config_src / "elasticsearch.yml").write_text("network.host: 127.0.0.1\n")
    (config_src / "jvm.options").write_text("-Xms512m\n")

    inject_es_config(str(es_home), str(config_src))

    jvm_dir = es_home / "config" / "jvm.options.d"
    assert jvm_dir.is_dir(), "jvm.options.d/ directory was not created"


def test_idempotent(tmp_path):
    """inject_es_config called twice overwrites files without raising an exception."""
    es_home = tmp_path / "elasticsearch-8.18.0"
    (es_home / "config").mkdir(parents=True)
    config_src = tmp_path / "config_src"
    config_src.mkdir()

    yml_content = "network.host: 127.0.0.1\n"
    jvm_content = "-Xms512m\n"
    (config_src / "elasticsearch.yml").write_text(yml_content)
    (config_src / "jvm.options").write_text(jvm_content)

    # First call
    inject_es_config(str(es_home), str(config_src))

    # Second call — must not raise and final contents must equal source
    inject_es_config(str(es_home), str(config_src))

    yml_dst = es_home / "config" / "elasticsearch.yml"
    jvm_dst = es_home / "config" / "jvm.options.d" / "nitrofind.options"
    assert yml_dst.read_text() == yml_content
    assert jvm_dst.read_text() == jvm_content
