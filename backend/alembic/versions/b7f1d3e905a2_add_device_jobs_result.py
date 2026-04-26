"""Add device_jobs.result JSONB column for post-completion reports.

Tier-2 demo polish: each device type emits a fake-but-plausible structured
result on completion (plate-reader heatmap data, thermocycler trace, etc.)
that the frontend renders inline under the experiment timeline step.

Revision ID: b7f1d3e905a2
Revises: a4d7f2e89c01
Create Date: 2026-04-26 03:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f1d3e905a2"
down_revision: Union[str, Sequence[str], None] = "a4d7f2e89c01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "device_jobs",
        sa.Column(
            "result", sa.dialects.postgresql.JSONB(), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("device_jobs", "result")
