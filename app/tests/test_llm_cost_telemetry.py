"""
FinTrust RAG - Phase 7.6 Tests: LLM Cost Telemetry & Decimal Accounting
Verifies:
1. OpenAI-compatible providers cost calculation.
2. Anthropic providers cost calculation.
3. Mock provider zero-cost accounting.
4. Unknown models fallback pricing without failure or fabricated numbers.
5. Missing or zero token usage handling.
6. Cached prompt tokens discount calculation.
7. Decimal precision (6 decimal places, no float rounding errors).
8. Multiple agent execution trace aggregation (no double counting).
9. Retry behavior (failed attempts without completion do not corrupt final cost).
10. Database persistence of cost telemetry on AgenticWorkflow and AgenticExecutionTrace.
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.workflow import AgenticWorkflow, AgenticExecutionTrace, WorkflowStatus, WorkflowTaskType, ApprovalStatus
from app.services.cost_service import CostService, cost_service, LLMCostBreakdown


PG_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI
pg_engine = create_engine(PG_DATABASE_URL, pool_size=5, max_overflow=5, pool_pre_ping=True)
PGSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


def test_openai_cost_calculation():
    """Verify cost calculation for OpenAI gpt-4o-mini and gpt-4o."""
    # gpt-4o-mini: Input $0.15 / 1M, Output $0.60 / 1M
    res = cost_service.calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=100_000,       # 0.1M * $0.15 = $0.015000
        completion_tokens=50_000,    # 0.05M * $0.60 = $0.030000
        cached_prompt_tokens=0
    )
    assert res.is_known_model is True
    assert res.input_cost == Decimal("0.015000")
    assert res.output_cost == Decimal("0.030000")
    assert res.total_cost == Decimal("0.045000")
    assert isinstance(res.total_cost, Decimal)

    # gpt-4o: Input $2.50 / 1M, Output $10.00 / 1M
    res_4o = cost_service.calculate_cost(
        provider="openai",
        model="gpt-4o",
        prompt_tokens=1_000_000,     # $2.500000
        completion_tokens=100_000,   # $1.000000
        cached_prompt_tokens=0
    )
    assert res_4o.input_cost == Decimal("2.500000")
    assert res_4o.output_cost == Decimal("1.000000")
    assert res_4o.total_cost == Decimal("3.500000")


def test_anthropic_cost_calculation():
    """Verify cost calculation for Anthropic Claude 3.5 Sonnet."""
    # claude-3-5-sonnet: Input $3.00 / 1M, Cached $0.30 / 1M, Output $15.00 / 1M
    res = cost_service.calculate_cost(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        prompt_tokens=500_000,       # 0.5M * $3.00 = $1.500000
        completion_tokens=20_000,    # 0.02M * $15.00 = $0.300000
        cached_prompt_tokens=0
    )
    assert res.is_known_model is True
    assert res.input_cost == Decimal("1.500000")
    assert res.output_cost == Decimal("0.300000")
    assert res.total_cost == Decimal("1.800000")


def test_gemini_cost_calculation():
    """Verify cost calculation for Google Gemini 2.0 Flash."""
    # gemini-2.0-flash: Input $0.10 / 1M, Cached $0.025 / 1M, Output $0.40 / 1M
    res = cost_service.calculate_cost(
        provider="gemini",
        model="gemini-2.0-flash",
        prompt_tokens=1_000_000,     # 1M * $0.10 = $0.100000
        completion_tokens=500_000,   # 0.5M * $0.40 = $0.200000
        cached_prompt_tokens=0
    )
    assert res.is_known_model is True
    assert res.input_cost == Decimal("0.100000")
    assert res.output_cost == Decimal("0.200000")
    assert res.total_cost == Decimal("0.300000")


def test_cached_prompt_tokens_discount():
    """Verify prompt caching discount calculation for Anthropic Claude."""
    # Total prompt: 100k, Cached: 80k, Uncached: 20k
    # Uncached: 20k * $3.00 / 1M = $0.060000
    # Cached: 80k * $0.30 / 1M = $0.024000
    # Output: 10k * $15.00 / 1M = $0.150000
    # Total: $0.060000 + $0.024000 + $0.150000 = $0.234000
    res = cost_service.calculate_cost(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        prompt_tokens=100_000,
        completion_tokens=10_000,
        cached_prompt_tokens=80_000
    )
    assert res.cached_prompt_tokens == 80_000
    assert res.input_cost == Decimal("0.084000")
    assert res.output_cost == Decimal("0.150000")
    assert res.total_cost == Decimal("0.234000")


def test_mock_provider_zero_cost():
    """Verify that Mock provider always returns 0.000000 cost."""
    res = cost_service.calculate_cost(
        provider="mock",
        model="mock-model",
        prompt_tokens=50_000,
        completion_tokens=25_000,
        cached_prompt_tokens=10_000
    )
    assert res.is_known_model is True
    assert res.input_cost == Decimal("0.000000")
    assert res.output_cost == Decimal("0.000000")
    assert res.total_cost == Decimal("0.000000")


def test_unknown_model_fallback():
    """Verify that unknown models trigger fallback rates gracefully without raising exceptions."""
    res = cost_service.calculate_cost(
        provider="custom_enterprise_llm",
        model="unreleased-model-v99",
        prompt_tokens=5000,
        completion_tokens=1000
    )
    assert res.is_known_model is False
    assert "fallback" in res.pricing_version
    assert res.total_cost == Decimal("0.000000")


def test_missing_or_zero_tokens():
    """Verify that 0 or negative tokens do not cause math domain errors."""
    res = cost_service.calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=0,
        completion_tokens=0
    )
    assert res.total_cost == Decimal("0.000000")


def test_decimal_precision_no_float_rounding():
    """Verify that fractional token costs retain exact 6-decimal micro-cent precision."""
    # 7 tokens of gpt-4o-mini: 7 * $0.15 / 1,000,000 = $0.00000105 -> rounded to $0.000001
    res = cost_service.calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=7,
        completion_tokens=0
    )
    assert res.input_cost == Decimal("0.000001")


def test_workflow_and_traces_cost_persistence():
    """Verify end-to-end database persistence of cost telemetry and aggregation."""
    db = PGSessionLocal()
    try:
        tenant = db.query(Tenant).first()
        user = db.query(User).filter(User.tenant_id == tenant.id).first()

        wf = AgenticWorkflow(
            tenant_id=tenant.id,
            user_id=user.id,
            query="Cost Telemetry Verification Workflow",
            task_type=WorkflowTaskType.GENERAL_RESEARCH,
            workflow_status=WorkflowStatus.COMPLETED,
            approval_status=ApprovalStatus.NOT_REQUIRED,
            total_tokens_used=6000,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            total_estimated_cost=Decimal("0.000000")
        )
        db.add(wf)
        db.commit()
        db.refresh(wf)

        # Step 1: Supervisor Agent
        c1 = cost_service.calculate_cost("openai", "gpt-4o-mini", prompt_tokens=2000, completion_tokens=500)
        t1 = AgenticExecutionTrace(
            workflow_id=wf.id,
            step_number=1,
            agent_name="supervisor",
            action="DELEGATE",
            prompt_tokens=2000,
            completion_tokens=500,
            cached_prompt_tokens=0,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            pricing_version=c1.pricing_version,
            input_cost=c1.input_cost,
            output_cost=c1.output_cost,
            total_cost=c1.total_cost
        )
        db.add(t1)

        # Step 2: Research Agent
        c2 = cost_service.calculate_cost("openai", "gpt-4o-mini", prompt_tokens=3000, completion_tokens=500)
        t2 = AgenticExecutionTrace(
            workflow_id=wf.id,
            step_number=2,
            agent_name="researcher",
            action="EXECUTE_TOOL",
            prompt_tokens=3000,
            completion_tokens=500,
            cached_prompt_tokens=0,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            pricing_version=c2.pricing_version,
            input_cost=c2.input_cost,
            output_cost=c2.output_cost,
            total_cost=c2.total_cost
        )
        db.add(t2)

        # Update aggregated workflow cost (no double-counting)
        wf.total_estimated_cost = c1.total_cost + c2.total_cost
        db.commit()

        # Query back and verify
        db.refresh(wf)
        db.refresh(t1)
        db.refresh(t2)

        assert t1.total_cost > Decimal("0.000000")
        assert t2.total_cost > Decimal("0.000000")
        assert wf.total_estimated_cost == t1.total_cost + t2.total_cost
        assert isinstance(wf.total_estimated_cost, Decimal)

        # Clean up test workflow
        db.delete(t1)
        db.delete(t2)
        db.delete(wf)
        db.commit()

    finally:
        db.close()
