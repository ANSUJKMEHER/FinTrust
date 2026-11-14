from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.citation_service import VerifiedCitation
from app.services.context_construction_service import EvidenceItem, StructuredContext

logger = logging.getLogger(__name__)


class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class VerifiedClaim:
    claim_id: str
    claim_text: str
    status: ClaimStatus
    confidence_score: float
    supporting_evidence_ids: List[str]
    citations: List[VerifiedCitation]
    extracted_entities: Dict[str, List[str]]  # "currency", "percentages", "statutes", "deadlines"
    entity_verification: Dict[str, bool]     # entity -> exists in evidence
    explanation: str


@dataclass
class VerificationSummary:
    total_claims: int
    supported_claims: int
    partially_supported_claims: int
    contradicted_claims: int
    unsupported_claims: int
    unverifiable_claims: int
    overall_faithfulness_score: float
    is_faithful: bool
    claims: List[VerifiedClaim]


class CitationVerificationService:
    """Verifies whether generated claims are faithfully supported by cited evidence."""

    # Regex patterns for deterministic financial/regulatory entity verification
    CURRENCY_REGEX = re.compile(r'\$[0-9,]+(?:\.[0-9]{2})?', re.IGNORECASE)
    PERCENT_REGEX = re.compile(r'\b[0-9]+(?:\.[0-9]+)?%|\b[0-9]+\s+percent\b', re.IGNORECASE)
    STATUTE_REGEX = re.compile(
        r'\b(?:BSA\s+)?Section\s+[0-9]+(?:\([a-zA-Z0-9]+\))?|\b(?:GDPR\s+)?Art(?:icle)?\.?\s+[0-9]+|\b[0-9]+\s+CFR\s+[0-9\.]+|\bSOX\s+(?:Section\s+)?[0-9]+',
        re.IGNORECASE
    )
    DEADLINE_REGEX = re.compile(
        r'\b[0-9]+\s+(?:calendar\s+|business\s+)?(?:days|hours|months|years|weeks)\b',
        re.IGNORECASE
    )

    def extract_claims(self, text: str) -> List[str]:
        """Splits answer text into discrete factual sentences/claims, stripping inline citations."""
        # Clean inline citations first to get pure statement text
        cleaned = re.sub(r'\[([^,\]]+),\s*([^,\]]+),\s*Page\s*[^\]]+\]', '', text)
        cleaned = re.sub(r'\[([^,\]]+),\s*Page\s*[^\]]+\]', '', cleaned)

        # Split on sentence boundaries
        raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', cleaned)
        claims = []
        for s in raw_sentences:
            s_clean = s.strip()
            # Ignore trivial refusal or disclaimer statements
            if len(s_clean) > 15 and not s_clean.lower().startswith("the provided documents do not contain"):
                claims.append(s_clean)
        return claims

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extracts critical financial figures, statutory sections, and deadlines from text."""
        return {
            "currency": self.CURRENCY_REGEX.findall(text),
            "percentages": self.PERCENT_REGEX.findall(text),
            "statutes": self.STATUTE_REGEX.findall(text),
            "deadlines": self.DEADLINE_REGEX.findall(text),
        }

    def verify_claim(
        self,
        claim_text: str,
        claim_index: int,
        citations: List[VerifiedCitation],
        evidence_registry: Dict[str, EvidenceItem]
    ) -> VerifiedClaim:
        """Evaluates a single claim against its associated cited evidence items."""
        claim_id = f"CLAIM_{claim_index:03d}"
        extracted = self.extract_entities(claim_text)

        # Collect evidence texts matching the citations for this claim
        supporting_evidence_ids = [c.evidence_id for c in citations if c.evidence_id and c.is_valid]
        if not supporting_evidence_ids:
            # Check if any citation was invalid
            if citations:
                return VerifiedClaim(
                    claim_id=claim_id,
                    claim_text=claim_text,
                    status=ClaimStatus.UNSUPPORTED,
                    confidence_score=0.1,
                    supporting_evidence_ids=[],
                    citations=citations,
                    extracted_entities=extracted,
                    entity_verification={},
                    explanation="Citations attached to this claim do not match any retrieved evidence in context."
                )
            else:
                return VerifiedClaim(
                    claim_id=claim_id,
                    claim_text=claim_text,
                    status=ClaimStatus.UNVERIFIABLE,
                    confidence_score=0.0,
                    supporting_evidence_ids=[],
                    citations=[],
                    extracted_entities=extracted,
                    entity_verification={},
                    explanation="No citations provided for this claim."
                )

        combined_evidence_text = " ".join(
            evidence_registry[eid].content for eid in supporting_evidence_ids if eid in evidence_registry
        ).lower()

        # Deterministic entity verification
        entity_checks: Dict[str, bool] = {}
        contradiction_detected = False
        unsupported_entities = False

        for category, entities in extracted.items():
            for entity in entities:
                ent_lower = entity.lower().strip()
                # Normalize spaces (e.g. "30  days" -> "30 days")
                ent_norm = re.sub(r'\s+', ' ', ent_lower)
                
                # Check presence in evidence
                if ent_norm in combined_evidence_text:
                    entity_checks[entity] = True
                else:
                    entity_checks[entity] = False
                    unsupported_entities = True
                    # If it's a numeric statutory figure or deadline that doesn't appear in evidence
                    if category in ("currency", "deadlines", "percentages", "statutes"):
                        contradiction_detected = True

        # Token overlap check (content words)
        claim_words = set(re.findall(r'\b[a-z0-9]{3,}\b', claim_text.lower()))
        evidence_words = set(re.findall(r'\b[a-z0-9]{3,}\b', combined_evidence_text))

        if not claim_words:
            overlap_ratio = 1.0
        else:
            overlap = len(claim_words.intersection(evidence_words))
            overlap_ratio = overlap / len(claim_words)

        # Determine Final Status
        if contradiction_detected:
            status = ClaimStatus.CONTRADICTED
            confidence = 0.85
            explanation = "Claim asserts specific figures, sections, or deadlines not supported by cited evidence."
        elif unsupported_entities:
            status = ClaimStatus.UNSUPPORTED
            confidence = 0.80
            explanation = "One or more critical financial entities could not be verified in cited passages."
        elif overlap_ratio >= 0.65:
            status = ClaimStatus.SUPPORTED
            confidence = min(0.98, 0.70 + (overlap_ratio * 0.3))
            explanation = "Claim is thoroughly established by cited evidence with verified entities."
        elif overlap_ratio >= 0.40:
            status = ClaimStatus.PARTIALLY_SUPPORTED
            confidence = 0.70
            explanation = "Claim has moderate semantic overlap with cited evidence but lacks full corroboration."
        else:
            status = ClaimStatus.UNSUPPORTED
            confidence = 0.50
            explanation = f"Insufficient textual evidence overlap ({overlap_ratio:.1%}) between claim and cited passages."

        return VerifiedClaim(
            claim_id=claim_id,
            claim_text=claim_text,
            status=status,
            confidence_score=confidence,
            supporting_evidence_ids=supporting_evidence_ids,
            citations=citations,
            extracted_entities=extracted,
            entity_verification=entity_checks,
            explanation=explanation
        )

    def verify_answer(
        self,
        answer_text: str,
        citations: List[VerifiedCitation],
        context: StructuredContext
    ) -> VerificationSummary:
        """Executes full multi-step claim verification for the entire generated answer."""
        claims_text = self.extract_claims(answer_text)
        if not claims_text:
            return VerificationSummary(
                total_claims=0,
                supported_claims=0,
                partially_supported_claims=0,
                contradicted_claims=0,
                unsupported_claims=0,
                unverifiable_claims=0,
                overall_faithfulness_score=1.0 if "insufficient evidence" in answer_text.lower() else 0.0,
                is_faithful=True,
                claims=[]
            )

        verified_claims: List[VerifiedClaim] = []
        supported_count = 0
        partial_count = 0
        contradicted_count = 0
        unsupported_count = 0
        unverifiable_count = 0

        # Map citations to claims based on proximity in original answer text
        for idx, claim in enumerate(claims_text, start=1):
            # Find citations that appear near this claim text in the answer
            claim_start = answer_text.find(claim[:30])
            claim_end = claim_start + len(claim) + 120  # Look ahead 120 chars for inline citation
            relevant_citations = [
                c for c in citations
                if c.raw_citation_text in answer_text[claim_start:claim_end]
            ]
            if not relevant_citations and citations:
                # If specific proximity failed, assign all valid citations from matching docs
                relevant_citations = [c for c in citations if c.is_valid]

            vc = self.verify_claim(
                claim_text=claim,
                claim_index=idx,
                citations=relevant_citations,
                evidence_registry=context.evidence_registry
            )
            verified_claims.append(vc)

            if vc.status == ClaimStatus.SUPPORTED:
                supported_count += 1
            elif vc.status == ClaimStatus.PARTIALLY_SUPPORTED:
                partial_count += 1
            elif vc.status == ClaimStatus.CONTRADICTED:
                contradicted_count += 1
            elif vc.status == ClaimStatus.UNSUPPORTED:
                unsupported_count += 1
            elif vc.status == ClaimStatus.UNVERIFIABLE:
                unverifiable_count += 1

        total = len(verified_claims)
        # Weighted faithfulness calculation: Supported=1.0, Partial=0.5, Contradicted=0.0, Unsupported=0.0
        weighted_score = (supported_count * 1.0 + partial_count * 0.5) / max(1, total)
        is_faithful = contradicted_count == 0 and unsupported_count == 0 and weighted_score >= 0.70

        return VerificationSummary(
            total_claims=total,
            supported_claims=supported_count,
            partially_supported_claims=partial_count,
            contradicted_claims=contradicted_count,
            unsupported_claims=unsupported_count,
            unverifiable_claims=unverifiable_count,
            overall_faithfulness_score=weighted_score,
            is_faithful=is_faithful,
            claims=verified_claims
        )
