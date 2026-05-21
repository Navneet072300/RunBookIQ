"""
Pydantic schemas for API request/response validation.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Alert Ingest ──────────────────────────────────────────────────────────────

class AlertIngestRequest(BaseModel):
    payload: dict[str, Any]
    source: str = Field(..., pattern="^(prometheus|kubernetes|zabbix|manual)$")
    tenant_id: Optional[str] = None


class AlertIngestResponse(BaseModel):
    accepted: int
    deduplicated: int
    incident_ids: list[str]


# ── Incidents ─────────────────────────────────────────────────────────────────

class IncidentListItem(BaseModel):
    id: uuid.UUID
    title: str
    severity: str
    status: str
    source: str
    opened_at: datetime
    resolved_at: Optional[datetime] = None
    has_playbook: bool = False

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    items: list[IncidentListItem]
    total: int
    page: int
    page_size: int


class PlaybookStep(BaseModel):
    step: int
    action: str
    description: str
    command: Optional[str] = None
    expected_outcome: Optional[str] = None


class PlaybookDetail(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    probable_cause: Optional[str] = None
    severity_assessment: Optional[str] = None
    runbook_steps: list[dict[str, Any]] = []
    escalation_path: Optional[str] = None
    auto_remediation_suggestion: Optional[str] = None
    remediation_approved: bool = False
    remediation_executed_at: Optional[datetime] = None
    remediation_result: Optional[str] = None
    model_used: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentDetail(BaseModel):
    id: uuid.UUID
    tenant_id: str
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    source: str
    assigned_to: Optional[str] = None
    labels: dict[str, Any] = {}
    alert_fingerprints: list[str] = []
    opened_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    playbook: Optional[PlaybookDetail] = None

    model_config = {"from_attributes": True}


class IncidentUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None


# ── Runbooks ──────────────────────────────────────────────────────────────────

class RunbookListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    content_type: str
    chunk_count: int
    last_indexed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunbookListResponse(BaseModel):
    items: list[RunbookListItem]
    total: int


# ── Remediation ───────────────────────────────────────────────────────────────

class RemediationApproveResponse(BaseModel):
    incident_id: uuid.UUID
    command: str
    dry_run_output: str
    live_output: str
    success: bool
    error: Optional[str] = None
