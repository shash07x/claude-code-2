"""CSV import format adapters + a small registry.

Detection order matters: the most specific header is checked first so that, for
example, a Linear export (which has a generic ``Title`` column) is never
mis-detected as something else. Jira (``Summary``) and Trello (``Card Name``) use
distinctive headers and are checked before Linear's ``Title``.
"""
from __future__ import annotations

from .base import DESCRIPTION_MAX, TITLE_MAX, FormatAdapter, MappedIssue
from .jira import JiraAdapter
from .linear import LinearAdapter
from .trello import TrelloAdapter

# Singleton adapters (stateless), in detection order.
_ADAPTERS: tuple[FormatAdapter, ...] = (
    JiraAdapter(),
    TrelloAdapter(),
    LinearAdapter(),
)
_BY_SOURCE: dict[str, FormatAdapter] = {a.source: a for a in _ADAPTERS}


def get_adapter(source: str) -> FormatAdapter:
    """Return the adapter for an explicit source, or raise KeyError."""
    return _BY_SOURCE[source]


def detect_adapter(headers: list[str] | set[str]) -> FormatAdapter | None:
    """Best-effort detect the source from (lower-cased) header names."""
    hset = set(headers)
    for adapter in _ADAPTERS:
        if adapter.detect(hset):
            return adapter
    return None


def available_sources() -> list[dict[str, str]]:
    return [{"source": a.source, "label": a.label} for a in _ADAPTERS]


__all__ = [
    "FormatAdapter",
    "MappedIssue",
    "TITLE_MAX",
    "DESCRIPTION_MAX",
    "get_adapter",
    "detect_adapter",
    "available_sources",
]
