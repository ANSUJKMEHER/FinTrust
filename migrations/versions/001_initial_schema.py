"""Initial PostgreSQL schema for FinTrust RAG (Phase 2)

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.db.base import GUID

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. PostgreSQL Extensions
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # 1. Tenants Table
    op.create_table(
        'tenants',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)

    # 2. Roles Table
    roles_table = op.create_table(
        'roles',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('description', sa.String(255), nullable=False)
    )

    # Seed Initial Standard Roles
    op.bulk_insert(
        roles_table,
        [
            {'id': 'ADMIN', 'description': 'Full tenant administration and unrestricted document access'},
            {'id': 'COMPLIANCE_OFFICER', 'description': 'Manage regulatory policies and compliance verification'},
            {'id': 'ANALYST', 'description': 'Query authorized documents and perform financial research'},
            {'id': 'AUDITOR', 'description': 'Strictly read-only access to authorized compliance documents and audit logs'}
        ]
    )

    # 3. Users Table
    op.create_table(
        'users',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('tenant_id', GUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_tenant_user_email')
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])

    # 4. User Roles Association Table
    op.create_table(
        'user_roles',
        sa.Column('user_id', GUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role_id', sa.String(50), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
    )

    # 5. Documents Table
    op.create_table(
        'documents',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('tenant_id', GUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('classification', sa.String(50), nullable=False, server_default='INTERNAL'),
        sa.Column('category', sa.String(100), nullable=False, server_default='GENERAL_COMPLIANCE'),
        sa.Column('current_version_num', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by_id', GUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'content_hash', name='uq_tenant_doc_content_hash')
    )
    op.create_index('ix_documents_tenant_id', 'documents', ['tenant_id'])
    op.create_index('idx_doc_tenant_class', 'documents', ['tenant_id', 'classification'])
    op.create_index('idx_doc_tenant_cat', 'documents', ['tenant_id', 'category'])

    # 6. Document Versions Table
    op.create_table(
        'document_versions',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('document_id', GUID(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_num', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(1000), nullable=False),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('total_chunks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by_id', GUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('document_id', 'version_num', name='uq_doc_version_num')
    )
    op.create_index('ix_document_versions_document_id', 'document_versions', ['document_id'])

    # 7. Document Permissions Table
    op.create_table(
        'document_permissions',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('document_id', GUID(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', GUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', sa.String(50), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', GUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('can_read', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('can_write', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('role_id IS NOT NULL OR user_id IS NOT NULL', name='ck_doc_perm_target_present'),
        sa.UniqueConstraint('document_id', 'role_id', name='uq_doc_role_perm'),
        sa.UniqueConstraint('document_id', 'user_id', name='uq_doc_user_perm')
    )
    op.create_index('ix_document_permissions_tenant_id', 'document_permissions', ['tenant_id'])
    op.create_index('idx_doc_perm_tenant_doc', 'document_permissions', ['tenant_id', 'document_id'])

    # 8. Audit Logs Table
    op.create_table(
        'audit_logs',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('tenant_id', GUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', GUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='SUCCESS'),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('idx_audit_tenant_action', 'audit_logs', ['tenant_id', 'action', 'created_at'])
    op.create_index('idx_audit_resource', 'audit_logs', ['tenant_id', 'resource_type', 'resource_id'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('document_permissions')
    op.drop_table('document_versions')
    op.drop_table('documents')
    op.drop_table('user_roles')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('tenants')
