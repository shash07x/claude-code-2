"""Notification business logic."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(notif)
    await db.flush()
    return notif


async def get_notifications(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[list[Notification], int]:
    """Return (page_items, total_matching_count)."""
    base = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        base = base.where(Notification.is_read.is_(False))

    count_result = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(
        base.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def get_unread_count(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )
    return result.scalar_one()


async def mark_read(
    db: AsyncSession, *, notification_id: uuid.UUID, user_id: uuid.UUID
) -> Notification | None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()
    if notif is None:
        return None
    if not notif.is_read:
        notif.is_read = True
        notif.read_at = _utcnow()
        await db.flush()
    return notif


async def mark_all_read(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    """Mark every unread notification as read. Returns the number of rows updated."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=_utcnow())
        .returning(Notification.id)
    )
    updated_ids = result.fetchall()
    return len(updated_ids)


async def delete_notification(
    db: AsyncSession, *, notification_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()
    if notif is None:
        return False
    await db.delete(notif)
    await db.flush()
    return True
