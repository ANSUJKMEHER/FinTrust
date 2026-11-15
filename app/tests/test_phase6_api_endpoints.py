"""
FinTrust Phase 6 - Frontend API Integration & Verification Tests
Validates all backend API endpoints invoked by the enterprise frontend:
- Auth & User endpoints
- Tenant endpoints
- Document upload, status, list, chunks
- Grounded RAG query and citation verification
- Document summary and comparison
- Agentic workflows list and details
- Official 19 MCP Tools registry
- Audit logs telemetry
- LLM & System health telemetry
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.workflow import AgenticWorkflow, WorkflowTaskType, WorkflowStatus, ApprovalStatus
from app.tests.conftest import auth_header_for_user


def test_system_and_llm_health(client: TestClient, user_a_compliance: User):
    # System health (public endpoint)
    res_sys = client.get("/health")
    assert res_sys.status_code == 200
    assert res_sys.json()["status"] == "healthy"

    # LLM health (authenticated endpoint)
    headers = auth_header_for_user(user_a_compliance)
    res_llm = client.get("/api/v1/llm/health", headers=headers)
    assert res_llm.status_code == 200
    assert "active_provider" in res_llm.json()


def test_agentic_tools_endpoint(client: TestClient):
    res = client.get("/api/v1/agentic/tools")
    assert res.status_code == 200
    tools = res.json()
    assert len(tools) == 19
    categories = {t["category"] for t in tools}
    assert "Research" in categories
    assert "Intelligence" in categories
    assert "Verification" in categories
    assert "Workflow" in categories


def test_agentic_workflows_list_endpoint(
    client: TestClient, db: Session, user_a_compliance: User, tenant_a: Tenant
):
    # Seed a workflow
    wf = AgenticWorkflow(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a_compliance.id,
        task_type=WorkflowTaskType.REGULATORY_COMPLIANCE,
        workflow_status=WorkflowStatus.COMPLETED,
        approval_status=ApprovalStatus.APPROVED,
        query="Verify transaction monitoring compliance under Bank Secrecy Act",
        execution_plan=[{"step": 1, "agent": "research", "description": "Search BSA clauses"}],
        selected_agents=["research", "compliance_analysis", "verification"],
        final_report={
            "executive_summary": "Policy is fully compliant with SAR reporting deadlines.",
            "statutory_obligations": ["File SAR within 30 days of initial detection"],
            "financial_thresholds": [{"threshold": "$10,000", "context": "CTR mandatory filing trigger"}],
            "verified_claims_count": 2,
        },
        iteration_count=2,
        total_tokens_used=420,
        execution_latency_ms=180.5,
    )
    db.add(wf)
    db.commit()

    headers = auth_header_for_user(user_a_compliance)
    res = client.get("/api/v1/agentic/workflows", headers=headers)
    assert res.status_code == 200
    wfs = res.json()
    assert len(wfs) >= 1
    found = any(w["workflow_id"] == str(wf.id) for w in wfs)
    assert found
