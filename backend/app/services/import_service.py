"""CSV bulk-import orchestration: parse -> map (per-format adapter) -> validate.

Two entry points share the same pipeline:

* ``build_preview`` — dry run; returns every row's mapped values + diagnostics
  without touching the database (powers the preview-before-import UI).
* ``commit_import`` — runs the same mapping/validation and persists the *valid*
  rows as issues via the existing ``issue_service`` (so column ordering and
  per-user scoping stay consistent with cards created on the board).

Input is the raw CSV text (the frontend reads the file and posts its contents),
which keeps the API a plain JSON endpoint — no multipart handling needed.
"""
from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.imports import (
    ImportPreviewResponse,
    ImportRowPreview,
)
from app.services import issue_service
from app.services.importers import (
    DESCRIPTION_MAX,
    TITLE_MAX,
    FormatAdapter,
    MappedIssue,
    detect_adapter,
    get_adapter,
)


_MAX_ROWS = 10_000

# M5: Characters that begin spreadsheet formula injection payloads.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class CsvImportError(Exception):
    """Un-importable input: malformed CSV or an unrecognizable source."""


def _parse_csv(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV text into (display headers, rows keyed by lower-cased header).

    A BOM (Excel often prepends one) is stripped so the first header matches.
    """
    text = csv_text.lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CsvImportError("The file has no header row.")

    display_headers = [(h or "").strip() for h in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for raw in reader:
        rows.append(
            {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
        )
    # H1: hard cap to prevent DoS from pathologically large CSVs.
    if len(rows) > _MAX_ROWS:
        raise CsvImportError(
            f"CSV exceeds the {_MAX_ROWS:,}-row limit. Split the file and import in batches."
        )
    return display_headers, rows


def _resolve_adapter(
    display_headers: list[str], source: str | None
) -> tuple[FormatAdapter, bool]:
    """Return (adapter, detected). Raises CsvImportError if undetectable."""
    if source is not None:
        return get_adapter(source), False
    norm = [h.lower() for h in display_headers]
    adapter = detect_adapter(norm)
    if adapter is None:
        raise CsvImportError(
            "Couldn't recognize this CSV as a Jira, Linear, or Trello export. "
            "Choose the source format manually."
        )
    return adapter, True


def _strip_formula(value: str) -> str:
    """M5: Prefix formula-injection payloads with a single quote (Excel-safe)."""
    if value and value[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value


def _validate(mapped: MappedIssue) -> None:
    """Apply generic (format-independent) rules in place: title + length."""
    if not mapped.title:
        mapped.errors.append("Missing a title - this row will be skipped.")
    else:
        mapped.title = _strip_formula(mapped.title)
        if len(mapped.title) > TITLE_MAX:
            mapped.title = mapped.title[:TITLE_MAX]
            mapped.warnings.append(f"Title truncated to {TITLE_MAX} characters.")

    if mapped.description:
        mapped.description = _strip_formula(mapped.description)
        if len(mapped.description) > DESCRIPTION_MAX:
            mapped.description = mapped.description[:DESCRIPTION_MAX]
            mapped.warnings.append(
                f"Description truncated to {DESCRIPTION_MAX} characters."
            )


def _is_blank(row: dict[str, str]) -> bool:
    return not any((v or "").strip() for v in row.values())


def _map_rows(
    adapter: FormatAdapter, rows: list[dict[str, str]]
) -> list[tuple[int, MappedIssue]]:
    """Map every non-blank row, keeping its 1-based CSV line number."""
    out: list[tuple[int, MappedIssue]] = []
    for index, row in enumerate(rows, start=2):  # header is line 1
        if _is_blank(row):
            continue
        mapped = adapter.map_row(row)
        _validate(mapped)
        out.append((index, mapped))
    return out


def build_preview(
    csv_text: str, source: str | None = None
) -> ImportPreviewResponse:
    display_headers, rows = _parse_csv(csv_text)
    adapter, detected = _resolve_adapter(display_headers, source)

    mapped_rows = _map_rows(adapter, rows)
    previews = [
        ImportRowPreview(
            row_number=line,
            title=m.title,
            description=m.description,
            status=m.status,
            priority=m.priority,
            valid=m.valid,
            errors=m.errors,
            warnings=m.warnings,
        )
        for line, m in mapped_rows
    ]
    valid_rows = sum(1 for _, m in mapped_rows if m.valid)

    mapped = adapter.mapped_fields()
    unmapped = [h for h in display_headers if h.lower() not in mapped]

    return ImportPreviewResponse(
        source=adapter.source,  # type: ignore[arg-type]
        detected=detected,
        total_rows=len(mapped_rows),
        valid_rows=valid_rows,
        invalid_rows=len(mapped_rows) - valid_rows,
        columns=display_headers,
        unmapped_columns=unmapped,
        rows=previews,
    )


async def commit_import(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    csv_text: str,
    source: str | None = None,
    workspace_id: uuid.UUID | None = None,
) -> tuple[str, int, int]:
    """Persist valid rows as issues. Returns (source, imported, skipped).

    Each issue is appended to the end of its target column via
    ``issue_service.create_issue`` so positions stay contiguous. The caller
    commits the transaction.
    """
    display_headers, rows = _parse_csv(csv_text)
    adapter, _ = _resolve_adapter(display_headers, source)

    imported = 0
    skipped = 0
    for _, mapped in _map_rows(adapter, rows):
        if not mapped.valid:
            skipped += 1
            continue
        await issue_service.create_issue(
            db,
            user_id=user_id,
            title=mapped.title,
            description=mapped.description,
            status=mapped.status,
            priority=mapped.priority,
            workspace_id=workspace_id,
        )
        imported += 1

    return adapter.source, imported, skipped
