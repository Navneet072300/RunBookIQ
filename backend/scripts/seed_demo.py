#!/usr/bin/env python3
"""
Seed script: inserts 3 sample incidents + playbooks so the dashboard is not empty.

Usage:
  cd backend
  python ../scripts/seed_demo.py
"""
import asyncio
import sys
import os

# PYTHONPATH=/app is already set in the container; nothing extra needed here

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logging import configure_logging
from app.models.incident import Incident, IncidentStatus
from app.models.playbook_response import PlaybookResponse

configure_logging()

DEMO_INCIDENTS = [
    {
        "title": "[CRITICAL] OOMKill: redis-primary-0 in production",
        "description": "Container redis-primary-0 was OOMKilled due to exceeding memory limits (2Gi).",
        "severity": "critical",
        "source": "kubernetes",
        "status": IncidentStatus.OPEN,
        "labels": {
            "namespace": "production",
            "kind": "Pod",
            "name": "redis-primary-0",
            "cluster": "prod-us-east-1",
        },
        "alert_fingerprints": ["fp_oomkill_redis_001"],
        "opened_at": datetime.now(tz=timezone.utc) - timedelta(minutes=15),
        "playbook": {
            "probable_cause": (
                "The Redis pod exceeded its memory limit of 2Gi, triggering an OOMKill. "
                "Likely cause: a large keyspace scan or an RDB snapshot during peak load "
                "caused transient memory spike above the container limit."
            ),
            "severity_assessment": "critical",
            "runbook_steps": [
                {
                    "step": 1,
                    "action": "Confirm OOMKill event",
                    "description": "Check the pod's previous container logs and events for OOMKill reason.",
                    "command": "kubectl logs redis-primary-0 -n production --previous | tail -50",
                    "expected_outcome": "OOMKill or Out of memory message visible",
                },
                {
                    "step": 2,
                    "action": "Check current memory metrics",
                    "description": "Query Prometheus for current memory usage of the pod.",
                    "command": "kubectl top pod redis-primary-0 -n production",
                    "expected_outcome": "Memory usage near or at limit",
                },
                {
                    "step": 3,
                    "action": "Review Redis memory configuration",
                    "description": "Inspect the Redis maxmemory setting vs container limit.",
                    "command": "kubectl exec redis-primary-0 -n production -- redis-cli CONFIG GET maxmemory",
                    "expected_outcome": "maxmemory should be 80% of container limit",
                },
                {
                    "step": 4,
                    "action": "Check for large key scans",
                    "description": "Look for KEYS * or SCAN patterns in slowlog.",
                    "command": "kubectl exec redis-primary-0 -n production -- redis-cli SLOWLOG GET 10",
                    "expected_outcome": "No unexpectedly slow commands",
                },
                {
                    "step": 5,
                    "action": "Restart pod if still crashing",
                    "description": "Perform rolling restart to restore service.",
                    "command": "kubectl rollout restart deployment/redis -n production",
                    "expected_outcome": "New pod starts and becomes Ready",
                },
            ],
            "escalation_path": "On-call SRE (PagerDuty) → Database Team Lead → VP Engineering",
            "auto_remediation_suggestion": "restart_deployment",
            "remediation_command": "kubectl rollout restart deployment/redis -n production",
        },
    },
    {
        "title": "[HIGH] HighCPUThrottle: api-server deployment in staging",
        "description": "API server pods are being CPU throttled. p99 latency increased 3x.",
        "severity": "high",
        "source": "prometheus",
        "status": IncidentStatus.ACKNOWLEDGED,
        "labels": {
            "namespace": "staging",
            "deployment": "api-server",
            "cluster": "staging-us-west-2",
            "job": "api-server",
        },
        "alert_fingerprints": ["fp_cpu_throttle_api_002"],
        "opened_at": datetime.now(tz=timezone.utc) - timedelta(hours=2),
        "acknowledged_at": datetime.now(tz=timezone.utc) - timedelta(hours=1, minutes=45),
        "playbook": {
            "probable_cause": (
                "The api-server deployment has CPU limits set too low (250m) for current traffic. "
                "A recent deployment increased per-request CPU consumption by ~40% "
                "due to inefficient JSON serialisation in the new endpoint."
            ),
            "severity_assessment": "high",
            "runbook_steps": [
                {
                    "step": 1,
                    "action": "Identify throttled pods",
                    "description": "Check CPU throttle metrics via kubectl top.",
                    "command": "kubectl top pods -n staging -l app=api-server",
                    "expected_outcome": "All pods at or near CPU limit",
                },
                {
                    "step": 2,
                    "action": "Check recent deployment changes",
                    "description": "Review what changed in the last deployment.",
                    "command": "kubectl rollout history deployment/api-server -n staging",
                    "expected_outcome": "Recent revision with code changes visible",
                },
                {
                    "step": 3,
                    "action": "Temporarily scale up",
                    "description": "Add replicas to reduce per-pod load while investigating.",
                    "command": "kubectl scale deployment/api-server --replicas=6 -n staging",
                    "expected_outcome": "Latency returns to normal within 2 minutes",
                },
                {
                    "step": 4,
                    "action": "Profile CPU usage",
                    "description": "Run pprof or equivalent profiling on a pod.",
                    "command": "kubectl exec -it $(kubectl get pod -n staging -l app=api-server -o name | head -1) -n staging -- python -c 'import cProfile; cProfile.run(\"import app\")'",
                    "expected_outcome": "Hot functions identified",
                },
            ],
            "escalation_path": "On-call SRE → Backend Team Lead",
            "auto_remediation_suggestion": "scale_deployment",
            "remediation_command": "kubectl scale deployment/api-server --replicas=6 -n staging",
        },
    },
    {
        "title": "[WARNING] DiskUsageHigh: worker-node-3 at 85%",
        "description": "Node worker-node-3 disk usage has reached 85%. Eviction threshold at 90%.",
        "severity": "warning",
        "source": "zabbix",
        "status": IncidentStatus.RESOLVED,
        "labels": {
            "node": "worker-node-3",
            "host": "worker-node-3",
            "cluster": "prod-eu-west-1",
            "filesystem": "/dev/sda1",
        },
        "alert_fingerprints": ["fp_disk_node3_003"],
        "opened_at": datetime.now(tz=timezone.utc) - timedelta(hours=6),
        "resolved_at": datetime.now(tz=timezone.utc) - timedelta(hours=4),
        "playbook": {
            "probable_cause": (
                "Worker node disk filled due to unrotated container logs and stale Docker images. "
                "The log rotation policy was misconfigured to retain 14 days instead of 3 days."
            ),
            "severity_assessment": "warning",
            "runbook_steps": [
                {
                    "step": 1,
                    "action": "Identify disk consumers",
                    "description": "SSH to node and find top disk consumers.",
                    "command": "du -sh /var/log/containers/* | sort -rh | head -20",
                    "expected_outcome": "Large log files or many container directories",
                },
                {
                    "step": 2,
                    "action": "Clean stale images",
                    "description": "Remove unused Docker images to reclaim space.",
                    "command": "docker image prune -a --filter 'until=24h' -f",
                    "expected_outcome": "Several GB reclaimed",
                },
                {
                    "step": 3,
                    "action": "Rotate old logs",
                    "description": "Force log rotation to clear old container logs.",
                    "command": "logrotate -f /etc/logrotate.conf",
                    "expected_outcome": "Disk usage drops below 70%",
                },
                {
                    "step": 4,
                    "action": "Fix log rotation config",
                    "description": "Update logrotate config to retain only 3 days.",
                    "command": "sed -i 's/rotate 14/rotate 3/' /etc/logrotate.d/containers",
                    "expected_outcome": "Config updated, verify with: cat /etc/logrotate.d/containers",
                },
            ],
            "escalation_path": "On-call SRE → Infrastructure Team (if node needs cordon)",
            "auto_remediation_suggestion": "none",
            "remediation_command": None,
        },
    },
]


async def seed():
    async with AsyncSessionLocal() as session:
        for demo in DEMO_INCIDENTS:
            # Check if already seeded
            existing = await session.execute(
                select(Incident).where(Incident.title == demo["title"])
            )
            if existing.scalar_one_or_none():
                print(f"  Already exists: {demo['title'][:60]}")
                continue

            pb_data = demo.pop("playbook")

            incident = Incident(
                tenant_id="default",
                title=demo["title"],
                description=demo.get("description"),
                severity=demo["severity"],
                source=demo["source"],
                status=demo["status"],
                labels=demo["labels"],
                alert_fingerprints=demo["alert_fingerprints"],
                opened_at=demo["opened_at"],
                acknowledged_at=demo.get("acknowledged_at"),
                resolved_at=demo.get("resolved_at"),
            )
            session.add(incident)
            await session.flush()

            playbook = PlaybookResponse(
                tenant_id="default",
                incident_id=incident.id,
                probable_cause=pb_data["probable_cause"],
                severity_assessment=pb_data["severity_assessment"],
                runbook_steps=pb_data["runbook_steps"],
                escalation_path=pb_data["escalation_path"],
                auto_remediation_suggestion=pb_data["auto_remediation_suggestion"],
                remediation_command=pb_data.get("remediation_command"),
                retrieved_chunks=[],
                model_used="gemini-2.0-flash",
            )
            session.add(playbook)
            print(f"  Created: {incident.title[:60]}")

        await session.commit()
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
