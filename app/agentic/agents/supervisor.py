"""
Supervisor Agent: Task classification, dynamic agent selection, execution planning,
workflow coordination, conflict escalation, and final compliance report synthesis.
"""
from datetime import datetime, timezone
import re
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.agentic.agents.base import BaseAgent
from app.agentic.conflict_resolution import ConflictResolutionEngine
from app.agentic.state import (
    AgenticWorkflowState,
    ComplianceFinding,
    DocumentComparisonFinding,
    EvidenceRegistryItem,
    IdentifiedConflict,
    InvestigationReport,
    ResearchFinding,
    VerificationResult,
)
from app.db.models.workflow import WorkflowTaskType
from app.llm.base import BaseLLMProvider


class SupervisorAgent(BaseAgent):
    """Chief orchestrator governing agent dispatch, verification review, and report assembly."""

    def __init__(self):
        super().__init__(
            name="supervisor_agent",
            description="Performs task classification, dynamic agent routing, verification evaluation, and synthesis."
        )
        self.conflict_engine = ConflictResolutionEngine()

    def classify_and_plan(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ) -> Dict[str, Any]:
        """Classifies the user query, determines task type, and selects relevant agents dynamically."""
        start_time = time.perf_counter()
        query = (state.get("user_query") or state.get("original_query") or state.get("query") or "").strip()
        query_lower = query.lower()

        # Deterministic heuristic task classification
        if any(k in query_lower for k in ["compare", "difference", "version", "changed", "diff"]):
            task_type = WorkflowTaskType.POLICY_COMPARISON.value
            selected_agents = ["doc_intelligence", "verification"]
            plan = [
                {"step": 1, "agent": "doc_intelligence", "objective": "Extract and compare multi-document policies and versions"},
                {"step": 2, "agent": "verification", "objective": "Verify extracted comparative findings against source texts"},
            ]
        elif any(k in query_lower for k in ["comply", "compliance", "audit", "violation", "breach", "bsa", "gdpr", "sox"]):
            task_type = WorkflowTaskType.REGULATORY_COMPLIANCE.value
            selected_agents = ["research", "compliance", "verification"]
            plan = [
                {"step": 1, "agent": "research", "objective": "Retrieve authorized statutory and policy evidence"},
                {"step": 2, "agent": "compliance", "objective": "Extract statutory obligations, thresholds, and identify potential gaps"},
                {"step": 3, "agent": "verification", "objective": "Independently audit compliance claims and validate citations"},
            ]
        elif any(k in query_lower for k in ["obligation", "requirement", "mandated", "must file", "deadline", "threshold"]):
            task_type = WorkflowTaskType.OBLIGATION_EXTRACTION.value
            selected_agents = ["research", "compliance", "verification"]
            plan = [
                {"step": 1, "agent": "research", "objective": "Retrieve target regulatory provisions"},
                {"step": 2, "agent": "compliance", "objective": "Extract quantitative thresholds, deadlines, and mandatory controls"},
                {"step": 3, "agent": "verification", "objective": "Verify entity values and statutory section citations"},
            ]
        elif any(k in query_lower for k in ["risk", "deficiency", "vulnerability", "exposure"]):
            task_type = WorkflowTaskType.RISK_INVESTIGATION.value
            selected_agents = ["research", "compliance", "verification"]
            plan = [
                {"step": 1, "agent": "research", "objective": "Identify documented risk factors and exception scenarios"},
                {"step": 2, "agent": "compliance", "objective": "Map risk triggers against compliance benchmarks"},
                {"step": 3, "agent": "verification", "objective": "Verify documented risk citations"},
            ]
        else:
            task_type = WorkflowTaskType.GENERAL_RESEARCH.value
            selected_agents = ["research", "verification"]
            plan = [
                {"step": 1, "agent": "research", "objective": "Execute hybrid search across authorized documentation"},
                {"step": 2, "agent": "verification", "objective": "Verify factual claims against retrieved evidence"},
            ]

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self.record_trace(
            state,
            action="classify_and_plan",
            inputs={"query": query},
            outputs={"task_type": task_type, "selected_agents": selected_agents, "plan_steps": len(plan)},
            status="SUCCESS",
            latency_ms=latency_ms,
        )

        return {
            "task_type": task_type,
            "selected_agents": selected_agents,
            "execution_plan": plan,
            "workflow_status": "PLANNING",
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    def evaluate_and_route(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Evaluates intermediate findings, triggers conflict detection, and decides routing."""
        start_time = time.perf_counter()
        
        # 1. Detect conflicts if db provided, or use conflict engine
        if db is not None:
            conflicts = self.conflict_engine.detect_and_resolve_conflicts(state, db)
        else:
            conflicts = self.conflict_engine.detect_conflicts(state)
        state["identified_conflicts"] = conflicts

        # 2. Check if human approval is required
        has_high_severity_conflict = any(c.get("severity") == "HIGH" for c in conflicts)
        mandated_human_review = state.get("approval_status") == "PENDING_APPROVAL"
        
        verification_results = state.get("verification_results", [])
        has_contradicted_claims = any(v.get("status") == "CONTRADICTED" for v in verification_results)

        if has_high_severity_conflict or has_contradicted_claims or mandated_human_review:
            approval_status = "PENDING_APPROVAL"
            next_action = "REQUIRE_APPROVAL"
        else:
            approval_status = state.get("approval_status", "NOT_REQUIRED")
            next_action = "GENERATE_REPORT"

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self.record_trace(
            state,
            action="evaluate_and_route",
            inputs={
                "conflicts_count": len(conflicts),
                "verification_count": len(verification_results),
            },
            outputs={
                "next_action": next_action,
                "approval_status": approval_status,
                "conflicts_detected": len(conflicts),
            },
            status="SUCCESS",
            latency_ms=latency_ms,
        )

        return {
            "identified_conflicts": conflicts,
            "approval_status": approval_status,
        }

    def synthesize_report(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ) -> Dict[str, Any]:
        """Synthesizes the authoritative 14-section Final Compliance Investigation Report."""
        start_time = time.perf_counter()
        query = (state.get("user_query") or state.get("original_query") or state.get("query") or "").strip()
        task_type = state.get("task_type", "GENERAL_RESEARCH")
        evidence_registry = state.get("evidence_registry", {})
        research_findings = state.get("research_findings", [])
        compliance_findings = state.get("compliance_findings", [])
        comparisons = state.get("document_comparisons", [])
        conflicts = state.get("identified_conflicts", [])
        verifications = state.get("verification_results", [])
        unresolved = state.get("unresolved_questions", [])

        # Documents Examined
        docs_examined = []
        seen_docs = set()
        for ev in evidence_registry.values():
            d_id = ev.get("document_id")
            if d_id and d_id not in seen_docs:
                seen_docs.add(d_id)
                docs_examined.append({
                    "document_id": d_id,
                    "title": ev.get("document_title"),
                    "classification": ev.get("document_classification"),
                })

        # Thresholds and Deadlines
        thresholds_list = []
        deadlines_list = []
        for f in compliance_findings:
            if f.get("financial_threshold"):
                thresholds_list.append({
                    "threshold": f["financial_threshold"],
                    "context": f["requirement_text"],
                    "citation": f["citations"][0] if f.get("citations") else "N/A"
                })
            if f.get("filing_deadline"):
                deadlines_list.append({
                    "deadline": f["filing_deadline"],
                    "context": f["requirement_text"],
                    "citation": f["citations"][0] if f.get("citations") else "N/A"
                })

        # Supporting Citations
        all_citations = list(dict.fromkeys(
            cit
            for finding in (compliance_findings + research_findings)
            for cit in finding.get("citations", [])
        ))

        # Verification summary metrics
        supported_cnt = sum(1 for v in verifications if v.get("status") == "SUPPORTED")
        partially_cnt = sum(1 for v in verifications if v.get("status") == "PARTIALLY_SUPPORTED")
        contradicted_cnt = sum(1 for v in verifications if v.get("status") == "CONTRADICTED")
        unsupported_cnt = sum(1 for v in verifications if v.get("status") == "UNSUPPORTED")
        total_claims = len(verifications)
        score = (supported_cnt + (partially_cnt * 0.5)) / max(1, total_claims)

        verification_summary = {
            "total_claims": total_claims,
            "supported_claims": supported_cnt,
            "partially_supported_claims": partially_cnt,
            "contradicted_claims": contradicted_cnt,
            "unsupported_claims": unsupported_cnt,
            "faithfulness_score": round(score, 4),
            "is_faithful": (contradicted_cnt == 0 and unsupported_cnt == 0 and score >= 0.70),
        }

        # Human Review Requirements
        human_reqs = []
        if conflicts:
            human_reqs.append(f"{len(conflicts)} cross-document conflict(s) require compliance officer reconciliation.")
        if contradicted_cnt > 0:
            human_reqs.append(f"{contradicted_cnt} finding(s) contradicted cited evidence and were rejected.")
        if any(f.get("category") == "REQUIRES_HUMAN_REVIEW" for f in compliance_findings):
            human_reqs.append("One or more compliance obligations require formal legal/audit interpretation.")

        # Construct Executive Summary
        exec_summary = (
            f"Automated multi-agent compliance investigation for objective: '{query}'. "
            f"Analyzed {len(docs_examined)} document(s) across {len(evidence_registry)} evidence item(s). "
            f"Identified {len(compliance_findings)} compliance requirement(s) and {len(conflicts)} conflict(s). "
            f"Verification outcome: {supported_cnt}/{max(1, total_claims)} claims supported with "
            f"{verification_summary['faithfulness_score']:.1%} faithfulness score."
        )

        conclusion = (
            f"Investigation concluded under task profile '{task_type}'. "
            f"Findings are evidence-anchored and subject to tenant boundary isolation. "
            "Note: This report provides automated technical analysis based strictly on authorized repository evidence and does not constitute formal legal counsel."
        )

        final_report: InvestigationReport = {
            "executive_summary": exec_summary,
            "investigation_objective": query,
            "documents_examined": docs_examined,
            "research_methodology": "LangGraph multi-agent hybrid search, deterministic entity extraction, and independent citation verification.",
            "regulatory_requirements": [
                {"requirement": f["requirement_text"], "statute": f.get("statutory_reference"), "citation": f["citations"][0] if f.get("citations") else "N/A"}
                for f in compliance_findings if f.get("category") == "CONFIRMED_REQUIREMENT"
            ],
            "compliance_findings": compliance_findings,
            "potential_gaps": [
                {"gap": f["requirement_text"], "rationale": f.get("qualifying_rationale"), "citation": f["citations"][0] if f.get("citations") else "N/A"}
                for f in compliance_findings if f.get("category") == "POTENTIAL_GAP"
            ],
            "thresholds_and_deadlines": {
                "thresholds": thresholds_list,
                "deadlines": deadlines_list,
            },
            "conflicting_evidence": conflicts,
            "supporting_citations": all_citations,
            "verification_summary": verification_summary,
            "unresolved_questions": unresolved,
            "human_review_requirements": human_reqs,
            "conclusion": conclusion,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self.record_trace(
            state,
            action="synthesize_final_report",
            inputs={"sections_generated": 14},
            outputs={"report_generated": True, "claims_verified": total_claims},
            status="SUCCESS",
            latency_ms=latency_ms,
        )

        return {
            "final_report": final_report,
            "workflow_status": "COMPLETED" if state.get("approval_status") != "PENDING_APPROVAL" else "PENDING_APPROVAL",
        }

    def execute(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ) -> Dict[str, Any]:
        """Default execute hook delegating to report synthesis if plan complete."""
        return self.synthesize_report(state, db, llm_provider)

    # Aliases for graph workflow integration
    plan_task = classify_and_plan
    evaluate_evidence_sufficiency = evaluate_and_route
    generate_final_report = synthesize_report
