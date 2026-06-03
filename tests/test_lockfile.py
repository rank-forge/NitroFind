"""
INFRA-01: Lockfile reproducibility tests.

Asserts that requirements.txt was generated with pip-compile --generate-hashes
and contains only pinned (==) versions — no loose specifiers.

Source: .planning/phases/01-infrastructure-schema-foundation/01-PLAN.md Task 3
Requirement: INFRA-01
"""

import pathlib
import re

import pytest


REQUIREMENTS_TXT = pathlib.Path(__file__).parent.parent / "requirements.txt"


def _read_requirements() -> list[str]:
    """Read all lines from requirements.txt.

    CR-04: guard against missing file — raises pytest.fail with an actionable
    message instead of the confusing FileNotFoundError that would otherwise bubble
    up from read_text() when requirements.txt has not yet been generated.
    """
    if not REQUIREMENTS_TXT.exists():
        pytest.fail(
            f"requirements.txt not found at {REQUIREMENTS_TXT}. "
            "Run: pip-compile --generate-hashes requirements.in"
        )
    return REQUIREMENTS_TXT.read_text(encoding="utf-8").splitlines()


def _is_continuation(line: str) -> bool:
    """Return True if the line is a hash-continuation line (starts with whitespace + --hash)."""
    return line.strip().startswith("--hash=")


def _is_comment(line: str) -> bool:
    """Return True if the line is a blank line or a comment."""
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def _is_via_comment(line: str) -> bool:
    """Return True if the line is a pip-compile '# via ...' annotation."""
    return line.strip().startswith("# via")


def _get_requirement_lines(lines: list[str]) -> list[str]:
    """
    Extract lines that are actual package specifiers (not comments, not hash lines,
    not pip-compile annotations, not blank lines).

    A requirement line is a line that starts with a package name (letter or digit)
    and is not a hash-continuation line.
    """
    result = []
    for line in lines:
        if _is_comment(line):
            continue
        if _is_continuation(line):
            continue
        # Skip lines starting with '--' (e.g., pip-compile headers like --generate-hashes)
        if line.strip().startswith("--"):
            continue
        # This should be a package specifier line like: packagename==1.2.3 \
        # Strip trailing backslash continuation
        specifier = line.strip().rstrip(" \\").strip()
        if specifier:
            result.append(specifier)
    return result


def test_no_loose_specifiers() -> None:
    """
    Every package specifier in requirements.txt must be pinned with ==.

    No bare package names, no >= or < specifiers, no wildcard versions.
    This ensures the lockfile is fully deterministic.

    INFRA-01 acceptance criterion: all transitive deps are pinned.
    """
    lines = _read_requirements()
    requirement_lines = _get_requirement_lines(lines)

    # Pattern: package_name==concrete_version (no wildcards, no ranges)
    # Allows extras like package[extra]==version
    pinned_pattern = re.compile(
        r"^[A-Za-z0-9_.\-]+(\[[A-Za-z0-9_,\-]+\])?==[0-9A-Za-z._+!-]+$"
    )

    loose_specifiers = []
    for line in requirement_lines:
        if not pinned_pattern.match(line):
            loose_specifiers.append(line)

    assert not loose_specifiers, (
        f"requirements.txt contains loose or non-pinned specifiers:\n"
        + "\n".join(f"  {line}" for line in loose_specifiers)
    )


def test_hashes_present() -> None:
    """
    requirements.txt must contain at least one --hash=sha256: line.

    This proves pip-compile --generate-hashes was used, enabling
    hash-verified installs for supply-chain security (T-01-02).

    INFRA-01 acceptance criterion: hashes present.
    """
    content = REQUIREMENTS_TXT.read_text(encoding="utf-8")
    assert "--hash=sha256:" in content, (
        "requirements.txt does not contain any --hash=sha256: lines. "
        "Regenerate with: pip-compile --generate-hashes requirements.in"
    )


def test_required_top_level_packages() -> None:
    """
    requirements.txt must contain pinned entries for all top-level dependencies
    declared in requirements.in:
      - elasticsearch
      - flask (added Phase 6; PyQt6 and qt-material removed)
      - requests

    Case-insensitive match on package name followed by ==.

    INFRA-01 acceptance criterion: all required top-level packages present.
    Phase 6 (CLEN-01): PyQt6 and qt-material removed; flask added.
    """
    content = REQUIREMENTS_TXT.read_text(encoding="utf-8").lower()

    required = [
        ("elasticsearch", "elasticsearch=="),
        ("flask", "flask=="),
        ("requests", "requests=="),
    ]

    missing = []
    for name, pattern in required:
        if pattern not in content:
            missing.append(name)

    assert not missing, (
        f"requirements.txt is missing pinned entries for: {', '.join(missing)}\n"
        "These are required top-level dependencies from requirements.in."
    )

    # Phase 6 (CLEN-01): Qt packages must not appear in the lockfile
    for qt_pkg in ("pyqt6==", "qt-material=="):
        assert qt_pkg not in content, (
            f"requirements.txt still contains Qt package '{qt_pkg}' — "
            "CLEN-01 requires all Qt dependencies removed in Phase 6."
        )
