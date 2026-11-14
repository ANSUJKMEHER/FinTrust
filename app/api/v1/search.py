import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.retrieval import (
    DenseSearchRequest,
    HybridSearchRequest,
    RetrievedChunkResponse,
    SearchResponse,
    SparseSearchRequest
)
from app.services.hybrid_search_service import HybridSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search & Retrieval"])


@router.post("/dense", response_model=SearchResponse)
def dense_search(
    request: DenseSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchResponse:
    """Executes dense semantic retrieval using 384-dimensional vector embeddings with tenant and ACL enforcement."""
    service = HybridSearchService(db)
    results = service.dense_search(request.query, current_user, limit=request.limit)
    chunk_responses = [RetrievedChunkResponse(**r) for r in results]
    return SearchResponse(
        query=request.query,
        total_results=len(chunk_responses),
        search_mode="dense",
        results=chunk_responses
    )


@router.post("/sparse", response_model=SearchResponse)
def sparse_search(
    request: SparseSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchResponse:
    """Executes sparse keyword retrieval using PostgreSQL GIN-indexed Full-Text Search with tenant and ACL enforcement."""
    service = HybridSearchService(db)
    results = service.sparse_search(request.query, current_user, limit=request.limit)
    chunk_responses = [RetrievedChunkResponse(**r) for r in results]
    return SearchResponse(
        query=request.query,
        total_results=len(chunk_responses),
        search_mode="sparse",
        results=chunk_responses
    )


@router.post("/hybrid", response_model=SearchResponse)
def hybrid_search(
    request: HybridSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchResponse:
    """Executes end-to-end hybrid retrieval:
    Dense Retrieval + Sparse Full-Text Search -> Reciprocal Rank Fusion (RRF) -> Cross-Encoder Reranking
    """
    service = HybridSearchService(db)
    results = service.hybrid_search(
        query=request.query,
        user=current_user,
        dense_limit=request.dense_limit,
        sparse_limit=request.sparse_limit,
        top_k=request.top_k,
        apply_rerank=request.apply_rerank
    )
    chunk_responses = [RetrievedChunkResponse(**r) for r in results]
    mode = "hybrid_reranked" if request.apply_rerank else "hybrid_rrf"
    return SearchResponse(
        query=request.query,
        total_results=len(chunk_responses),
        search_mode=mode,
        results=chunk_responses
    )
