from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DesignSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "design_sessions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        nullable=False,
        default=SessionStatus.ACTIVE,
    )
    part_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(  # noqa: F821
        back_populates="sessions", foreign_keys=[project_id]
    )
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DesignSession {self.title}>"
