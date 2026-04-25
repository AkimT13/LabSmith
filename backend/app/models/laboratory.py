from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Laboratory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "laboratories"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    creator: Mapped["User"] = relationship(  # noqa: F821
        back_populates="created_labs", foreign_keys=[created_by]
    )
    memberships: Mapped[list["LabMembership"]] = relationship(  # noqa: F821
        back_populates="laboratory", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        back_populates="laboratory", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Laboratory {self.slug}>"
