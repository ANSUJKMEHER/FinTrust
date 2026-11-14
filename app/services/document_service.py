import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PermissionDeniedError,
    TenantAccessViolationError
)
from app.db.models.document import (
    Document,
    DocumentClassification,
    DocumentVersion,
    ProcessingStatus
)
from app.db.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        self.perm_service = PermissionService(db)
        self.audit = AuditService(db)

    def create_document(self, data: DocumentCreate, creator: User) -> Document:
        """Creates a new document and initial version. Requires ADMIN or COMPLIANCE_OFFICER."""
        if not creator.has_role("ADMIN") and not creator.has_role("COMPLIANCE_OFFICER"):
            raise PermissionDeniedError("Only ADMIN or COMPLIANCE_OFFICER roles can upload documents.")

        # Duplicate detection within tenant via SHA-256 hash
        existing = self.repo.get_by_content_hash_in_tenant(data.content_hash, creator.tenant_id)
        if existing:
            raise EntityAlreadyExistsError(
                f"Document with identical content hash already exists in this tenant (ID: {existing.id})."
            )

        doc = Document(
            tenant_id=creator.tenant_id,
            title=data.title,
            original_filename=data.original_filename,
            mime_type=data.mime_type,
            file_size_bytes=data.file_size_bytes,
            content_hash=data.content_hash,
            classification=data.classification,
            category=data.category,
            current_version_num=1,
            status=ProcessingStatus.PENDING,
            created_by_id=creator.id
        )

        created_doc = self.repo.create_with_version(
            document=doc,
            storage_path=data.storage_path,
            total_pages=data.total_pages
        )

        self.audit.log(
            tenant_id=creator.tenant_id,
            action="DOC_CREATE",
            resource_type="DOCUMENT",
            resource_id=str(created_doc.id),
            user_id=creator.id,
            details={
                "title": created_doc.title,
                "content_hash": created_doc.content_hash,
                "classification": created_doc.classification.value,
                "category": created_doc.category
            }
        )
        return created_doc

    def get_document(self, document_id: uuid.UUID, user: User) -> Document:
        """Retrieves a single document by ID, enforcing tenant isolation and ACL rules."""
        doc = self.repo.get_by_id_and_tenant(document_id, user.tenant_id, load_versions=True)
        if not doc:
            raise EntityNotFoundError(f"Document with id '{document_id}' not found.")

        self.perm_service.check_read_permission(doc, user)
        return doc

    def list_documents(
        self,
        user: User,
        classification: Optional[DocumentClassification] = None,
        category: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """Lists documents accessible to the requesting user within their tenant."""
        all_docs = self.repo.list_by_tenant(
            tenant_id=user.tenant_id,
            classification=classification,
            category=category,
            status=status,
            skip=skip,
            limit=limit
        )

        # Apply ACL filter for non-ADMIN users
        if user.has_role("ADMIN"):
            return all_docs

        accessible_docs: List[Document] = []
        for doc in all_docs:
            can_read, _ = self.perm_service.evaluate_access(doc, user)
            if can_read:
                accessible_docs.append(doc)

        return accessible_docs

    def update_document(
        self,
        document_id: uuid.UUID,
        data: DocumentUpdate,
        user: User
    ) -> Document:
        """Updates document metadata. Requires write permission on the document."""
        doc = self.repo.get_by_id_and_tenant(document_id, user.tenant_id)
        if not doc:
            raise EntityNotFoundError(f"Document with id '{document_id}' not found.")

        self.perm_service.check_write_permission(doc, user)

        changes = {}
        if data.title is not None:
            changes["title"] = {"old": doc.title, "new": data.title}
            doc.title = data.title
        if data.classification is not None:
            changes["classification"] = {"old": doc.classification.value, "new": data.classification.value}
            doc.classification = data.classification
        if data.category is not None:
            changes["category"] = {"old": doc.category, "new": data.category}
            doc.category = data.category
        if data.status is not None:
            changes["status"] = {"old": doc.status.value, "new": data.status.value}
            doc.status = data.status
        if data.error_message is not None:
            doc.error_message = data.error_message

        updated = self.repo.update(doc)

        self.audit.log(
            tenant_id=user.tenant_id,
            action="DOC_UPDATE",
            resource_type="DOCUMENT",
            resource_id=str(updated.id),
            user_id=user.id,
            details=changes
        )
        return updated

    def delete_document(self, document_id: uuid.UUID, user: User) -> None:
        """Deletes a document and its cascading versions/permissions.
        Auditors can NEVER delete documents.
        """
        if user.has_role("AUDITOR"):
            raise PermissionDeniedError("Auditors have strictly read-only permissions and cannot delete documents.")

        doc = self.repo.get_by_id_and_tenant(document_id, user.tenant_id)
        if not doc:
            raise EntityNotFoundError(f"Document with id '{document_id}' not found.")

        # Must have write permission or be ADMIN
        self.perm_service.check_write_permission(doc, user)

        doc_title = doc.title
        self.repo.delete(doc)

        self.audit.log(
            tenant_id=user.tenant_id,
            action="DOC_DELETE",
            resource_type="DOCUMENT",
            resource_id=str(document_id),
            user_id=user.id,
            details={"title": doc_title}
        )
