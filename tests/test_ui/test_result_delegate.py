"""
tests/test_ui/test_result_delegate.py — Unit tests for ResultDelegate and _result_to_html.

Requirement coverage:
  SRCH-02: Result rows show title, domain, and highlighted excerpt via HTML delegate.
  UIPL-01: Query terms highlighted in result excerpts using <b> tags from ES.

Tests:
  - _result_to_html returns correct title, domain, and excerpt HTML
  - _result_to_html uses highlight_title[0] / highlight_body[0] when present (UIPL-01)
  - _result_to_html falls back to title/excerpt when highlights are empty or None
  - _ROW_PADDING == QMargins(8, 8, 8, 8) (UI-SPEC 8-point grid)
  - ResultDelegate._make_doc returns QTextDocument with documentMargin == 0
  - ResultDelegate.sizeHint returns positive height for non-empty HTML

Uses pytest-qt's qtbot fixture for widget lifecycle management.
Pure-function tests (_result_to_html) do NOT require qtbot.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article_result(**kwargs):
    """Build an ArticleResult with required fields, overridable via kwargs."""
    from nitrofind.search.models import ArticleResult
    defaults = {
        "title": "Ferrari 308",
        "url": "https://en.wikipedia.org/wiki/Ferrari_308",
        "source_domain": "wikipedia.org",
        "score": 1.0,
    }
    defaults.update(kwargs)
    return ArticleResult(**defaults)


# ---------------------------------------------------------------------------
# Tests: _result_to_html (pure-function, no qtbot needed)
# ---------------------------------------------------------------------------

def test_result_to_html_contains_title_domain_and_color():
    """Test 1: _result_to_html returns title, domain, and #80cbc4 color (SRCH-02)."""
    from nitrofind.ui.result_delegate import _result_to_html

    result = _make_article_result(
        title="Ferrari 308",
        source_domain="wikipedia.org",
    )
    html = _result_to_html(result)

    assert "Ferrari 308" in html, "HTML must contain the article title"
    assert "wikipedia.org" in html, "HTML must contain the source domain"
    assert "#80cbc4" in html, "HTML must contain the muted teal domain color"


def test_result_to_html_uses_highlight_title_and_body_when_present():
    """Test 2: _result_to_html uses highlight_title[0] and highlight_body[0] when present (UIPL-01)."""
    from nitrofind.ui.result_delegate import _result_to_html

    result = _make_article_result(
        title="Ferrari 308",
        highlight_title=["<b>Ferrari</b> 308"],
        highlight_body=["The <b>Ferrari</b> 308 GTB was produced from 1975."],
        excerpt="The Ferrari 308 GTB was produced from 1975.",
    )
    html = _result_to_html(result)

    assert "<b>Ferrari</b> 308" in html, "HTML must use highlight_title[0] when present"
    assert "<b>Ferrari</b> 308 GTB" in html, "HTML must use highlight_body[0] when present"
    # Confirm the plain title is NOT used when highlight is available
    # (the highlight already contains "Ferrari 308" so we check the bold tag is present)
    assert "<b>Ferrari</b>" in html, "highlight tags must be preserved"


def test_result_to_html_falls_back_to_plain_when_highlights_empty():
    """Test 3: _result_to_html falls back to title and excerpt when highlights are empty lists."""
    from nitrofind.ui.result_delegate import _result_to_html

    result = _make_article_result(
        title="Lamborghini Countach",
        source_domain="en.wikipedia.org",
        excerpt="Italian supercar produced 1974–1990.",
        highlight_title=[],
        highlight_body=[],
    )
    html = _result_to_html(result)

    assert "Lamborghini Countach" in html, "Must fall back to plain title when highlight_title is empty"
    assert "Italian supercar produced 1974–1990." in html, (
        "Must fall back to excerpt when highlight_body is empty"
    )


def test_result_to_html_falls_back_to_plain_when_highlights_none():
    """Test 4: _result_to_html falls back to title and excerpt when highlights are None."""
    from nitrofind.ui.result_delegate import _result_to_html
    from nitrofind.search.models import ArticleResult

    # Construct directly to pass None highlights (not empty list)
    result = ArticleResult(
        title="Porsche 911",
        url="https://en.wikipedia.org/wiki/Porsche_911",
        source_domain="wikipedia.org",
        score=0.9,
        excerpt="Classic German sports car.",
        highlight_title=None,   # type: ignore[arg-type]  # simulate None from untrusted source
        highlight_body=None,    # type: ignore[arg-type]
    )
    html = _result_to_html(result)

    assert "Porsche 911" in html, "Must fall back to plain title when highlight_title is None"
    assert "Classic German sports car." in html, "Must fall back to excerpt when highlight_body is None"


def test_row_padding_constant():
    """Test 7: _ROW_PADDING == QMargins(8, 8, 8, 8) — UI-SPEC 8-point grid enforcement."""
    from PyQt6.QtCore import QMargins
    from nitrofind.ui.result_delegate import _ROW_PADDING

    assert _ROW_PADDING == QMargins(8, 8, 8, 8), (
        f"_ROW_PADDING must be QMargins(8,8,8,8) per UI-SPEC; got {_ROW_PADDING}"
    )


# ---------------------------------------------------------------------------
# Tests: ResultDelegate (require qtbot for QTextDocument metrics)
# ---------------------------------------------------------------------------

def test_make_doc_returns_document_with_zero_margin(qtbot):
    """Test 5: ResultDelegate._make_doc sets documentMargin to 0.

    QStyledItemDelegate is a QObject, not a QWidget — do not call qtbot.addWidget.
    qtbot is still needed here to ensure a QApplication is running.
    """
    from nitrofind.ui.result_delegate import ResultDelegate

    # QStyledItemDelegate is a QObject, not a QWidget; no addWidget call needed.
    delegate = ResultDelegate()

    html = "<b>Test Title</b><br>domain.com<br>Some excerpt text."
    doc = delegate._make_doc(html, width=400)

    assert doc.documentMargin() == 0, (
        f"_make_doc must set documentMargin=0; got {doc.documentMargin()}"
    )
    assert doc.textWidth() == 400, (
        f"_make_doc must set textWidth to supplied width; got {doc.textWidth()}"
    )


def test_size_hint_returns_positive_height(qtbot):
    """Test 6: ResultDelegate.sizeHint returns a QSize with positive height for non-empty HTML.

    viewOptions() was removed in Qt6. Use QStyleOptionViewItem directly and
    set the rect manually to simulate the view's available width.
    """
    from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QStyleOptionViewItem
    from PyQt6.QtCore import Qt, QRect
    from nitrofind.ui.result_delegate import ResultDelegate, _result_to_html

    list_widget = QListWidget()
    qtbot.addWidget(list_widget)
    list_widget.resize(400, 600)

    delegate = ResultDelegate()
    list_widget.setItemDelegate(delegate)

    result = _make_article_result(
        title="BMW M3",
        source_domain="motor1.com",
        excerpt="High-performance saloon from Bavaria.",
    )
    html = _result_to_html(result)

    item = QListWidgetItem()
    item.setData(Qt.ItemDataRole.UserRole, html)
    list_widget.addItem(item)

    # Build a QStyleOptionViewItem with a valid rect simulating 400px width
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 400, 60)

    size = delegate.sizeHint(option, list_widget.model().index(0, 0))
    assert size.height() > 0, (
        f"sizeHint must return positive height for non-empty HTML; got {size.height()}"
    )
    assert size.width() >= 0, "sizeHint must return non-negative width"
