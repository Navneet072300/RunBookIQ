"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # alert_events
    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "source",
            sa.Enum("kubernetes", "prometheus", "zabbix", "manual", name="alertsource"),
            nullable=False,
        ),
        sa.Column("alert_name", sa.String(256), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "critical", "high", "warning", "info", "unknown", name="alertseverity"
            ),
            nullable=False,
        ),
        sa.Column("namespace", sa.String(128), nullable=True),
        sa.Column("cluster", sa.String(128), nullable=True),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "annotations", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_events_tenant_id", "alert_events", ["tenant_id"])
    op.create_index("ix_alert_events_fingerprint", "alert_events", ["fingerprint"])
    op.create_index("ix_alert_events_incident_id", "alert_events", ["incident_id"])
    op.create_index(
        "ix_alert_events_tenant_fingerprint",
        "alert_events",
        ["tenant_id", "fingerprint"],
    )
    op.create_index(
        "ix_alert_events_tenant_source", "alert_events", ["tenant_id", "source"]
    )
    op.create_index("ix_alert_events_fired_at", "alert_events", ["fired_at"])

    # incidents
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "acknowledged",
                "resolved",
                "suppressed",
                name="incidentstatus",
            ),
            nullable=False,
        ),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("assigned_to", sa.String(256), nullable=True),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "alert_fingerprints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_tenant_id", "incidents", ["tenant_id"])
    op.create_index(
        "ix_incidents_tenant_status", "incidents", ["tenant_id", "status"]
    )
    op.create_index("ix_incidents_opened_at", "incidents", ["opened_at"])

    # playbook_responses
    op.create_table(
        "playbook_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("probable_cause", sa.Text(), nullable=True),
        sa.Column("severity_assessment", sa.String(32), nullable=True),
        sa.Column(
            "runbook_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("escalation_path", sa.Text(), nullable=True),
        sa.Column("auto_remediation_suggestion", sa.Text(), nullable=True),
        sa.Column("remediation_command", sa.Text(), nullable=True),
        sa.Column("remediation_approved", sa.Boolean(), nullable=False, default=False),
        sa.Column("remediation_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remediation_result", sa.Text(), nullable=True),
        sa.Column(
            "retrieved_chunks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("raw_claude_response", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id"),
    )
    op.create_index(
        "ix_playbook_responses_tenant_id", "playbook_responses", ["tenant_id"]
    )
    op.create_index(
        "ix_playbook_responses_incident_id", "playbook_responses", ["incident_id"]
    )

    # runbooks
    op.create_table(
        "runbooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, default=0),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runbooks_tenant_id", "runbooks", ["tenant_id"])
    op.create_index("ix_runbooks_tenant_name", "runbooks", ["tenant_id", "name"])

    # runbook_chunks
    op.create_table(
        "runbook_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("runbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, default=0),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runbook_chunks_tenant_id", "runbook_chunks", ["tenant_id"])
    op.create_index("ix_runbook_chunks_runbook_id", "runbook_chunks", ["runbook_id"])
    # HNSW index for cosine similarity search
    op.execute(
        """
        CREATE INDEX ix_runbook_chunks_embedding_hnsw
        ON runbook_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.drop_table("runbook_chunks")
    op.drop_table("runbooks")
    op.drop_table("playbook_responses")
    op.drop_table("incidents")
    op.drop_table("alert_events")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP TYPE IF EXISTS alertsource")
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS incidentstatus")
