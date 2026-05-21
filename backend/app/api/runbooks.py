"""
POST /api/v1/runbooks/upload  — upload runbook file, trigger embedding
GET  /api/v1/runbooks         — list indexed runbooks
DELETE /api/v1/runbooks/{id}  — remove a runbook and its chunks
POST /api/v1/runbooks/{id}/reindex — re-embed existing runbook
"""
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.api.schemas import RunbookListItem, RunbookListResponse
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.runbook import Runbook
from app.models.runbook_chunk import RunbookChunk
from app.workers.tasks import enqueue_runbook_indexing

settings = get_settings()
router = APIRouter(prefix="/runbooks", tags=["runbooks"])
log = get_logger(__name__)

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("/upload", status_code=202)
async def upload_runbook(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """Upload a runbook file and trigger async embedding pipeline."""
    # Validate file type
    allowed_types = {
        "text/plain", "text/markdown", "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    content_type = file.content_type or "text/plain"
    filename_lower = (file.filename or "").lower()

    is_allowed = (
        content_type in allowed_types
        or filename_lower.endswith((".md", ".txt", ".pdf", ".docx"))
    )
    if not is_allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Allowed: markdown, PDF, DOCX, text",
        )

    # Read and validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
        )

    # Save to disk
    upload_dir = Path(settings.upload_dir) / tenant_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{uuid.uuid4().hex}_{Path(file.filename or 'runbook').name}"
    file_path = upload_dir / safe_filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)

    log.info(
        "runbook_uploaded",
        filename=file.filename,
        size=len(file_bytes),
        path=str(file_path),
    )

    # Enqueue indexing job
    job_id = enqueue_runbook_indexing(
        file_path=str(file_path),
        name=name,
        tenant_id=tenant_id,
        description=description or None,
        content_type=content_type,
    )

    return {
        "message": "Runbook upload accepted, indexing in progress",
        "job_id": job_id,
        "name": name,
    }


@router.get("", response_model=RunbookListResponse)
async def list_runbooks(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all indexed runbooks with metadata."""
    stmt = (
        select(Runbook)
        .where(Runbook.tenant_id == tenant_id)
        .order_by(Runbook.created_at.desc())
    )
    runbooks = (await db.execute(stmt)).scalars().all()

    count_stmt = select(func.count()).where(Runbook.tenant_id == tenant_id)
    total = (await db.execute(count_stmt)).scalar_one()

    return RunbookListResponse(
        items=[RunbookListItem.model_validate(r) for r in runbooks],
        total=total,
    )


@router.delete("/{runbook_id}", status_code=204)
async def delete_runbook(
    runbook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """Remove a runbook and all its embedded chunks."""
    runbook = await _get_runbook_or_404(db, runbook_id, tenant_id)

    await db.execute(
        delete(RunbookChunk).where(RunbookChunk.runbook_id == runbook_id)
    )
    await db.delete(runbook)
    log.info("runbook_deleted", runbook_id=str(runbook_id))


@router.post("/{runbook_id}/reindex", status_code=202)
async def reindex_runbook(
    runbook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """Re-embed an existing runbook (e.g., after model change)."""
    runbook = await _get_runbook_or_404(db, runbook_id, tenant_id)

    if not runbook.file_path or not Path(runbook.file_path).exists():
        raise HTTPException(
            status_code=409,
            detail="Original file not available for re-indexing",
        )

    job_id = enqueue_runbook_indexing(
        file_path=runbook.file_path,
        name=runbook.name,
        tenant_id=tenant_id,
        description=runbook.description,
        content_type=runbook.content_type,
    )
    return {"message": "Re-indexing enqueued", "job_id": job_id}


async def _get_runbook_or_404(
    db: AsyncSession, runbook_id: uuid.UUID, tenant_id: str
) -> Runbook:
    stmt = select(Runbook).where(
        Runbook.id == runbook_id,
        Runbook.tenant_id == tenant_id,
    )
    runbook = (await db.execute(stmt)).scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return runbook
