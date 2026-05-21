"""
RAG Orchestrator: ties together retriever → prompt_builder → claude_caller.
Entry point: handle_alert(alert_event) -> PlaybookResponse
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.normaliser import NormalisedAlert
from app.models.incident import Incident, IncidentStatus
from app.models.playbook_response import PlaybookResponse
from app.rag.claude_caller import call_claude
from app.rag.prompt_builder import build_prompt
from app.rag.retriever import retrieve_relevant_chunks
from app.remediation.remediation_registry import get_remediation_command

settings = get_settings()
log = get_logger(__name__)

VALID_REMEDIATION_SUGGESTIONS = {
    "restart_deployment",
    "scale_deployment",
    "cordon_node",
    "rollback_deployment",
    "none",
}


async def handle_alert(
    session: AsyncSession,
    alert: NormalisedAlert,
) -> tuple[Incident, PlaybookResponse]:
    """
    Full RAG pipeline for a single alert:
    1. Create/update Incident record
    2. Retrieve relevant runbook chunks
    3. Build Claude prompt
    4. Call Claude
    5. Store PlaybookResponse
    6. Return (incident, playbook)
    """
    # 1. Create Incident
    incident = Incident(
        tenant_id=alert.tenant_id,
        title=f"[{alert.severity.value.upper()}] {alert.alert_name}",
        description=alert.description,
        status=IncidentStatus.OPEN,
        severity=alert.severity.value,
        source=alert.source.value,
        labels=alert.labels,
        alert_fingerprints=[alert.fingerprint],
    )
    session.add(incident)
    await session.flush()

    log.info(
        "incident_created",
        incident_id=str(incident.id),
        alert_name=alert.alert_name,
        severity=alert.severity.value,
    )

    # 2. Retrieve runbook chunks
    try:
        chunks = await retrieve_relevant_chunks(session, alert)
    except Exception as exc:
        log.error("retrieval_failed", error=str(exc), incident_id=str(incident.id))
        chunks = []

    # 3 & 4. Build prompt and call Claude
    messages = build_prompt(alert, chunks)
    try:
        claude_result = await call_claude(messages)
    except Exception as exc:
        log.error("claude_call_failed", error=str(exc), incident_id=str(incident.id))
        claude_result = {
            "probable_cause": f"Claude unavailable: {exc}",
            "severity": alert.severity.value,
            "runbook_steps": [],
            "escalation_path": "Escalate to on-call SRE immediately",
            "auto_remediation_suggestion": "none",
            "auto_remediation_details": "",
        }

    # Validate auto_remediation_suggestion
    suggestion = claude_result.get("auto_remediation_suggestion", "none")
    if suggestion not in VALID_REMEDIATION_SUGGESTIONS:
        suggestion = "none"

    # Look up approved remediation command
    remediation_cmd = None
    if suggestion != "none":
        remediation_cmd = get_remediation_command(
            suggestion=suggestion,
            labels=alert.labels,
            namespace=alert.namespace or settings.k8s_namespace,
        )

    # 5. Store PlaybookResponse
    playbook = PlaybookResponse(
        tenant_id=alert.tenant_id,
        incident_id=incident.id,
        probable_cause=claude_result.get("probable_cause"),
        severity_assessment=claude_result.get("severity"),
        runbook_steps=claude_result.get("runbook_steps", []),
        escalation_path=claude_result.get("escalation_path"),
        auto_remediation_suggestion=suggestion,
        remediation_command=remediation_cmd,
        retrieved_chunks=[
            {"content": c["content"], "score": c["score"], "runbook_id": c["runbook_id"]}
            for c in chunks
        ],
        raw_claude_response=claude_result.get("_raw"),
        model_used=claude_result.get("_model", settings.llm_model),
    )
    session.add(playbook)
    await session.flush()

    return incident, playbook


async def regenerate_playbook(
    session: AsyncSession,
    incident: Incident,
    alert: NormalisedAlert,
) -> PlaybookResponse:
    """Regenerate playbook for an existing incident (e.g., after new runbooks indexed)."""
    from sqlalchemy import select

    existing = await session.execute(
        select(PlaybookResponse).where(
            PlaybookResponse.incident_id == incident.id
        )
    )
    old_playbook = existing.scalar_one_or_none()

    chunks = await retrieve_relevant_chunks(session, alert)
    messages = build_prompt(alert, chunks)
    claude_result = await call_claude(messages)

    suggestion = claude_result.get("auto_remediation_suggestion", "none")
    if suggestion not in VALID_REMEDIATION_SUGGESTIONS:
        suggestion = "none"

    remediation_cmd = None
    if suggestion != "none":
        remediation_cmd = get_remediation_command(
            suggestion=suggestion,
            labels=alert.labels,
            namespace=alert.namespace or settings.k8s_namespace,
        )

    if old_playbook:
        old_playbook.probable_cause = claude_result.get("probable_cause")
        old_playbook.severity_assessment = claude_result.get("severity")
        old_playbook.runbook_steps = claude_result.get("runbook_steps", [])
        old_playbook.escalation_path = claude_result.get("escalation_path")
        old_playbook.auto_remediation_suggestion = suggestion
        old_playbook.remediation_command = remediation_cmd
        old_playbook.retrieved_chunks = [
            {"content": c["content"], "score": c["score"], "runbook_id": c["runbook_id"]}
            for c in chunks
        ]
        old_playbook.raw_claude_response = claude_result.get("_raw")
        old_playbook.model_used = claude_result.get("_model", settings.llm_model)
        old_playbook.remediation_approved = False
        await session.flush()
        return old_playbook
    else:
        playbook = PlaybookResponse(
            tenant_id=incident.tenant_id,
            incident_id=incident.id,
            probable_cause=claude_result.get("probable_cause"),
            severity_assessment=claude_result.get("severity"),
            runbook_steps=claude_result.get("runbook_steps", []),
            escalation_path=claude_result.get("escalation_path"),
            auto_remediation_suggestion=suggestion,
            remediation_command=remediation_cmd,
            retrieved_chunks=[
                {"content": c["content"], "score": c["score"], "runbook_id": c["runbook_id"]}
                for c in chunks
            ],
            raw_claude_response=claude_result.get("_raw"),
            model_used=claude_result.get("_model", settings.llm_model),
        )
        session.add(playbook)
        await session.flush()
        return playbook
