import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limiter import RateLimitDependency
from app.db.models.document_chunk import DocumentChunk
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.rag import (
    CitationResponse,
    CitationVerificationRequest,
    CitationVerificationResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    VerificationSummaryResponse,
    VerifiedClaimResponse
)
from app.services.citation_service import CitationService
from app.services.citation_verification_service import CitationVerificationService
from app.services.context_construction_service import ContextConstructionService
from app.services.rag_orchestrator import RAGOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["Grounded Generation & RAG"])

rag_rate_limit = RateLimitDependency(
    max_requests=settings.RATE_LIMIT_RAG_PER_MINUTE,
    window_seconds=60,
    scope="rag_query"
)


@router.post("/query", response_model=RAGQueryResponse, dependencies=[Depends(rag_rate_limit)])
def query_rag(
    request: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> RAGQueryResponse:
    """Executes full grounded RAG pipeline:
    Hybrid Retrieval -> Context Construction -> Sufficiency Check -> Grounded Generation -> Citation Verification
    """
    orchestrator = RAGOrchestrator(db)
    try:
        response = orchestrator.execute_rag_pipeline(request, current_user)
        return response
    except Exception as e:
        logger.error(f"RAG query execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query execution failed: {str(e)}"
        )


@router.post("/verify", response_model=CitationVerificationResponse)
def verify_citations(
    request: CitationVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CitationVerificationResponse:
    """Standalone claim extraction, entity verification, and citation faithfulness check."""
    # Retrieve specified chunks enforcing tenant isolation
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.id.in_(request.chunk_ids),
        DocumentChunk.tenant_id == current_user.tenant_id
    ).all()

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="None of the specified chunk IDs exist or belong to your tenant."
        )

    chunk_dicts = [
        {
            "chunk_id": c.id,
            "document_id": c.document_id,
            "document_version_id": c.document_version_id,
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "section_heading": c.section_heading,
            "heading_breadcrumb": c.heading_breadcrumb,
            "content": c.content,
            "token_count": c.token_count,
            "document_title": c.document.title if c.document else "Document",
            "document_classification": c.document.classification.value if c.document else "INTERNAL",
            "relevance_score": 1.0
        }
        for c in chunks
    ]

    builder = ContextConstructionService()
    ctx = builder.build_context(query="verification", retrieved_chunks=chunk_dicts)

    cit_service = CitationService()
    cit_result = cit_service.extract_and_validate_citations(request.answer_text, ctx.evidence_registry)

    verifier = CitationVerificationService()
    summary = verifier.verify_answer(request.answer_text, cit_result.citations, ctx)

    claims_resp = [
        VerifiedClaimResponse(
            claim_id=vc.claim_id,
            claim_text=vc.claim_text,
            status=vc.status.value,
            confidence_score=vc.confidence_score,
            supporting_evidence_ids=vc.supporting_evidence_ids,
            explanation=vc.explanation
        )
        for vc in summary.claims
    ]

    summary_resp = VerificationSummaryResponse(
        total_claims=summary.total_claims,
        supported_claims=summary.supported_claims,
        partially_supported_claims=summary.partially_supported_claims,
        contradicted_claims=summary.contradicted_claims,
        unsupported_claims=summary.unsupported_claims,
        unverifiable_claims=summary.unverifiable_claims,
        overall_faithfulness_score=summary.overall_faithfulness_score,
        is_faithful=summary.is_faithful,
        claims=claims_resp
    )

    return CitationVerificationResponse(summary=summary_resp)
