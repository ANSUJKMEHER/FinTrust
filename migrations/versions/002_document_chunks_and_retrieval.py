"""Document chunks, pgvector embeddings, and full-text search schema for FinTrust RAG (Phase 3)

Revision ID: 002_document_chunks_and_retrieval
Revises: 001_initial_schema
Create Date: 2026-11-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.db.base import GUID, VectorType

revision: str = '002_chunks_retrieval'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. PostgreSQL pgvector Extension
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # 1. Document Chunks Table
    op.create_table(
        'document_chunks',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('tenant_id', GUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', GUID(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_version_id', GUID(), sa.ForeignKey('document_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('section_heading', sa.String(500), nullable=True),
        sa.Column('heading_breadcrumb', sa.String(1000), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('embedding', VectorType(dim=384), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('document_version_id', 'chunk_index', name='uq_version_chunk_index')
    )

    op.create_index('ix_document_chunks_tenant_id', 'document_chunks', ['tenant_id'])
    op.create_index('idx_chunk_tenant_doc', 'document_chunks', ['tenant_id', 'document_id'])
    op.create_index('idx_chunk_tenant_version', 'document_chunks', ['tenant_id', 'document_version_id'])
    op.create_index('idx_chunk_tenant_created', 'document_chunks', ['tenant_id', 'created_at'])

    # 2. PostgreSQL-specific Extensions & Performance Indexes
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Full-text search generated column and GIN index
        op.execute(sa.text("""
            ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_vector tsvector
            GENERATED ALWAYS AS (to_tsvector('english', coalesce(section_heading, '') || ' ' || content)) STORED;
        """))
        op.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_search_vector_gin 
            ON document_chunks USING gin(search_vector);
        """))

        # HNSW Cosine Distance Index for pgvector 384-dimensional embeddings
        op.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw;"))
        op.execute(sa.text("DROP INDEX IF EXISTS idx_chunks_search_vector_gin;"))

    op.drop_table('document_chunks')
