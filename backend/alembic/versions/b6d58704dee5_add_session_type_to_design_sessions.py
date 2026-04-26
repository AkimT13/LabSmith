"""add session_type to design_sessions

Revision ID: b6d58704dee5
Revises: 0975421fbff3
Create Date: 2026-04-25 21:07:23.224570

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6d58704dee5'
down_revision: Union[str, Sequence[str], None] = '0975421fbff3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Adds the session_type column to design_sessions. The enum values stored in
    Postgres are the Python enum NAMES (uppercase) — this matches the existing
    SessionStatus convention. The serialized JSON values come out lowercase
    because SessionType inherits from str (`PART_DESIGN = "part_design"`), so
    SQLAlchemy translates name <-> value across the wire.

    All existing rows backfill to PART_DESIGN via the server_default, which is
    fine because pre-M5 the only chat pipeline IS the part-design pipeline.

    The Postgres enum type is created explicitly here because the asyncpg
    driver (unlike psycopg2) does not auto-create types as a side effect of
    add_column.
    """
    session_type_enum = sa.Enum("PART_DESIGN", "ONBOARDING", name="session_type")
    session_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "design_sessions",
        sa.Column(
            "session_type",
            session_type_enum,
            server_default="PART_DESIGN",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("design_sessions", "session_type")
    sa.Enum(name="session_type").drop(op.get_bind(), checkfirst=True)
