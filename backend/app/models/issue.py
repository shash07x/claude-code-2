"""Issue (task) model — the unit of work shown as a card on the Sprint Board."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Issue(Base, TimestampMixin):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Kanban column. Stored as String (not a DB enum) for SQLite/Postgres
    # portability — same convention as Notification.type.
    # Values: backlog | in_progress | review | done
    status: Mapped[str] = mapped_column(
        String(20), default="backlog", nullable=False, index=True
    )
    # 0-based ordering within the column (ascending). Persisted on every drop.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # low | medium | high | urgent
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)

    user: Mapped["User"] = relationship(back_populates="issues")  # noqa: F821
    workspace: Mapped["Workspace | None"] = relationship("Workspace", back_populates="issues")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Issue {self.title!r} {self.status} pos={self.position}>"
