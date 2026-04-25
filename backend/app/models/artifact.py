from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ArtifactType(str, enum.Enum):
    STL = "stl"
    STEP = "step"
    SPEC_JSON = "spec_json"
    VALIDATION_JSON = "validation_json"


class Artifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "artifacts"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("design_sessions.id"), nullable=False
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, name="artifact_type"), nullable=False
    )
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    spec_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    session: Mapped["DesignSession"] = relationship(  # noqa: F821
        back_populates="artifacts", foreign_keys=[session_id]
    )
    message: Mapped["Message | None"] = relationship(  # noqa: F821
        back_populates="artifacts", foreign_keys=[message_id]
    )

    def __repr__(self) -> str:
        return f"<Artifact {self.artifact_type} v{self.version}>"
