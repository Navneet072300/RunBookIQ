import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlaybookResponse(Base):
    __tablename__ = "playbook_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True, unique=True
    )
    probable_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity_assessment: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    runbook_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    escalation_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_remediation_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remediation_command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remediation_approved: Mapped[bool] = mapped_column(default=False)
    remediation_executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    remediation_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retrieved_chunks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    raw_claude_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
