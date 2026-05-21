"""
Executes pre-approved kubectl commands with a mandatory dry-run first.
Runs in a subprocess with a strict timeout.
"""
import asyncio
import re
import shlex
from typing import Optional

from app.core.logging import get_logger

log = get_logger(__name__)

COMMAND_TIMEOUT_SECONDS = 60
ALLOWED_VERBS = {"rollout", "scale", "cordon", "uncordon"}

# Regex guard — prevents command injection via label values
_SAFE_ARG = re.compile(r"^[a-zA-Z0-9\-_/=.]+$")


def _validate_command(cmd: str) -> None:
    """Raise ValueError if command contains unsafe characters or disallowed verbs."""
    parts = shlex.split(cmd)
    if not parts or parts[0] != "kubectl":
        raise ValueError("Only kubectl commands are allowed")

    verb = parts[1] if len(parts) > 1 else ""
    if verb not in ALLOWED_VERBS:
        raise ValueError(f"kubectl verb '{verb}' is not in the allowlist: {ALLOWED_VERBS}")

    for arg in parts[2:]:
        if not _SAFE_ARG.match(arg):
            raise ValueError(f"Unsafe argument detected: {arg!r}")


async def _run_command(cmd: str, timeout: int = COMMAND_TIMEOUT_SECONDS) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    parts = shlex.split(cmd)
    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, "", f"Command timed out after {timeout}s"

    return proc.returncode, stdout.decode(), stderr.decode()


async def execute_remediation(
    command: str,
    dry_run: bool = True,
) -> dict:
    """
    Execute a remediation command.
    Always runs dry-run first; if that succeeds, optionally runs live.

    Returns dict: {success, dry_run_output, live_output, error}
    """
    try:
        _validate_command(command)
    except ValueError as exc:
        log.error("command_validation_failed", command=command, error=str(exc))
        return {"success": False, "error": str(exc), "dry_run_output": "", "live_output": ""}

    # Dry run first
    dry_cmd = command + " --dry-run=client"
    log.info("remediation_dry_run", command=dry_cmd)
    rc, stdout, stderr = await _run_command(dry_cmd)

    if rc != 0:
        log.error("dry_run_failed", command=dry_cmd, rc=rc, stderr=stderr)
        return {
            "success": False,
            "error": f"Dry-run failed (rc={rc}): {stderr}",
            "dry_run_output": stdout or stderr,
            "live_output": "",
        }

    dry_output = stdout or stderr
    log.info("dry_run_succeeded", command=dry_cmd, output=dry_output[:200])

    if dry_run:
        return {
            "success": True,
            "dry_run_output": dry_output,
            "live_output": "",
            "error": None,
        }

    # Live execution
    log.info("remediation_executing", command=command)
    rc, stdout, stderr = await _run_command(command)

    if rc != 0:
        log.error("remediation_failed", command=command, rc=rc, stderr=stderr)
        return {
            "success": False,
            "error": f"Execution failed (rc={rc}): {stderr}",
            "dry_run_output": dry_output,
            "live_output": stdout or stderr,
        }

    log.info("remediation_succeeded", command=command, output=stdout[:200])
    return {
        "success": True,
        "dry_run_output": dry_output,
        "live_output": stdout or stderr,
        "error": None,
    }
