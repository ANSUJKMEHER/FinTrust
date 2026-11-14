from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
import uuid
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, GUID, VectorType

if TYPE_CHECKING:
    from app.db.models.document import Document, DocumentVersion
    from app.db.models.tenant import Tenant


class DocumentChunk(Base):
    """Stores structured document chunks with vector embeddings and full-text search metadata."""
    __tablename__ = "document_chunks"

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
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    heading_breadcrumb: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of chunk content
    embedding: Mapped[Optional[List[float]]] = mapped_column(VectorType(dim=384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    version: Mapped["DocumentVersion"] = relationship("DocumentVersion", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_version_chunk_index"),
        Index("idx_chunk_tenant_doc", "tenant_id", "document_id"),
        Index("idx_chunk_tenant_version", "tenant_id", "document_version_id"),
        Index("idx_chunk_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk id={self.id} doc_id={self.document_id} "
            f"v_id={self.document_version_id} idx={self.chunk_index}>"
        )
