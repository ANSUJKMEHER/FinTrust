import json
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.document_chunk import DocumentChunk
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ChunkRepository(BaseRepository[DocumentChunk]):
    """Data access layer for document chunks, vector embeddings, and full-text search."""

    def __init__(self, db: Session):
        super().__init__(DocumentChunk, db)

    def bulk_create(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Atomically inserts a batch of document chunks."""
        self.db.add_all(chunks)
        self.db.flush()
        return chunks

    def delete_by_version(self, version_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """Deletes all chunks belonging to a specific document version."""
        deleted = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_version_id == version_id,
                DocumentChunk.tenant_id == tenant_id
            )
            .delete(synchronize_session=False)
        )
        self.db.flush()
        return deleted

    def delete_by_document(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """Deletes all chunks belonging to a document."""
        deleted = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id
            )
            .delete(synchronize_session=False)
        )
        self.db.flush()
        return deleted

    def list_by_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[DocumentChunk]:
        return (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def dense_search(
        self,
        tenant_id: uuid.UUID,
        allowed_doc_ids: List[uuid.UUID],
        query_vector: List[float],
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Dense semantic retrieval using pgvector cosine distance (<=>).
        
        Enforces tenant isolation and document-level ACLs directly at the database query level.
        """
        if not allowed_doc_ids:
            return []

        dialect_name = self.db.bind.dialect.name if self.db.bind else "postgresql"

        if dialect_name == "postgresql":
            vector_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
            sql = text("""
                SELECT 
                    c.id as chunk_id,
                    c.document_id,
                    c.document_version_id,
                    c.chunk_index,
                    c.page_number,
                    c.section_heading,
                    c.heading_breadcrumb,
                    c.content,
                    c.token_count,
                    d.title as document_title,
                    d.classification as document_classification,
                    (c.embedding <=> CAST(:query_vector AS vector)) as cosine_distance
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.tenant_id = :tenant_id
                  AND c.document_id IN :allowed_doc_ids
                  AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> CAST(:query_vector AS vector) ASC
                LIMIT :limit;
            """)
            result = self.db.execute(
                sql,
                {
                    "tenant_id": tenant_id,
                    "allowed_doc_ids": tuple(allowed_doc_ids),
                    "query_vector": vector_str,
                    "limit": limit
                }
            )
            rows = []
            for r in result.fetchall():
                dist = float(r.cosine_distance) if r.cosine_distance is not None else 1.0
                similarity = max(0.0, 1.0 - dist)
                rows.append({
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "document_version_id": r.document_version_id,
                    "chunk_index": r.chunk_index,
                    "page_number": r.page_number,
                    "section_heading": r.section_heading,
                    "heading_breadcrumb": r.heading_breadcrumb,
                    "content": r.content,
                    "token_count": r.token_count,
                    "document_title": r.document_title,
                    "document_classification": str(r.document_classification),
                    "cosine_distance": dist,
                    "dense_score": similarity,
                })
            return rows
        else:
            # SQLite fallback for in-memory unit tests
            chunks = (
                self.db.query(DocumentChunk)
                .filter(
                    DocumentChunk.tenant_id == tenant_id,
                    DocumentChunk.document_id.in_(allowed_doc_ids)
                )
                .limit(limit)
                .all()
            )
            return [
                {
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "document_version_id": c.document_version_id,
                    "chunk_index": c.chunk_index,
                    "page_number": c.page_number,
                    "section_heading": c.section_heading,
                    "heading_breadcrumb": c.heading_breadcrumb,
                    "content": c.content,
                    "token_count": c.token_count,
                    "document_title": c.document.title if c.document else "Untitled",
                    "document_classification": str(c.document.classification) if c.document else "INTERNAL",
                    "cosine_distance": 0.1,
                    "dense_score": 0.9,
                }
                for c in chunks
            ]

    def sparse_search(
        self,
        tenant_id: uuid.UUID,
        allowed_doc_ids: List[uuid.UUID],
        query_text: str,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Sparse keyword retrieval using PostgreSQL Full-Text Search (websearch_to_tsquery + ts_rank_cd).
        
        Enforces tenant isolation and document-level ACLs directly at the database query level.
        """
        if not allowed_doc_ids or not query_text.strip():
            return []

        clean_query = query_text.strip()
        dialect_name = self.db.bind.dialect.name if self.db.bind else "postgresql"

        if dialect_name == "postgresql":
            # 1. Try websearch_to_tsquery for natural queries
            sql = text("""
                SELECT 
                    c.id as chunk_id,
                    c.document_id,
                    c.document_version_id,
                    c.chunk_index,
                    c.page_number,
                    c.section_heading,
                    c.heading_breadcrumb,
                    c.content,
                    c.token_count,
                    d.title as document_title,
                    d.classification as document_classification,
                    ts_rank_cd(c.search_vector, websearch_to_tsquery('english', :query_text)) as fts_rank
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.tenant_id = :tenant_id
                  AND c.document_id IN :allowed_doc_ids
                  AND c.search_vector @@ websearch_to_tsquery('english', :query_text)
                ORDER BY fts_rank DESC
                LIMIT :limit;
            """)
            result = self.db.execute(
                sql,
                {
                    "tenant_id": tenant_id,
                    "allowed_doc_ids": tuple(allowed_doc_ids),
                    "query_text": clean_query,
                    "limit": limit
                }
            )
            rows = []
            for r in result.fetchall():
                rows.append({
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "document_version_id": r.document_version_id,
                    "chunk_index": r.chunk_index,
                    "page_number": r.page_number,
                    "section_heading": r.section_heading,
                    "heading_breadcrumb": r.heading_breadcrumb,
                    "content": r.content,
                    "token_count": r.token_count,
                    "document_title": r.document_title,
                    "document_classification": str(r.document_classification),
                    "sparse_score": float(r.fts_rank) if r.fts_rank else 0.0,
                })

            # If strict websearch returned 0 hits (typical for conversational questions without ALL words in one chunk),
            # fallback to OR combination of stemmed lexemes with cover density ranking (ts_rank_cd)
            if not rows:
                fallback_sql = text("""
                    WITH query_lexemes AS (
                        SELECT string_agg(lexeme, ' | ') as or_query
                        FROM unnest(to_tsvector('english', :query_text))
                    )
                    SELECT 
                        c.id as chunk_id,
                        c.document_id,
                        c.document_version_id,
                        c.chunk_index,
                        c.page_number,
                        c.section_heading,
                        c.heading_breadcrumb,
                        c.content,
                        c.token_count,
                        d.title as document_title,
                        d.classification as document_classification,
                        ts_rank_cd(c.search_vector, to_tsquery('english', ql.or_query)) as fts_rank
                    FROM document_chunks c
                    JOIN documents d ON d.id = c.document_id
                    CROSS JOIN query_lexemes ql
                    WHERE c.tenant_id = :tenant_id
                      AND c.document_id IN :allowed_doc_ids
                      AND ql.or_query IS NOT NULL
                      AND (
                          c.search_vector @@ to_tsquery('english', ql.or_query)
                          OR c.content ILIKE :ilike_query
                      )
                    ORDER BY fts_rank DESC
                    LIMIT :limit;
                """)
                fb_result = self.db.execute(
                    fallback_sql,
                    {
                        "tenant_id": tenant_id,
                        "allowed_doc_ids": tuple(allowed_doc_ids),
                        "query_text": clean_query,
                        "ilike_query": f"%{clean_query}%",
                        "limit": limit
                    }
                )
                for r in fb_result.fetchall():
                    rows.append({
                        "chunk_id": r.chunk_id,
                        "document_id": r.document_id,
                        "document_version_id": r.document_version_id,
                        "chunk_index": r.chunk_index,
                        "page_number": r.page_number,
                        "section_heading": r.section_heading,
                        "heading_breadcrumb": r.heading_breadcrumb,
                        "content": r.content,
                        "token_count": r.token_count,
                        "document_title": r.document_title,
                        "document_classification": str(r.document_classification),
                        "sparse_score": float(r.fts_rank) if r.fts_rank else 0.05,
                    })
            return rows
        else:
            # SQLite fallback with ILIKE / LIKE
            chunks = (
                self.db.query(DocumentChunk)
                .filter(
                    DocumentChunk.tenant_id == tenant_id,
                    DocumentChunk.document_id.in_(allowed_doc_ids),
                    DocumentChunk.content.ilike(f"%{clean_query}%")
                )
                .limit(limit)
                .all()
            )
            return [
                {
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "document_version_id": c.document_version_id,
                    "chunk_index": c.chunk_index,
                    "page_number": c.page_number,
                    "section_heading": c.section_heading,
                    "heading_breadcrumb": c.heading_breadcrumb,
                    "content": c.content,
                    "token_count": c.token_count,
                    "document_title": c.document.title if c.document else "Untitled",
                    "document_classification": str(c.document.classification) if c.document else "INTERNAL",
                    "sparse_score": 0.5,
                }
                for c in chunks
            ]
