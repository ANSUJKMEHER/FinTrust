import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PermissionDeniedError,
    ValidationError
)
from app.core.security import hash_password
from app.db.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit_service import AuditService


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)
        self.audit = AuditService(db)

    def create_user(
        self,
        tenant_id: uuid.UUID,
        data: UserCreate,
        creator: Optional[User] = None
    ) -> User:
        """Creates a new user within the specified tenant.
        If creator is provided, verifies that creator has ADMIN role in that tenant.
        """
        if creator and not creator.has_role("ADMIN"):
            raise PermissionDeniedError("Only ADMIN users can provision new accounts.")

        # Check unique email within tenant
        existing = self.repo.get_by_email_in_tenant(data.email, tenant_id)
        if existing:
            raise EntityAlreadyExistsError(f"User with email '{data.email}' already exists in this tenant.")

        # Resolve assigned roles
        roles = self.repo.get_roles_by_names(data.role_names)
        if not roles and data.role_names:
            raise ValidationError(f"Invalid role names: {data.role_names}")

        hashed_pw = hash_password(data.password)
        user = User(
            tenant_id=tenant_id,
            email=data.email,
            hashed_password=hashed_pw,
            full_name=data.full_name,
            is_active=True,
            roles=roles
        )

        created_user = self.repo.create(user)

        self.audit.log(
            tenant_id=tenant_id,
            action="USER_CREATE",
            resource_type="USER",
            resource_id=str(created_user.id),
            user_id=creator.id if creator else None,
            details={
                "email": created_user.email,
                "full_name": created_user.full_name,
                "roles": [r.id for r in created_user.roles]
            }
        )
        return created_user

    def get_user_by_id(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> User:
        user = self.repo.get_by_id_and_tenant(user_id, tenant_id)
        if not user:
            raise EntityNotFoundError(f"User with id '{user_id}' not found.")
        return user

    def list_users(self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[User]:
        return self.repo.list_by_tenant(tenant_id, skip=skip, limit=limit)

    def update_user(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: UserUpdate,
        actor: User
    ) -> User:
        """Updates user details. Only ADMIN can update other users or modify roles."""
        if actor.id != user_id and not actor.has_role("ADMIN"):
            raise PermissionDeniedError("Unauthorized to update this user.")

        user = self.get_user_by_id(user_id, tenant_id)

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.is_active is not None:
            if not actor.has_role("ADMIN"):
                raise PermissionDeniedError("Only ADMIN can toggle user active status.")
            user.is_active = data.is_active
        if data.role_names is not None:
            if not actor.has_role("ADMIN"):
                raise PermissionDeniedError("Only ADMIN can modify assigned roles.")
            roles = self.repo.get_roles_by_names(data.role_names)
            user.roles = roles

        updated = self.repo.update(user)
        self.audit.log(
            tenant_id=tenant_id,
            action="USER_UPDATE",
            resource_type="USER",
            resource_id=str(updated.id),
            user_id=actor.id,
            details={"is_active": updated.is_active, "roles": [r.id for r in updated.roles]}
        )
        return updated
