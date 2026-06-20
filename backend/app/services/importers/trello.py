"""Trello CSV export adapter.

Trello's CSV uses ``Card Name`` + ``Card Description``. There is no status or
priority column: a card's column is its **list name** (free text chosen by the
user), and Trello has no native priority — teams encode it with labels. So this
adapter overrides the generic lookups with keyword heuristics:

* status  ← substring match of the list name against the four canonical buckets
* priority ← keyword match against the card's labels (defaults to medium)
"""
from __future__ import annotations

from .base import FormatAdapter


class TrelloAdapter(FormatAdapter):
    source = "trello"
    label = "Trello"
    detect_field = "card name"

    title_field = "card name"
    description_field = "card description"
    status_field = "list name"
    priority_field = ""  # derived from labels, not a column

    def mapped_fields(self) -> set[str]:
        # Labels feed the derived priority, so they're a mapped column too.
        return super().mapped_fields() | {"labels"}

    # Ordered: more specific / "later" stages first so e.g. "Ready for Review"
    # beats a stray "in" match. First keyword found in the list name wins.
    _STATUS_KEYWORDS = (
        ("done", "done"),
        ("complete", "done"),
        ("finished", "done"),
        ("shipped", "done"),
        ("released", "done"),
        ("review", "review"),
        ("qa", "review"),
        ("testing", "review"),
        ("approval", "review"),
        ("progress", "in_progress"),
        ("doing", "in_progress"),
        ("wip", "in_progress"),
        ("development", "in_progress"),
        ("active", "in_progress"),
        ("backlog", "backlog"),
        ("to do", "backlog"),
        ("todo", "backlog"),
        ("inbox", "backlog"),
        ("ideas", "backlog"),
        ("new", "backlog"),
    )
    _PRIORITY_KEYWORDS = (
        ("urgent", "urgent"),
        ("critical", "urgent"),
        ("blocker", "urgent"),
        ("p0", "urgent"),
        ("high", "high"),
        ("p1", "high"),
        ("low", "low"),
        ("minor", "low"),
        ("p3", "low"),
    )

    def _map_status(self, row: dict[str, str], warnings: list[str]) -> str:
        raw = (row.get(self.status_field) or "").strip()
        if not raw:
            return self.default_status
        low = raw.lower()
        for keyword, canon in self._STATUS_KEYWORDS:
            if keyword in low:
                return canon
        warnings.append(
            f"List {raw!r} didn't match a column; placed in {self.default_status}."
        )
        return self.default_status

    def _map_priority(self, row: dict[str, str], warnings: list[str]) -> str:
        labels = (row.get("labels") or "").lower()
        if not labels.strip():
            return self.default_priority
        for keyword, canon in self._PRIORITY_KEYWORDS:
            if keyword in labels:
                return canon
        return self.default_priority
