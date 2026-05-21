"""
Normalises raw alert payloads from any source into a canonical AlertEvent.

Deduplication: SHA-256 fingerprint of (source + alertname + sorted labels).
If the fingerprint exists in Redis with TTL > 0, the alert is a duplicate.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_async_redis
from app.models.alert_event import AlertSeverity, AlertSource

settings = get_settings()
log = get_logger(__name__)

SEVERITY_MAP: dict[str, AlertSeverity] = {
    "critical": AlertSeverity.CRITICAL,
    "high": AlertSeverity.HIGH,
    "error": AlertSeverity.HIGH,
    "warning": AlertSeverity.WARNING,
    "warn": AlertSeverity.WARNING,
    "average": AlertSeverity.WARNING,
    "information": AlertSeverity.INFO,
    "info": AlertSeverity.INFO,
    "low": AlertSeverity.INFO,
    "not classified": AlertSeverity.UNKNOWN,
}


class NormalisedAlert:
    """Canonical in-memory representation before DB write."""

    def __init__(
        self,
        *,
        tenant_id: str,
        fingerprint: str,
        source: AlertSource,
        alert_name: str,
        severity: AlertSeverity,
        namespace: Optional[str],
        cluster: Optional[str],
        labels: dict[str, str],
        annotations: dict[str, str],
        raw_payload: dict[str, Any],
        description: Optional[str],
        fired_at: datetime,
        resolved_at: Optional[datetime] = None,
    ):
        self.id = uuid4()
        self.tenant_id = tenant_id
        self.fingerprint = fingerprint
        self.source = source
        self.alert_name = alert_name
        self.severity = severity
        self.namespace = namespace
        self.cluster = cluster
        self.labels = labels
        self.annotations = annotations
        self.raw_payload = raw_payload
        self.description = description
        self.fired_at = fired_at
        self.resolved_at = resolved_at


def compute_fingerprint(source: str, alert_name: str, labels: dict[str, Any]) -> str:
    sorted_labels = json.dumps(dict(sorted(labels.items())), sort_keys=True)
    raw = f"{source}:{alert_name}:{sorted_labels}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def is_duplicate(fingerprint: str, tenant_id: str) -> bool:
    redis = get_async_redis()
    key = f"dedup:{tenant_id}:{fingerprint}"
    exists = await redis.exists(key)
    return bool(exists)


async def mark_seen(fingerprint: str, tenant_id: str) -> None:
    redis = get_async_redis()
    key = f"dedup:{tenant_id}:{fingerprint}"
    await redis.setex(key, settings.dedup_ttl_seconds, "1")


def _map_severity(raw: Optional[str]) -> AlertSeverity:
    if raw is None:
        return AlertSeverity.UNKNOWN
    return SEVERITY_MAP.get(raw.lower().strip(), AlertSeverity.UNKNOWN)


def normalise_prometheus(
    payload: dict[str, Any], tenant_id: str
) -> list[NormalisedAlert]:
    """Parse Alertmanager webhook payload (may contain multiple alerts)."""
    alerts = payload.get("alerts", [])
    result: list[NormalisedAlert] = []

    for alert in alerts:
        labels: dict[str, str] = alert.get("labels", {})
        annotations: dict[str, str] = alert.get("annotations", {})
        alert_name = labels.get("alertname", "unknown")
        severity_raw = labels.get("severity", labels.get("priority", None))
        namespace = labels.get("namespace", None)
        cluster = labels.get("cluster", labels.get("kubernetes_cluster", None))

        fingerprint = compute_fingerprint("prometheus", alert_name, labels)
        fired_at_str = alert.get("startsAt")
        fired_at = (
            datetime.fromisoformat(fired_at_str.replace("Z", "+00:00"))
            if fired_at_str
            else datetime.now(tz=timezone.utc)
        )
        ends_at_str = alert.get("endsAt")
        resolved_at = None
        if ends_at_str and ends_at_str != "0001-01-01T00:00:00Z":
            resolved_at = datetime.fromisoformat(ends_at_str.replace("Z", "+00:00"))

        result.append(
            NormalisedAlert(
                tenant_id=tenant_id,
                fingerprint=fingerprint,
                source=AlertSource.PROMETHEUS,
                alert_name=alert_name,
                severity=_map_severity(severity_raw),
                namespace=namespace,
                cluster=cluster,
                labels=labels,
                annotations=annotations,
                raw_payload=alert,
                description=annotations.get("description", annotations.get("summary")),
                fired_at=fired_at,
                resolved_at=resolved_at,
            )
        )
    return result


def normalise_kubernetes(
    event: dict[str, Any], tenant_id: str
) -> Optional[NormalisedAlert]:
    """Parse a K8s event object."""
    reason = event.get("reason", "Unknown")
    message = event.get("message", "")
    involved = event.get("involvedObject", {})
    namespace = involved.get("namespace") or event.get("metadata", {}).get("namespace")
    labels: dict[str, str] = event.get("metadata", {}).get("labels") or {}
    labels.setdefault("kind", involved.get("kind", ""))
    labels.setdefault("name", involved.get("name", ""))
    labels.setdefault("namespace", namespace or "")

    event_type = event.get("type", "Normal")
    severity = AlertSeverity.INFO
    if event_type == "Warning":
        severity = AlertSeverity.WARNING
    if reason.lower() in ("failed", "backoff", "unhealthy", "oomkilling"):
        severity = AlertSeverity.HIGH

    fingerprint = compute_fingerprint("kubernetes", reason, labels)
    first_time = event.get("firstTimestamp") or event.get("eventTime")
    fired_at = (
        datetime.fromisoformat(first_time.replace("Z", "+00:00"))
        if first_time
        else datetime.now(tz=timezone.utc)
    )

    return NormalisedAlert(
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        source=AlertSource.KUBERNETES,
        alert_name=reason,
        severity=severity,
        namespace=namespace,
        cluster=None,
        labels=labels,
        annotations={},
        raw_payload=event,
        description=message,
        fired_at=fired_at,
    )


def normalise_zabbix(
    problem: dict[str, Any], tenant_id: str
) -> Optional[NormalisedAlert]:
    """Parse a Zabbix problem.get result entry."""
    name = problem.get("name", "unknown")
    severity_int = int(problem.get("severity", 0))
    severity_map = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.INFO,
        2: AlertSeverity.WARNING,
        3: AlertSeverity.WARNING,
        4: AlertSeverity.HIGH,
        5: AlertSeverity.CRITICAL,
    }
    severity = severity_map.get(severity_int, AlertSeverity.UNKNOWN)
    labels: dict[str, str] = {
        "host": problem.get("hosts", [{}])[0].get("host", ""),
        "triggerid": str(problem.get("objectid", "")),
        "eventid": str(problem.get("eventid", "")),
    }
    fingerprint = compute_fingerprint("zabbix", name, labels)
    clock = problem.get("clock")
    fired_at = (
        datetime.fromtimestamp(int(clock), tz=timezone.utc)
        if clock
        else datetime.now(tz=timezone.utc)
    )
    return NormalisedAlert(
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        source=AlertSource.ZABBIX,
        alert_name=name,
        severity=severity,
        namespace=None,
        cluster=None,
        labels=labels,
        annotations={},
        raw_payload=problem,
        description=problem.get("description", name),
        fired_at=fired_at,
    )


async def normalise_and_deduplicate(
    raw_payload: dict[str, Any],
    source: str,
    tenant_id: str,
) -> list[NormalisedAlert]:
    """Entry point: normalise payload and filter duplicates."""
    alerts: list[NormalisedAlert] = []

    if source == "prometheus":
        alerts = normalise_prometheus(raw_payload, tenant_id)
    elif source == "kubernetes":
        alert = normalise_kubernetes(raw_payload, tenant_id)
        if alert:
            alerts = [alert]
    elif source == "zabbix":
        alert = normalise_zabbix(raw_payload, tenant_id)
        if alert:
            alerts = [alert]
    else:
        log.warning("unknown_source", source=source)
        return []

    unique: list[NormalisedAlert] = []
    for alert in alerts:
        if await is_duplicate(alert.fingerprint, tenant_id):
            log.info(
                "alert_deduplicated",
                fingerprint=alert.fingerprint,
                alert_name=alert.alert_name,
            )
            continue
        await mark_seen(alert.fingerprint, tenant_id)
        unique.append(alert)

    return unique
