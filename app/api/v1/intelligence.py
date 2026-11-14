import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.intelligence import (
    ComparisonFindingSchema,
    ComplianceDeadlineSchema,
    DocumentComparisonRequest,
    DocumentComparisonResponse,
    DocumentSummaryRequest,
    DocumentSummaryResponse,
    FinancialThresholdSchema,
    KeyObligationSchema
)
from app.schemas.rag import CitationResponse
from app.services.document_comparison_service import DocumentComparisonService
from app.services.document_summary_service import DocumentSummaryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Financial Document Intelligence"])


@router.post("/summarize", response_model=DocumentSummaryResponse)
def summarize_document(
    request: DocumentSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentSummaryResponse:
    """Produces an evidence-grounded compliance and financial intelligence summary of an authorized document."""
    service = DocumentSummaryService(db)
    try:
        res = service.summarize_document(request.document_id, current_user)

        obligations_schema = [
            KeyObligationSchema(
                obligation_text=o.obligation_text,
                section_heading=o.section_heading,
                citation=o.citation,
                evidence_id=o.evidence_id
            )
            for o in res.key_obligations
        ]

        thresholds_schema = [
            FinancialThresholdSchema(
                metric_name=t.metric_name,
                threshold_value=t.threshold_value,
                section_heading=t.section_heading,
                citation=t.citation
            )
            for t in res.financial_thresholds
        ]

        deadlines_schema = [
            ComplianceDeadlineSchema(
                event_trigger=d.event_trigger,
                filing_window=d.filing_window,
                section_heading=d.section_heading,
                citation=d.citation
            )
            for d in res.compliance_deadlines
        ]

        citations_schema = [
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
            for c in res.citations
        ]

        return DocumentSummaryResponse(
            document_id=res.document_id,
            document_title=res.document_title,
            document_classification=res.document_classification,
            total_pages=res.total_pages,
            total_chunks=res.total_chunks,
            executive_summary=res.executive_summary,
            key_obligations=obligations_schema,
            financial_thresholds=thresholds_schema,
            compliance_deadlines=deadlines_schema,
            regulatory_references=res.regulatory_references,
            identified_risks_and_exceptions=res.identified_risks_and_exceptions,
            citations=citations_schema
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Summarization error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/compare", response_model=DocumentComparisonResponse)
def compare_documents(
    request: DocumentComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentComparisonResponse:
    """Performs structured comparative analysis between two authorized compliance documents."""
    service = DocumentComparisonService(db)
    try:
        res = service.compare_documents(request.doc1_id, request.doc2_id, current_user)

        findings_schema = [
            ComparisonFindingSchema(
                finding_id=f.finding_id,
                finding_type=f.finding_type.value,
                description=f.description,
                doc1_statement=f.doc1_statement,
                doc1_citation=f.doc1_citation,
                doc2_statement=f.doc2_statement,
                doc2_citation=f.doc2_citation,
                confidence_score=f.confidence_score
            )
            for f in res.findings
        ]

        return DocumentComparisonResponse(
            doc1_id=res.doc1_id,
            doc1_title=res.doc1_title,
            doc2_id=res.doc2_id,
            doc2_title=res.doc2_title,
            total_findings=res.total_findings,
            findings_by_type=res.findings_by_type,
            findings=findings_schema
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Document comparison error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
