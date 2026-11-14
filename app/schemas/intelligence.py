from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from app.schemas.rag import CitationResponse


class DocumentSummaryRequest(BaseModel):
    document_id: uuid.UUID = Field(..., description="Target document ID to summarize")


class KeyObligationSchema(BaseModel):
    obligation_text: str
    section_heading: Optional[str]
    citation: str
    evidence_id: str


class FinancialThresholdSchema(BaseModel):
    metric_name: str
    threshold_value: str
    section_heading: Optional[str]
    citation: str


class ComplianceDeadlineSchema(BaseModel):
    event_trigger: str
    filing_window: str
    section_heading: Optional[str]
    citation: str


class DocumentSummaryResponse(BaseModel):
    document_id: uuid.UUID
    document_title: str
    document_classification: str
    total_pages: Optional[int]
    total_chunks: int
    executive_summary: str
    key_obligations: List[KeyObligationSchema]
    financial_thresholds: List[FinancialThresholdSchema]
    compliance_deadlines: List[ComplianceDeadlineSchema]
    regulatory_references: List[str]
    identified_risks_and_exceptions: List[str]
    citations: List[CitationResponse]


class DocumentComparisonRequest(BaseModel):
    doc1_id: uuid.UUID = Field(..., description="First document ID (baseline / earlier policy)")
    doc2_id: uuid.UUID = Field(..., description="Second document ID (comparison / updated policy)")


class ComparisonFindingSchema(BaseModel):
    finding_id: str
    finding_type: str
    description: str
    doc1_statement: Optional[str] = None
    doc1_citation: Optional[str] = None
    doc2_statement: Optional[str] = None
    doc2_citation: Optional[str] = None
    confidence_score: float = 0.95


class DocumentComparisonResponse(BaseModel):
    doc1_id: uuid.UUID
    doc1_title: str
    doc2_id: uuid.UUID
    doc2_title: str
    total_findings: int
    findings_by_type: Dict[str, int]
    findings: List[ComparisonFindingSchema]
