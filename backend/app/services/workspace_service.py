"""Workspace business logic."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace


async def create_workspace(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    name: str,
) -> Workspace:
    ws = Workspace(owner_id=owner_id, name=name)
    db.add(ws)
    await db.flush()
    return ws


async def get_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> Workspace | None:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    return result.scalar_one_or_none()
