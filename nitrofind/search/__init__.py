# NitroFind search package
from nitrofind.search.models import ArticleResult  # noqa: F401

__all__ = ["SearchEngine", "ArticleResult"]


def __getattr__(name: str):
    """Load legacy Qt search engine only when explicitly requested."""
    if name == "SearchEngine":
        from nitrofind.search.engine import SearchEngine

        return SearchEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
