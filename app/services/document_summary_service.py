from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.db.models.document import Document
from app.db.models.user import User
from app.llm.base import BaseLLMProvider
from app.llm.factory import get_llm_provider
from app.repositories.chunk_repository import ChunkRepository
from app.services.audit_service import AuditService
from app.services.citation_service import CitationService, VerifiedCitation
from app.services.context_construction_service import ContextConstructionService, StructuredContext
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


@dataclass
class KeyObligation:
    obligation_text: str
    section_heading: Optional[str]
    citation: str
    evidence_id: str


@dataclass
class FinancialThreshold:
    metric_name: str
    threshold_value: str
    section_heading: Optional[str]
    citation: str


@dataclass
class ComplianceDeadline:
    event_trigger: str
    filing_window: str
    section_heading: Optional[str]
    citation: str


@dataclass
class DocumentSummaryResult:
    document_id: uuid.UUID
    document_title: str
    document_classification: str
    total_pages: Optional[int]
    total_chunks: int
    executive_summary: str
    key_obligations: List[KeyObligation]
    financial_thresholds: List[FinancialThreshold]
    compliance_deadlines: List[ComplianceDeadline]
    regulatory_references: List[str]
    identified_risks_and_exceptions: List[str]
    citations: List[VerifiedCitation]


class DocumentSummaryService:
    """Produces structured, evidence-traceable intelligence summaries from compliance documents."""

    def __init__(
        self,
        db: Session,
        llm_provider: Optional[BaseLLMProvider] = None,
        citation_service: Optional[CitationService] = None
    ):
        self.db = db
        self.perm_service = PermissionService(db)
        self.chunk_repo = ChunkRepository(db)
        self.audit = AuditService(db)
        self.llm_provider = llm_provider or get_llm_provider()
        self.citation_service = citation_service or CitationService()
        self.context_builder = ContextConstructionService(max_context_tokens=6000)

    def summarize_document(
        self,
        document_id: uuid.UUID,
        user: User
    ) -> DocumentSummaryResult:
        """Generates an evidence-traceable multi-faceted compliance summary."""
        doc = self.db.query(Document).filter(
            Document.id == document_id,
            Document.tenant_id == user.tenant_id
        ).first()

        if not doc:
            raise EntityNotFoundError(f"Document '{document_id}' not found in user tenant.")

        # Enforce document-level read permission
        self.perm_service.check_read_permission(doc, user)

        # Retrieve all chunks for this document
        chunks = self.chunk_repo.list_by_document(doc.id, user.tenant_id, skip=0, limit=200)
        if not chunks:
            raise EntityNotFoundError(f"Document '{document_id}' has 0 indexed chunks.")

        # Convert chunk DB entities to dictionary form for context builder
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
                "document_title": doc.title,
                "document_classification": doc.classification.value,
                "relevance_score": 1.0
            }
            for c in chunks
        ]

        structured_ctx = self.context_builder.build_context(
            query=f"Comprehensive summary for {doc.title}",
            retrieved_chunks=chunk_dicts
        )

        # Structured deterministic extraction of facts & thresholds
        obligations: List[KeyObligation] = []
        thresholds: List[FinancialThreshold] = []
        deadlines: List[ComplianceDeadline] = []
        statutes: Set[str] = set()
        risks: List[str] = []

        all_text_snippets = []

        for item in structured_ctx.evidence_items:
            content = item.content
            all_text_snippets.append(content)
            cit = item.citation_label

            # Extract statutes (e.g. BSA Section 5318(g), 31 CFR 1020.320, GDPR Art. 33)
            statute_matches = re.findall(
                r'\b(?:BSA\s+)?Section\s+[0-9]+(?:\([a-zA-Z0-9]+\))?|\b[0-9]+\s+CFR\s+[0-9\.]+|\bGDPR\s+Art(?:icle)?\s+[0-9]+|\bSOX\s+[0-9]+|\bTitle\s+VII\b',
                content,
                re.IGNORECASE
            )
            for s in statute_matches:
                statutes.add(s)

            # Extract deadlines
            deadline_matches = re.findall(
                r'([^.\n]*\b([0-9]+\s+(?:calendar\s+|business\s+)?(?:days|hours|months|years))\b[^.\n]*)',
                content,
                re.IGNORECASE
            )
            for d_full, d_val in deadline_matches:
                deadlines.append(
                    ComplianceDeadline(
                        event_trigger=d_full.strip()[:100],
                        filing_window=d_val.strip(),
                        section_heading=item.section_heading,
                        citation=cit
                    )
                )

            # Extract financial thresholds (e.g. $5,000, $10,000, 25 percent)
            threshold_matches = re.findall(
                r'([^.\n]*(\$[0-9,]+|\b[0-9]+\s+percent|\b100%)[^.\n]*)',
                content,
                re.IGNORECASE
            )
            for t_full, t_val in threshold_matches:
                thresholds.append(
                    FinancialThreshold(
                        metric_name=t_full.strip()[:100],
                        threshold_value=t_val.strip(),
                        section_heading=item.section_heading,
                        citation=cit
                    )
                )

            # Extract obligations (sentences containing must, shall, required)
            sentences = re.split(r'(?<=[.!?])\s+', content)
            for sent in sentences:
                sent_clean = sent.strip()
                if re.search(r'\b(must|shall|required to|mandated)\b', sent_clean, re.IGNORECASE) and len(sent_clean) > 25:
                    obligations.append(
                        KeyObligation(
                            obligation_text=sent_clean,
                            section_heading=item.section_heading,
                            citation=cit,
                            evidence_id=item.evidence_id
                        )
                    )
                if re.search(r'\b(risk|deficiency|breach|violation|penalty)\b', sent_clean, re.IGNORECASE) and len(sent_clean) > 25:
                    risks.append(f"{sent_clean} {cit}")

        # Construct Executive Summary
        first_chunk = chunks[0].content[:400]
        exec_summary = (
            f"The document '{doc.title}' establishes statutory governance and procedural controls. "
            f"Core provisions encompass {len(statutes)} regulatory citations, "
            f"{len(thresholds)} statutory reporting thresholds, and {len(deadlines)} mandatory compliance deadlines. "
            f"Opening authority specifies: {first_chunk} [{doc.title}, {chunks[0].section_heading or 'General'}, Page {chunks[0].page_number or 'N/A'}]."
        )

        # Citations
        citations = [
            VerifiedCitation(
                citation_id=uuid.uuid4(),
                raw_citation_text=item.citation_label,
                is_valid=True,
                evidence_id=item.evidence_id,
                document_id=item.document_id,
                document_version_id=item.document_version_id,
                chunk_id=item.chunk_id,
                document_title=item.document_title,
                section_heading=item.section_heading,
                page_number=item.page_number,
                supporting_text_span=item.content[:200]
            )
            for item in structured_ctx.evidence_items[:10]
        ]

        # Audit log
        self.audit.log(
            tenant_id=user.tenant_id,
            action="DOC_SUMMARIZE",
            resource_type="DOCUMENT",
            resource_id=str(doc.id),
            user_id=user.id,
            details={
                "title": doc.title,
                "total_obligations": len(obligations),
                "total_thresholds": len(thresholds)
            }
        )

        return DocumentSummaryResult(
            document_id=doc.id,
            document_title=doc.title,
            document_classification=doc.classification.value,
            total_pages=doc.versions[0].total_pages if doc.versions else None,
            total_chunks=len(chunks),
            executive_summary=exec_summary,
            key_obligations=obligations[:15],
            financial_thresholds=thresholds[:10],
            compliance_deadlines=deadlines[:10],
            regulatory_references=sorted(list(statutes)),
            identified_risks_and_exceptions=risks[:8],
            citations=citations
        )
