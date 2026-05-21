"""
Tests for the RAG orchestrator using mocked Claude and embedding calls.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.normaliser import NormalisedAlert
from app.models.alert_event import AlertSeverity, AlertSource


def make_alert(
    alert_name: str = "HighMemoryUsage",
    severity: AlertSeverity = AlertSeverity.HIGH,
    namespace: str = "production",
) -> NormalisedAlert:
    return NormalisedAlert(
        tenant_id="test-tenant",
        fingerprint="abc123",
        source=AlertSource.PROMETHEUS,
        alert_name=alert_name,
        severity=severity,
        namespace=namespace,
        cluster="prod-cluster",
        labels={"namespace": namespace, "job": "api-server"},
        annotations={"description": "Memory usage above threshold"},
        raw_payload={},
        description="Memory usage above threshold",
        fired_at=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_orchestrator_creates_incident_and_playbook(
    db_session, mock_anthropic_client, mock_embedder
):
    """Full orchestrator run should create both Incident and PlaybookResponse."""
    from app.rag.orchestrator import handle_alert

    with patch("app.embeddings.embedder.get_openai_client", return_value=mock_embedder):
        with patch(
            "app.rag.claude_caller.get_anthropic_client",
            return_value=mock_anthropic_client,
        ):
            alert = make_alert()
            incident, playbook = await handle_alert(db_session, alert)

    assert incident.id is not None
    assert incident.title == "[HIGH] HighMemoryUsage"
    assert incident.severity == "high"
    assert incident.source == "prometheus"

    assert playbook.incident_id == incident.id
    assert playbook.probable_cause is not None
    assert len(playbook.runbook_steps) > 0
    assert playbook.auto_remediation_suggestion == "restart_deployment"


@pytest.mark.asyncio
async def test_orchestrator_handles_claude_failure(db_session, mock_embedder):
    """Orchestrator should still create an incident even if Claude fails."""
    from app.rag.orchestrator import handle_alert

    mock_claude = AsyncMock()
    mock_claude.messages.create = AsyncMock(side_effect=RuntimeError("Claude API unavailable"))

    with patch("app.embeddings.embedder.get_openai_client", return_value=mock_embedder):
        with patch(
            "app.rag.claude_caller.get_anthropic_client", return_value=mock_claude
        ):
            alert = make_alert()
            incident, playbook = await handle_alert(db_session, alert)

    assert incident.id is not None
    assert "Claude unavailable" in (playbook.probable_cause or "")


@pytest.mark.asyncio
async def test_orchestrator_invalid_remediation_suggestion(
    db_session, mock_embedder
):
    """Orchestrator should sanitise invalid auto_remediation_suggestion to 'none'."""
    from app.rag.orchestrator import handle_alert

    mock_claude = AsyncMock()
    mock_response = AsyncMock()
    mock_response.content = [
        AsyncMock(
            text='{"probable_cause": "test", "severity": "high", "runbook_steps": [], '
            '"escalation_path": "SRE", "auto_remediation_suggestion": "rm -rf /",'
            '"auto_remediation_details": "malicious"}'
        )
    ]
    mock_response.usage = AsyncMock(input_tokens=100, output_tokens=50)
    mock_response.model = "claude-test"
    mock_claude.messages.create = AsyncMock(return_value=mock_response)

    with patch("app.embeddings.embedder.get_openai_client", return_value=mock_embedder):
        with patch(
            "app.rag.claude_caller.get_anthropic_client", return_value=mock_claude
        ):
            alert = make_alert()
            incident, playbook = await handle_alert(db_session, alert)

    assert playbook.auto_remediation_suggestion == "none"
    assert playbook.remediation_command is None


def test_prompt_builder_includes_alert_context():
    """Prompt builder should embed alert name and severity in the user message."""
    from app.rag.prompt_builder import build_prompt

    alert = make_alert(alert_name="DiskFull", severity=AlertSeverity.CRITICAL)
    chunks = [
        {
            "content": "When disk is full, check inode usage with df -i",
            "score": 0.92,
            "runbook_id": "abc",
        }
    ]
    messages = build_prompt(alert, chunks)
    assert len(messages) == 1
    content = messages[0]["content"]
    assert "DiskFull" in content
    assert "critical" in content
    assert "inode usage" in content


def test_prompt_builder_no_chunks():
    """Prompt builder should handle empty chunk list gracefully."""
    from app.rag.prompt_builder import build_prompt

    alert = make_alert()
    messages = build_prompt(alert, [])
    content = messages[0]["content"]
    assert "No matching runbook sections" in content


def test_claude_caller_json_extraction():
    """_extract_json should handle raw JSON, fenced JSON, and bare objects."""
    from app.rag.claude_caller import _extract_json

    # Raw JSON
    raw = '{"probable_cause": "test", "severity": "high"}'
    result = _extract_json(raw)
    assert result["probable_cause"] == "test"

    # Fenced JSON
    fenced = '```json\n{"probable_cause": "fenced", "severity": "critical"}\n```'
    result = _extract_json(fenced)
    assert result["probable_cause"] == "fenced"

    # Invalid — returns fallback
    bad = "This is not JSON at all!"
    result = _extract_json(bad)
    assert "probable_cause" in result
    assert result["auto_remediation_suggestion"] == "none"
