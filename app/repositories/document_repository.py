import uuid
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.db.models.document import Document, DocumentVersion, DocumentClassification, ProcessingStatus
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: Session):
        super().__init__(Document, db)

    def get_by_id_and_tenant(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        load_versions: bool = False
    ) -> Optional[Document]:
        query = self.db.query(Document).filter(
            Document.id == document_id,
            Document.tenant_id == tenant_id
        )
        if load_versions:
            query = query.options(joinedload(Document.versions))
        return query.first()

    def get_by_content_hash_in_tenant(
        self,
        content_hash: str,
        tenant_id: uuid.UUID
    ) -> Optional[Document]:
        return self.db.query(Document).filter(
            Document.content_hash == content_hash,
            Document.tenant_id == tenant_id
        ).first()

    def create_with_version(
        self,
        document: Document,
        storage_path: str,
        total_pages: Optional[int] = None
    ) -> Document:
        """Atomically creates a new document record and its initial version (v1)."""
        self.db.add(document)
        self.db.flush()  # Populates document.id

        version = DocumentVersion(
            document_id=document.id,
            version_num=1,
            storage_path=storage_path,
            total_pages=total_pages,
            created_by_id=document.created_by_id
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        classification: Optional[DocumentClassification] = None,
        category: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        allowed_doc_ids: Optional[List[uuid.UUID]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        query = self.db.query(Document).filter(Document.tenant_id == tenant_id)

        if classification:
            query = query.filter(Document.classification == classification)
        if category:
            query = query.filter(Document.category == category)
        if status:
            query = query.filter(Document.status == status)
        if allowed_doc_ids is not None:
            query = query.filter(Document.id.in_(allowed_doc_ids))

        return query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
