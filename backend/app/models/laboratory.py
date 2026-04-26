from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lab_document import LabDocument
    from app.models.lab_membership import LabMembership
    from app.models.project import Project
    from app.models.user import User


class Laboratory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "laboratories"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    creator: Mapped[User] = relationship(
        back_populates="created_labs", foreign_keys=[created_by]
    )
    memberships: Mapped[list[LabMembership]] = relationship(
        back_populates="laboratory", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="laboratory", cascade="all, delete-orphan"
    )
    documents: Mapped[list[LabDocument]] = relationship(
        back_populates="laboratory", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Laboratory {self.slug}>"
