import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.permission import DocumentPermission
from app.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[DocumentPermission]):
    def __init__(self, db: Session):
        super().__init__(DocumentPermission, db)

    def get_user_permission(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> Optional[DocumentPermission]:
        return self.db.query(DocumentPermission).filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.user_id == user_id,
            DocumentPermission.tenant_id == tenant_id
        ).first()

    def get_role_permissions(
        self,
        document_id: uuid.UUID,
        role_ids: List[str],
        tenant_id: uuid.UUID
    ) -> List[DocumentPermission]:
        return self.db.query(DocumentPermission).filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.role_id.in_(role_ids),
            DocumentPermission.tenant_id == tenant_id
        ).all()

    def list_for_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> List[DocumentPermission]:
        return self.db.query(DocumentPermission).filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.tenant_id == tenant_id
        ).all()

    def get_accessible_document_ids_for_user(
        self,
        user_id: uuid.UUID,
        role_ids: List[str],
        tenant_id: uuid.UUID,
        require_write: bool = False
    ) -> List[uuid.UUID]:
        """Returns the list of document IDs explicitly granted to this user or any of their roles."""
        query = self.db.query(DocumentPermission.document_id).filter(
            DocumentPermission.tenant_id == tenant_id
        )
        if require_write:
            query = query.filter(DocumentPermission.can_write == True)
        else:
            query = query.filter(DocumentPermission.can_read == True)

        query = query.filter(
            (DocumentPermission.user_id == user_id) |
            (DocumentPermission.role_id.in_(role_ids))
        )
        return [row[0] for row in query.distinct().all()]

    def grant_or_update(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        role_id: Optional[str],
        user_id: Optional[uuid.UUID],
        can_read: bool,
        can_write: bool
    ) -> DocumentPermission:
        query = self.db.query(DocumentPermission).filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.tenant_id == tenant_id
        )
        if user_id:
            perm = query.filter(DocumentPermission.user_id == user_id).first()
        else:
            perm = query.filter(DocumentPermission.role_id == role_id).first()

        if perm:
            perm.can_read = can_read
            perm.can_write = can_write
        else:
            perm = DocumentPermission(
                document_id=document_id,
                tenant_id=tenant_id,
                role_id=role_id,
                user_id=user_id,
                can_read=can_read,
                can_write=can_write
            )
            self.db.add(perm)

        self.db.commit()
        self.db.refresh(perm)
        return perm
