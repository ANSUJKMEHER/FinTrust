from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.user import User
from app.llm.base import BaseLLMProvider
from app.llm.factory import get_llm_provider
from app.schemas.rag import (
    CitationResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    VerificationSummaryResponse,
    VerifiedClaimResponse
)
from app.services.audit_service import AuditService
from app.services.citation_service import CitationService
from app.services.citation_verification_service import CitationVerificationService, VerificationSummary
from app.services.context_construction_service import ContextConstructionService, StructuredContext
from app.services.evidence_sufficiency_service import EvidenceSufficiencyService, SufficiencyEvaluation
from app.services.grounded_generation_service import GroundedGenerationResult, GroundedGenerationService
from app.services.hybrid_search_service import HybridSearchService

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """Enterprise RAG Orchestrator executing hybrid retrieval, sufficiency check, generation, and verification."""

    def __init__(
        self,
        db: Session,
        llm_provider: Optional[BaseLLMProvider] = None
    ):
        self.db = db
        self.search_service = HybridSearchService(db)
        self.context_builder = ContextConstructionService(max_context_tokens=settings.RAG_MAX_CONTEXT_TOKENS)
        self.sufficiency_service = EvidenceSufficiencyService(min_sufficiency_score=settings.RAG_SUFFICIENCY_MIN_SCORE)
        self.generation_service = GroundedGenerationService(llm_provider=llm_provider)
        self.verification_service = CitationVerificationService()
        self.audit = AuditService(db)

    def execute_rag_pipeline(
        self,
        request: RAGQueryRequest,
        user: User
    ) -> RAGQueryResponse:
        """Executes full enterprise RAG pipeline for an authenticated tenant user."""
        start_total = time.perf_counter()

        # 1. Retrieval Stage (Strict tenant isolation and document ACL filtering applied at DB query level)
        t_ret_start = time.perf_counter()
        retrieved_chunks = self.search_service.hybrid_search(
            query=request.query,
            user=user,
            dense_limit=request.dense_limit,
            sparse_limit=request.sparse_limit,
            top_k=request.top_k,
            apply_rerank=request.apply_rerank
        )
        retrieval_latency_ms = (time.perf_counter() - t_ret_start) * 1000.0

        # 2. Context Construction Stage
        structured_ctx = self.context_builder.build_context(
            query=request.query,
            retrieved_chunks=retrieved_chunks
        )

        # 3. Evidence Sufficiency Evaluation
        sufficiency: SufficiencyEvaluation = self.sufficiency_service.evaluate_sufficiency(
            query=request.query,
            context=structured_ctx
        )

        # 4. Grounded Generation Stage
        if sufficiency.should_refuse:
            # Deterministic principled refusal when evidence is insufficient
            answer_text = sufficiency.refusal_message or settings.RAG_REFUSAL_MESSAGE
            gen_result = GroundedGenerationResult(
                answer=answer_text,
                is_refusal=True,
                citations=[],
                valid_citation_count=0,
                invalid_citation_count=0,
                cited_evidence_ids=[],
                model_name="rule_engine_refusal",
                provider_name="rule_engine",
                prompt_tokens=0,
                completion_tokens=len(answer_text.split()) * 2,
                total_tokens=len(answer_text.split()) * 2,
                generation_latency_ms=0.5
            )
            verification_summary_resp = None
        else:
            gen_result = self.generation_service.generate_grounded_answer(
                query=request.query,
                context=structured_ctx,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            # 5. Citation Faithfulness & Entity Verification Stage
            if request.verify_citations and not gen_result.is_refusal:
                v_summary: VerificationSummary = self.verification_service.verify_answer(
                    answer_text=gen_result.answer,
                    citations=gen_result.citations,
                    context=structured_ctx
                )

                claims_resp = [
                    VerifiedClaimResponse(
                        claim_id=vc.claim_id,
                        claim_text=vc.claim_text,
                        status=vc.status.value,
                        confidence_score=vc.confidence_score,
                        supporting_evidence_ids=vc.supporting_evidence_ids,
                        explanation=vc.explanation
                    )
                    for vc in v_summary.claims
                ]

                verification_summary_resp = VerificationSummaryResponse(
                    total_claims=v_summary.total_claims,
                    supported_claims=v_summary.supported_claims,
                    partially_supported_claims=v_summary.partially_supported_claims,
                    contradicted_claims=v_summary.contradicted_claims,
                    unsupported_claims=v_summary.unsupported_claims,
                    unverifiable_claims=v_summary.unverifiable_claims,
                    overall_faithfulness_score=v_summary.overall_faithfulness_score,
                    is_faithful=v_summary.is_faithful,
                    claims=claims_resp
                )
            else:
                verification_summary_resp = None

        total_latency_ms = (time.perf_counter() - start_total) * 1000.0

        # 6. Audit Logging
        self.audit.log(
            tenant_id=user.tenant_id,
            action="RAG_QUERY",
            resource_type="RAG",
            resource_id=f"query_{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            details={
                "query": request.query[:150],
                "is_refusal": gen_result.is_refusal,
                "retrieved_count": len(retrieved_chunks),
                "total_tokens": gen_result.total_tokens,
                "total_latency_ms": round(total_latency_ms, 2)
            }
        )

        # Convert citations to Pydantic responses
        citation_responses = [
            CitationResponse(
                citation_id=c.citation_id,
                raw_citation_text=c.raw_citation_text,
                is_valid=c.is_valid,
                evidence_id=c.evidence_id,
                document_id=c.document_id,
                document_version_id=c.document_version_id,
                chunk_id=c.chunk_id,
                document_title=c.document_title,
                section_heading=c.section_heading,
                page_number=c.page_number,
                supporting_text_span=c.supporting_text_span,
                validation_error=c.validation_error
            )
            for c in gen_result.citations
        ]

        return RAGQueryResponse(
            query=request.query,
            answer=gen_result.answer,
            is_refusal=gen_result.is_refusal,
            sufficiency_status=sufficiency.status.value,
            sufficiency_score=round(sufficiency.sufficiency_score, 4),
            citations=citation_responses,
            verification=verification_summary_resp,
            retrieved_chunks_count=len(retrieved_chunks),
            model=gen_result.model_name,
            provider=gen_result.provider_name,
            prompt_tokens=gen_result.prompt_tokens,
            completion_tokens=gen_result.completion_tokens,
            total_tokens=gen_result.total_tokens,
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            generation_latency_ms=round(gen_result.generation_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2)
        )
