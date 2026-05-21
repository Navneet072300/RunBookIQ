"""
POST /api/v1/alerts/ingest — receive alert payloads from any source.
Validates source type, deduplicates, and enqueues RAG processing via RQ.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.api.schemas import AlertIngestRequest, AlertIngestResponse
from app.core.logging import get_logger
from app.ingestion.normaliser import normalise_and_deduplicate
from app.workers.tasks import enqueue_alert_processing

router = APIRouter(prefix="/alerts", tags=["alerts"])
log = get_logger(__name__)


@router.post("/ingest", response_model=AlertIngestResponse, status_code=202)
async def ingest_alert(
    request: AlertIngestRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
):
    """
    Receive an alert payload from Prometheus, Kubernetes, or Zabbix.
    Deduplicates and enqueues async RAG processing.
    """
    effective_tenant = request.tenant_id or tenant_id

    log.info(
        "alert_ingest_received",
        source=request.source,
        tenant_id=effective_tenant,
    )

    try:
        alerts = await normalise_and_deduplicate(
            request.payload,
            source=request.source,
            tenant_id=effective_tenant,
        )
    except Exception as exc:
        log.error("normalisation_failed", source=request.source, error=str(exc))
        raise HTTPException(status_code=422, detail=f"Normalisation error: {exc}")

    total_received = 1
    deduplicated = total_received - len(alerts)
    incident_ids = []

    for alert in alerts:
        try:
            job_id = enqueue_alert_processing(alert)
            incident_ids.append(job_id)
            log.info(
                "alert_enqueued",
                alert_name=alert.alert_name,
                fingerprint=alert.fingerprint,
                job_id=job_id,
            )
        except Exception as exc:
            log.error(
                "enqueue_failed",
                alert_name=alert.alert_name,
                error=str(exc),
            )

    return AlertIngestResponse(
        accepted=len(alerts),
        deduplicated=deduplicated,
        incident_ids=incident_ids,
    )
