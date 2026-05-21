"""
RQ task definitions and enqueue helpers.

Tasks run in the RQ worker process (synchronous wrappers around async code).
"""
import asyncio
from typing import Any, Optional
from uuid import UUID

from rq import Queue, get_current_job

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging()
settings = get_settings()
log = get_logger(__name__)


def _get_queue(name: str = "default") -> Queue:
    from app.core.redis import get_sync_redis
    return Queue(name, connection=get_sync_redis())


def enqueue_alert_processing(alert) -> str:
    """Enqueue an alert for RAG processing. Returns job ID."""
    import pickle
    q = _get_queue("high")
    job = q.enqueue(
        process_alert_job,
        alert,
        job_timeout=300,
        result_ttl=86400,
    )
    return job.id


def enqueue_runbook_indexing(
    *,
    file_path: str,
    name: str,
    tenant_id: str,
    description: Optional[str] = None,
    content_type: str = "text/markdown",
) -> str:
    """Enqueue a runbook for embedding pipeline. Returns job ID."""
    q = _get_queue("default")
    job = q.enqueue(
        index_runbook_job,
        file_path=file_path,
        name=name,
        tenant_id=tenant_id,
        description=description,
        content_type=content_type,
        job_timeout=600,
        result_ttl=86400,
    )
    return job.id


def process_alert_job(alert) -> dict[str, str]:
    """
    RQ job: runs the full RAG pipeline for a NormalisedAlert.
    Returns {incident_id, playbook_id}.
    """
    return asyncio.run(_process_alert_async(alert))


async def _process_alert_async(alert) -> dict[str, str]:
    from app.core.database import AsyncSessionLocal
    from app.notifications.notifier import send_incident_notification
    from app.rag.orchestrator import handle_alert

    async with AsyncSessionLocal() as session:
        try:
            incident, playbook = await handle_alert(session, alert)
            await session.commit()

            log.info(
                "alert_processed",
                incident_id=str(incident.id),
                playbook_id=str(playbook.id),
            )

            # Send Slack notification (fire and forget)
            try:
                await send_incident_notification(incident, playbook)
            except Exception as exc:
                log.warning("slack_notification_error", error=str(exc))

            return {"incident_id": str(incident.id), "playbook_id": str(playbook.id)}
        except Exception as exc:
            await session.rollback()
            log.error("alert_processing_failed", error=str(exc))
            raise


def index_runbook_job(
    file_path: str,
    name: str,
    tenant_id: str,
    description: Optional[str] = None,
    content_type: str = "text/markdown",
) -> str:
    """RQ job: runs the runbook embedding pipeline."""
    return asyncio.run(
        _index_runbook_async(
            file_path=file_path,
            name=name,
            tenant_id=tenant_id,
            description=description,
            content_type=content_type,
        )
    )


async def _index_runbook_async(
    file_path: str,
    name: str,
    tenant_id: str,
    description: Optional[str],
    content_type: str,
) -> str:
    from app.embeddings.ingest_runbook import ingest_file

    runbook_id = await ingest_file(
        file_path=file_path,
        name=name,
        tenant_id=tenant_id,
        description=description,
    )
    log.info("runbook_indexed_by_worker", runbook_id=str(runbook_id), name=name)
    return str(runbook_id)
