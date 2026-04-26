"""cascade device_jobs FKs so artifact/device deletes don't get blocked

Without ON DELETE CASCADE on `device_jobs.artifact_id`, deleting a project
fails with a FK violation: SQLAlchemy cascades project → sessions →
artifacts, but Postgres rejects the artifact delete because old print jobs
still reference it. Same risk on `device_id` if a device is deleted via raw
SQL outside the SQLAlchemy session cascade.

Revision ID: e74c2d1a91b8
Revises: d3a91f7c4e10
Create Date: 2026-04-26 01:30:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e74c2d1a91b8"
down_revision: Union[str, Sequence[str], None] = "d3a91f7c4e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "device_jobs_artifact_id_fkey", "device_jobs", type_="foreignkey"
    )
    op.create_foreign_key(
        "device_jobs_artifact_id_fkey",
        "device_jobs",
        "artifacts",
        ["artifact_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "device_jobs_device_id_fkey", "device_jobs", type_="foreignkey"
    )
    op.create_foreign_key(
        "device_jobs_device_id_fkey",
        "device_jobs",
        "lab_devices",
        ["device_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "device_jobs_device_id_fkey", "device_jobs", type_="foreignkey"
    )
    op.create_foreign_key(
        "device_jobs_device_id_fkey",
        "device_jobs",
        "lab_devices",
        ["device_id"],
        ["id"],
    )

    op.drop_constraint(
        "device_jobs_artifact_id_fkey", "device_jobs", type_="foreignkey"
    )
    op.create_foreign_key(
        "device_jobs_artifact_id_fkey",
        "device_jobs",
        "artifacts",
        ["artifact_id"],
        ["id"],
    )
