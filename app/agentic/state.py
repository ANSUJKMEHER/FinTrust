"""
Shared LangGraph Workflow State for Phase 5 Agentic Architecture.
"""
from typing import Any, Dict, List, Optional, TypedDict
import uuid


class EvidenceRegistryItem(TypedDict, total=False):
    evidence_id: str
    chunk_id: str
    document_id: str
    document_version_id: str
    document_title: str
    document_classification: str
    page_number: Optional[int]
    section_heading: Optional[str]
    heading_breadcrumb: Optional[str]
    content: str
    token_count: int
    relevance_score: float
    citation_label: str


class ResearchFinding(TypedDict, total=False):
    finding_id: str
    topic: str
    summary: str
    supporting_evidence_ids: List[str]
    citations: List[str]
    relevance_score: float
    is_sufficient: bool
    missing_aspects: List[str]


class ComplianceFinding(TypedDict, total=False):
    finding_id: str
    category: str  # "CONFIRMED_REQUIREMENT", "POTENTIAL_GAP", "INSUFFICIENT_EVIDENCE", "REQUIRES_HUMAN_REVIEW"
    requirement_text: str
    statutory_reference: Optional[str]
    filing_deadline: Optional[str]
    financial_threshold: Optional[str]
    supporting_evidence_ids: List[str]
    citations: List[str]
    confidence_score: float
    qualifying_rationale: str


class DocumentComparisonFinding(TypedDict, total=False):
    finding_id: str
    finding_type: str  # "THRESHOLD_MODIFIED", "DEADLINE_MODIFIED", "SECTION_ADDED", "SECTION_REMOVED", etc.
    description: str
    doc1_title: str
    doc1_statement: Optional[str]
    doc1_citation: Optional[str]
    doc2_title: str
    doc2_statement: Optional[str]
    doc2_citation: Optional[str]
    confidence_score: float


class IdentifiedConflict(TypedDict, total=False):
    conflict_id: str
    conflict_type: str  # "THRESHOLD_DISCREPANCY", "DEADLINE_DISCREPANCY", "OBLIGATION_CONTRADICTION"
    description: str
    item_a: Dict[str, Any]
    item_b: Dict[str, Any]
    severity: str  # "HIGH", "MEDIUM", "LOW"
    requires_human_review: bool
    resolution_status: str  # "UNRESOLVED", "RECONCILED", "ESCALATED_TO_HUMAN"
    reconciliation_notes: Optional[str]


class VerificationResult(TypedDict, total=False):
    claim_id: str
    claim_text: str
    status: str  # "SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "UNVERIFIABLE"
    supporting_evidence_ids: List[str]
    citations: List[str]
    extracted_entities: Dict[str, List[str]]
    entity_verification: Dict[str, bool]
    confidence_score: float
    explanation: str


class ExecutionTraceItem(TypedDict, total=False):
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


class InvestigationReport(TypedDict, total=False):
    executive_summary: str
    investigation_objective: str
    documents_examined: List[Dict[str, Any]]
    research_methodology: str
    regulatory_requirements: List[Dict[str, Any]]
    compliance_findings: List[ComplianceFinding]
    potential_gaps: List[Dict[str, Any]]
    thresholds_and_deadlines: Dict[str, List[Any]]
    conflicting_evidence: List[IdentifiedConflict]
    supporting_citations: List[str]
    verification_summary: Dict[str, Any]
    unresolved_questions: List[str]
    human_review_requirements: List[str]
    conclusion: str
    generated_at: str


class AgenticWorkflowState(TypedDict, total=False):
    """Authoritative shared typed state passed across all LangGraph nodes."""
    workflow_id: str
    tenant_id: str
    user_id: str
    user_roles: List[str]
    original_query: str
    normalized_query: str
    task_type: str  # REGULATORY_COMPLIANCE, POLICY_COMPARISON, RISK_INVESTIGATION, OBLIGATION_EXTRACTION, GENERAL_RESEARCH
    execution_plan: List[Dict[str, Any]]
    selected_agents: List[str]
    current_step: str
    iteration_count: int
    max_iterations: int
    
    # Evidence & Findings
    evidence_registry: Dict[str, EvidenceRegistryItem]
    research_findings: List[ResearchFinding]
    compliance_findings: List[ComplianceFinding]
    document_comparisons: List[DocumentComparisonFinding]
    verification_results: List[VerificationResult]
    identified_conflicts: List[IdentifiedConflict]
    unresolved_questions: List[str]
    
    # Human Approval
    approval_status: str  # NOT_REQUIRED, PENDING_APPROVAL, APPROVED, REJECTED, NEEDS_REVISION
    approval_metadata: Dict[str, Any]
    
    # Observability & Lifecycle
    execution_trace: List[ExecutionTraceItem]
    token_usage: Dict[str, int]
    workflow_status: str  # INITIALIZED, PLANNING, EXECUTING, VERIFYING, PENDING_APPROVAL, COMPLETED, REFUSED, FAILED
    final_report: Optional[InvestigationReport]
    errors: List[str]
