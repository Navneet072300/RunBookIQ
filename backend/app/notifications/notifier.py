"""
Slack notifier — sends incident alerts using Block Kit formatted messages.
"""
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.incident import Incident
from app.models.playbook_response import PlaybookResponse

settings = get_settings()
log = get_logger(__name__)

SEVERITY_EMOJI = {
    "critical": ":red_circle:",
    "high": ":large_orange_circle:",
    "warning": ":large_yellow_circle:",
    "info": ":large_blue_circle:",
    "unknown": ":white_circle:",
}


def _severity_color(severity: str) -> str:
    colors = {
        "critical": "#FF0000",
        "high": "#FF6600",
        "warning": "#FFCC00",
        "info": "#0099FF",
        "unknown": "#CCCCCC",
    }
    return colors.get(severity.lower(), "#CCCCCC")


def build_incident_blocks(
    incident: Incident,
    playbook: Optional[PlaybookResponse],
    base_url: str = "",
) -> list[dict[str, Any]]:
    """Build Slack Block Kit blocks for an incident notification."""
    emoji = SEVERITY_EMOJI.get(incident.severity.lower(), ":white_circle:")
    incident_url = f"{base_url}/incidents/{incident.id}" if base_url else ""

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} New Incident: {incident.title[:150]}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Severity:*\n{incident.severity.upper()}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Source:*\n{incident.source.capitalize()}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\n{incident.status.value.capitalize()}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Namespace:*\n{incident.labels.get('namespace', 'N/A')}",
                },
            ],
        },
    ]

    if playbook and playbook.probable_cause:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Probable Cause:*\n{playbook.probable_cause[:500]}",
                },
            }
        )

    if playbook and playbook.escalation_path:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Escalation Path:*\n{playbook.escalation_path[:300]}",
                },
            }
        )

    if incident_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Playbook"},
                        "url": incident_url,
                        "style": "primary",
                    }
                ],
            }
        )

    return blocks


async def send_incident_notification(
    incident: Incident,
    playbook: Optional[PlaybookResponse] = None,
    webhook_url: Optional[str] = None,
    base_url: str = "",
) -> bool:
    """Send a Slack notification for a new incident. Returns True on success."""
    url = webhook_url or settings.slack_webhook_url
    if not url:
        log.debug("slack_notification_skipped", reason="no webhook URL configured")
        return False

    blocks = build_incident_blocks(incident, playbook, base_url)
    payload = {
        "attachments": [
            {
                "color": _severity_color(incident.severity),
                "blocks": blocks,
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        log.info(
            "slack_notification_sent",
            incident_id=str(incident.id),
            severity=incident.severity,
        )
        return True
    except Exception as exc:
        log.error(
            "slack_notification_failed",
            incident_id=str(incident.id),
            error=str(exc),
        )
        return False
