from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    memberships: Mapped[list["LabMembership"]] = relationship(  # noqa: F821
        back_populates="user", foreign_keys="LabMembership.user_id"
    )
    created_labs: Mapped[list["Laboratory"]] = relationship(  # noqa: F821
        back_populates="creator", foreign_keys="Laboratory.created_by"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
