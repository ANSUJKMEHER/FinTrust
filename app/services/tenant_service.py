import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import EntityAlreadyExistsError, EntityNotFoundError
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.repositories.tenant_repository import TenantRepository
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services.audit_service import AuditService

DEFAULT_ROLES = [
    ("ADMIN", "Full tenant administration, user management, and complete document access"),
    ("COMPLIANCE_OFFICER", "Manage regulatory policies, compliance checks, and document permissions"),
    ("ANALYST", "Query documents, run compliance research, and analyze authorized regulatory files"),
    ("AUDITOR", "Strictly read-only access to authorized compliance documents and complete audit trails"),
]


class TenantService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TenantRepository(db)
        self.audit = AuditService(db)

    def ensure_system_roles(self) -> None:
        """Seeds initial system roles if they do not exist."""
        for role_id, description in DEFAULT_ROLES:
            role = self.db.query(Role).filter(Role.id == role_id).first()
            if not role:
                role = Role(id=role_id, description=description)
                self.db.add(role)
        self.db.commit()

    def create_tenant(self, data: TenantCreate) -> Tenant:
        self.ensure_system_roles()
        existing = self.repo.get_by_slug(data.slug)
        if existing:
            raise EntityAlreadyExistsError(f"Tenant with slug '{data.slug}' already exists.")

        tenant = Tenant(
            name=data.name,
            slug=data.slug,
            is_active=True
        )
        created = self.repo.create(tenant)
        self.audit.log(
            tenant_id=created.id,
            action="TENANT_CREATE",
            resource_type="TENANT",
            resource_id=str(created.id),
            details={"name": created.name, "slug": created.slug}
        )
        return created

    def get_tenant_by_id(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.repo.get_by_id(tenant_id)
        if not tenant:
            raise EntityNotFoundError(f"Tenant with id '{tenant_id}' not found.")
        return tenant

    def get_tenant_by_slug(self, slug: str) -> Tenant:
        tenant = self.repo.get_by_slug(slug)
        if not tenant:
            raise EntityNotFoundError(f"Tenant with slug '{slug}' not found.")
        return tenant

    def list_tenants(self, skip: int = 0, limit: int = 100) -> List[Tenant]:
        return self.repo.list_active(skip=skip, limit=limit)
