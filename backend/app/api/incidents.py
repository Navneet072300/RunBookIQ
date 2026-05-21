"""
GET  /api/v1/incidents         — paginated incident list
GET  /api/v1/incidents/{id}    — full incident detail with playbook
PATCH /api/v1/incidents/{id}   — update status/assignee
GET  /api/v1/incidents/{id}/playbook/stream  — SSE streaming playbook
"""
import asyncio
import json
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.api.schemas import (
    IncidentDetail,
    IncidentListItem,
    IncidentListResponse,
    IncidentUpdateRequest,
    PlaybookDetail,
)
from app.core.logging import get_logger
from app.models.incident import Incident, IncidentStatus
from app.models.playbook_response import PlaybookResponse

router = APIRouter(prefix="/incidents", tags=["incidents"])
log = get_logger(__name__)


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """Paginated list of incidents with optional filters."""
    stmt = select(Incident).where(Incident.tenant_id == tenant_id)

    if status:
        try:
            stmt = stmt.where(Incident.status == IncidentStatus(status))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    if severity:
        stmt = stmt.where(Incident.severity == severity.lower())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Incident.opened_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    # Check which incidents have playbooks
    incident_ids = [r.id for r in rows]
    playbook_ids: set[uuid.UUID] = set()
    if incident_ids:
        pb_stmt = select(PlaybookResponse.incident_id).where(
            PlaybookResponse.incident_id.in_(incident_ids)
        )
        playbook_ids = set((await db.execute(pb_stmt)).scalars().all())

    items = [
        IncidentListItem(
            id=r.id,
            title=r.title,
            severity=r.severity,
            status=r.status.value,
            source=r.source,
            opened_at=r.opened_at,
            resolved_at=r.resolved_at,
            has_playbook=r.id in playbook_ids,
        )
        for r in rows
    ]

    return IncidentListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """Full incident detail including generated playbook."""
    incident = await _get_incident_or_404(db, incident_id, tenant_id)

    pb_stmt = select(PlaybookResponse).where(
        PlaybookResponse.incident_id == incident_id
    )
    playbook = (await db.execute(pb_stmt)).scalar_one_or_none()

    return IncidentDetail(
        id=incident.id,
        tenant_id=incident.tenant_id,
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        status=incident.status.value,
        source=incident.source,
        assigned_to=incident.assigned_to,
        labels=incident.labels,
        alert_fingerprints=incident.alert_fingerprints or [],
        opened_at=incident.opened_at,
        acknowledged_at=incident.acknowledged_at,
        resolved_at=incident.resolved_at,
        playbook=PlaybookDetail.model_validate(playbook) if playbook else None,
    )


@router.patch("/{incident_id}", response_model=IncidentDetail)
async def update_incident(
    incident_id: uuid.UUID,
    update: IncidentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """Update incident status or assignee."""
    from datetime import datetime, timezone

    incident = await _get_incident_or_404(db, incident_id, tenant_id)

    if update.status:
        try:
            new_status = IncidentStatus(update.status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {update.status}")
        incident.status = new_status
        if new_status == IncidentStatus.ACKNOWLEDGED and not incident.acknowledged_at:
            incident.acknowledged_at = datetime.now(tz=timezone.utc)
        elif new_status == IncidentStatus.RESOLVED and not incident.resolved_at:
            incident.resolved_at = datetime.now(tz=timezone.utc)

    if update.assigned_to is not None:
        incident.assigned_to = update.assigned_to

    await db.flush()
    return await get_incident(incident_id, db, tenant_id)


@router.get("/{incident_id}/playbook/stream")
async def stream_playbook(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """
    SSE endpoint: streams Claude output token-by-token.
    Regenerates the playbook on demand using stored alert data.
    """
    incident = await _get_incident_or_404(db, incident_id, tenant_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            from app.ingestion.normaliser import NormalisedAlert, AlertSource, AlertSeverity
            from app.rag.retriever import retrieve_relevant_chunks
            from app.rag.prompt_builder import build_prompt
            from app.rag.claude_caller import stream_claude
            from datetime import datetime, timezone

            # Reconstruct a NormalisedAlert from incident metadata for retrieval
            alert = NormalisedAlert(
                tenant_id=incident.tenant_id,
                fingerprint=incident.alert_fingerprints[0] if incident.alert_fingerprints else "",
                source=AlertSource(incident.source) if incident.source in [s.value for s in AlertSource] else AlertSource.MANUAL,
                alert_name=incident.title.split("] ", 1)[-1] if "] " in incident.title else incident.title,
                severity=AlertSeverity(incident.severity) if incident.severity in [s.value for s in AlertSeverity] else AlertSeverity.UNKNOWN,
                namespace=incident.labels.get("namespace"),
                cluster=incident.labels.get("cluster"),
                labels=incident.labels,
                annotations={},
                raw_payload={},
                description=incident.description,
                fired_at=incident.opened_at or datetime.now(tz=timezone.utc),
            )

            chunks = await retrieve_relevant_chunks(db, alert)
            messages = build_prompt(alert, chunks)

            async for token in stream_claude(messages):
                yield f"data: {json.dumps({'token': token})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            log.error("stream_playbook_error", incident_id=str(incident_id), error=str(exc))
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _get_incident_or_404(
    db: AsyncSession, incident_id: uuid.UUID, tenant_id: str
) -> Incident:
    stmt = select(Incident).where(
        Incident.id == incident_id,
        Incident.tenant_id == tenant_id,
    )
    incident = (await db.execute(stmt)).scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
