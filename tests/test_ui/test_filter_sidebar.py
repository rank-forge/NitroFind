"""
tests/test_ui/test_filter_sidebar.py — Unit tests for FilterSidebar.

Requirement coverage:
  SRCH-04: Filter sidebar narrows results by manufacturer/era/body_style without
           clearing the query.

Tests:
  - FilterSidebar construction: three labelled groups (Manufacturer, Era, Body Style)
  - manufacturer_checks dict contains exactly the 10 expected keys
  - era_checks dict contains exactly the 8 expected keys
  - body_style_checks dict contains exactly the 8 expected keys
  - collect_filters() returns [] when no checkbox is checked
  - collect_filters() returns correct term clause when Ferrari is checked
  - Checking a second manufacturer unchecks the first (single-select enforcement)
  - collect_filters() matches build_filter_clauses() output for combined state
  - After checking and unchecking Ferrari, collect_filters() returns []

Uses pytest-qt's qtbot fixture for widget lifecycle management.
"""

import pytest

try:
    import PyQt6  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PYQT6_AVAILABLE,
    reason="PyQt6 not installed",
)

# Expected hardcoded values (from UI-SPEC Component 5)
EXPECTED_MANUFACTURERS = {
    "Ferrari", "Porsche", "BMW", "Ford", "Chevrolet",
    "Toyota", "Honda", "Lamborghini", "McLaren", "Aston Martin",
}
EXPECTED_ERAS = {
    "1950s", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s",
}
EXPECTED_BODY_STYLES = {
    "Coupe", "Sedan", "Convertible", "SUV", "Hatchback", "Wagon", "Pickup", "Van",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_three_labelled_groups_exist(qtbot):
    """Test 1: FilterSidebar has three labelled groups: Manufacturer, Era, Body Style."""
    from PyQt6.QtWidgets import QLabel
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    # Find all QLabel descendants
    labels = sidebar.findChildren(QLabel)
    label_texts = {lbl.text() for lbl in labels}

    assert "Manufacturer" in label_texts, (
        f"Expected 'Manufacturer' group label; found labels: {label_texts}"
    )
    assert "Era" in label_texts, (
        f"Expected 'Era' group label; found labels: {label_texts}"
    )
    assert "Body Style" in label_texts, (
        f"Expected 'Body Style' group label; found labels: {label_texts}"
    )


def test_manufacturer_checks_has_exactly_10_keys(qtbot):
    """Test 2: manufacturer_checks contains exactly the 10 expected manufacturer keys."""
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    assert set(sidebar.manufacturer_checks.keys()) == EXPECTED_MANUFACTURERS, (
        f"manufacturer_checks keys mismatch.\n"
        f"  Expected: {sorted(EXPECTED_MANUFACTURERS)}\n"
        f"  Got:      {sorted(sidebar.manufacturer_checks.keys())}"
    )


def test_era_checks_has_exactly_8_keys(qtbot):
    """Test 3: era_checks contains exactly the 8 expected era keys."""
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    assert set(sidebar.era_checks.keys()) == EXPECTED_ERAS, (
        f"era_checks keys mismatch.\n"
        f"  Expected: {sorted(EXPECTED_ERAS)}\n"
        f"  Got:      {sorted(sidebar.era_checks.keys())}"
    )


def test_body_style_checks_has_exactly_8_keys(qtbot):
    """Test 4: body_style_checks contains exactly the 8 expected body style keys."""
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    assert set(sidebar.body_style_checks.keys()) == EXPECTED_BODY_STYLES, (
        f"body_style_checks keys mismatch.\n"
        f"  Expected: {sorted(EXPECTED_BODY_STYLES)}\n"
        f"  Got:      {sorted(sidebar.body_style_checks.keys())}"
    )


def test_collect_filters_returns_empty_when_nothing_checked(qtbot):
    """Test 5: collect_filters() returns [] when no checkbox is checked."""
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    result = sidebar.collect_filters()
    assert result == [], (
        f"collect_filters() must return [] when no boxes are checked; got {result!r}"
    )


def test_collect_filters_returns_manufacturer_clause_when_ferrari_checked(qtbot):
    """Test 6: collect_filters() returns correct term clause when Ferrari is checked."""
    from nitrofind.search.query_builder import build_filter_clauses
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    sidebar.manufacturer_checks["Ferrari"].setChecked(True)

    result = sidebar.collect_filters()
    expected = build_filter_clauses(manufacturer="Ferrari")

    assert result == expected, (
        f"collect_filters() with Ferrari checked must equal build_filter_clauses(manufacturer='Ferrari').\n"
        f"  Expected: {expected!r}\n"
        f"  Got:      {result!r}"
    )


def test_single_select_per_manufacturer_group(qtbot):
    """Test 7: Checking a second manufacturer automatically unchecks the first."""
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    # Check Ferrari first
    sidebar.manufacturer_checks["Ferrari"].setChecked(True)
    assert sidebar.manufacturer_checks["Ferrari"].isChecked(), (
        "Ferrari should be checked after setChecked(True)"
    )

    # Now check Porsche — Ferrari must become unchecked
    sidebar.manufacturer_checks["Porsche"].setChecked(True)

    assert sidebar.manufacturer_checks["Porsche"].isChecked(), (
        "Porsche should be checked after setChecked(True)"
    )
    assert not sidebar.manufacturer_checks["Ferrari"].isChecked(), (
        "Ferrari must be unchecked when Porsche is selected (single-select enforcement)"
    )


def test_collect_filters_matches_build_filter_clauses(qtbot):
    """Test 8: collect_filters() == build_filter_clauses() for combined manufacturer + era state."""
    from nitrofind.search.query_builder import build_filter_clauses
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    sidebar.manufacturer_checks["Ferrari"].setChecked(True)
    sidebar.era_checks["1980s"].setChecked(True)

    result = sidebar.collect_filters()
    expected = build_filter_clauses(manufacturer="Ferrari", era_bucket="1980s")

    assert result == expected, (
        f"collect_filters() must equal build_filter_clauses(manufacturer='Ferrari', era_bucket='1980s').\n"
        f"  Expected: {expected!r}\n"
        f"  Got:      {result!r}"
    )


def test_uncheck_returns_to_empty(qtbot):
    """Test 9: After checking then unchecking Ferrari, collect_filters() returns []."""
    from nitrofind.ui.filter_sidebar import FilterSidebar

    sidebar = FilterSidebar()
    qtbot.addWidget(sidebar)

    # Check Ferrari
    sidebar.manufacturer_checks["Ferrari"].setChecked(True)
    assert sidebar.collect_filters() != [], (
        "collect_filters() should not be empty after checking Ferrari"
    )

    # Uncheck Ferrari — group allows zero selection
    sidebar.manufacturer_checks["Ferrari"].setChecked(False)

    result = sidebar.collect_filters()
    assert result == [], (
        f"collect_filters() must return [] after unchecking the only checked box; got {result!r}"
    )
