"""
Document Intelligence Agent: Reuses Phase 4 Summarization and Comparison services
to extract structured compliance summaries and detect cross-document differences.
"""
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.agentic.agents.base import BaseAgent
from app.agentic.state import AgenticWorkflowState, DocumentComparisonFinding
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.db.models.document import Document
from app.db.models.user import User
from app.llm.base import BaseLLMProvider
from app.services.document_comparison_service import DocumentComparisonService
from app.services.document_summary_service import DocumentSummaryService


class DocumentIntelligenceAgent(BaseAgent):
    """Reuses Phase 4 DocumentSummaryService and DocumentComparisonService for agentic workflows."""

    def __init__(self):
        super().__init__(
            name="document_intelligence_agent",
            description="Performs multi-document differential comparison and structured compliance document summarization."
        )

    def execute(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        if db is None:
            try:
                from app.agentic.mcp.context import get_current_mcp_context
                ctx = get_current_mcp_context()
                db = ctx.db_session
            except Exception:
                db = state.get("db_session")

        tenant_id_str = state.get("tenant_id")
        user_id_str = state.get("user_id")

        if not db or not tenant_id_str or not user_id_str:
            return {
                "document_comparisons": state.get("document_comparisons", []),
                "comparison_findings": state.get("comparison_findings", []),
            }

        if not tenant_id_str or not user_id_str:
            err = "DocumentIntelligenceAgent failed: tenant_id or user_id missing in state."
            self.record_trace(state, "analyze_documents", None, None, status="FAILED", error_details=err)
            return {"errors": state.get("errors", []) + [err]}

        tenant_uuid = uuid.UUID(tenant_id_str)
        user_uuid = uuid.UUID(user_id_str)
        user = db.query(User).filter(User.id == user_uuid, User.tenant_id == tenant_uuid).first()
        if not user:
            err = f"DocumentIntelligenceAgent failed: user '{user_uuid}' not found."
            self.record_trace(state, "analyze_documents", None, None, status="FAILED", error_details=err)
            return {"errors": state.get("errors", []) + [err]}

        task_type = state.get("task_type", "GENERAL_RESEARCH")
        execution_plan = state.get("execution_plan", [])
        
        # Check if target document IDs are provided in plan or state
        doc_ids: List[str] = []
        for step in execution_plan:
            if "document_ids" in step:
                doc_ids.extend([str(d) for d in step["document_ids"]])
        
        # If not in plan, check if documents exist in evidence registry
        evidence_registry = state.get("evidence_registry", {})
        if not doc_ids and evidence_registry:
            doc_ids = list(dict.fromkeys(item["document_id"] for item in evidence_registry.values()))

        comparison_findings: List[DocumentComparisonFinding] = state.get("document_comparisons", [])

        # Scenario 1: Multi-Document / Version Comparison (2 or more documents)
        if len(doc_ids) >= 2 or task_type == "POLICY_COMPARISON":
            if len(doc_ids) >= 2:
                doc1_id = uuid.UUID(doc_ids[0])
                doc2_id = uuid.UUID(doc_ids[1])
                comparison_service = DocumentComparisonService(db=db)
                try:
                    comp_result = comparison_service.compare_documents(
                        doc1_id=doc1_id,
                        doc2_id=doc2_id,
                        user=user,
                    )
                    for f in comp_result.findings:
                        item: DocumentComparisonFinding = {
                            "finding_id": f.finding_id,
                            "finding_type": f.finding_type.value,
                            "description": f.description,
                            "doc1_title": comp_result.doc1_title,
                            "doc1_statement": f.doc1_statement,
                            "doc1_citation": f.doc1_citation,
                            "doc2_title": comp_result.doc2_title,
                            "doc2_statement": f.doc2_statement,
                            "doc2_citation": f.doc2_citation,
                            "confidence_score": f.confidence_score,
                        }
                        comparison_findings.append(item)

                    latency_ms = (time.perf_counter() - start_time) * 1000.0
                    self.record_trace(
                        state,
                        action="compare_documents",
                        inputs={"doc1_id": str(doc1_id), "doc2_id": str(doc2_id)},
                        outputs={"findings_count": len(comp_result.findings), "total_findings": comp_result.total_findings},
                        status="SUCCESS",
                        latency_ms=latency_ms,
                    )
                    return {"document_comparisons": comparison_findings}
                except (EntityNotFoundError, PermissionDeniedError) as exc:
                    err = f"Document comparison failed: {str(exc)}"
                    self.record_trace(state, "compare_documents", None, None, status="FAILED", error_details=err)
                    return {"errors": state.get("errors", []) + [err]}

        # Scenario 2: Single Document Structured Summarization
        if doc_ids:
            target_doc_id = uuid.UUID(doc_ids[0])
            summary_service = DocumentSummaryService(db=db, llm_provider=llm_provider)
            try:
                summary_result = summary_service.summarize_document(
                    document_id=target_doc_id,
                    user=user,
                )
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                self.record_trace(
                    state,
                    action="summarize_document",
                    inputs={"document_id": str(target_doc_id)},
                    outputs={
                        "title": summary_result.document_title,
                        "obligations_count": len(summary_result.key_obligations),
                        "thresholds_count": len(summary_result.financial_thresholds),
                        "deadlines_count": len(summary_result.compliance_deadlines),
                    },
                    status="SUCCESS",
                    latency_ms=latency_ms,
                )
                return {
                    "document_comparisons": comparison_findings,
                }
            except (EntityNotFoundError, PermissionDeniedError) as exc:
                err = f"Document summarization failed: {str(exc)}"
                self.record_trace(state, "summarize_document", None, None, status="FAILED", error_details=err)
                return {"errors": state.get("errors", []) + [err]}

        # If no explicit document IDs found to compare or summarize
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self.record_trace(
            state,
            action="evaluate_documents",
            inputs={"doc_ids_count": len(doc_ids)},
            outputs={"status": "SKIPPED_NO_TARGET_DOCS"},
            status="SUCCESS",
            latency_ms=latency_ms,
        )
        return {"document_comparisons": comparison_findings}
