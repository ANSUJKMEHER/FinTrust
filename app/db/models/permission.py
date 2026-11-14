import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, GUID

if TYPE_CHECKING:
    from app.db.models.document import Document
    from app.db.models.user import User
    from app.db.models.role import Role


class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    can_read: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="permissions")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="user_permissions")
    role: Mapped[Optional["Role"]] = relationship("Role")

    __table_args__ = (
        CheckConstraint(
            "role_id IS NOT NULL OR user_id IS NOT NULL",
            name="ck_doc_perm_target_present"
        ),
        UniqueConstraint(
            "document_id", "role_id",
            name="uq_doc_role_perm"
        ),
        UniqueConstraint(
            "document_id", "user_id",
            name="uq_doc_user_perm"
        ),
        Index("idx_doc_perm_tenant_doc", "tenant_id", "document_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentPermission doc={self.document_id} role={self.role_id} "
            f"user={self.user_id} r={self.can_read} w={self.can_write}>"
        )
