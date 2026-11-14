import uuid
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DocumentAccessDeniedError,
    EntityNotFoundError,
    PermissionDeniedError,
    TenantAccessViolationError
)
from app.db.models.document import Document, DocumentClassification
from app.db.models.permission import DocumentPermission
from app.db.models.user import User
from app.repositories.permission_repository import PermissionRepository
from app.schemas.permission import PermissionGrant
from app.services.audit_service import AuditService


class PermissionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PermissionRepository(db)
        self.audit = AuditService(db)

    def evaluate_access(
        self,
        document: Document,
        user: User
    ) -> Tuple[bool, bool]:
        """Evaluates (can_read, can_write) for a user against a target document.
        
        Resolution Hierarchy:
        1. Tenant Boundary: Cross-tenant access is immediately False.
        2. ADMIN: Full read and write.
        3. AUDITOR: Strictly read-only; can_write is permanently False.
        4. User-Specific Override: If document_permissions has a row for (document.id, user.id),
           its values take absolute precedence over role rules.
        5. Role-Level Grants: If any role assigned to user has a grant row, permissions are merged (OR).
        6. Default Classification Fallback:
           - PUBLIC: read=True, write=False
           - INTERNAL: read=True, write=False
           - CONFIDENTIAL: read=False, write=False (explicit grant required)
           - STRICTLY_CONFIDENTIAL: read=False, write=False (explicit grant required)
        """
        if document.tenant_id != user.tenant_id:
            return False, False

        user_roles = user.role_names

        # 1. ADMIN has global tenant privileges
        if "ADMIN" in user_roles:
            return True, True

        # 2. Check for explicit User-Specific Permission Override
        user_perm = self.repo.get_user_permission(
            document_id=document.id,
            user_id=user.id,
            tenant_id=user.tenant_id
        )
        if user_perm is not None:
            can_read = user_perm.can_read
            can_write = user_perm.can_write
            # Hard safety constraint: Auditor cannot write regardless of user-specific grant
            if "AUDITOR" in user_roles:
                can_write = False
            return can_read, can_write

        # 3. Check for Role-Based Permission Grants
        role_perms = self.repo.get_role_permissions(
            document_id=document.id,
            role_ids=user_roles,
            tenant_id=user.tenant_id
        )
        if role_perms:
            can_read = any(rp.can_read for rp in role_perms)
            can_write = any(rp.can_write for rp in role_perms)
            if "AUDITOR" in user_roles:
                can_write = False
            return can_read, can_write

        # 4. Default Classification Policy
        if document.classification in (DocumentClassification.PUBLIC, DocumentClassification.INTERNAL):
            return True, False
        
        # CONFIDENTIAL and STRICTLY_CONFIDENTIAL require explicit permission grants
        return False, False

    def check_read_permission(self, document: Document, user: User) -> None:
        can_read, _ = self.evaluate_access(document, user)
        if not can_read:
            raise DocumentAccessDeniedError(
                f"User '{user.email}' is not authorized to read document '{document.id}'."
            )

    def check_write_permission(self, document: Document, user: User) -> None:
        _, can_write = self.evaluate_access(document, user)
        if not can_write:
            raise DocumentAccessDeniedError(
                f"User '{user.email}' is not authorized to modify document '{document.id}'."
            )

    def grant_permission(
        self,
        document_id: uuid.UUID,
        grant: PermissionGrant,
        actor: User
    ) -> DocumentPermission:
        """Grants or updates a document permission. Only Admins can manage permissions."""
        if not actor.has_role("ADMIN") and not actor.has_role("COMPLIANCE_OFFICER"):
            raise PermissionDeniedError("Only ADMIN or COMPLIANCE_OFFICER can manage document permissions.")

        # Verify document exists in actor's tenant
        doc = self.db.query(Document).filter(
            Document.id == document_id,
            Document.tenant_id == actor.tenant_id
        ).first()
        if not doc:
            raise EntityNotFoundError(f"Document with id '{document_id}' not found.")

        # If user_id is supplied, verify target user belongs to the same tenant
        if grant.user_id:
            target_user = self.db.query(User).filter(
                User.id == grant.user_id,
                User.tenant_id == actor.tenant_id
            ).first()
            if not target_user:
                raise TenantAccessViolationError("Target user does not belong to your tenant.")

        perm = self.repo.grant_or_update(
            document_id=document_id,
            tenant_id=actor.tenant_id,
            role_id=grant.role_id,
            user_id=grant.user_id,
            can_read=grant.can_read,
            can_write=grant.can_write
        )

        self.audit.log(
            tenant_id=actor.tenant_id,
            action="PERMISSION_GRANT",
            resource_type="PERMISSION",
            resource_id=str(perm.id),
            user_id=actor.id,
            details={
                "document_id": str(document_id),
                "role_id": grant.role_id,
                "user_id": str(grant.user_id) if grant.user_id else None,
                "can_read": grant.can_read,
                "can_write": grant.can_write
            }
        )
        return perm

    def list_permissions(self, document_id: uuid.UUID, actor: User) -> List[DocumentPermission]:
        """Lists all permissions for a document. Admin or Compliance Officer only."""
        if not actor.has_role("ADMIN") and not actor.has_role("COMPLIANCE_OFFICER") and not actor.has_role("AUDITOR"):
            raise PermissionDeniedError("Unauthorized to inspect document ACL rules.")
        return self.repo.list_for_document(document_id, actor.tenant_id)
