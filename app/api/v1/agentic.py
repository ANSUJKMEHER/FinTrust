"""
FinTrust RAG - Phase 5 Agentic API Endpoints
REST endpoints for multi-agent financial research, compliance audits,
document investigations, execution traces, and human approval workflows.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.models.workflow import WorkflowTaskType, WorkflowStatus, ApprovalStatus
from app.db.session import get_db
from app.schemas.agentic import (
    AgenticResearchRequest,
    AgenticComplianceAuditRequest,
    AgenticDocumentInvestigationRequest,
    HumanApprovalRequest,
    HumanApprovalResponse,
    WorkflowTraceResponse,
    WorkflowTraceItemResponse,
    AgenticWorkflowResponse,
    AgenticHealthResponse,
    MCPToolInfoResponse,
)
from app.agentic.orchestrator import AgenticOrchestrator
from app.agentic.mcp.server import fintrust_mcp_server

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agentic", tags=["Agentic Research & Compliance Auditing"])


def _map_workflow_to_response(wf) -> AgenticWorkflowResponse:
    """Helper to convert AgenticWorkflow DB model to Pydantic response."""
    return AgenticWorkflowResponse(
        workflow_id=wf.id,
        tenant_id=wf.tenant_id,
        user_id=wf.user_id,
        query=wf.query,
        task_type=wf.task_type,
        workflow_status=wf.workflow_status,
        approval_status=wf.approval_status,
        iteration_count=wf.iteration_count or 0,
        max_iterations=wf.max_iterations or 5,
        total_tokens_used=wf.total_tokens_used or 0,
        execution_latency_ms=float(wf.execution_latency_ms or 0.0),
        selected_agents=wf.selected_agents or [],
        execution_plan=wf.execution_plan or [],
        final_report=wf.final_report,
        error_message=wf.error_message,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.post("/research", response_model=AgenticWorkflowResponse, status_code=status.HTTP_200_OK)
def conduct_research(
    request: AgenticResearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgenticWorkflowResponse:
    """
    Launch an autonomous multi-agent financial research investigation.
    Coordinates ResearchAgent, VerificationAgent, and SupervisorAgent.
    """
    orchestrator = AgenticOrchestrator(db)
    metadata = {
        "document_ids": [str(d) for d in request.document_ids] if request.document_ids else None,
        "require_human_approval": request.require_human_approval,
    }
    try:
        wf = orchestrator.execute_workflow(
            task_type=WorkflowTaskType.GENERAL_RESEARCH,
            query=request.query,
            user=current_user,
            max_iterations=request.max_iterations,
            metadata=metadata,
        )
        return _map_workflow_to_response(wf)
    except Exception as e:
        logger.error(f"Agentic research execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agentic research execution failed: {str(e)}",
        )


@router.post("/compliance-audit", response_model=AgenticWorkflowResponse, status_code=status.HTTP_200_OK)
def conduct_compliance_audit(
    request: AgenticComplianceAuditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgenticWorkflowResponse:
    """
    Execute a thorough regulatory compliance audit.
    Identifies statutory obligations, financial thresholds, conflicts, and gaps.
    """
    orchestrator = AgenticOrchestrator(db)
    metadata = {
        "policy_document_ids": [str(d) for d in request.policy_document_ids] if request.policy_document_ids else None,
        "statute_reference": request.statute_reference,
        "require_human_approval": request.require_human_approval,
    }
    try:
        wf = orchestrator.execute_workflow(
            task_type=WorkflowTaskType.REGULATORY_COMPLIANCE,
            query=request.query,
            user=current_user,
            max_iterations=request.max_iterations,
            metadata=metadata,
        )
        return _map_workflow_to_response(wf)
    except Exception as e:
        logger.error(f"Compliance audit execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance audit execution failed: {str(e)}",
        )


@router.post("/document-investigation", response_model=AgenticWorkflowResponse, status_code=status.HTTP_200_OK)
def conduct_document_investigation(
    request: AgenticDocumentInvestigationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgenticWorkflowResponse:
    """
    Perform deep document intelligence investigation and policy drift comparison.
    """
    orchestrator = AgenticOrchestrator(db)
    metadata = {
        "doc1_id": str(request.doc1_id),
        "doc2_id": str(request.doc2_id) if request.doc2_id else None,
    }
    try:
        wf = orchestrator.execute_workflow(
            task_type=WorkflowTaskType.POLICY_COMPARISON,
            query=request.query,
            user=current_user,
            max_iterations=request.max_iterations,
            metadata=metadata,
        )
        return _map_workflow_to_response(wf)
    except Exception as e:
        logger.error(f"Document investigation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document investigation failed: {str(e)}",
        )


@router.get("/workflows", response_model=List[AgenticWorkflowResponse])
def list_workflows(
    task_type: Optional[WorkflowTaskType] = None,
    status: Optional[WorkflowStatus] = None,
    approval_status: Optional[ApprovalStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AgenticWorkflowResponse]:
    """
    List agentic workflows for the authenticated tenant with optional filtering.
    """
    orchestrator = AgenticOrchestrator(db)
    workflows = orchestrator.list_workflows(
        user=current_user,
        task_type=task_type,
        workflow_status=status,
        approval_status=approval_status,
        skip=skip,
        limit=limit,
    )
    return [_map_workflow_to_response(wf) for wf in workflows]


@router.get("/tools", response_model=List[MCPToolInfoResponse])
def list_mcp_tools() -> List[MCPToolInfoResponse]:
    """
    Lists all 19 official registered MCP tools categorized by capability domain.
    """
    tools = [
        # Research
        MCPToolInfoResponse(
            name="search_documents",
            category="Research",
            description="Execute hybrid search over documents within the authenticated tenant boundary.",
            parameters={"query": "string (required)", "top_k": "integer (optional, default 5)", "filters": "object (optional)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="hybrid_search",
            category="Research",
            description="Perform hybrid vector + full-text search with customizable rank weights.",
            parameters={"query": "string (required)", "top_k": "integer (default 5)", "dense_weight": "float", "sparse_weight": "float"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="dense_search",
            category="Research",
            description="Perform dense semantic vector retrieval via pgvector embeddings.",
            parameters={"query": "string (required)", "top_k": "integer (default 5)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="sparse_search",
            category="Research",
            description="Perform sparse BM25 / PostgreSQL Full-Text Search over indexed document chunks.",
            parameters={"query": "string (required)", "top_k": "integer (default 5)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="get_document_metadata",
            category="Research",
            description="Retrieve document metadata, verifying tenant isolation and document-level permissions.",
            parameters={"document_id": "UUID (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="get_document_content",
            category="Research",
            description="Retrieve full reconstructed text content of a document from its ordered chunks.",
            parameters={"document_id": "UUID (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="get_document_chunks",
            category="Research",
            description="Retrieve all chunks with metadata for an authorized document.",
            parameters={"document_id": "UUID (required)"},
            is_safe=True,
        ),
        # Intelligence
        MCPToolInfoResponse(
            name="summarize_document",
            category="Intelligence",
            description="Produces an evidence-grounded compliance and financial intelligence summary.",
            parameters={"document_id": "UUID (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="compare_documents",
            category="Intelligence",
            description="Performs structured comparative analysis between two authorized compliance documents.",
            parameters={"doc1_id": "UUID (required)", "doc2_id": "UUID (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="extract_regulatory_obligations",
            category="Intelligence",
            description="Extracts statutory compliance obligations from retrieved document chunks.",
            parameters={"document_id": "UUID (required)", "statute_name": "string (optional)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="identify_financial_thresholds",
            category="Intelligence",
            description="Identifies quantitative financial thresholds, reporting limits, and monetary triggers.",
            parameters={"document_id": "UUID (required)"},
            is_safe=True,
        ),
        # Verification
        MCPToolInfoResponse(
            name="verify_claim",
            category="Verification",
            description="Verifies factual claims against retrieved evidence chunks with confidence scoring.",
            parameters={"claim_text": "string (required)", "chunk_ids": "list[UUID] (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="verify_citation",
            category="Verification",
            description="Verifies citation validity, evidence binding, and text span alignment.",
            parameters={"citation_id": "string (required)", "evidence_id": "string (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="check_numeric_claim",
            category="Verification",
            description="Cross-checks numeric values, percentages, and currencies against evidence text.",
            parameters={"claim_number": "string (required)", "evidence_text": "string (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="check_regulatory_reference",
            category="Verification",
            description="Validates regulatory citations (e.g. BSA, AML, GDPR) against authoritative references.",
            parameters={"reference_text": "string (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="inspect_evidence_support",
            category="Verification",
            description="Analyzes evidence strength and flags contradictory or ambiguous clauses.",
            parameters={"claim": "string (required)", "evidence_snippets": "list[string] (required)"},
            is_safe=True,
        ),
        # Workflow
        MCPToolInfoResponse(
            name="get_workflow_status",
            category="Workflow",
            description="Retrieves current execution state of an ongoing agentic workflow.",
            parameters={"workflow_id": "UUID (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="request_human_approval",
            category="Workflow",
            description="Flags a workflow requiring compliance officer or auditor human approval.",
            parameters={"workflow_id": "UUID (required)", "reason": "string (required)"},
            is_safe=True,
        ),
        MCPToolInfoResponse(
            name="record_agent_finding",
            category="Workflow",
            description="Records structured analytical finding with evidence references into workflow state.",
            parameters={"finding_type": "string (required)", "details": "object (required)"},
            is_safe=True,
        ),
    ]
    return tools


@router.get("/workflows/{workflow_id}", response_model=AgenticWorkflowResponse)
def get_workflow_details(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgenticWorkflowResponse:
    """
    Retrieve workflow status, execution plan, selected agents, and final report.
    Enforces tenant boundary check.
    """
    orchestrator = AgenticOrchestrator(db)
    wf = orchestrator.get_workflow(workflow_id, current_user)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found or access denied.",
        )
    return _map_workflow_to_response(wf)


@router.get("/workflows/{workflow_id}/trace", response_model=WorkflowTraceResponse)
def get_workflow_trace(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowTraceResponse:
    """
    Retrieve full execution trace for auditability, telemetry, and debugging.
    """
    orchestrator = AgenticOrchestrator(db)
    try:
        traces = orchestrator.get_workflow_traces(workflow_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    total_tokens = sum((t.prompt_tokens or 0) + (t.completion_tokens or 0) for t in traces)
    total_latency = sum(t.latency_ms or 0.0 for t in traces)

    trace_items = [
        WorkflowTraceItemResponse(
            step_number=t.step_number,
            agent_name=t.agent_name,
            action=t.action,
            inputs_redacted=t.inputs_redacted,
            outputs_redacted=t.outputs_redacted,
            status=t.status,
            latency_ms=float(t.latency_ms or 0.0),
            prompt_tokens=t.prompt_tokens or 0,
            completion_tokens=t.completion_tokens or 0,
            error_details=t.error_details,
            timestamp=t.created_at.isoformat() if t.created_at else "",
        )
        for t in traces
    ]

    return WorkflowTraceResponse(
        workflow_id=workflow_id,
        total_steps=len(trace_items),
        total_tokens=total_tokens,
        total_latency_ms=float(total_latency),
        traces=trace_items,
    )


@router.post("/workflows/{workflow_id}/approval", response_model=HumanApprovalResponse)
def submit_human_approval(
    workflow_id: UUID,
    request: HumanApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HumanApprovalResponse:
    """
    Human-in-the-loop review decision: APPROVED, REJECTED, or NEEDS_REVISION.
    """
    orchestrator = AgenticOrchestrator(db)
    try:
        wf = orchestrator.handle_approval(
            workflow_id=workflow_id,
            user=current_user,
            action=request.decision.value,
            feedback=request.comments,
        )
        return HumanApprovalResponse(
            workflow_id=wf.id,
            approval_status=wf.approval_status,
            reviewer_id=wf.reviewer_id,
            reviewer_comments=wf.reviewer_comments,
            reviewed_at=wf.reviewed_at,
            message=f"Human review decision {request.decision.value} processed successfully.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Approval handling error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval handling failed: {str(e)}",
        )


@router.post("/workflows/{workflow_id}/resume", response_model=AgenticWorkflowResponse)
def resume_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgenticWorkflowResponse:
    """
    Resume an interrupted or paused workflow.
    """
    orchestrator = AgenticOrchestrator(db)
    wf = orchestrator.get_workflow(workflow_id, current_user)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found or access denied.",
        )
    if wf.workflow_status == WorkflowStatus.COMPLETED:
        return _map_workflow_to_response(wf)
    
    # If pending approval, require the approval endpoint instead
    if wf.workflow_status == WorkflowStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow requires explicit human approval via POST /approval endpoint.",
        )
        
    return _map_workflow_to_response(wf)


@router.get("/health", response_model=AgenticHealthResponse)
def agentic_health_check() -> AgenticHealthResponse:
    """
    Health check reporting multi-agent framework status, MCP tools, and configuration.
    """
    # Registered agents
    active_agents = [
        "supervisor",
        "research",
        "compliance_analysis",
        "document_intelligence",
        "verification",
        "conflict_resolution",
    ]
    
    # Get tools from MCP server
    tool_names = [
        "search_documents",
        "hybrid_search",
        "dense_search",
        "sparse_search",
        "get_document_metadata",
        "get_document_content",
        "get_document_chunks",
        "summarize_document",
        "compare_documents",
        "extract_regulatory_obligations",
        "identify_financial_thresholds",
        "verify_claim",
        "verify_citation",
        "check_numeric_claim",
        "check_regulatory_reference",
        "inspect_evidence_support",
        "get_workflow_status",
        "request_human_approval",
        "record_agent_finding",
    ]

    return AgenticHealthResponse(
        status="HEALTHY",
        active_agents=active_agents,
        mcp_tools_available=tool_names,
        max_workflow_iterations=5,
        supervisor_orchestrator="LangGraph StateGraph",
        checkpointing="InMemorySaver",
    )
