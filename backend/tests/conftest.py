"""
pytest fixtures for RunbookIQ tests.
"""
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.main import app
from app.api.deps import get_db, get_tenant_id

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with DB and tenant overrides."""
    async def override_db():
        yield db_session

    async def override_tenant():
        return "test-tenant"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_tenant_id] = override_tenant

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_anthropic_client():
    """Mock the Anthropic Claude API call."""
    with patch("app.rag.claude_caller.get_anthropic_client") as mock:
        client = AsyncMock()
        mock.return_value = client

        mock_response = AsyncMock()
        mock_response.content = [
            AsyncMock(
                text="""```json
{
  "probable_cause": "High memory usage caused OOMKill on pod redis-primary-0",
  "severity": "high",
  "runbook_steps": [
    {
      "step": 1,
      "action": "Check pod logs",
      "description": "Review recent logs for the affected pod",
      "command": "kubectl logs redis-primary-0 -n production --previous",
      "expected_outcome": "OOMKill event visible in logs"
    },
    {
      "step": 2,
      "action": "Check memory limits",
      "description": "Review resource limits for the deployment",
      "command": "kubectl describe pod redis-primary-0 -n production",
      "expected_outcome": "Memory limit and request values visible"
    }
  ],
  "escalation_path": "On-call SRE > Database Team Lead > VP Engineering",
  "auto_remediation_suggestion": "restart_deployment",
  "auto_remediation_details": "Restart the redis deployment to clear OOMKilled pods"
}
```"""
            )
        ]
        mock_response.usage = AsyncMock(input_tokens=500, output_tokens=300)
        mock_response.model = "claude-sonnet-4-20250514"
        client.messages.create = AsyncMock(return_value=mock_response)
        yield client


@pytest.fixture
def mock_embedder():
    """Mock the OpenAI embedding call."""
    with patch("app.embeddings.embedder.get_openai_client") as mock:
        client = AsyncMock()
        mock.return_value = client

        mock_response = AsyncMock()
        mock_response.data = [
            AsyncMock(embedding=[0.1] * 1536)
        ]
        client.embeddings.create = AsyncMock(return_value=mock_response)
        yield client


@pytest.fixture
def mock_redis():
    """Mock Redis for deduplication."""
    with patch("app.ingestion.normaliser.get_async_redis") as mock:
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.setex = AsyncMock(return_value=True)
        mock.return_value = redis
        yield redis


@pytest.fixture
def sample_prometheus_payload():
    return {
        "version": "4",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighMemoryUsage",
                    "severity": "high",
                    "namespace": "production",
                    "pod": "redis-primary-0",
                    "cluster": "prod-us-east",
                },
                "annotations": {
                    "description": "Pod redis-primary-0 memory usage is above 90%",
                    "summary": "High memory usage on redis-primary-0",
                },
                "startsAt": "2025-01-15T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
    }


@pytest.fixture
def sample_k8s_event():
    return {
        "reason": "OOMKilling",
        "message": "Memory limit reached for container redis",
        "type": "Warning",
        "involvedObject": {
            "kind": "Pod",
            "name": "redis-primary-0",
            "namespace": "production",
        },
        "metadata": {
            "namespace": "production",
            "labels": {},
        },
        "firstTimestamp": "2025-01-15T10:00:00Z",
    }
