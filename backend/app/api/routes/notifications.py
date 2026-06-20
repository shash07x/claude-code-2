"""Notification endpoints. All routes require an authenticated user."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationRead,
    UnreadCountResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False, description="Return only unread notifications"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    items, total = await notification_service.get_notifications(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    unread_count = await notification_service.get_unread_count(
        db, user_id=current_user.id
    )
    return NotificationListResponse(
        items=[NotificationRead.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    count = await notification_service.get_unread_count(db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    notif = await notification_service.mark_read(
        db, notification_id=notification_id, user_id=current_user.id
    )
    if notif is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    await db.commit()
    return NotificationRead.model_validate(notif)


@router.post("/read-all", response_model=UnreadCountResponse)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    await notification_service.mark_all_read(db, user_id=current_user.id)
    await db.commit()
    return UnreadCountResponse(unread_count=0)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    deleted = await notification_service.delete_notification(
        db, notification_id=notification_id, user_id=current_user.id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
