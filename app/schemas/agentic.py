"""
Pydantic schemas for Phase 5 Agentic API endpoints and data transfer models.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from app.db.models.workflow import ApprovalStatus, WorkflowStatus, WorkflowTaskType


class AgenticResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Research or regulatory inquiry")
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Optional target document filters")
    max_iterations: int = Field(5, ge=1, le=10, description="Max supervisor iterations")
    require_human_approval: bool = Field(False, description="Whether to mandate human signoff prior to finalization")


class AgenticComplianceAuditRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Compliance audit objective")
    policy_document_ids: Optional[List[uuid.UUID]] = Field(None, description="Specific policy document IDs to audit")
    statute_reference: Optional[str] = Field(None, description="Target statute or regulation (e.g. BSA, GDPR)")
    max_iterations: int = Field(5, ge=1, le=10)
    require_human_approval: bool = Field(False)


class AgenticDocumentInvestigationRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Investigation inquiry")
    doc1_id: uuid.UUID = Field(..., description="Baseline document ID")
    doc2_id: Optional[uuid.UUID] = Field(None, description="Target comparison document ID")
    max_iterations: int = Field(5, ge=1, le=10)


class HumanApprovalRequest(BaseModel):
    decision: ApprovalStatus = Field(..., description="Decision: APPROVED, REJECTED, or NEEDS_REVISION")
    comments: Optional[str] = Field(None, min_length=3, description="Reviewer feedback or justification")


class HumanApprovalResponse(BaseModel):
    workflow_id: uuid.UUID
    approval_status: ApprovalStatus
    reviewer_id: uuid.UUID
    reviewer_comments: Optional[str]
    reviewed_at: datetime
    message: str


class WorkflowTraceItemResponse(BaseModel):
    step_number: int
    agent_name: str
    action: str
    inputs_redacted: Optional[Dict[str, Any]]
    outputs_redacted: Optional[Dict[str, Any]]
    status: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    error_details: Optional[str]
    timestamp: str


class WorkflowTraceResponse(BaseModel):
    workflow_id: uuid.UUID
    total_steps: int
    total_tokens: int
    total_latency_ms: float
    traces: List[WorkflowTraceItemResponse]


class AgenticWorkflowResponse(BaseModel):
    workflow_id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    query: str
    task_type: WorkflowTaskType
    workflow_status: WorkflowStatus
    approval_status: ApprovalStatus
    iteration_count: int
    max_iterations: int
    total_tokens_used: int
    execution_latency_ms: float
    selected_agents: Optional[List[str]] = None
    execution_plan: Optional[List[Dict[str, Any]]] = None
    final_report: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AgenticHealthResponse(BaseModel):
    status: str
    active_agents: List[str]
    mcp_tools_available: List[str]
    max_workflow_iterations: int
    supervisor_orchestrator: str
    checkpointing: str
