from dataclasses import dataclass, field
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
import uuid

from app.services.context_construction_service import EvidenceItem

logger = logging.getLogger(__name__)


@dataclass
class VerifiedCitation:
    citation_id: uuid.UUID
    raw_citation_text: str
    is_valid: bool
    evidence_id: Optional[str]
    document_id: Optional[uuid.UUID]
    document_version_id: Optional[uuid.UUID]
    chunk_id: Optional[uuid.UUID]
    document_title: str
    section_heading: Optional[str]
    page_number: Optional[int]
    supporting_text_span: Optional[str] = None
    validation_error: Optional[str] = None


@dataclass
class CitationExtractionResult:
    citations: List[VerifiedCitation]
    valid_citation_count: int
    invalid_citation_count: int
    cited_evidence_ids: Set[str]
    cited_document_ids: Set[uuid.UUID]


class CitationService:
    """Parses, validates, and resolves inline citations against the evidence registry."""

    # Matches: [Document Title, Section Heading, Page X] or [Document Title, Section Heading, Page N/A]
    CITATION_REGEX = re.compile(
        r'\[([^,\]]+),\s*([^,\]]+),\s*Page\s*([0-9]+|N/A|n/a)\]',
        re.IGNORECASE
    )

    # Fallback pattern for shorter bracketed citations: [Document Title, Page X]
    FALLBACK_CITATION_REGEX = re.compile(
        r'\[([^,\]]+),\s*Page\s*([0-9]+|N/A|n/a)\]',
        re.IGNORECASE
    )

    def extract_and_validate_citations(
        self,
        answer_text: str,
        evidence_registry: Dict[str, EvidenceItem]
    ) -> CitationExtractionResult:
        """Extracts citations from generated text and verifies each against provided evidence items."""
        citations: List[VerifiedCitation] = []
        cited_evidence_ids: Set[str] = set()
        cited_doc_ids: Set[uuid.UUID] = set()

        valid_count = 0
        invalid_count = 0

        # 1. Primary Regex: [Title, Section, Page X]
        matches = list(self.CITATION_REGEX.finditer(answer_text))
        matched_spans = [m.span() for m in matches]

        # 2. Check Fallback Regex: [Title, Page X] for spans not already captured
        fallback_matches = list(self.FALLBACK_CITATION_REGEX.finditer(answer_text))
        for fm in fallback_matches:
            f_span = fm.span()
            if not any(s[0] <= f_span[0] and f_span[1] <= s[1] for s in matched_spans):
                matches.append(fm)

        for match in matches:
            raw_text = match.group(0)
            groups = match.groups()

            if len(groups) == 3:
                doc_title_cand, section_cand, page_str = groups
                doc_title_cand = doc_title_cand.strip()
                section_cand = section_cand.strip()
            else:
                doc_title_cand, page_str = groups
                doc_title_cand = doc_title_cand.strip()
                section_cand = "General"

            parsed_page: Optional[int] = None
            if page_str.isdigit():
                parsed_page = int(page_str)

            # Match against evidence registry: prefer both title and section match
            matched_evidence: Optional[EvidenceItem] = None
            for eid, ev in evidence_registry.items():
                title_clean = ev.document_title.strip().lower()
                cand_clean = doc_title_cand.lower()
                sec_clean = (ev.section_heading or "").strip().lower()
                cand_sec_clean = section_cand.strip().lower()

                if cand_clean in title_clean or title_clean in cand_clean:
                    page_matches = (parsed_page is None or ev.page_number is None or parsed_page == ev.page_number)
                    section_matches = (cand_sec_clean in sec_clean or sec_clean in cand_sec_clean) if cand_sec_clean and cand_sec_clean != "general" else False
                    if page_matches and section_matches:
                        matched_evidence = ev
                        break

            # If no exact section match, fallback to any chunk from that document matching page
            if not matched_evidence:
                for eid, ev in evidence_registry.items():
                    title_clean = ev.document_title.strip().lower()
                    cand_clean = doc_title_cand.lower()
                    if cand_clean in title_clean or title_clean in cand_clean:
                        if parsed_page is None or ev.page_number is None or parsed_page == ev.page_number:
                            matched_evidence = ev
                            break

            # If not matched by title, try fuzzy section match
            if not matched_evidence:
                for eid, ev in evidence_registry.items():
                    sec_clean = (ev.section_heading or "").lower()
                    if section_cand.lower() in sec_clean and len(section_cand) > 3:
                        matched_evidence = ev
                        break

            if matched_evidence:
                valid_count += 1
                cited_evidence_ids.add(matched_evidence.evidence_id)
                cited_doc_ids.add(matched_evidence.document_id)

                citations.append(
                    VerifiedCitation(
                        citation_id=uuid.uuid4(),
                        raw_citation_text=raw_text,
                        is_valid=True,
                        evidence_id=matched_evidence.evidence_id,
                        document_id=matched_evidence.document_id,
                        document_version_id=matched_evidence.document_version_id,
                        chunk_id=matched_evidence.chunk_id,
                        document_title=matched_evidence.document_title,
                        section_heading=matched_evidence.section_heading,
                        page_number=matched_evidence.page_number,
                        supporting_text_span=matched_evidence.content[:300]
                    )
                )
            else:
                invalid_count += 1
                citations.append(
                    VerifiedCitation(
                        citation_id=uuid.uuid4(),
                        raw_citation_text=raw_text,
                        is_valid=False,
                        evidence_id=None,
                        document_id=None,
                        document_version_id=None,
                        chunk_id=None,
                        document_title=doc_title_cand,
                        section_heading=section_cand,
                        page_number=parsed_page,
                        validation_error=f"Citation '{raw_text}' does not match any retrieved evidence in context."
                    )
                )

        return CitationExtractionResult(
            citations=citations,
            valid_citation_count=valid_count,
            invalid_citation_count=invalid_count,
            cited_evidence_ids=cited_evidence_ids,
            cited_document_ids=cited_doc_ids
        )
