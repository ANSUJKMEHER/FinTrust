import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, GUID, TimestampMixin
from app.db.models.role import user_roles

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.role import Role
    from app.db.models.document import Document
    from app.db.models.audit import AuditLog
    from app.db.models.permission import DocumentPermission


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin"
    )
    documents_created: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="created_by",
        foreign_keys="Document.created_by_id"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user"
    )
    user_permissions: Mapped[List["DocumentPermission"]] = relationship(
        "DocumentPermission",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_tenant_user_email"),
    )

    @property
    def role_names(self) -> List[str]:
        return [r.id for r in self.roles]

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} tenant_id={self.tenant_id}>"
