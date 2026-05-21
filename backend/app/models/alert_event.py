import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"
    UNKNOWN = "unknown"


class AlertSource(str, enum.Enum):
    KUBERNETES = "kubernetes"
    PROMETHEUS = "prometheus"
    ZABBIX = "zabbix"
    MANUAL = "manual"


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[AlertSource] = mapped_column(
        Enum(AlertSource, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    alert_name: Mapped[str] = mapped_column(String(256), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AlertSeverity.UNKNOWN,
    )
    namespace: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    cluster: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    annotations: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    incident_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_alert_events_tenant_fingerprint", "tenant_id", "fingerprint"),
        Index("ix_alert_events_tenant_source", "tenant_id", "source"),
        Index("ix_alert_events_fired_at", "fired_at"),
    )
