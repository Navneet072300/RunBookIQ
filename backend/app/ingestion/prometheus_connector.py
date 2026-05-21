"""
Prometheus / Alertmanager connector.

Exposes a webhook receiver endpoint (handled at the API layer) AND
provides a polling loop that calls /api/v2/alerts on Alertmanager directly.
"""
import asyncio
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)

ALERTMANAGER_ALERTS_PATH = "/api/v2/alerts"
POLL_INTERVAL_SECONDS = 30


async def fetch_firing_alerts(base_url: str) -> list[dict[str, Any]]:
    """Fetch currently firing alerts from Alertmanager REST API."""
    url = base_url.rstrip("/") + ALERTMANAGER_ALERTS_PATH
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params={"active": "true", "silenced": "false"})
        resp.raise_for_status()
        return resp.json()


def _alertmanager_to_webhook_format(
    alerts: list[dict[str, Any]]
) -> dict[str, Any]:
    """Convert GET /api/v2/alerts response to Alertmanager webhook format."""
    firing = []
    for a in alerts:
        status = a.get("status", {})
        if status.get("state") == "active":
            firing.append(
                {
                    "labels": a.get("labels", {}),
                    "annotations": a.get("annotations", {}),
                    "startsAt": a.get("startsAt", ""),
                    "endsAt": a.get("endsAt", ""),
                    "generatorURL": a.get("generatorURL", ""),
                    "fingerprint": a.get("fingerprint", ""),
                }
            )
    return {"alerts": firing, "status": "firing", "version": "4"}


async def start_prometheus_poller(
    ingest_callback, base_url: Optional[str] = None
) -> None:
    """
    Background polling loop — calls Alertmanager every POLL_INTERVAL_SECONDS
    and passes firing alerts to ingest_callback.
    """
    url = base_url or settings.prometheus_alertmanager_url
    if not url:
        log.warning("prometheus_poller_disabled", reason="no ALERTMANAGER_URL set")
        return

    log.info("prometheus_poller_starting", url=url)
    while True:
        try:
            raw_alerts = await fetch_firing_alerts(url)
            if raw_alerts:
                payload = _alertmanager_to_webhook_format(raw_alerts)
                await ingest_callback(payload, source="prometheus")
        except Exception as exc:
            log.error("prometheus_poll_error", error=str(exc))
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
