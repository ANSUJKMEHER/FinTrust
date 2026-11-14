"""
Unit tests for Document Summary and Document Comparison Services.
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.db.models.document import Document, DocumentClassification, DocumentVersion, ProcessingStatus
from app.db.models.document_chunk import DocumentChunk
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.llm.mock_provider import MockLLMProvider
from app.services.citation_service import CitationService
from app.services.document_comparison_service import ComparisonFindingType, DocumentComparisonService
from app.services.document_summary_service import DocumentSummaryService
from app.tests.conftest import create_test_user


def make_test_document(
    db: Session,
    tenant_id: uuid.UUID,
    title: str,
    classification: DocumentClassification = DocumentClassification.INTERNAL,
    status: ProcessingStatus = ProcessingStatus.COMPLETED,
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title=title,
        original_filename=f"{title.lower().replace(' ', '_')}.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        content_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        classification=classification,
        category="COMPLIANCE",
        current_version_num=1,
        status=status,
    )
    db.add(doc)
    db.flush()
    return doc


def make_test_version(
    db: Session,
    document_id: uuid.UUID,
    total_pages: int = 5,
) -> DocumentVersion:
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=document_id,
        version_num=1,
        storage_path=f"/storage/{document_id}_v1.pdf",
        total_pages=total_pages,
        total_chunks=2,
    )
    db.add(version)
    db.flush()
    return version


def test_document_summary_extraction(db: Session, tenant_a: Tenant):
    compliance_officer = create_test_user(
        db=db,
        tenant_id=tenant_a.id,
        email="compliance_officer@alpha.com",
        role_names=["COMPLIANCE_OFFICER"],
    )

    doc = make_test_document(
        db=db,
        tenant_id=tenant_a.id,
        title="AML Compliance Policy 2024",
    )
    version = make_test_version(
        db=db,
        document_id=doc.id,
        total_pages=5,
    )

    chunk1 = DocumentChunk(
        tenant_id=tenant_a.id,
        document_id=doc.id,
        document_version_id=version.id,
        chunk_index=0,
        page_number=1,
        section_heading="1. Mandatory Reporting",
        heading_breadcrumb="1. Mandatory Reporting",
        content="Under BSA Section 5318(g), financial institutions must file a SAR within 30 calendar days for transactions exceeding $5,000.",
        token_count=20,
        content_hash="c1" + "0" * 62,
    )
    chunk2 = DocumentChunk(
        tenant_id=tenant_a.id,
        document_id=doc.id,
        document_version_id=version.id,
        chunk_index=1,
        page_number=2,
        section_heading="2. Penalty and Risk",
        heading_breadcrumb="2. Penalty and Risk",
        content="Failure to comply risks civil monetary penalties up to $100,000 per violation.",
        token_count=15,
        content_hash="c2" + "0" * 62,
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    mock_provider = MockLLMProvider()
    citation_service = CitationService()
    summary_service = DocumentSummaryService(
        db=db,
        llm_provider=mock_provider,
        citation_service=citation_service,
    )

    result = summary_service.summarize_document(
        document_id=doc.id,
        user=compliance_officer,
    )

    assert result.document_id == doc.id
    assert result.document_title == "AML Compliance Policy 2024"
    assert result.total_chunks == 2
    assert len(result.key_obligations) >= 1
    assert any("$5,000" in t.threshold_value for t in result.financial_thresholds)
    assert any("30 calendar days" in d.filing_window for d in result.compliance_deadlines)
    assert any("5318(g)" in r for r in result.regulatory_references)
    assert len(result.citations) >= 1


def test_document_summary_tenant_isolation_rejection(
    db: Session,
    tenant_a: Tenant,
    tenant_b: Tenant,
):
    user_b = create_test_user(
        db=db,
        tenant_id=tenant_b.id,
        email="auditor@beta.com",
        role_names=["AUDITOR"],
    )

    doc_a = make_test_document(
        db=db,
        tenant_id=tenant_a.id,
        title="Tenant A Proprietary Risk Report",
    )
    db.commit()

    summary_service = DocumentSummaryService(db=db)

    # Attempting to summarize Tenant A's document with Tenant B's user must raise EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        summary_service.summarize_document(
            document_id=doc_a.id,
            user=user_b,
        )


def test_document_summary_confidential_acl_rejection(
    db: Session,
    tenant_a: Tenant,
):
    analyst = create_test_user(
        db=db,
        tenant_id=tenant_a.id,
        email="analyst@alpha.com",
        role_names=["ANALYST"],
    )

    confidential_doc = make_test_document(
        db=db,
        tenant_id=tenant_a.id,
        title="Executive Compensation and Acquisition Targets",
        classification=DocumentClassification.CONFIDENTIAL,
    )
    db.commit()

    summary_service = DocumentSummaryService(db=db)

    # Analyst does not have explicit read grant on CONFIDENTIAL document
    with pytest.raises(PermissionDeniedError):
        summary_service.summarize_document(
            document_id=confidential_doc.id,
            user=analyst,
        )


def test_document_comparison_detects_threshold_and_deadline_changes(
    db: Session,
    tenant_a: Tenant,
):
    officer = create_test_user(
        db=db,
        tenant_id=tenant_a.id,
        email="officer2@alpha.com",
        role_names=["COMPLIANCE_OFFICER"],
    )

    # Document 1: 2023 Policy
    doc1 = make_test_document(
        db=db,
        tenant_id=tenant_a.id,
        title="Policy v1 - 2023",
    )
    # Document 2: 2024 Policy
    doc2 = make_test_document(
        db=db,
        tenant_id=tenant_a.id,
        title="Policy v2 - 2024",
    )

    v1 = make_test_version(
        db=db,
        document_id=doc1.id,
        total_pages=2,
    )
    v2 = make_test_version(
        db=db,
        document_id=doc2.id,
        total_pages=3,
    )

    # Chunks for v1
    c1_1 = DocumentChunk(
        tenant_id=tenant_a.id,
        document_id=doc1.id,
        document_version_id=v1.id,
        chunk_index=0,
        page_number=1,
        section_heading="SAR Reporting",
        heading_breadcrumb="SAR Reporting",
        content="SAR reports must be submitted within 30 calendar days for transactions exceeding $5,000.",
        token_count=18,
        content_hash="h1" + "0" * 62,
    )
    # Chunks for v2: modified deadline (15 days), modified threshold ($10,000), added section
    c2_1 = DocumentChunk(
        tenant_id=tenant_a.id,
        document_id=doc2.id,
        document_version_id=v2.id,
        chunk_index=0,
        page_number=1,
        section_heading="SAR Reporting",
        heading_breadcrumb="SAR Reporting",
        content="SAR reports must be submitted within 15 calendar days for transactions exceeding $10,000.",
        token_count=18,
        content_hash="h2" + "0" * 62,
    )
    c2_2 = DocumentChunk(
        tenant_id=tenant_a.id,
        document_id=doc2.id,
        document_version_id=v2.id,
        chunk_index=1,
        page_number=2,
        section_heading="Crypto Asset Screening",
        heading_breadcrumb="Crypto Asset Screening",
        content="All virtual currency transactions above $3,000 require enhanced counterparty verification.",
        token_count=16,
        content_hash="h3" + "0" * 62,
    )
    db.add_all([c1_1, c2_1, c2_2])
    db.commit()

    comparison_service = DocumentComparisonService(db=db)
    result = comparison_service.compare_documents(
        doc1_id=doc1.id,
        doc2_id=doc2.id,
        user=officer,
    )

    assert result.doc1_id == doc1.id
    assert result.doc2_id == doc2.id
    assert result.total_findings >= 1

    finding_types = [f.finding_type for f in result.findings]
    assert ComparisonFindingType.THRESHOLD_MODIFIED in finding_types or ComparisonFindingType.DEADLINE_MODIFIED in finding_types
    assert ComparisonFindingType.SECTION_ADDED in finding_types


def test_document_comparison_cross_tenant_rejection(
    db: Session,
    tenant_a: Tenant,
    tenant_b: Tenant,
):
    user_a = create_test_user(
        db=db,
        tenant_id=tenant_a.id,
        email="admin@alpha.com",
        role_names=["ADMIN"],
    )

    doc_a = make_test_document(
        db=db,
        tenant_id=tenant_a.id,
        title="Tenant A Document",
    )
    doc_b = make_test_document(
        db=db,
        tenant_id=tenant_b.id,
        title="Tenant B Document",
    )
    db.commit()

    comparison_service = DocumentComparisonService(db=db)
    # Attempting to compare a tenant's document with another tenant's document must fail
    with pytest.raises(EntityNotFoundError):
        comparison_service.compare_documents(
            doc1_id=doc_a.id,
            doc2_id=doc_b.id,
            user=user_a,
        )
