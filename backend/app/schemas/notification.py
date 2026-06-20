"""Notification request/response schemas."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

NotificationType = Literal["mention", "assignment", "comment", "system"]


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str | None
    resource_type: str | None
    resource_id: str | None
    is_read: bool
    read_at: dt.datetime | None
    created_at: dt.datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class CreateNotificationRequest(BaseModel):
    """Used internally and in tests; not exposed as a user-facing endpoint."""

    type: NotificationType
    title: str
    body: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
