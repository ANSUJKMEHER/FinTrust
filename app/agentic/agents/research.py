"""
Research Agent: Performs permission-aware hybrid search, discovers relevant passages,
and populates the central evidence registry.
"""
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.agentic.agents.base import BaseAgent
from app.agentic.state import AgenticWorkflowState, EvidenceRegistryItem, ResearchFinding
from app.core.exceptions import EntityNotFoundError
from app.db.models.document import Document
from app.db.models.user import User
from app.llm.base import BaseLLMProvider
from app.services.hybrid_search_service import HybridSearchService


class ResearchAgent(BaseAgent):
    """Searches authorized financial documents, retrieves relevant passages, and maintains the evidence registry."""

    def __init__(self):
        super().__init__(
            name="research_agent",
            description="Performs dense, sparse, and hybrid retrieval across authorized tenant documents."
        )

    def execute(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        query = state.get("user_query") or state.get("normalized_query") or state.get("original_query") or state.get("query") or ""
        tenant_id_str = state.get("tenant_id")
        user_id_str = state.get("user_id")

        if db is None:
            try:
                from app.agentic.mcp.context import get_current_mcp_context
                ctx = get_current_mcp_context()
                db = ctx.db_session
            except Exception:
                db = state.get("db_session")

        if not db or not tenant_id_str or not user_id_str:
            # If no DB session or credentials provided (e.g. synthetic test), preserve existing registry
            return {
                "evidence_registry": state.get("evidence_registry", {}),
                "research_findings": state.get("research_findings", []),
            }

        tenant_uuid = uuid.UUID(tenant_id_str)
        user_uuid = uuid.UUID(user_id_str)

        # Retrieve user record for deterministic permission evaluation
        user = db.query(User).filter(User.id == user_uuid, User.tenant_id == tenant_uuid).first()
        if not user:
            err = f"ResearchAgent failed: user '{user_uuid}' not found in tenant '{tenant_uuid}'."
            self.record_trace(state, "search_documents", {"query": query}, None, status="FAILED", error_details=err)
            return {"errors": state.get("errors", []) + [err]}

        search_service = HybridSearchService(db=db)
        
        # Execute hybrid search with tenant isolation & document ACL enforcement
        search_results = search_service.hybrid_search(
            query=query,
            user=user,
            top_k=8,
            apply_rerank=True,
        )

        evidence_registry: Dict[str, EvidenceRegistryItem] = state.get("evidence_registry", {})
        research_findings: List[ResearchFinding] = state.get("research_findings", [])
        
        current_ev_count = len(evidence_registry)
        added_findings: List[ResearchFinding] = []

        if not search_results:
            finding_id = f"RES_{len(research_findings) + 1:03d}"
            unresolved = state.get("unresolved_questions", [])
            unresolved.append(f"No authorized evidence retrieved for query: '{query}'")
            state["unresolved_questions"] = unresolved

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            self.record_trace(
                state,
                action="hybrid_search",
                inputs={"query": query, "top_k": 8},
                outputs={"retrieved_count": 0, "status": "NO_EVIDENCE_FOUND"},
                status="SUCCESS",
                latency_ms=latency_ms,
            )
            return {
                "research_findings": research_findings,
                "unresolved_questions": unresolved,
            }

        for idx, result in enumerate(search_results, start=current_ev_count + 1):
            ev_id = f"EVIDENCE_{idx:03d}"
            chunk_id_str = str(result.chunk_id)
            doc_id_str = str(result.document_id)

            # Format canonical citation label
            sec = result.section_heading or "General"
            pg = f"Page {result.page_number}" if result.page_number else "Page N/A"
            citation_label = f"[{result.document_title}, {sec}, {pg}]"

            # Register in evidence registry
            evidence_registry[ev_id] = {
                "evidence_id": ev_id,
                "chunk_id": chunk_id_str,
                "document_id": doc_id_str,
                "document_version_id": str(result.document_version_id) if result.document_version_id else "",
                "document_title": result.document_title,
                "document_classification": result.document_classification,
                "page_number": result.page_number,
                "section_heading": result.section_heading,
                "heading_breadcrumb": result.heading_breadcrumb,
                "content": result.content,
                "token_count": result.token_count,
                "relevance_score": round(result.score, 4),
                "citation_label": citation_label,
            }

            # Generate structured research finding
            finding: ResearchFinding = {
                "finding_id": f"RES_{idx:03d}",
                "topic": result.section_heading or result.document_title,
                "summary": result.content[:250].strip() + ("..." if len(result.content) > 250 else ""),
                "supporting_evidence_ids": [ev_id],
                "citations": [citation_label],
                "relevance_score": round(result.score, 4),
                "is_sufficient": result.score >= 0.35,
                "missing_aspects": [],
            }
            added_findings.append(finding)

        research_findings.extend(added_findings)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        self.record_trace(
            state,
            action="hybrid_search_and_registry",
            inputs={"query": query, "top_k": 8},
            outputs={
                "retrieved_count": len(search_results),
                "evidence_items_registered": len(added_findings),
                "top_score": max((r.score for r in search_results), default=0.0)
            },
            status="SUCCESS",
            latency_ms=latency_ms,
        )

        return {
            "evidence_registry": evidence_registry,
            "research_findings": research_findings,
        }
