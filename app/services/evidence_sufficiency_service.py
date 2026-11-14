from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.core.config import settings
from app.services.context_construction_service import StructuredContext

logger = logging.getLogger(__name__)


class SufficiencyStatus(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIALLY_SUFFICIENT = "PARTIALLY_SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass
class SufficiencyEvaluation:
    status: SufficiencyStatus
    sufficiency_score: float
    max_retrieval_score: float
    term_coverage_ratio: float
    covered_query_terms: List[str]
    missing_query_terms: List[str]
    rationale: str
    should_refuse: bool
    refusal_message: Optional[str] = None


class EvidenceSufficiencyService:
    """Evaluates whether retrieved evidence is sufficient, partially sufficient, or inadequate."""

    # Common English stopwords to ignore when checking query term coverage
    STOPWORDS = {
        "what", "which", "where", "when", "how", "does", "explain", "describe", "tell",
        "about", "this", "that", "these", "those", "have", "with", "from", "into",
        "during", "before", "after", "above", "below", "under", "over", "between",
        "their", "there", "they", "them", "then", "some", "more", "most", "other",
        "into", "through", "during", "rules", "requirements", "regulations", "policy",
        "the", "and", "are", "for", "not", "but", "can", "could", "should", "would",
        "will", "was", "were", "all", "any", "been", "being", "had", "has", "out"
    }

    def __init__(self, min_sufficiency_score: float = settings.RAG_SUFFICIENCY_MIN_SCORE):
        self.min_sufficiency_score = min_sufficiency_score

    def extract_informative_query_terms(self, query: str) -> List[str]:
        """Extracts substantive keywords from user query, excluding punctuation and stopwords."""
        raw_words = re.findall(r'\b[a-zA-Z0-9_\-\.]{3,}\b', query.lower())
        informative = [w for w in raw_words if w not in self.STOPWORDS]
        return list(dict.fromkeys(informative))  # Preserve order, unique

    def evaluate_sufficiency(
        self,
        query: str,
        context: StructuredContext
    ) -> SufficiencyEvaluation:
        """Determines whether available evidence can reliably support a complete or partial answer."""
        if not context.evidence_items:
            return SufficiencyEvaluation(
                status=SufficiencyStatus.INSUFFICIENT,
                sufficiency_score=0.0,
                max_retrieval_score=0.0,
                term_coverage_ratio=0.0,
                covered_query_terms=[],
                missing_query_terms=self.extract_informative_query_terms(query),
                rationale="Zero retrieved chunks were found matching the query.",
                should_refuse=True,
                refusal_message=settings.RAG_REFUSAL_MESSAGE
            )

        query_terms = self.extract_informative_query_terms(query)
        if not query_terms:
            query_terms = [query.lower()]

        # Aggregate evidence content
        all_evidence_text = " ".join(item.content.lower() for item in context.evidence_items)

        covered = [t for t in query_terms if t in all_evidence_text]
        missing = [t for t in query_terms if t not in all_evidence_text]

        coverage_ratio = len(covered) / max(1, len(query_terms))
        max_score = max((item.relevance_score for item in context.evidence_items), default=0.0)

        # Composite sufficiency score combining top relevance and query term coverage
        # Weighting: 40% top retrieval score, 60% query concept coverage
        composite_score = (max_score * 0.4) + (coverage_ratio * 0.6)

        # Decision thresholding
        if coverage_ratio < 0.25 and max_score < self.min_sufficiency_score:
            status = SufficiencyStatus.INSUFFICIENT
            should_refuse = True
            refusal_msg = settings.RAG_REFUSAL_MESSAGE
            rationale = (
                f"Retrieved evidence covers only {coverage_ratio:.1%} of query concepts and top relevance "
                f"({max_score:.2f}) falls below required threshold ({self.min_sufficiency_score:.2f})."
            )
        elif coverage_ratio < 0.55:
            status = SufficiencyStatus.PARTIALLY_SUFFICIENT
            should_refuse = False
            refusal_msg = None
            rationale = (
                f"Partial evidence coverage ({coverage_ratio:.1%}). Supported concepts: {covered}. "
                f"Missing concepts: {missing}."
            )
        else:
            status = SufficiencyStatus.SUFFICIENT
            should_refuse = False
            refusal_msg = None
            rationale = f"Strong evidence coverage ({coverage_ratio:.1%}) with verified relevance ({max_score:.2f})."

        return SufficiencyEvaluation(
            status=status,
            sufficiency_score=composite_score,
            max_retrieval_score=max_score,
            term_coverage_ratio=coverage_ratio,
            covered_query_terms=covered,
            missing_query_terms=missing,
            rationale=rationale,
            should_refuse=should_refuse,
            refusal_message=refusal_msg
        )
