"""
FinTrust RAG - Phase 5 Unit Tests for LangGraph Multi-Agent Workflows
Tests state transitions, dynamic agent selection, evidence registry integrity,
conflict detection, verification auditor, and supervisor synthesis.
"""

import uuid
import pytest
from app.agentic.state import AgenticWorkflowState
from app.agentic.workflow import build_agentic_workflow_graph, route_after_planning, route_after_evaluation
from app.agentic.agents.supervisor import SupervisorAgent
from app.agentic.agents.verification import VerificationAgent
from app.agentic.conflict_resolution import ConflictResolutionEngine
from app.db.models.workflow import WorkflowTaskType, WorkflowStatus, ApprovalStatus


@pytest.fixture
def base_workflow_state() -> AgenticWorkflowState:
    """Creates a base typed state for testing graph transitions."""
    return {
        "workflow_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "user_roles": ["COMPLIANCE_OFFICER"],
        "user_groups": ["Compliance"],
        "user_query": "Audit suspicious transaction reporting compliance requirements under FinCEN.",
        "task_type": "COMPLIANCE_AUDIT",
        "workflow_phase": "PLANNING",
        "metadata": {},
        "execution_plan": [],
        "selected_agents": [],
        "evidence_registry": {},
        "research_findings": [],
        "compliance_findings": [],
        "comparison_findings": [],
        "identified_conflicts": [],
        "verification_results": [],
        "human_approval_status": "NOT_REQUIRED",
        "iteration_count": 0,
        "max_iterations": 3,
        "execution_trace": [],
        "final_report": None,
        "total_tokens_used": 0,
    }


def test_supervisor_planning_dynamic_agent_selection(base_workflow_state):
    """Test supervisor dynamically routes based on inquiry intent."""
    supervisor = SupervisorAgent()

    # 1. Comparison query
    base_workflow_state["user_query"] = "Compare refund policy versions 2023 and 2024."
    plan1 = supervisor.plan_task(base_workflow_state)
    assert "doc_intelligence" in plan1["selected_agents"]
    assert "verification" in plan1["selected_agents"]

    # 2. Compliance audit query
    base_workflow_state["user_query"] = "Audit customer due diligence compliance obligations."
    plan2 = supervisor.plan_task(base_workflow_state)
    assert "research" in plan2["selected_agents"]
    assert "compliance" in plan2["selected_agents"]
    assert "verification" in plan2["selected_agents"]

    # 3. Simple research
    base_workflow_state["user_query"] = "What is the capital reserve ratio requirement?"
    plan3 = supervisor.plan_task(base_workflow_state)
    assert "research" in plan3["selected_agents"]
    assert "verification" in plan3["selected_agents"]


def test_graph_conditional_routing(base_workflow_state):
    """Verify conditional edge routing functions."""
    base_workflow_state["selected_agents"] = ["research", "compliance", "verification"]
    next_node = route_after_planning(base_workflow_state)
    assert next_node == "research_node"

    base_workflow_state["selected_agents"] = ["doc_intelligence", "verification"]
    next_node = route_after_planning(base_workflow_state)
    assert next_node == "doc_intelligence_node"

    # Route after evaluation: if conflicts need human escalation
    base_workflow_state["identified_conflicts"] = [
        {"conflict_type": "THRESHOLD_DISCREPANCY", "resolution_strategy": "ESCALATE_TO_HUMAN"}
    ]
    base_workflow_state["human_approval_status"] = "PENDING_APPROVAL"
    next_node = route_after_evaluation(base_workflow_state)
    assert next_node == "human_approval_node"

    # Once approved, routes to final report
    base_workflow_state["human_approval_status"] = "APPROVED"
    next_node = route_after_evaluation(base_workflow_state)
    assert next_node == "supervisor_report_node"


def test_conflict_detection_engine(base_workflow_state):
    """Test bi-temporal contradiction and threshold discrepancy detection."""
    engine = ConflictResolutionEngine()

    state = dict(base_workflow_state)
    state["evidence_registry"] = {
        "CHUNK_1": {"document_title": "Policy A"},
        "CHUNK_2": {"document_title": "Policy B"},
    }
    state["compliance_findings"] = [
        {
            "finding_id": "CF_001",
            "requirement_text": "Transactions over $10,000 must be reported.",
            "document_id": "DOC_A",
            "chunk_id": "CHUNK_1",
            "supporting_evidence_ids": ["CHUNK_1"],
            "category": "CONFIRMED_REQUIREMENT",
            "statutory_reference": "31 CFR 1010.311",
            "financial_threshold": "$10,000",
            "filing_deadline": "15 days",
            "page_number": 1,
            "citations": ["[Policy A, p.1]"],
        },
        {
            "finding_id": "CF_002",
            "requirement_text": "Transactions over $5,000 must be reported.",
            "document_id": "DOC_B",
            "chunk_id": "CHUNK_2",
            "supporting_evidence_ids": ["CHUNK_2"],
            "category": "CONFIRMED_REQUIREMENT",
            "statutory_reference": "Branch Rule",
            "financial_threshold": "$5,000",
            "filing_deadline": "30 days",
            "page_number": 4,
            "citations": ["[Policy B, p.4]"],
        },
    ]

    conflicts = engine.detect_conflicts(state)
    assert len(conflicts) >= 2
    types = [c["conflict_type"] for c in conflicts]
    assert "THRESHOLD_DISCREPANCY" in types
    assert "DEADLINE_DISCREPANCY" in types
    assert all(c["requires_human_review"] is True for c in conflicts)


def test_verification_agent_audit(base_workflow_state):
    """Test verification agent validates supported claims and rejects contradictions."""
    agent = VerificationAgent()

    test_evidence = {
        "EVID_01": {
            "chunk_id": "CHUNK_01",
            "document_id": "DOC_01",
            "content": "All banks must file a Suspicious Activity Report within 30 calendar days of initial detection for amounts exceeding $10,000.",
        }
    }

    # 1. Ground truth claim
    state = dict(base_workflow_state)
    state["evidence_registry"] = test_evidence
    state["compliance_findings"] = [
        {
            "finding_id": "CF_01",
            "requirement_text": "Banks must file a Suspicious Activity Report within 30 calendar days for amounts exceeding $10,000.",
            "supporting_evidence_ids": ["EVID_01"],
            "citations": ["[DOC_01, p.1]"],
            "category": "CONFIRMED_REQUIREMENT",
        }
    ]
    res1 = agent.execute(state)
    v1 = res1["verification_results"][0]
    assert v1["status"] == "SUPPORTED"
    assert v1["confidence_score"] >= 0.85

    # 2. Contradicted claim with falsified number ($50,000 instead of $10,000)
    state["compliance_findings"] = [
        {
            "finding_id": "CF_02",
            "requirement_text": "Banks must file a SAR for amounts exceeding $50,000 within 30 calendar days.",
            "supporting_evidence_ids": ["EVID_01"],
            "citations": ["[DOC_01, p.1]"],
            "category": "CONFIRMED_REQUIREMENT",
        }
    ]
    res2 = agent.execute(state)
    v2 = res2["verification_results"][0]
    assert v2["status"] == "CONTRADICTED"

    # 3. Fabricated evidence ID
    state["compliance_findings"] = [
        {
            "finding_id": "CF_03",
            "requirement_text": "Banks must retain records for 5 years.",
            "supporting_evidence_ids": ["NON_EXISTENT_CHUNK"],
            "citations": ["[FAKE_DOC, p.99]"],
            "category": "CONFIRMED_REQUIREMENT",
        }
    ]
    res3 = agent.execute(state)
    v3 = res3["verification_results"][0]
    assert v3["status"] == "UNSUPPORTED"


def test_supervisor_14_section_final_report_synthesis(base_workflow_state):
    """Test synthesis of comprehensive 14-section compliance report."""
    supervisor = SupervisorAgent()

    state = dict(base_workflow_state)
    state["evidence_registry"] = {
        "EVID_01": {
            "document_id": "DOC_1",
            "document_title": "FinCEN AML Policy",
            "document_classification": "INTERNAL",
            "content": "Mandatory SAR filing required within 30 days.",
        }
    }
    state["compliance_findings"] = [
        {
            "finding_id": "CF_1",
            "requirement_text": "Mandatory SAR filing required within 30 days.",
            "category": "CONFIRMED_REQUIREMENT",
            "statutory_reference": "31 CFR 1010.311",
            "citations": ["[FinCEN AML, p.1]"],
            "financial_threshold": None,
            "filing_deadline": "30 days",
        }
    ]
    state["verification_results"] = [
        {
            "claim_id": "VRF_01",
            "claim_text": "Mandatory SAR filing required within 30 days.",
            "status": "SUPPORTED",
            "confidence_score": 0.95,
        }
    ]

    report_output = supervisor.generate_final_report(state)
    final_report = report_output["final_report"]

    expected_sections = [
        "executive_summary",
        "investigation_objective",
        "documents_examined",
        "research_methodology",
        "regulatory_requirements",
        "compliance_findings",
        "potential_gaps",
        "thresholds_and_deadlines",
        "conflicting_evidence",
        "supporting_citations",
        "verification_summary",
        "unresolved_questions",
        "human_review_requirements",
        "conclusion",
    ]

    for section in expected_sections:
        assert section in final_report, f"Missing section: {section}"

    assert final_report["verification_summary"]["is_faithful"] is True
    assert final_report["verification_summary"]["supported_claims"] == 1
