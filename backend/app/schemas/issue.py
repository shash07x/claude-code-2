"""Issue + Sprint Board request/response schemas."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IssueStatus = Literal["backlog", "in_progress", "review", "done"]
IssuePriority = Literal["low", "medium", "high", "urgent"]

# Canonical board column order + display labels (single source of truth).
BOARD_COLUMNS: list[IssueStatus] = ["backlog", "review", "in_progress", "done"]
COLUMN_LABELS: dict[str, str] = {
    "backlog": "Backlog",
    "in_progress": "In Progress",
    "review": "Review",
    "done": "Done",
}


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    status: str
    position: int
    priority: str
    created_at: dt.datetime
    updated_at: dt.datetime


class IssueCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: IssueStatus = "backlog"
    priority: IssuePriority = "medium"


class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    priority: IssuePriority | None = None


class IssueMove(BaseModel):
    """Persist a drag-and-drop drop: target column + index within that column."""

    status: IssueStatus
    position: int = Field(..., ge=0)


class BoardColumn(BaseModel):
    status: IssueStatus
    title: str
    items: list[IssueRead]


class BoardResponse(BaseModel):
    columns: list[BoardColumn]
