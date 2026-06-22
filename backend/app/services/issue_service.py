"""Issue + Sprint Board business logic.

Ordering model: every issue has an integer ``position`` (0-based) that is unique
and contiguous within its ``(user_id, status)`` column. Moves re-index the
affected column(s) so positions always stay contiguous — simple and correct for
the small card counts a sprint board holds.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.issue import Issue


async def _ordered_column(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: str,
    exclude_id: uuid.UUID | None = None,
) -> list[Issue]:
    """Return a column's issues ordered by position, optionally excluding one."""
    stmt = (
        select(Issue)
        .where(Issue.user_id == user_id, Issue.status == status)
        .order_by(Issue.position.asc(), Issue.created_at.asc())
    )
    result = await db.execute(stmt)
    issues = list(result.scalars().all())
    if exclude_id is not None:
        issues = [i for i in issues if i.id != exclude_id]
    return issues


async def get_board(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, list[Issue]]:
    """Return {status: [issues ordered by position]} for every column the user has."""
    stmt = (
        select(Issue)
        .where(Issue.user_id == user_id)
        .order_by(Issue.status.asc(), Issue.position.asc(), Issue.created_at.asc())
    )
    result = await db.execute(stmt)
    grouped: dict[str, list[Issue]] = {}
    for issue in result.scalars().all():
        grouped.setdefault(issue.status, []).append(issue)
    return grouped


async def get_issue(
    db: AsyncSession, *, issue_id: uuid.UUID, user_id: uuid.UUID
) -> Issue | None:
    result = await db.execute(
        select(Issue).where(Issue.id == issue_id, Issue.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_issue(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    description: str | None = None,
    status: str = "backlog",
    priority: str = "medium",
    workspace_id: uuid.UUID | None = None,
) -> Issue:
    # Append to the end of the target column.
    existing = await _ordered_column(db, user_id=user_id, status=status)
    issue = Issue(
        user_id=user_id,
        workspace_id=workspace_id,
        title=title,
        description=description,
        status=status,
        priority=priority,
        position=len(existing),
    )
    db.add(issue)
    await db.flush()
    return issue


async def update_issue(
    db: AsyncSession,
    *,
    issue: Issue,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
) -> Issue:
    if title is not None:
        issue.title = title
    if description is not None:
        issue.description = description
    if priority is not None:
        issue.priority = priority
    await db.flush()
    return issue


async def move_issue(
    db: AsyncSession, *, issue: Issue, new_status: str, new_index: int
) -> Issue:
    """Move an issue to ``new_status`` at ``new_index`` and re-index columns.

    ``new_index`` is the desired position within the target column's list
    *excluding* the issue being moved (clamped to a valid range).
    """
    old_status = issue.status

    # Rebuild the target column with the issue inserted at the requested index.
    target = await _ordered_column(
        db, user_id=issue.user_id, status=new_status, exclude_id=issue.id
    )
    new_index = max(0, min(new_index, len(target)))
    issue.status = new_status
    target.insert(new_index, issue)
    for idx, item in enumerate(target):
        item.position = idx

    # If the column changed, the source column has a gap — re-index it too.
    if old_status != new_status:
        source = await _ordered_column(
            db, user_id=issue.user_id, status=old_status, exclude_id=issue.id
        )
        for idx, item in enumerate(source):
            item.position = idx

    await db.flush()
    return issue


async def delete_issue(db: AsyncSession, *, issue: Issue) -> None:
    status = issue.status
    user_id = issue.user_id
    await db.delete(issue)
    await db.flush()
    # Re-index the column the issue was removed from so positions stay contiguous.
    remaining = await _ordered_column(db, user_id=user_id, status=status)
    for idx, item in enumerate(remaining):
        item.position = idx
    await db.flush()
