"""Tests for API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_health_check(client):
    with patch("app.core.redis.get_async_redis") as mock_redis:
        r = AsyncMock()
        r.ping = AsyncMock(return_value=True)
        mock_redis.return_value = r
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_list_incidents_empty(client):
    resp = await client.get("/api/v1/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_incident_not_found(client):
    resp = await client.get("/api/v1/incidents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_runbooks_empty(client):
    resp = await client.get("/api/v1/runbooks")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_ingest_alert_unknown_source(client):
    with patch("app.core.redis.get_async_redis") as mock_redis:
        r = AsyncMock()
        r.exists = AsyncMock(return_value=0)
        r.setex = AsyncMock()
        mock_redis.return_value = r

        resp = await client.post(
            "/api/v1/alerts/ingest",
            json={"payload": {}, "source": "invalid_source"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_prometheus_alert(client, sample_prometheus_payload, mock_redis):
    with patch("app.ingestion.normaliser.get_async_redis", return_value=mock_redis):
        with patch("app.workers.tasks.enqueue_alert_processing", return_value="job-123"):
            resp = await client.post(
                "/api/v1/alerts/ingest",
                json={"payload": sample_prometheus_payload, "source": "prometheus"},
            )
    assert resp.status_code == 202
    data = resp.json()
    assert data["accepted"] == 1
    assert data["deduplicated"] == 0
