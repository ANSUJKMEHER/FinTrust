"""Agentic workflows, execution traces, and human approval schema for FinTrust RAG (Phase 5)

Revision ID: 003_agentic_workflows
Revises: 002_chunks_retrieval
Create Date: 2026-11-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.db.base import GUID

revision: str = '003_agentic_workflows'
down_revision: Union[str, None] = '002_chunks_retrieval'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agentic Workflows Table
    op.create_table(
        'agentic_workflows',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('tenant_id', GUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', GUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('workflow_status', sa.String(50), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('execution_plan', sa.JSON(), nullable=True),
        sa.Column('selected_agents', sa.JSON(), nullable=True),
        sa.Column('state_snapshot', sa.JSON(), nullable=True),
        sa.Column('final_report', sa.JSON(), nullable=True),
        sa.Column('approval_status', sa.String(50), nullable=False),
        sa.Column('reviewer_id', GUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewer_comments', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('iteration_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_iterations', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('total_tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('execution_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index('ix_agentic_workflows_tenant_id', 'agentic_workflows', ['tenant_id'])
    op.create_index('ix_agentic_workflows_user_id', 'agentic_workflows', ['user_id'])
    op.create_index('ix_agentic_workflows_task_type', 'agentic_workflows', ['task_type'])
    op.create_index('ix_agentic_workflows_workflow_status', 'agentic_workflows', ['workflow_status'])
    op.create_index('ix_agentic_workflows_approval_status', 'agentic_workflows', ['approval_status'])
    op.create_index('idx_agentic_wf_tenant_status', 'agentic_workflows', ['tenant_id', 'workflow_status'])
    op.create_index('idx_agentic_wf_tenant_created', 'agentic_workflows', ['tenant_id', 'created_at'])

    # 2. Execution Traces Table
    op.create_table(
        'agentic_execution_traces',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('workflow_id', GUID(), sa.ForeignKey('agentic_workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.String(100), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('inputs_redacted', sa.JSON(), nullable=True),
        sa.Column('outputs_redacted', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='SUCCESS'),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index('ix_agentic_execution_traces_workflow_id', 'agentic_execution_traces', ['workflow_id'])
    op.create_index('idx_trace_wf_step', 'agentic_execution_traces', ['workflow_id', 'step_number'])


def downgrade() -> None:
    op.drop_table('agentic_execution_traces')
    op.drop_table('agentic_workflows')
