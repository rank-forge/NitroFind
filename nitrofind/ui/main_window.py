"""
StubMainWindow — placeholder main window for Phase 1.

Phase 4 replaces this entirely with the full search UI (search bar, result
list, filter panel, detail pane). For now it simply confirms that Elasticsearch
started successfully by showing a centered "Search engine ready." label.

The window title uses an em-dash (—) not a hyphen, per UI-SPEC typography.
"""

from PyQt6.QtWidgets import QMainWindow, QLabel
from PyQt6.QtCore import Qt


class StubMainWindow(QMainWindow):
    """Placeholder main window shown after ES is healthy. Phase 4 replaces this."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NitroFind — Ready")
        self.setMinimumSize(800, 600)
        label = QLabel("Search engine ready.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)
