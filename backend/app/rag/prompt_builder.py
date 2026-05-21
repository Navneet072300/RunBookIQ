"""
Builds the system + user prompt for Claude.
"""
import json
from typing import Any

from app.ingestion.normaliser import NormalisedAlert

SYSTEM_PROMPT = """\
You are an expert Site Reliability Engineer (SRE) and DevOps specialist with deep knowledge \
of Kubernetes, Prometheus alerting, infrastructure operations, and incident management.

Given an infrastructure alert and relevant runbook sections, your task is to produce a \
structured incident triage playbook.

You MUST respond with valid JSON matching this exact schema:
{
  "probable_cause": "A concise explanation of what likely caused this alert",
  "severity": "critical|high|warning|info",
  "runbook_steps": [
    {
      "step": 1,
      "action": "Short imperative action title",
      "description": "Detailed description of the step",
      "command": "Optional: exact command to run",
      "expected_outcome": "What you expect to see after this step"
    }
  ],
  "escalation_path": "Who to page and under what conditions (e.g., on-call SRE > Team Lead > VP Eng)",
  "auto_remediation_suggestion": "One of: restart_deployment|scale_deployment|cordon_node|rollback_deployment|none",
  "auto_remediation_details": "Human-readable explanation of the suggested auto-remediation"
}

Rules:
- runbook_steps should be ordered triage steps (5-10 steps typical)
- Be specific: include real kubectl commands, Prometheus queries, log grep patterns
- auto_remediation_suggestion MUST be one of the allowed values exactly
- If no runbook context is available, reason from first principles
- severity should reflect actual impact, not just the alert label
"""


def build_prompt(
    alert: NormalisedAlert,
    retrieved_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build the messages list for the Claude API call.
    Returns [{"role": "user", "content": "..."}]
    """
    # Format alert context
    alert_context = {
        "alert_name": alert.alert_name,
        "source": alert.source.value,
        "severity": alert.severity.value,
        "namespace": alert.namespace,
        "cluster": alert.cluster,
        "description": alert.description,
        "labels": alert.labels,
        "annotations": alert.annotations,
        "fired_at": alert.fired_at.isoformat(),
    }

    # Format retrieved chunks
    chunks_text = ""
    if retrieved_chunks:
        chunks_text = "\n\n## Relevant Runbook Sections\n"
        for i, chunk in enumerate(retrieved_chunks, 1):
            score_pct = int(chunk["score"] * 100)
            chunks_text += (
                f"\n### Runbook Section {i} (relevance: {score_pct}%)\n"
                f"{chunk['content']}\n"
            )
    else:
        chunks_text = "\n\n## Runbook Context\nNo matching runbook sections found. Use general SRE knowledge.\n"

    user_message = f"""\
## Incident Alert

```json
{json.dumps(alert_context, indent=2, default=str)}
```
{chunks_text}

Please generate a structured triage playbook for this incident.
"""

    return [{"role": "user", "content": user_message}]
