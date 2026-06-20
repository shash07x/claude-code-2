"""Issue + Sprint Board endpoints. All routes require an authenticated owner."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.issue import Issue
from app.models.user import User
from app.schemas.issue import (
    BOARD_COLUMNS,
    COLUMN_LABELS,
    BoardColumn,
    BoardResponse,
    IssueCreate,
    IssueMove,
    IssueRead,
    IssueUpdate,
)
from app.services import issue_service

router = APIRouter(prefix="/issues", tags=["issues"])


async def _get_owned_issue(
    issue_id: uuid.UUID, db: AsyncSession, user: User
) -> Issue:
    issue = await issue_service.get_issue(db, issue_id=issue_id, user_id=user.id)
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )
    return issue


@router.get("/board", response_model=BoardResponse)
async def get_board(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BoardResponse:
    """Return all of the user's issues grouped into the four fixed columns."""
    grouped = await issue_service.get_board(db, user_id=current_user.id)
    columns = [
        BoardColumn(
            status=col,
            title=COLUMN_LABELS[col],
            items=[IssueRead.model_validate(i) for i in grouped.get(col, [])],
        )
        for col in BOARD_COLUMNS
    ]
    return BoardResponse(columns=columns)


@router.post("", response_model=IssueRead, status_code=status.HTTP_201_CREATED)
async def create_issue(
    payload: IssueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueRead:
    issue = await issue_service.create_issue(
        db,
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
    )
    await db.commit()
    return IssueRead.model_validate(issue)


@router.patch("/{issue_id}", response_model=IssueRead)
async def update_issue(
    issue_id: uuid.UUID,
    payload: IssueUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueRead:
    issue = await _get_owned_issue(issue_id, db, current_user)
    issue = await issue_service.update_issue(
        db,
        issue=issue,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
    )
    await db.commit()
    await db.refresh(issue)  # reload server-updated `updated_at`
    return IssueRead.model_validate(issue)


@router.patch("/{issue_id}/move", response_model=IssueRead)
async def move_issue(
    issue_id: uuid.UUID,
    payload: IssueMove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueRead:
    """Persist a drag-and-drop drop: set the issue's column + ordering."""
    issue = await _get_owned_issue(issue_id, db, current_user)
    issue = await issue_service.move_issue(
        db, issue=issue, new_status=payload.status, new_index=payload.position
    )
    await db.commit()
    await db.refresh(issue)  # reload server-updated `updated_at`
    return IssueRead.model_validate(issue)


@router.delete(
    "/{issue_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def delete_issue(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    issue = await _get_owned_issue(issue_id, db, current_user)
    await issue_service.delete_issue(db, issue=issue)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
