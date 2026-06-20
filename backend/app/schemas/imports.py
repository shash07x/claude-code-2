"""CSV bulk-import request/response schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ImportSource = Literal["jira", "linear", "trello"]

SOURCE_LABELS: dict[str, str] = {
    "jira": "Jira",
    "linear": "Linear",
    "trello": "Trello",
}


class ImportPreviewRequest(BaseModel):
    csv_text: str = Field(..., min_length=1)
    # Omit to auto-detect the source from the CSV header row.
    source: ImportSource | None = None


class ImportRowPreview(BaseModel):
    row_number: int  # 1-based line in the CSV (header is line 1)
    title: str
    description: str | None
    status: str
    priority: str
    valid: bool
    errors: list[str]
    warnings: list[str]


class ImportPreviewResponse(BaseModel):
    source: ImportSource
    detected: bool  # True when `source` was auto-detected rather than supplied
    total_rows: int
    valid_rows: int
    invalid_rows: int
    columns: list[str]  # header names as they appeared in the CSV
    unmapped_columns: list[str]  # columns TeamSync has no home for (dropped)
    rows: list[ImportRowPreview]


class ImportCommitRequest(BaseModel):
    csv_text: str = Field(..., min_length=1)
    source: ImportSource | None = None


class ImportCommitResponse(BaseModel):
    source: ImportSource
    imported: int  # issues created
    skipped: int  # rows skipped (invalid / blank)
