"""Tests for the alert normaliser and deduplication logic."""
import pytest

from app.ingestion.normaliser import (
    NormalisedAlert,
    compute_fingerprint,
    normalise_kubernetes,
    normalise_prometheus,
    normalise_zabbix,
)
from app.models.alert_event import AlertSeverity, AlertSource


def test_compute_fingerprint_deterministic():
    fp1 = compute_fingerprint("prometheus", "HighCPU", {"namespace": "prod", "job": "api"})
    fp2 = compute_fingerprint("prometheus", "HighCPU", {"job": "api", "namespace": "prod"})
    assert fp1 == fp2, "Fingerprint must be order-independent"


def test_compute_fingerprint_different_inputs():
    fp1 = compute_fingerprint("prometheus", "HighCPU", {"namespace": "prod"})
    fp2 = compute_fingerprint("prometheus", "HighMemory", {"namespace": "prod"})
    assert fp1 != fp2


def test_normalise_prometheus(sample_prometheus_payload):
    alerts = normalise_prometheus(sample_prometheus_payload, "tenant1")
    assert len(alerts) == 1
    a = alerts[0]
    assert a.source == AlertSource.PROMETHEUS
    assert a.alert_name == "HighMemoryUsage"
    assert a.severity == AlertSeverity.HIGH
    assert a.namespace == "production"
    assert a.cluster == "prod-us-east"
    assert a.tenant_id == "tenant1"
    assert a.fingerprint != ""


def test_normalise_prometheus_empty():
    result = normalise_prometheus({"alerts": []}, "tenant1")
    assert result == []


def test_normalise_kubernetes(sample_k8s_event):
    alert = normalise_kubernetes(sample_k8s_event, "tenant1")
    assert alert is not None
    assert alert.source == AlertSource.KUBERNETES
    assert alert.alert_name == "OOMKilling"
    assert alert.severity == AlertSeverity.HIGH
    assert alert.namespace == "production"
    assert "redis-primary-0" in alert.labels.get("name", "")


def test_normalise_zabbix():
    problem = {
        "eventid": "12345",
        "objectid": "67890",
        "name": "Disk space is low",
        "severity": "4",
        "clock": "1705312800",
        "hosts": [{"host": "web-server-01", "hostid": "100"}],
    }
    alert = normalise_zabbix(problem, "tenant1")
    assert alert is not None
    assert alert.source == AlertSource.ZABBIX
    assert alert.alert_name == "Disk space is low"
    assert alert.severity == AlertSeverity.HIGH
    assert alert.labels["host"] == "web-server-01"


@pytest.mark.asyncio
async def test_deduplication(mock_redis, sample_prometheus_payload):
    from app.ingestion.normaliser import normalise_and_deduplicate

    # First call — should pass through
    result = await normalise_and_deduplicate(
        sample_prometheus_payload, "prometheus", "tenant1"
    )
    assert len(result) == 1

    # Simulate Redis returning 1 (key exists) for duplicate
    mock_redis.exists.return_value = 1
    result2 = await normalise_and_deduplicate(
        sample_prometheus_payload, "prometheus", "tenant1"
    )
    assert len(result2) == 0, "Duplicate alert should be filtered"
