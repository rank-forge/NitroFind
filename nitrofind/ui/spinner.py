"""
SpinnerWidget — animated arc spinner using QPainter and QTimer.

UI-SPEC Pattern 5: 48x48 custom QWidget with 120-degree teal arc rotating
at 30 degrees per 100 ms tick (12 frames per revolution = 1200 ms/rotation).

Anti-pattern guard: do NOT use QProgressBar in indeterminate mode.
QProgressBar animation is visually inconsistent across platforms; this custom
QWidget gives pixel-accurate control as specified in UI-SPEC.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QPen, QColor


class SpinnerWidget(QWidget):
    """
    Animated arc spinner widget.

    - Fixed size: 48 x 48 px
    - Transparent background (WA_TranslucentBackground)
    - Accent color: #26a69a (teal from qt-material dark_teal.xml)
    - Arc span: 120 degrees (one-third of circle)
    - Rotation: 30 degrees per 100 ms tick (1200 ms per full revolution)
    - Timer is parented to self so it is automatically destroyed with the widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(100)

    def _rotate(self):
        """Advance rotation by 30 degrees per tick."""
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        """Draw the arc at the current rotation angle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#26a69a"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        margin = 4
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        # Qt's drawArc expects angles in 1/16th-degree units.
        # start angle = _angle * 16; span = 120 * 16 (120-degree arc).
        painter.drawArc(rect, self._angle * 16, 120 * 16)
