from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.db.models.document import Document
from app.db.models.user import User
from app.repositories.chunk_repository import ChunkRepository
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class ComparisonFindingType(str, Enum):
    THRESHOLD_MODIFIED = "THRESHOLD_MODIFIED"
    DEADLINE_MODIFIED = "DEADLINE_MODIFIED"
    OBLIGATION_ADDED = "OBLIGATION_ADDED"
    OBLIGATION_REMOVED = "OBLIGATION_REMOVED"
    SECTION_ADDED = "SECTION_ADDED"
    SECTION_REMOVED = "SECTION_REMOVED"
    CLASSIFICATION_CHANGED = "CLASSIFICATION_CHANGED"


@dataclass
class ComparisonFinding:
    finding_id: str
    finding_type: ComparisonFindingType
    description: str
    doc1_statement: Optional[str]
    doc1_citation: Optional[str]
    doc2_statement: Optional[str]
    doc2_citation: Optional[str]
    confidence_score: float = 0.95


@dataclass
class DocumentComparisonResult:
    doc1_id: uuid.UUID
    doc1_title: str
    doc2_id: uuid.UUID
    doc2_title: str
    total_findings: int
    findings_by_type: Dict[str, int]
    findings: List[ComparisonFinding]


class DocumentComparisonService:
    """Analyzes differences in regulatory obligations, thresholds, and deadlines between two documents."""

    def __init__(self, db: Session):
        self.db = db
        self.perm_service = PermissionService(db)
        self.chunk_repo = ChunkRepository(db)
        self.audit = AuditService(db)

    def _extract_clauses(self, chunks: List[Any], doc_title: str) -> List[Dict[str, Any]]:
        clauses = []
        for c in chunks:
            cit = f"[{doc_title}, {c.section_heading or 'General'}, Page {c.page_number or 'N/A'}]"
            sentences = re.split(r'(?<=[.!?])\s+', c.content)
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) > 20:
                    clauses.append({
                        "text": s_clean,
                        "section": c.section_heading,
                        "citation": cit,
                        "chunk_id": c.id
                    })
        return clauses

    def compare_documents(
        self,
        doc1_id: uuid.UUID,
        doc2_id: uuid.UUID,
        user: User
    ) -> DocumentComparisonResult:
        """Executes structured multi-layer comparison between two authorized documents."""
        # 1. Access Control
        doc1 = self.db.query(Document).filter(
            Document.id == doc1_id,
            Document.tenant_id == user.tenant_id
        ).first()
        doc2 = self.db.query(Document).filter(
            Document.id == doc2_id,
            Document.tenant_id == user.tenant_id
        ).first()

        if not doc1:
            raise EntityNotFoundError(f"Document 1 with ID '{doc1_id}' not found in user tenant.")
        if not doc2:
            raise EntityNotFoundError(f"Document 2 with ID '{doc2_id}' not found in user tenant.")

        self.perm_service.check_read_permission(doc1, user)
        self.perm_service.check_read_permission(doc2, user)

        chunks1 = self.chunk_repo.list_by_document(doc1.id, user.tenant_id, skip=0, limit=200)
        chunks2 = self.chunk_repo.list_by_document(doc2.id, user.tenant_id, skip=0, limit=200)

        findings: List[ComparisonFinding] = []
        finding_idx = 1

        # Check classification difference
        if doc1.classification != doc2.classification:
            findings.append(
                ComparisonFinding(
                    finding_id=f"FINDING_{finding_idx:03d}",
                    finding_type=ComparisonFindingType.CLASSIFICATION_CHANGED,
                    description=f"Security classification changed from {doc1.classification.value} to {doc2.classification.value}.",
                    doc1_statement=f"Classification: {doc1.classification.value}",
                    doc1_citation=f"[{doc1.title}, Metadata, Page N/A]",
                    doc2_statement=f"Classification: {doc2.classification.value}",
                    doc2_citation=f"[{doc2.title}, Metadata, Page N/A]",
                    confidence_score=1.0
                )
            )
            finding_idx += 1

        # Check Section Structure
        sec1 = {c.section_heading for c in chunks1 if c.section_heading}
        sec2 = {c.section_heading for c in chunks2 if c.section_heading}

        for added_sec in sec2 - sec1:
            matching_c = next((c for c in chunks2 if c.section_heading == added_sec), None)
            findings.append(
                ComparisonFinding(
                    finding_id=f"FINDING_{finding_idx:03d}",
                    finding_type=ComparisonFindingType.SECTION_ADDED,
                    description=f"New section introduced: '{added_sec}'.",
                    doc1_statement=None,
                    doc1_citation=None,
                    doc2_statement=matching_c.content[:200] if matching_c else added_sec,
                    doc2_citation=f"[{doc2.title}, {added_sec}, Page {matching_c.page_number if matching_c else 'N/A'}]",
                    confidence_score=1.0
                )
            )
            finding_idx += 1

        for removed_sec in sec1 - sec2:
            matching_c = next((c for c in chunks1 if c.section_heading == removed_sec), None)
            findings.append(
                ComparisonFinding(
                    finding_id=f"FINDING_{finding_idx:03d}",
                    finding_type=ComparisonFindingType.SECTION_REMOVED,
                    description=f"Section removed in current document: '{removed_sec}'.",
                    doc1_statement=matching_c.content[:200] if matching_c else removed_sec,
                    doc1_citation=f"[{doc1.title}, {removed_sec}, Page {matching_c.page_number if matching_c else 'N/A'}]",
                    doc2_statement=None,
                    doc2_citation=None,
                    confidence_score=1.0
                )
            )
            finding_idx += 1

        # Clause-level extraction
        clauses1 = self._extract_clauses(chunks1, doc1.title)
        clauses2 = self._extract_clauses(chunks2, doc2.title)

        # Threshold and Deadline Differences
        text1_all = " ".join(c["text"] for c in clauses1)
        text2_all = " ".join(c["text"] for c in clauses2)

        # Detect specific threshold differences
        money_matches1 = set(re.findall(r'\$[0-9,]+', text1_all))
        money_matches2 = set(re.findall(r'\$[0-9,]+', text2_all))

        for m2 in money_matches2 - money_matches1:
            matching_cl2 = next((cl for cl in clauses2 if m2 in cl["text"]), None)
            findings.append(
                ComparisonFinding(
                    finding_id=f"FINDING_{finding_idx:03d}",
                    finding_type=ComparisonFindingType.THRESHOLD_MODIFIED,
                    description=f"Financial threshold {m2} appears in '{doc2.title}' but not in '{doc1.title}'.",
                    doc1_statement=None,
                    doc1_citation=None,
                    doc2_statement=matching_cl2["text"] if matching_cl2 else m2,
                    doc2_citation=matching_cl2["citation"] if matching_cl2 else f"[{doc2.title}, General, Page N/A]",
                    confidence_score=0.92
                )
            )
            finding_idx += 1

        # Detect deadline differences
        deadline_matches1 = set(re.findall(r'\b[0-9]+\s+(?:calendar\s+|business\s+)?(?:days|hours|months)\b', text1_all, re.IGNORECASE))
        deadline_matches2 = set(re.findall(r'\b[0-9]+\s+(?:calendar\s+|business\s+)?(?:days|hours|months)\b', text2_all, re.IGNORECASE))

        for d2 in deadline_matches2 - deadline_matches1:
            matching_cl2 = next((cl for cl in clauses2 if d2.lower() in cl["text"].lower()), None)
            findings.append(
                ComparisonFinding(
                    finding_id=f"FINDING_{finding_idx:03d}",
                    finding_type=ComparisonFindingType.DEADLINE_MODIFIED,
                    description=f"Compliance timeframe '{d2}' specified in '{doc2.title}' is absent in '{doc1.title}'.",
                    doc1_statement=None,
                    doc1_citation=None,
                    doc2_statement=matching_cl2["text"] if matching_cl2 else d2,
                    doc2_citation=matching_cl2["citation"] if matching_cl2 else f"[{doc2.title}, General, Page N/A]",
                    confidence_score=0.90
                )
            )
            finding_idx += 1

        # Audit log
        self.audit.log(
            tenant_id=user.tenant_id,
            action="DOC_COMPARE",
            resource_type="DOCUMENT",
            resource_id=f"{doc1.id}:{doc2.id}",
            user_id=user.id,
            details={
                "doc1_title": doc1.title,
                "doc2_title": doc2.title,
                "total_findings": len(findings)
            }
        )

        by_type: Dict[str, int] = {}
        for f in findings:
            by_type[f.finding_type.value] = by_type.get(f.finding_type.value, 0) + 1

        return DocumentComparisonResult(
            doc1_id=doc1.id,
            doc1_title=doc1.title,
            doc2_id=doc2.id,
            doc2_title=doc2.title,
            total_findings=len(findings),
            findings_by_type=by_type,
            findings=findings
        )
