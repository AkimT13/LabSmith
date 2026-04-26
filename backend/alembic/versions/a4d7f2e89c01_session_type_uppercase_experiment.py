"""Add the uppercase EXPERIMENT value to session_type.

The earlier M11 migration added `'experiment'` lowercase, but the existing
session_type enum stores values uppercase (`PART_DESIGN`, `ONBOARDING`)
because SQLAlchemy serializes enum *names* by default and we never set
`values_callable` on the SessionType column. So inserts fail with
"invalid input value for enum session_type: 'EXPERIMENT'".

Fix is one line: add the uppercase variant. The lowercase value stays as
an orphan in the type definition — harmless, never written.

Revision ID: a4d7f2e89c01
Revises: f9e2c8b41a73
Create Date: 2026-04-26 03:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a4d7f2e89c01"
down_revision: Union[str, Sequence[str], None] = "f9e2c8b41a73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE session_type ADD VALUE IF NOT EXISTS 'EXPERIMENT'"
    )


def downgrade() -> None:
    """Postgres doesn't support removing enum values without recreating the
    type. Intentionally a no-op."""
    pass
