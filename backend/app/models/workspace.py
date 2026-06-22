"""Workspace model — the top-level multi-tenant scope for issues and collaboration."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    owner: Mapped["User"] = relationship("User", back_populates="owned_workspaces")  # noqa: F821
    issues: Mapped[list["Issue"]] = relationship("Issue", back_populates="workspace")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Workspace {self.name!r}>"
