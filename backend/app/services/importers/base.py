"""Shared types + base class for CSV import format adapters.

Each external tool (Jira, Linear, Trello) exports a CSV with its own column
names and status/priority vocabularies. An adapter knows how to:

* recognise its own export from the header row (``detect``)
* map a single CSV row onto TeamSync's minimal Issue shape (``map_row``)

TeamSync issues only carry title/description/status/priority today, so every
adapter funnels a rich export down to those four fields. Columns an adapter does
*not* read are surfaced to the user as "unmapped" (see ``known_fields``) rather
than dropped silently.

Field lookups are done against **lower-cased, stripped** header keys; the import
service normalises every row that way before handing it to an adapter, so adapter
field names below are written in lowercase.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Canonical targets — mirror app.schemas.issue (single source of truth there).
CANONICAL_STATUSES = ("backlog", "in_progress", "review", "done")
CANONICAL_PRIORITIES = ("low", "medium", "high", "urgent")

TITLE_MAX = 255
DESCRIPTION_MAX = 2000


@dataclass
class MappedIssue:
    """One CSV row mapped onto TeamSync's Issue fields, plus diagnostics.

    ``errors`` block the row from importing; ``warnings`` mean it imported but a
    value was adjusted (status defaulted, title truncated, …).
    """

    title: str
    description: str | None
    status: str
    priority: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


class FormatAdapter:
    """Base adapter: generic column-driven mapping.

    Subclasses set the field/vocabulary class attributes. Formats whose mapping
    isn't a flat column lookup (e.g. Trello derives status from a free-text list
    name and priority from labels) override ``_map_status`` / ``_map_priority``.
    """

    source: str = ""
    label: str = ""
    detect_field: str = ""  # header that uniquely identifies this export

    title_field: str = ""
    description_field: str = ""
    status_field: str = ""
    priority_field: str = ""

    status_map: dict[str, str] = {}
    priority_map: dict[str, str] = {}
    default_status: str = "backlog"
    default_priority: str = "medium"

    def detect(self, headers: set[str]) -> bool:
        return bool(self.detect_field) and self.detect_field in headers

    def mapped_fields(self) -> set[str]:
        """Header keys (lower-cased) whose data actually lands on an Issue.

        Everything else in the CSV is reported to the user as *unmapped* — it is
        dropped, since TeamSync issues only hold these four fields today.
        """
        fields = {
            self.title_field,
            self.description_field,
            self.status_field,
            self.priority_field,
        }
        fields.discard("")
        return fields

    # -- mapping -------------------------------------------------------------

    def map_row(self, row: dict[str, str]) -> MappedIssue:
        warnings: list[str] = []
        title = (row.get(self.title_field) or "").strip()
        description = self._extract_description(row)
        status = self._map_status(row, warnings)
        priority = self._map_priority(row, warnings)
        return MappedIssue(
            title=title,
            description=description,
            status=status,
            priority=priority,
            warnings=warnings,
        )

    def _extract_description(self, row: dict[str, str]) -> str | None:
        if not self.description_field:
            return None
        raw = (row.get(self.description_field) or "").strip()
        return raw or None

    def _map_status(self, row: dict[str, str], warnings: list[str]) -> str:
        raw = (row.get(self.status_field) or "").strip()
        if not raw:
            return self.default_status
        mapped = self.status_map.get(raw.lower())
        if mapped is None:
            warnings.append(
                f"Unrecognized status {raw!r}; placed in {self.default_status}."
            )
            return self.default_status
        return mapped

    def _map_priority(self, row: dict[str, str], warnings: list[str]) -> str:
        if not self.priority_field:
            return self.default_priority
        raw = (row.get(self.priority_field) or "").strip()
        if not raw:
            return self.default_priority
        mapped = self.priority_map.get(raw.lower())
        if mapped is None:
            warnings.append(
                f"Unrecognized priority {raw!r}; set to {self.default_priority}."
            )
            return self.default_priority
        return mapped
