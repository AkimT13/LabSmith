from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LabRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class LabMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lab_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "laboratory_id", name="uq_user_laboratory"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    laboratory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratories.id"), nullable=False
    )
    role: Mapped[LabRole] = mapped_column(
        Enum(LabRole, name="lab_role"), nullable=False, default=LabRole.MEMBER
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="memberships", foreign_keys=[user_id]
    )
    laboratory: Mapped["Laboratory"] = relationship(  # noqa: F821
        back_populates="memberships", foreign_keys=[laboratory_id]
    )

    def __repr__(self) -> str:
        return f"<LabMembership user={self.user_id} lab={self.laboratory_id} role={self.role}>"
