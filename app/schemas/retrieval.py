from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class DenseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    limit: int = Field(default=25, ge=1, le=100, description="Maximum number of candidates to retrieve")


class SparseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Keyword / regulatory query")
    limit: int = Field(default=25, ge=1, le=100, description="Maximum number of candidates to retrieve")


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Hybrid search query")
    dense_limit: int = Field(default=25, ge=1, le=100, description="Dense candidates limit")
    sparse_limit: int = Field(default=25, ge=1, le=100, description="Sparse candidates limit")
    top_k: int = Field(default=5, ge=1, le=50, description="Final number of top results to return")
    apply_rerank: bool = Field(default=True, description="Whether to apply cross-encoder reranking")


class RetrievedChunkResponse(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_index: int
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    heading_breadcrumb: Optional[str] = None
    content: str
    token_count: int
    document_title: str
    document_classification: str
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_rank: Optional[int] = None
    sparse_score: Optional[float] = None
    rrf_rank: Optional[int] = None
    rrf_score: Optional[float] = None
    cross_encoder_score: Optional[float] = None
    retrieval_sources: List[str] = []


class SearchResponse(BaseModel):
    query: str
    total_results: int
    search_mode: str
    results: List[RetrievedChunkResponse]
