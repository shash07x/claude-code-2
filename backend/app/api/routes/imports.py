"""CSV bulk-import endpoints. All routes require an authenticated user.

* ``POST /imports/preview`` — dry-run mapping + validation (no DB writes).
* ``POST /imports/commit``  — persist the valid rows as issues.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.imports import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewRequest,
    ImportPreviewResponse,
)
from app.services import import_service

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    payload: ImportPreviewRequest,
    current_user: User = Depends(get_current_user),
) -> ImportPreviewResponse:
    try:
        return import_service.build_preview(payload.csv_text, source=payload.source)
    except import_service.CsvImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.post("/commit", response_model=ImportCommitResponse)
async def commit_import(
    payload: ImportCommitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportCommitResponse:
    try:
        source, imported, skipped = await import_service.commit_import(
            db,
            user_id=current_user.id,
            csv_text=payload.csv_text,
            source=payload.source,
        )
    except import_service.CsvImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    await db.commit()
    return ImportCommitResponse(
        source=source,  # type: ignore[arg-type]
        imported=imported,
        skipped=skipped,
    )
