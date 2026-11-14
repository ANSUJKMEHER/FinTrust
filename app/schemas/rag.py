from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000, description="Financial or regulatory question")
    top_k: int = Field(default=5, ge=1, le=20, description="Final number of evidence chunks to provide")
    dense_limit: int = Field(default=25, ge=1, le=100, description="Dense candidate limit")
    sparse_limit: int = Field(default=25, ge=1, le=100, description="Sparse candidate limit")
    apply_rerank: bool = Field(default=True, description="Whether to apply cross-encoder reranking")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=50, le=4000)
    verify_citations: bool = Field(default=True, description="Whether to run post-generation claim verification")


class CitationResponse(BaseModel):
    citation_id: uuid.UUID
    raw_citation_text: str
    is_valid: bool
    evidence_id: Optional[str] = None
    document_id: Optional[uuid.UUID] = None
    document_version_id: Optional[uuid.UUID] = None
    chunk_id: Optional[uuid.UUID] = None
    document_title: str
    section_heading: Optional[str] = None
    page_number: Optional[int] = None
    supporting_text_span: Optional[str] = None
    validation_error: Optional[str] = None


class VerifiedClaimResponse(BaseModel):
    claim_id: str
    claim_text: str
    status: str
    confidence_score: float
    supporting_evidence_ids: List[str]
    explanation: str


class VerificationSummaryResponse(BaseModel):
    total_claims: int
    supported_claims: int
    partially_supported_claims: int
    contradicted_claims: int
    unsupported_claims: int
    unverifiable_claims: int
    overall_faithfulness_score: float
    is_faithful: bool
    claims: List[VerifiedClaimResponse]


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    is_refusal: bool
    sufficiency_status: str
    sufficiency_score: float
    citations: List[CitationResponse]
    verification: Optional[VerificationSummaryResponse] = None
    retrieved_chunks_count: int
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    retrieval_latency_ms: float
    generation_latency_ms: float
    total_latency_ms: float


class CitationVerificationRequest(BaseModel):
    answer_text: str = Field(..., min_length=5, description="Generated answer text containing inline citations")
    chunk_ids: List[uuid.UUID] = Field(..., description="List of chunk IDs cited by the answer")


class CitationVerificationResponse(BaseModel):
    summary: VerificationSummaryResponse
