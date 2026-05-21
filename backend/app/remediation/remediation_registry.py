"""
Maps auto_remediation_suggestion values from Claude to concrete kubectl commands.
Human approval gate is enforced at the API layer before execution.
"""
from typing import Any, Optional

from app.core.logging import get_logger

log = get_logger(__name__)

# Mapping from suggestion key -> command template
REMEDIATION_TEMPLATES: dict[str, str] = {
    "restart_deployment": (
        "kubectl rollout restart deployment/{deployment} -n {namespace}"
    ),
    "scale_deployment": (
        "kubectl scale deployment/{deployment} --replicas={replicas} -n {namespace}"
    ),
    "cordon_node": "kubectl cordon {node}",
    "rollback_deployment": (
        "kubectl rollout undo deployment/{deployment} -n {namespace}"
    ),
}

# Safe pre-approved commands (allowed for auto-execution after approval)
SAFE_SUGGESTIONS = {"restart_deployment", "cordon_node", "rollback_deployment"}


def get_remediation_command(
    suggestion: str,
    labels: dict[str, str],
    namespace: str = "default",
    replicas: int = 1,
) -> Optional[str]:
    """
    Build the concrete remediation command from suggestion + context labels.
    Returns None if suggestion is 'none' or unmapped.
    """
    if suggestion == "none" or suggestion not in REMEDIATION_TEMPLATES:
        return None

    template = REMEDIATION_TEMPLATES[suggestion]

    deployment = (
        labels.get("deployment")
        or labels.get("app")
        or labels.get("name")
        or "UNKNOWN_DEPLOYMENT"
    )
    node = labels.get("node") or labels.get("kubernetes_node") or "UNKNOWN_NODE"

    cmd = template.format(
        deployment=deployment,
        namespace=namespace,
        node=node,
        replicas=replicas,
    )
    log.debug("remediation_command_built", suggestion=suggestion, command=cmd)
    return cmd


def is_safe_suggestion(suggestion: str) -> bool:
    return suggestion in SAFE_SUGGESTIONS
