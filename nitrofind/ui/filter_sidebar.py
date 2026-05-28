"""
nitrofind.ui.filter_sidebar — Filter sidebar with three single-select QCheckBox groups.

Exports:
  MANUFACTURERS  — ordered tuple of 10 manufacturer values (UI-SPEC Component 5)
  ERAS           — ordered tuple of 8 era bucket values (UI-SPEC Component 5)
  BODY_STYLES    — ordered tuple of 8 body style values (UI-SPEC Component 5)
  FilterSidebar  — QWidget with three filter groups and collect_filters() method

Requirement coverage:
  SRCH-04: Filter sidebar narrows results by manufacturer, era_bucket, body_style
           without clearing the query. Checkbox state is preserved across new
           searches; collect_filters() is called on every _execute_search() call
           so active filters apply to every query.

Design decisions (UI-SPEC Component 5, RESEARCH.md A1 + A3):
  A1 — Single-select per dimension: only one manufacturer, one era, and one body
       style can be active at a time. This matches the build_filter_clauses()
       signature (one string per arg, not a list).
  A3 — Hardcoded values for v1: the filter options are module-level constants.
       Dynamic ES aggregation-based values are deferred to v2.

Single-select implementation idiom:
  QButtonGroup(self) with setExclusive(False) + manual uncheck-siblings via
  stateChanged signal. This idiom is chosen over setExclusive(True) alone
  because QButtonGroup.setExclusive(True) prevents a user from unchecking the
  currently checked box (clicks are silently ignored when exclusive and only one
  button is checked). The manual approach allows zero-selection (no filter on
  that dimension) while still enforcing at-most-one-checked per group.
  See: test_uncheck_returns_to_empty and test_single_select_per_manufacturer_group.

Threat model (T-04-05):
  Filter values passed to build_filter_clauses come exclusively from the
  module-level constant tuples (MANUFACTURERS, ERAS, BODY_STYLES) — never
  from raw user input. The values go into ES term query values (not DSL keys),
  so injection is structurally impossible at this boundary.

Anti-patterns avoided:
  Qt5-style short-form enums (Qt.AlignLeft, Qt.Horizontal) — all enums use
  fully-qualified Qt6 form (Qt.AlignmentFlag.AlignLeft, etc.)
  logger.debug(f"...") — all logger calls use % formatting per CLAUDE.md
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from nitrofind.search.query_builder import build_filter_clauses

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level hardcoded filter values (UI-SPEC Component 5, Assumption A3)
# ---------------------------------------------------------------------------

MANUFACTURERS: tuple[str, ...] = (
    "Ferrari",
    "Porsche",
    "BMW",
    "Ford",
    "Chevrolet",
    "Toyota",
    "Honda",
    "Lamborghini",
    "McLaren",
    "Aston Martin",
)

ERAS: tuple[str, ...] = (
    "1950s",
    "1960s",
    "1970s",
    "1980s",
    "1990s",
    "2000s",
    "2010s",
    "2020s",
)

BODY_STYLES: tuple[str, ...] = (
    "Coupe",
    "Sedan",
    "Convertible",
    "SUV",
    "Hatchback",
    "Wagon",
    "Pickup",
    "Van",
)


# ---------------------------------------------------------------------------
# FilterSidebar
# ---------------------------------------------------------------------------

class FilterSidebar(QWidget):
    """QWidget filter sidebar with three single-select checkbox groups.

    Groups:
      Manufacturer: 10 hardcoded values from MANUFACTURERS
      Era:          8 hardcoded era buckets from ERAS
      Body Style:   8 hardcoded body styles from BODY_STYLES

    Selection model:
      At most one checkbox per group may be checked at any time
      (single-select, Assumption A1). Checking a new box in a group
      unchecks the previously checked box in the same group via
      stateChanged signal. Unchecking the active box yields None for
      that dimension (zero-selection allowed).

    collect_filters() translates the current checkbox state to the
    build_filter_clauses() output for the active selections.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.setLayout(layout)

        # Build three filter groups
        self._manufacturer_checks: dict[str, QCheckBox] = {}
        self._era_checks: dict[str, QCheckBox] = {}
        self._body_style_checks: dict[str, QCheckBox] = {}

        self._build_group(
            layout,
            header="Manufacturer",
            values=MANUFACTURERS,
            checks_dict=self._manufacturer_checks,
        )
        self._build_group(
            layout,
            header="Era",
            values=ERAS,
            checks_dict=self._era_checks,
        )
        self._build_group(
            layout,
            header="Body Style",
            values=BODY_STYLES,
            checks_dict=self._body_style_checks,
        )

        logger.debug("FilterSidebar constructed with %d manufacturer, %d era, %d body-style checks",
                     len(self._manufacturer_checks),
                     len(self._era_checks),
                     len(self._body_style_checks))

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _build_group(
        self,
        layout: QVBoxLayout,
        header: str,
        values: tuple[str, ...],
        checks_dict: dict[str, QCheckBox],
    ) -> None:
        """Add a labelled group of QCheckBox widgets to the layout.

        Single-select is enforced via a QButtonGroup with setExclusive(False)
        plus a manual _uncheck_siblings handler wired to each box's stateChanged
        signal. This allows zero-selection (the user can uncheck the active box)
        while still ensuring at most one box is checked per group.

        Args:
            layout:      Parent QVBoxLayout to add widgets to.
            header:      Group label string ("Manufacturer", "Era", "Body Style").
            values:      Ordered tuple of option strings.
            checks_dict: Empty dict to populate with {value: QCheckBox} entries.
        """
        # Group header label
        label = QLabel(header)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label)

        # QButtonGroup with setExclusive(False) — mutual exclusion is handled
        # manually via stateChanged to allow zero-selection.
        btn_group = QButtonGroup(self)
        btn_group.setExclusive(False)

        for value in values:
            cb = QCheckBox(value)
            btn_group.addButton(cb)
            checks_dict[value] = cb
            layout.addWidget(cb)

        # Wire single-select: when any box in this group is checked, uncheck all
        # others in the same group. Uses a default-arg capture to bind checks_dict.
        def _uncheck_siblings(state: int, source_dict: dict = checks_dict) -> None:
            """Uncheck all other boxes when one is checked (single-select per group)."""
            if state == Qt.CheckState.Checked.value:
                # Find the sender (the checkbox that just changed)
                sender = self.sender()
                for key, cb in source_dict.items():
                    if cb is not sender and cb.isChecked():
                        # Block signals temporarily to avoid re-entrant calls
                        cb.blockSignals(True)
                        cb.setChecked(False)
                        cb.blockSignals(False)

        for cb in checks_dict.values():
            cb.stateChanged.connect(_uncheck_siblings)

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def collect_filters(self) -> list[dict]:
        """Translate current checkbox state to build_filter_clauses() output.

        Finds the single checked value in each group (or None if none is
        checked) and delegates to build_filter_clauses().

        Returns:
            List of ES term filter dicts. Empty list when no checkbox is
            checked (no filters applied).
        """
        manufacturer = next(
            (k for k, cb in self._manufacturer_checks.items() if cb.isChecked()), None
        )
        era_bucket = next(
            (k for k, cb in self._era_checks.items() if cb.isChecked()), None
        )
        body_style = next(
            (k for k, cb in self._body_style_checks.items() if cb.isChecked()), None
        )
        return build_filter_clauses(
            manufacturer=manufacturer,
            era_bucket=era_bucket,
            body_style=body_style,
        )

    # ---------------------------------------------------------------------------
    # Read-only property accessors (for test introspection — mirrors LoadingWindow
    # accessor convention from loading_window.py)
    # ---------------------------------------------------------------------------

    @property
    def manufacturer_checks(self) -> dict[str, QCheckBox]:
        """Read-only accessor: {manufacturer_name: QCheckBox} dict."""
        return self._manufacturer_checks

    @property
    def era_checks(self) -> dict[str, QCheckBox]:
        """Read-only accessor: {era_name: QCheckBox} dict."""
        return self._era_checks

    @property
    def body_style_checks(self) -> dict[str, QCheckBox]:
        """Read-only accessor: {body_style_name: QCheckBox} dict."""
        return self._body_style_checks
