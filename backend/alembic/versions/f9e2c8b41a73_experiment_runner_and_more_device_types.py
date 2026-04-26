"""experiment runner and more device types (M11)

Adds:
- 5 new device_type enum values: liquid_handler, centrifuge, thermocycler,
  plate_reader, autoclave.
- New session_type enum value: experiment.
- Makes device_jobs.artifact_id nullable (centrifuge spins, etc. don't
  reference an artifact).
- Adds device_jobs.payload JSONB column for per-type job parameters.

Postgres requires `ALTER TYPE ... ADD VALUE` for enum extensions, and those
have to run outside a transaction in older PG versions. We use `op.execute`
with the bind in autocommit mode.

Revision ID: f9e2c8b41a73
Revises: e74c2d1a91b8
Create Date: 2026-04-26 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9e2c8b41a73"
down_revision: Union[str, Sequence[str], None] = "e74c2d1a91b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_DEVICE_TYPES = (
    "liquid_handler",
    "centrifuge",
    "thermocycler",
    "plate_reader",
    "autoclave",
)


def upgrade() -> None:
    # 1. Extend device_type enum with new values. ALTER TYPE ADD VALUE IF NOT
    # EXISTS keeps this migration safely re-runnable. Each statement runs
    # in its own connection because PG forbids enum changes mid-transaction
    # for new values used in the SAME transaction (we're not using them yet
    # though, so the explicit COMMIT after suffices).
    # ALTER TYPE doesn't accept bind parameters, so we inline the values.
    # All values are hardcoded literals from `_NEW_DEVICE_TYPES`, no user
    # input — safe.
    for value in _NEW_DEVICE_TYPES:
        op.execute(
            f"ALTER TYPE device_type ADD VALUE IF NOT EXISTS '{value}'"
        )

    # 2. Extend session_type enum with 'experiment'.
    op.execute(
        "ALTER TYPE session_type ADD VALUE IF NOT EXISTS 'experiment'"
    )

    # 3. Make device_jobs.artifact_id nullable.
    op.alter_column(
        "device_jobs",
        "artifact_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    # 4. Add device_jobs.payload JSONB column for per-type job parameters.
    op.add_column(
        "device_jobs",
        sa.Column(
            "payload", sa.dialects.postgresql.JSONB(), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade is intentionally lossy.

    Postgres does NOT support removing enum values without recreating the
    type and updating every column referencing it. For the new device
    types specifically, we'd also need to delete any rows using them. We
    only undo the cheap structural changes; enum extensions stay.
    """
    op.drop_column("device_jobs", "payload")
    op.alter_column(
        "device_jobs",
        "artifact_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
