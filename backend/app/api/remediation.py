"""
POST /api/v1/remediation/{incident_id}/approve — approve and execute auto-remediation
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.api.schemas import RemediationApproveResponse
from app.core.logging import get_logger
from app.models.incident import Incident
from app.models.playbook_response import PlaybookResponse
from app.remediation.kubectl_runner import execute_remediation

router = APIRouter(prefix="/remediation", tags=["remediation"])
log = get_logger(__name__)


@router.post("/{incident_id}/approve", response_model=RemediationApproveResponse)
async def approve_remediation(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """
    Approve and execute the auto-remediation command for an incident.
    Always runs a dry-run first, then executes live.
    """
    # Get the playbook for this incident
    pb_stmt = select(PlaybookResponse).where(
        PlaybookResponse.incident_id == incident_id
    )
    playbook = (await db.execute(pb_stmt)).scalar_one_or_none()

    if not playbook:
        raise HTTPException(status_code=404, detail="No playbook found for this incident")

    if playbook.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not playbook.remediation_command:
        raise HTTPException(
            status_code=409,
            detail="No auto-remediation command available for this incident",
        )

    if playbook.remediation_approved and playbook.remediation_executed_at:
        raise HTTPException(
            status_code=409,
            detail="Remediation already executed",
        )

    log.info(
        "remediation_approved",
        incident_id=str(incident_id),
        command=playbook.remediation_command,
    )

    # Execute with dry_run=False (runs dry-run internally first)
    result = await execute_remediation(
        command=playbook.remediation_command,
        dry_run=False,
    )

    # Update playbook record
    playbook.remediation_approved = True
    playbook.remediation_executed_at = datetime.now(tz=timezone.utc)
    playbook.remediation_result = (
        result.get("live_output") or result.get("error") or "completed"
    )
    await db.flush()

    return RemediationApproveResponse(
        incident_id=incident_id,
        command=playbook.remediation_command,
        dry_run_output=result.get("dry_run_output", ""),
        live_output=result.get("live_output", ""),
        success=result.get("success", False),
        error=result.get("error"),
    )


@router.post("/{incident_id}/dry-run", response_model=RemediationApproveResponse)
async def dry_run_remediation(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """Preview the remediation command with dry-run only (does not execute live)."""
    pb_stmt = select(PlaybookResponse).where(
        PlaybookResponse.incident_id == incident_id
    )
    playbook = (await db.execute(pb_stmt)).scalar_one_or_none()

    if not playbook:
        raise HTTPException(status_code=404, detail="No playbook found for this incident")

    if playbook.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not playbook.remediation_command:
        raise HTTPException(status_code=409, detail="No remediation command available")

    result = await execute_remediation(
        command=playbook.remediation_command,
        dry_run=True,
    )

    return RemediationApproveResponse(
        incident_id=incident_id,
        command=playbook.remediation_command,
        dry_run_output=result.get("dry_run_output", ""),
        live_output="",
        success=result.get("success", False),
        error=result.get("error"),
    )
