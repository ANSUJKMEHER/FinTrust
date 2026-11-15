"""
Verification Agent: Independently audits claims, validates citations, performs deterministic
entity checks, and flags unsupported or contradictory findings.
"""
import re
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.agentic.agents.base import BaseAgent
from app.agentic.state import (
    AgenticWorkflowState,
    ComplianceFinding,
    EvidenceRegistryItem,
    ResearchFinding,
    VerificationResult,
)
from app.llm.base import BaseLLMProvider
from app.services.citation_verification_service import CitationVerificationService, ClaimStatus


class VerificationAgent(BaseAgent):
    """Adversarial verification auditor that checks claims against evidence and rejects ungrounded statements."""

    def __init__(self):
        super().__init__(
            name="verification_agent",
            description="Performs independent claim verification, entity checks, citation validity, and contradiction detection."
        )
        self.verifier = CitationVerificationService()

    def execute(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        evidence_registry: Dict[str, EvidenceRegistryItem] = state.get("evidence_registry", {})
        compliance_findings: List[ComplianceFinding] = state.get("compliance_findings", [])
        research_findings: List[ResearchFinding] = state.get("research_findings", [])
        existing_results: List[VerificationResult] = state.get("verification_results", [])

        verification_results: List[VerificationResult] = []
        claim_counter = len(existing_results) + 1

        supported_count = 0
        partially_supported_count = 0
        contradicted_count = 0
        unsupported_count = 0

        # Build evidence lookup text for fast verification
        evidence_texts = {
            eid: (item.get("content") or item.get("chunk_text") or "").lower()
            for eid, item in evidence_registry.items()
        }

        # 1. Audit Compliance Findings
        for finding in compliance_findings:
            claim_text = finding.get("requirement_text", "")
            if not claim_text:
                continue

            supporting_eids = finding.get("supporting_evidence_ids", [])
            citations = finding.get("citations", [])

            # Extract entities (currency, deadlines, percentages, statutes)
            entities = self.verifier.extract_entities(claim_text)
            
            # Combine text of cited evidence
            relevant_evidence = " ".join(evidence_texts.get(eid, "") for eid in supporting_eids)

            # Check if cited evidence actually exists in registry
            valid_eids = [eid for eid in supporting_eids if eid in evidence_registry]
            if not valid_eids:
                status = "UNSUPPORTED"
                explanation = "Claim references fabricated or unindexed evidence IDs."
                confidence = 0.1
                unsupported_count += 1
            else:
                # Deterministic entity verification
                entity_checks: Dict[str, bool] = {}
                contradiction_found = False

                for cat, ent_list in entities.items():
                    for ent in ent_list:
                        ent_norm = re.sub(r'\s+', ' ', ent.lower().strip())
                        if ent_norm in relevant_evidence:
                            entity_checks[ent] = True
                        else:
                            entity_checks[ent] = False
                            # Specific numbers or statutory sections not in evidence
                            if cat in ("currency", "deadlines", "percentages", "statutes"):
                                contradiction_found = True

                # Word overlap entailment
                words_claim = set(re.findall(r'\b[a-z0-9]{3,}\b', claim_text.lower()))
                words_ev = set(re.findall(r'\b[a-z0-9]{3,}\b', relevant_evidence))
                overlap = len(words_claim.intersection(words_ev)) / max(1, len(words_claim))

                if contradiction_found:
                    status = "CONTRADICTED"
                    explanation = "Claim asserts specific figures, sections, or deadlines not supported by cited evidence."
                    confidence = 0.90
                    contradicted_count += 1
                elif overlap >= 0.60 and all(entity_checks.values()):
                    status = "SUPPORTED"
                    explanation = "Claim is thoroughly corroborated by cited evidence with verified figures."
                    confidence = 0.95
                    supported_count += 1
                elif overlap >= 0.35:
                    status = "PARTIALLY_SUPPORTED"
                    explanation = "Claim has partial textual corroboration but lacks full statutory verification."
                    confidence = 0.70
                    partially_supported_count += 1
                else:
                    status = "UNSUPPORTED"
                    explanation = f"Insufficient textual overlap ({overlap:.1%}) between claim and cited passages."
                    confidence = 0.50
                    unsupported_count += 1

            res: VerificationResult = {
                "claim_id": f"VRF_{claim_counter:03d}",
                "claim_text": claim_text,
                "status": status,
                "supporting_evidence_ids": supporting_eids,
                "citations": citations,
                "extracted_entities": entities,
                "entity_verification": entity_checks if 'entity_checks' in locals() else {},
                "confidence_score": confidence,
                "explanation": explanation,
            }
            verification_results.append(res)
            claim_counter += 1

        # 2. Audit Research Findings
        for finding in research_findings:
            claim_text = finding.get("claim_text") or finding.get("finding_text") or ""
            if not claim_text:
                continue
            eid = finding.get("evidence_id")
            supporting_eids = [eid] if eid else finding.get("supporting_evidence_ids", [])
            citations = finding.get("citations", [])

            entities = self.verifier.extract_entities(claim_text)
            relevant_evidence = " ".join(evidence_texts.get(e, "") for e in supporting_eids)

            valid_eids = [e for e in supporting_eids if e in evidence_registry]
            if not valid_eids:
                status = "UNSUPPORTED"
                explanation = "Claim references unindexed evidence ID."
                confidence = 0.1
                unsupported_count += 1
            else:
                entity_checks = {}
                contradiction_found = False
                for cat, ent_list in entities.items():
                    for ent in ent_list:
                        ent_norm = re.sub(r'\s+', ' ', ent.lower().strip())
                        if ent_norm in relevant_evidence:
                            entity_checks[ent] = True
                        else:
                            entity_checks[ent] = False
                            if cat in ("currency", "deadlines", "percentages", "statutes"):
                                contradiction_found = True

                words_claim = set(re.findall(r'\b[a-z0-9]{3,}\b', claim_text.lower()))
                words_ev = set(re.findall(r'\b[a-z0-9]{3,}\b', relevant_evidence))
                overlap = len(words_claim.intersection(words_ev)) / max(1, len(words_claim))

                if contradiction_found:
                    status = "CONTRADICTED"
                    explanation = "Entities or numeric thresholds contradict provided evidence."
                    confidence = 0.85
                    contradicted_count += 1
                elif overlap >= 0.70:
                    status = "SUPPORTED"
                    explanation = f"Claim supported by evidence with high textual overlap ({overlap:.1%})."
                    confidence = 0.95
                    supported_count += 1
                elif overlap >= 0.35:
                    status = "PARTIALLY_SUPPORTED"
                    explanation = "Claim has partial textual corroboration."
                    confidence = 0.70
                    partially_supported_count += 1
                else:
                    status = "UNSUPPORTED"
                    explanation = f"Insufficient textual overlap ({overlap:.1%})."
                    confidence = 0.50
                    unsupported_count += 1

            res = {
                "claim_id": f"VRF_{claim_counter:03d}",
                "claim_text": claim_text,
                "status": status,
                "supporting_evidence_ids": supporting_eids,
                "citations": citations,
                "extracted_entities": entities,
                "entity_verification": entity_checks,
                "confidence_score": confidence,
                "explanation": explanation,
            }
            verification_results.append(res)
            claim_counter += 1

        total_claims = len(verification_results)
        faithfulness_score = (supported_count + (partially_supported_count * 0.5)) / max(1, total_claims)
        is_faithful = (contradicted_count == 0) and (unsupported_count == 0) and (faithfulness_score >= 0.70)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self.record_trace(
            state,
            action="verify_findings",
            inputs={"claims_evaluated": total_claims},
            outputs={
                "total_claims": total_claims,
                "supported": supported_count,
                "partially_supported": partially_supported_count,
                "contradicted": contradicted_count,
                "unsupported": unsupported_count,
                "overall_faithfulness": round(faithfulness_score, 4),
                "is_faithful": is_faithful,
            },
            status="SUCCESS",
            latency_ms=latency_ms,
        )

        return {
            "verification_results": existing_results + verification_results,
        }
