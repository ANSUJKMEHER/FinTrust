"""LLM cost telemetry, token cache accounting, and monetary tracking schema (Phase 7.6)

Revision ID: 004_llm_cost_telemetry
Revises: 003_agentic_workflows
Create Date: 2026-11-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '004_llm_cost_telemetry'
down_revision: Union[str, None] = '003_agentic_workflows'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add cost and provider tracking columns to agentic_workflows
    op.add_column(
        'agentic_workflows',
        sa.Column('total_estimated_cost', sa.Numeric(14, 6), nullable=False, server_default='0.000000')
    )
    op.add_column(
        'agentic_workflows',
        sa.Column('llm_provider', sa.String(50), nullable=True)
    )
    op.add_column(
        'agentic_workflows',
        sa.Column('llm_model', sa.String(100), nullable=True)
    )

    # 2. Add granular cost, cache, and provider columns to agentic_execution_traces
    op.add_column(
        'agentic_execution_traces',
        sa.Column('cached_prompt_tokens', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column(
        'agentic_execution_traces',
        sa.Column('llm_provider', sa.String(50), nullable=True)
    )
    op.add_column(
        'agentic_execution_traces',
        sa.Column('llm_model', sa.String(100), nullable=True)
    )
    op.add_column(
        'agentic_execution_traces',
        sa.Column('pricing_version', sa.String(50), nullable=True)
    )
    op.add_column(
        'agentic_execution_traces',
        sa.Column('input_cost', sa.Numeric(14, 6), nullable=False, server_default='0.000000')
    )
    op.add_column(
        'agentic_execution_traces',
        sa.Column('output_cost', sa.Numeric(14, 6), nullable=False, server_default='0.000000')
    )
    op.add_column(
        'agentic_execution_traces',
        sa.Column('total_cost', sa.Numeric(14, 6), nullable=False, server_default='0.000000')
    )


def downgrade() -> None:
    op.drop_column('agentic_execution_traces', 'total_cost')
    op.drop_column('agentic_execution_traces', 'output_cost')
    op.drop_column('agentic_execution_traces', 'input_cost')
    op.drop_column('agentic_execution_traces', 'pricing_version')
    op.drop_column('agentic_execution_traces', 'llm_model')
    op.drop_column('agentic_execution_traces', 'llm_provider')
    op.drop_column('agentic_execution_traces', 'cached_prompt_tokens')

    op.drop_column('agentic_workflows', 'llm_model')
    op.drop_column('agentic_workflows', 'llm_provider')
    op.drop_column('agentic_workflows', 'total_estimated_cost')
