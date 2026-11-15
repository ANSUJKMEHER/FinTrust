"""
Compliance Analysis Agent: Identifies regulatory requirements, extracts statutory obligations,
deadlines, and financial thresholds, and distinguishes confirmed requirements from potential gaps.
"""
import re
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.agentic.agents.base import BaseAgent
from app.agentic.state import AgenticWorkflowState, ComplianceFinding, EvidenceRegistryItem
from app.llm.base import BaseLLMProvider


class ComplianceAnalysisAgent(BaseAgent):
    """Analyzes regulatory and policy text to extract obligations, thresholds, and compliance gaps."""

    # Regulatory detection patterns
    STATUTE_PATTERN = re.compile(
        r'\b(?:BSA\s+)?Section\s+[0-9]+(?:\([a-zA-Z0-9]+\))?|\b[0-9]+\s+CFR\s+[0-9\.]+|\bGDPR\s+Art(?:icle)?\s+[0-9]+|\bSOX\s+[0-9]+|\bFinCEN\s+CDD\s+Rule\b|\bTitle\s+VII\b',
        re.IGNORECASE
    )
    DEADLINE_PATTERN = re.compile(
        r'\b[0-9]+\s+(?:calendar\s+|business\s+)?(?:days|hours|months|weeks|years)\b',
        re.IGNORECASE
    )
    THRESHOLD_PATTERN = re.compile(
        r'(?:\$[0-9,]+(?:\.[0-9]{2})?|\b[0-9]+(?:\.[0-9]+)?%|\b[0-9]+\s+percent\b)',
        re.IGNORECASE
    )
    OBLIGATION_KEYWORDS = re.compile(r'\b(must|shall|is required to|are required to|mandated|strictly prohibited)\b', re.IGNORECASE)

    def __init__(self):
        super().__init__(
            name="compliance_agent",
            description="Extracts statutory obligations, thresholds, deadlines, and evaluates policy coverage with qualified language."
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
        evidence_registry: Dict[str, EvidenceRegistryItem] = state.get("evidence_registry", {})
        existing_findings: List[ComplianceFinding] = state.get("compliance_findings", [])
        
        new_findings: List[ComplianceFinding] = []
        finding_idx = len(existing_findings) + 1

        for ev_id, ev_item in evidence_registry.items():
            content = ev_item.get("content", "")
            cit = ev_item.get("citation_label", f"[{ev_item.get('document_title', 'Doc')}, Page N/A]")
            
            # Split content into sentences
            sentences = re.split(r'(?<=[.!?])\s+', content)

            for sent in sentences:
                sent_clean = sent.strip()
                if len(sent_clean) < 25:
                    continue

                is_obligation = bool(self.OBLIGATION_KEYWORDS.search(sent_clean))
                statute_match = self.STATUTE_PATTERN.search(sent_clean)
                deadline_match = self.DEADLINE_PATTERN.search(sent_clean)
                threshold_match = self.THRESHOLD_PATTERN.search(sent_clean)

                if is_obligation or statute_match or deadline_match or threshold_match:
                    # Categorize using qualified compliance taxonomy
                    if statute_match and (deadline_match or threshold_match):
                        category = "CONFIRMED_REQUIREMENT"
                        rationale = "Statutory provision with explicit quantitative threshold or deadline codified in authorized evidence."
                        confidence = 0.95
                    elif is_obligation:
                        category = "CONFIRMED_REQUIREMENT"
                        rationale = "Mandatory operational control identified with normative obligation language ('must'/'shall')."
                        confidence = 0.88
                    elif any(w in sent_clean.lower() for w in ["gap", "missing", "failure", "breach", "penalty"]):
                        category = "POTENTIAL_GAP"
                        rationale = "Passage indicates potential deficiency, penalty trigger, or exception requiring operational verification."
                        confidence = 0.80
                    else:
                        category = "REQUIRES_HUMAN_REVIEW"
                        rationale = "Relevant financial or regulatory metric observed; conditional applicability requires auditor interpretation."
                        confidence = 0.70

                    finding: ComplianceFinding = {
                        "finding_id": f"COMP_{finding_idx:03d}",
                        "category": category,
                        "requirement_text": sent_clean,
                        "statutory_reference": statute_match.group(0) if statute_match else None,
                        "filing_deadline": deadline_match.group(0) if deadline_match else None,
                        "financial_threshold": threshold_match.group(0) if threshold_match else None,
                        "supporting_evidence_ids": [ev_id],
                        "citations": [cit],
                        "confidence_score": confidence,
                        "qualifying_rationale": rationale,
                    }
                    new_findings.append(finding)
                    finding_idx += 1

        # If evidence was retrieved but no specific obligations detected
        if evidence_registry and not new_findings:
            new_findings.append({
                "finding_id": f"COMP_{finding_idx:03d}",
                "category": "INSUFFICIENT_EVIDENCE",
                "requirement_text": "Retrieved evidence does not contain explicit statutory obligation or threshold clauses for the target inquiry.",
                "statutory_reference": None,
                "filing_deadline": None,
                "financial_threshold": None,
                "supporting_evidence_ids": list(evidence_registry.keys()),
                "citations": [item["citation_label"] for item in evidence_registry.values()],
                "confidence_score": 0.50,
                "qualifying_rationale": "Evidence sufficiency check indicated absent normative requirements.",
            })

        all_findings = existing_findings + new_findings
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        self.record_trace(
            state,
            action="compliance_analysis",
            inputs={"evidence_items_examined": len(evidence_registry)},
            outputs={
                "compliance_findings_count": len(new_findings),
                "confirmed_requirements": sum(1 for f in new_findings if f["category"] == "CONFIRMED_REQUIREMENT"),
                "potential_gaps": sum(1 for f in new_findings if f["category"] == "POTENTIAL_GAP"),
                "requires_review": sum(1 for f in new_findings if f["category"] == "REQUIRES_HUMAN_REVIEW"),
            },
            status="SUCCESS",
            latency_ms=latency_ms,
        )

        return {"compliance_findings": all_findings}
