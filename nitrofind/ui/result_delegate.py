"""
nitrofind.ui.result_delegate — QStyledItemDelegate for result list rows.

Exports:
  _ROW_PADDING      — QMargins(8, 8, 8, 8) per UI-SPEC Component 3 (8-point grid)
  _result_to_html   — Free function: ArticleResult → three-line HTML fragment
  ResultDelegate    — QStyledItemDelegate subclass rendering HTML via QTextDocument

Requirement coverage:
  SRCH-02: Result rows display title, source domain, and highlighted excerpt.
  UIPL-01: Query terms highlighted in result excerpts using <b> tags from ES.

Pitfall 3 contract:
  _make_doc MUST be called with identical arguments from BOTH paint() and
  sizeHint(). If the two calls diverge (different textWidth or margin), list
  items will be truncated or show excessive blank space. See 04-RESEARCH.md
  Pitfall 3.

Threat model (T-04-04):
  HTML fragments from _result_to_html are rendered exclusively by Qt Rich Text
  via QTextDocument inside QStyledItemDelegate. No QtWebEngine is involved.
  Qt Rich Text supports a controlled HTML subset (no <script>, no event
  handlers), so XSS from article content is mitigated at the rendering layer.

Data role contract (written by MainWindow in Plan 03):
  Qt.ItemDataRole.UserRole      → HTML string (rendered by paint/sizeHint)
  Qt.ItemDataRole.UserRole + 1  → ArticleResult object (for detail pane on
                                  selection)

Anti-patterns avoided:
  Qt5-style short-form enums (Qt.AlignLeft, Qt.Horizontal) — all enums use
  fully-qualified Qt6 form (Qt.ItemDataRole.UserRole, etc.)
  logger.debug(f"...") — all logger calls use % formatting per CLAUDE.md
"""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QMargins, QSize, Qt
from PyQt6.QtGui import QTextDocument, QTextOption
from PyQt6.QtWidgets import QStyledItemDelegate

if TYPE_CHECKING:
    from nitrofind.search.models import ArticleResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

# UI-SPEC Component 3: 8px padding on all sides (8-point grid)
_ROW_PADDING = QMargins(8, 8, 8, 8)


# ---------------------------------------------------------------------------
# Module-level free function
# ---------------------------------------------------------------------------

def _result_to_html(result: "ArticleResult") -> str:
    """Build the three-line HTML fragment for a single result row.

    Prefers ES highlight_title[0] over plain title when available (UIPL-01).
    Prefers ES highlight_body[0] over plain excerpt when available (UIPL-01).
    Falls back to plain title/excerpt when highlight lists are empty or None.

    Args:
        result: ArticleResult with title, source_domain, excerpt, highlight_title,
                and highlight_body fields.

    Returns:
        HTML string with three lines:
          1. Bold title (11pt) — plain or ES-highlighted
          2. Source domain in muted teal (#80cbc4, 9pt)
          3. Excerpt/highlight body (9pt, may contain <b> tags)
    """
    # Use highlight_title[0] if truthy (non-None and non-empty), else plain title
    highlight_title = result.highlight_title
    if highlight_title:
        title = highlight_title[0]
    else:
        title = result.title

    # Use highlight_body[0] if truthy (non-None and non-empty), else plain excerpt
    highlight_body = result.highlight_body
    if highlight_body:
        excerpt = highlight_body[0]
    else:
        excerpt = result.excerpt

    # WR-01: source_domain is a plain-text scraped value (never ES-highlighted)
    # and must be HTML-escaped. title/excerpt may contain intentional <b> tags
    # from ES highlighter and must NOT be escaped.
    return (
        f"<b style='font-size:11pt'>{title}</b>"
        f"<br><span style='color:#80cbc4;font-size:9pt'>{html.escape(result.source_domain)}</span>"
        f"<br><span style='font-size:9pt'>{excerpt}</span>"
    )


# ---------------------------------------------------------------------------
# ResultDelegate
# ---------------------------------------------------------------------------

class ResultDelegate(QStyledItemDelegate):
    """QStyledItemDelegate that renders result rows as multi-line HTML.

    Each row is a three-line HTML fragment built by _result_to_html:
      Line 1: Bold article title (11pt), optionally ES-highlighted
      Line 2: Source domain in muted teal (#80cbc4, 9pt)
      Line 3: Excerpt or ES-highlighted body fragment (9pt)

    The delegate reads the pre-built HTML string from Qt.ItemDataRole.UserRole
    on each QListWidgetItem. MainWindow (Plan 03) is responsible for setting
    that role when populating the list.

    Pitfall 3 compliance:
      _make_doc is the single code path that constructs and configures a
      QTextDocument. Both paint() and sizeHint() call it with the same html
      and width, ensuring height measurements are consistent.
    """

    def _make_doc(self, html: str, width: int) -> QTextDocument:
        """Create and configure a QTextDocument for the given HTML and width.

        Both paint() and sizeHint() MUST call this method with identical
        arguments to avoid height mismatch (Pitfall 3).

        Args:
            html:  HTML string to render (pre-built by _result_to_html).
            width: Available rendering width in pixels (after margin removal).

        Returns:
            Fully configured QTextDocument ready for drawContents() or size().
        """
        toption = QTextOption()
        toption.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        doc = QTextDocument()
        doc.setHtml(html)
        doc.setTextWidth(width)
        doc.setDefaultTextOption(toption)
        doc.setDocumentMargin(0)
        return doc

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        """Render the HTML fragment for the given index at the given rect.

        Saves/restores QPainter state around the translate+drawContents call
        so sibling rows are not affected by this row's coordinate transform.

        Args:
            painter: Active QPainter for the view.
            option:  Style option containing the item rect.
            index:   Model index; UserRole carries the HTML string.
        """
        painter.save()
        html = index.data(Qt.ItemDataRole.UserRole)
        if not html:
            painter.restore()
            return

        rect = option.rect.marginsRemoved(_ROW_PADDING)
        doc = self._make_doc(html, rect.width())
        painter.translate(rect.topLeft())
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:  # type: ignore[override]
        """Return the required size for the given index.

        Uses _make_doc with the same html/width as paint() so the returned
        height matches what paint() actually renders (Pitfall 3).

        Args:
            option: Style option containing the item rect width.
            index:  Model index; UserRole carries the HTML string.

        Returns:
            QSize with width from option.rect and height from QTextDocument.size().
        """
        html = index.data(Qt.ItemDataRole.UserRole)
        if not html:
            return QSize(option.rect.width(), 40)  # fallback minimum height

        rect = option.rect.marginsRemoved(_ROW_PADDING)
        doc = self._make_doc(html, rect.width())
        rect.setHeight(int(doc.size().height()))
        return rect.marginsAdded(_ROW_PADDING).size()
