from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.db.models.document import Document, DocumentVersion, ProcessingStatus
from app.db.models.document_chunk import DocumentChunk
from app.db.models.user import User
from app.parsers import parser_registry
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.audit_service import AuditService
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates parsing, heading-aware chunking, vector embedding generation, and atomic indexing."""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = ChunkRepository(db)
        self.chunker = ChunkingService()
        self.embedding_service = EmbeddingService()
        self.perm_service = PermissionService(db)
        self.audit = AuditService(db)

    def process_document(
        self,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        file_path: Path
    ) -> bool:
        """Executes full parsing, chunking, embedding, and indexing pipeline for a document version."""
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        version = self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not doc or not version:
            logger.error(f"Cannot process document {document_id}: document or version record missing.")
            return False

        try:
            doc.status = ProcessingStatus.PROCESSING
            doc.error_message = None
            self.db.commit()

            # 1. Parse File
            parser = parser_registry.get_parser(file_path, doc.mime_type)
            parsed_doc = parser.parse(file_path)

            if parsed_doc.total_pages:
                version.total_pages = parsed_doc.total_pages

            # 2. Structure-Aware Chunking
            chunks_output = self.chunker.chunk_document(parsed_doc)
            if not chunks_output:
                logger.warning(f"Document {document_id} yielded 0 chunks.")
                doc.status = ProcessingStatus.INDEXED
                version.total_chunks = 0
                self.db.commit()
                return True

            # 3. Generate Vector Embeddings (Batched)
            chunk_texts = [c.content for c in chunks_output]
            embeddings = self.embedding_service.embed_documents(chunk_texts, batch_size=32)

            # 4. Construct Persistent Entities
            chunk_entities = []
            for idx, c in enumerate(chunks_output):
                emb = embeddings[idx] if idx < len(embeddings) else None
                chunk_entities.append(
                    DocumentChunk(
                        tenant_id=doc.tenant_id,
                        document_id=doc.id,
                        document_version_id=version.id,
                        chunk_index=c.chunk_index,
                        page_number=c.page_number,
                        section_heading=c.section_heading,
                        heading_breadcrumb=c.heading_breadcrumb,
                        content=c.content,
                        token_count=c.token_count,
                        content_hash=c.content_hash,
                        embedding=emb
                    )
                )

            # 5. Clear any prior chunks (for idempotency) and bulk insert
            self.chunk_repo.delete_by_version(version.id, doc.tenant_id)
            self.chunk_repo.bulk_create(chunk_entities)

            # 6. Update Document and Version State
            version.total_chunks = len(chunk_entities)
            doc.status = ProcessingStatus.INDEXED
            doc.error_message = None
            self.db.commit()

            # 7. Audit Log
            self.audit.log(
                tenant_id=doc.tenant_id,
                action="DOC_INDEXED",
                resource_type="DOCUMENT",
                resource_id=str(doc.id),
                user_id=doc.created_by_id,
                details={
                    "total_chunks": len(chunk_entities),
                    "version_num": version.version_num,
                    "pages": version.total_pages
                }
            )
            logger.info(f"Successfully processed and indexed document {doc.id} ({len(chunk_entities)} chunks).")
            return True

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
            self.db.rollback()
            try:
                doc = self.db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = str(e)
                    self.db.commit()
            except Exception as rollback_err:
                logger.error(f"Failed to record failure status: {rollback_err}")
            return False

    def reprocess_document(self, document_id: uuid.UUID, actor: User) -> Document:
        """Reprocesses an existing document from its original stored file."""
        if not actor.has_role("ADMIN") and not actor.has_role("COMPLIANCE_OFFICER"):
            raise PermissionDeniedError("Only ADMIN or COMPLIANCE_OFFICER roles can trigger document reprocessing.")

        doc = self.doc_repo.get_by_id_and_tenant(document_id, actor.tenant_id, load_versions=True)
        if not doc:
            raise EntityNotFoundError(f"Document with id '{document_id}' not found.")

        if not doc.versions:
            raise EntityNotFoundError(f"Document '{document_id}' has no associated versions.")

        latest_version = doc.versions[0]  # Ordered desc by version_num
        file_path = Path(latest_version.storage_path)

        if not file_path.exists():
            raise EntityNotFoundError(f"Physical file at path '{file_path}' does not exist on disk.")

        success = self.process_document(doc.id, latest_version.id, file_path)
        if not success:
            raise RuntimeError(f"Reprocessing failed for document '{document_id}'. Check error_message.")

        self.db.refresh(doc)
        return doc
