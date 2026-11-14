"""
Unit tests for Citation Verification Service and Evidence Sufficiency Service.
"""
import uuid
import pytest
from app.services.citation_service import VerifiedCitation
from app.services.citation_verification_service import (
    CitationVerificationService,
    ClaimStatus,
)
from app.services.evidence_sufficiency_service import (
    EvidenceSufficiencyService,
    SufficiencyStatus,
)
from app.services.context_construction_service import (
    ContextConstructionService,
    EvidenceItem,
    StructuredContext,
)


def test_entity_extraction_patterns():
    service = CitationVerificationService()
    text = (
        "Under BSA Section 5318(g) and 31 CFR 1020.320, banks must file within 30 calendar days "
        "when transactions exceed $5,000. Capital reserves must remain at least 15% under SOX Section 404."
    )
    entities = service.extract_entities(text)

    assert "$5,000" in entities["currency"]
    assert "15%" in entities["percentages"]
    assert any("5318(g)" in s for s in entities["statutes"])
    assert any("1020.320" in s for s in entities["statutes"])
    assert "30 calendar days" in entities["deadlines"]


def test_verify_claim_supported():
    service = CitationVerificationService()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    evidence = EvidenceItem(
        evidence_id="EVIDENCE_001",
        chunk_id=chunk_id,
        document_id=doc_id,
        document_version_id=uuid.uuid4(),
        document_title="AML Policy Manual",
        document_classification="INTERNAL",
        page_number=4,
        section_heading="1.2 SAR Reporting",
        heading_breadcrumb="1.2 SAR Reporting",
        content="Financial institutions must file a SAR within 30 calendar days following initial detection.",
        token_count=15,
        relevance_score=0.95,
    )
    registry = {"EVIDENCE_001": evidence}

    citation = VerifiedCitation(
        citation_id=uuid.uuid4(),
        raw_citation_text="[AML Policy Manual, 1.2 SAR Reporting, Page 4]",
        is_valid=True,
        evidence_id="EVIDENCE_001",
        document_id=doc_id,
        document_version_id=evidence.document_version_id,
        chunk_id=chunk_id,
        document_title="AML Policy Manual",
        section_heading="1.2 SAR Reporting",
        page_number=4,
        supporting_text_span=evidence.content,
    )

    claim = "Financial institutions must file a SAR within 30 calendar days following detection."
    result = service.verify_claim(
        claim_text=claim,
        claim_index=1,
        citations=[citation],
        evidence_registry=registry,
    )

    assert result.status == ClaimStatus.SUPPORTED
    assert result.confidence_score >= 0.70
    assert result.entity_verification.get("30 calendar days") is True


def test_verify_claim_contradicted_hallucinated_deadline():
    service = CitationVerificationService()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    evidence = EvidenceItem(
        evidence_id="EVIDENCE_001",
        chunk_id=chunk_id,
        document_id=doc_id,
        document_version_id=uuid.uuid4(),
        document_title="AML Policy Manual",
        document_classification="INTERNAL",
        page_number=4,
        section_heading="1.2 SAR Reporting",
        heading_breadcrumb="1.2 SAR Reporting",
        content="Financial institutions must file a SAR within 30 calendar days.",
        token_count=15,
        relevance_score=0.95,
    )
    registry = {"EVIDENCE_001": evidence}

    citation = VerifiedCitation(
        citation_id=uuid.uuid4(),
        raw_citation_text="[AML Policy Manual, 1.2 SAR Reporting, Page 4]",
        is_valid=True,
        evidence_id="EVIDENCE_001",
        document_id=doc_id,
        document_version_id=evidence.document_version_id,
        chunk_id=chunk_id,
        document_title="AML Policy Manual",
        section_heading="1.2 SAR Reporting",
        page_number=4,
        supporting_text_span=evidence.content,
    )

    # Claim introduces a hallucinated deadline "90 calendar days" not in evidence
    claim = "Financial institutions must file a SAR within 90 calendar days."
    result = service.verify_claim(
        claim_text=claim,
        claim_index=1,
        citations=[citation],
        evidence_registry=registry,
    )

    assert result.status == ClaimStatus.CONTRADICTED
    assert result.entity_verification.get("90 calendar days") is False


def test_verify_answer_summary():
    service = CitationVerificationService()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    evidence = EvidenceItem(
        evidence_id="EVIDENCE_001",
        chunk_id=chunk_id,
        document_id=doc_id,
        document_version_id=uuid.uuid4(),
        document_title="AML Policy Manual",
        document_classification="INTERNAL",
        page_number=4,
        section_heading="1.2 SAR Reporting",
        heading_breadcrumb="1.2 SAR Reporting",
        content="Under BSA Section 5318(g), SAR reports must be submitted within 30 calendar days for amounts over $5,000.",
        token_count=20,
        relevance_score=0.95,
    )

    structured_context = StructuredContext(
        evidence_items=[evidence],
        evidence_registry={"EVIDENCE_001": evidence},
        total_tokens=20,
        formatted_context_block="<evidence_context>...</evidence_context>",
    )

    citation = VerifiedCitation(
        citation_id=uuid.uuid4(),
        raw_citation_text="[AML Policy Manual, 1.2 SAR Reporting, Page 4]",
        is_valid=True,
        evidence_id="EVIDENCE_001",
        document_id=doc_id,
        document_version_id=evidence.document_version_id,
        chunk_id=chunk_id,
        document_title="AML Policy Manual",
        section_heading="1.2 SAR Reporting",
        page_number=4,
        supporting_text_span=evidence.content,
    )

    answer_text = (
        "Under BSA Section 5318(g), SAR reports must be submitted within 30 calendar days "
        "[AML Policy Manual, 1.2 SAR Reporting, Page 4]."
    )

    summary = service.verify_answer(
        answer_text=answer_text,
        citations=[citation],
        context=structured_context,
    )

    assert summary.total_claims >= 1
    assert summary.supported_claims >= 1
    assert summary.contradicted_claims == 0
    assert summary.overall_faithfulness_score >= 0.70
    assert summary.is_faithful is True


def test_evidence_sufficiency_sufficient():
    sufficiency_service = EvidenceSufficiencyService(min_sufficiency_score=0.30)
    context_service = ContextConstructionService(max_context_tokens=2000)

    chunks = [
        {
            "chunk_id": uuid.uuid4(),
            "document_id": uuid.uuid4(),
            "document_version_id": uuid.uuid4(),
            "document_title": "AML Policy Manual",
            "document_classification": "INTERNAL",
            "section_heading": "1.2 SAR Reporting",
            "heading_breadcrumb": "1.2 SAR Reporting",
            "page_number": 4,
            "content": "Mandatory SAR filing deadline is 30 calendar days following detection.",
            "token_count": 15,
            "relevance_score": 0.88,
        }
    ]

    query = "What is the mandatory SAR filing deadline?"
    context = context_service.build_context(query=query, retrieved_chunks=chunks)
    eval_result = sufficiency_service.evaluate_sufficiency(query=query, context=context)

    assert eval_result.should_refuse is False
    assert eval_result.status in (SufficiencyStatus.SUFFICIENT, SufficiencyStatus.PARTIALLY_SUFFICIENT)
    assert eval_result.sufficiency_score >= 0.30
    assert len(eval_result.covered_query_terms) >= 2


def test_evidence_sufficiency_insufficient_triggers_refusal():
    sufficiency_service = EvidenceSufficiencyService(min_sufficiency_score=0.30)
    context_service = ContextConstructionService(max_context_tokens=2000)

    chunks = [
        {
            "chunk_id": uuid.uuid4(),
            "document_id": uuid.uuid4(),
            "document_version_id": uuid.uuid4(),
            "document_title": "IT Equipment Policy",
            "document_classification": "INTERNAL",
            "section_heading": "Laptop Allocation",
            "heading_breadcrumb": "IT > Laptop",
            "page_number": 1,
            "content": "Laptops are replaced every three years for full time staff members.",
            "token_count": 14,
            "relevance_score": 0.15,
        }
    ]

    query = "What are the regulatory capital adequacy requirements for tier 1 assets?"
    context = context_service.build_context(query=query, retrieved_chunks=chunks)
    eval_result = sufficiency_service.evaluate_sufficiency(query=query, context=context)

    assert eval_result.should_refuse is True
    assert eval_result.status == SufficiencyStatus.INSUFFICIENT
    assert eval_result.refusal_message is not None
    assert "The provided documents do not contain sufficient evidence" in eval_result.refusal_message
