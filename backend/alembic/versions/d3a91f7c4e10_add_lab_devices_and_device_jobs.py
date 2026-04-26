"""add lab devices and device jobs

Revision ID: d3a91f7c4e10
Revises: cc8b4a6f0d9e
Create Date: 2026-04-26 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d3a91f7c4e10"
down_revision: Union[str, Sequence[str], None] = "cc8b4a6f0d9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PostgreSQL has no CREATE TYPE IF NOT EXISTS, so wrap each in a DO block
    # to make the migration re-runnable after a partial failure. asyncpg
    # rejects multi-statement prepared queries, so issue them separately.
    op.execute(
        "DO $$ BEGIN CREATE TYPE device_type AS ENUM ('printer_3d'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE device_status AS ENUM "
        "('idle', 'busy', 'offline', 'error'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE device_job_status AS ENUM "
        "('queued', 'running', 'complete', 'failed', 'cancelled'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )

    # `create_type=False` keeps op.create_table from re-issuing CREATE TYPE.
    device_type = postgresql.ENUM(
        "printer_3d", name="device_type", create_type=False
    )
    device_status = postgresql.ENUM(
        "idle", "busy", "offline", "error", name="device_status", create_type=False
    )
    job_status = postgresql.ENUM(
        "queued", "running", "complete", "failed", "cancelled",
        name="device_job_status", create_type=False,
    )

    op.create_table(
        "lab_devices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("laboratory_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("device_type", device_type, nullable=False),
        sa.Column("status", device_status, nullable=False, server_default="idle"),
        sa.Column("capabilities", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "mean_seconds_per_cm3",
            sa.Float(),
            nullable=False,
            server_default=sa.text("12.0"),
        ),
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
        sa.ForeignKeyConstraint(["laboratory_id"], ["laboratories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lab_devices_laboratory_id",
        "lab_devices",
        ["laboratory_id"],
    )

    op.create_table(
        "device_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("submitted_by", sa.UUID(), nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="queued"),
        sa.Column("queue_position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("simulated_duration_seconds", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["device_id"], ["lab_devices.id"]),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_jobs_device_status_position",
        "device_jobs",
        ["device_id", "status", "queue_position"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_device_jobs_device_status_position", table_name="device_jobs")
    op.drop_table("device_jobs")
    op.drop_index("ix_lab_devices_laboratory_id", table_name="lab_devices")
    op.drop_table("lab_devices")
    sa.Enum(name="device_job_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="device_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="device_type").drop(op.get_bind(), checkfirst=True)
