import concurrent.futures
import io
from pathlib import Path
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient
import psycopg2
import pymupdf
import docx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.exceptions import EntityAlreadyExistsError
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.document import Document, DocumentClassification, DocumentVersion, ProcessingStatus
from app.db.models.document_chunk import DocumentChunk
from app.db.models.permission import DocumentPermission
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.schemas.permission import PermissionGrant
from app.services.document_service import DocumentService
from app.services.hybrid_search_service import HybridSearchService
from app.services.ingestion_service import IngestionService
from app.services.permission_service import PermissionService

PG_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI

pg_engine = create_engine(
    PG_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
PGSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture(scope="module")
def pg_db_setup():
    """Verifies PostgreSQL connection, extensions, and tables for Phase 3."""
    conn = psycopg2.connect(PG_DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://"))
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    cur.execute('CREATE EXTENSION IF NOT EXISTS "vector";')
    cur.close()
    conn.close()

    Base.metadata.create_all(bind=pg_engine)
    db = PGSessionLocal()
    roles = [
        Role(id="ADMIN", description="Tenant Administrator"),
        Role(id="COMPLIANCE_OFFICER", description="Compliance Officer"),
        Role(id="ANALYST", description="Financial Analyst"),
        Role(id="AUDITOR", description="Internal/External Auditor"),
    ]
    for r in roles:
        if not db.query(Role).filter(Role.id == r.id).first():
            db.add(r)
    db.commit()
    db.close()
    yield


@pytest.fixture
def pg_session(pg_db_setup) -> Session:
    """Isolated transaction on real PostgreSQL for test cases."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = PGSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def pg_client(pg_session: Session) -> TestClient:
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(
    db: Session,
    tenant: Tenant,
    email: str,
    roles: list[str],
    password: str = "SecurePass123!"
) -> User:
    role_objs = db.query(Role).filter(Role.id.in_(roles)).all()
    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password(password),
        full_name=f"User {email.split('@')[0]}",
        is_active=True,
        roles=role_objs
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_header(user: User) -> dict:
    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=user.role_names
    )
    return {"Authorization": f"Bearer {token}"}


def create_sample_markdown(path: Path) -> Path:
    content = """# Bank Secrecy Act and Anti-Money Laundering Policy

## 1. Statutory Authority and Scope
The statutory obligations governing suspicious activity monitoring are codified under BSA Section 5318(g) and 31 CFR 1020.320.
All covered financial institutions must establish and maintain an effective anti-money laundering program reasonably designed to achieve compliance.

## 2. Suspicious Activity Report (SAR) Filing Thresholds
Financial institutions must file a Suspicious Activity Report for transactions aggregating at or above specific statutory thresholds.

| Violation Type | Dollar Threshold | Mandatory Filing Window | Form Type |
| Insider Abuse | Any dollar amount | 30 calendar days | FinCEN Form 111 |
| Known Suspect Transaction | $5,000 or greater | 30 calendar days | FinCEN Form 111 |
| Unknown Suspect Transaction | $25,000 or greater | 60 calendar days | FinCEN Form 111 |

## 3. Customer Due Diligence and Beneficial Ownership
Pursuant to the FinCEN CDD Rule (31 CFR 1010.230), covered institutions must identify and verify the identity of beneficial owners.
A beneficial owner is any individual who owns directly or indirectly 25 percent or more of equity interests.

## 4. GDPR Article 33 Breach Notification Obligations
In the event of a personal data security breach involving customer financial records, the supervisory authority must be notified within 72 hours of becoming aware of the breach.
"""
    path.write_text(content, encoding="utf-8")
    return path


def create_sample_docx(path: Path) -> Path:
    doc = docx.Document()
    doc.add_heading("Basel III Liquidity Risk Standards", level=1)
    doc.add_paragraph("This standard specifies regulatory liquidity management rules for global systemically important banks.")

    doc.add_heading("Liquidity Coverage Ratio (LCR)", level=2)
    doc.add_paragraph("The Liquidity Coverage Ratio requires institutions to hold high-quality liquid assets equal to or greater than total net cash outflows over a 30-day stress period.")

    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Regulatory Metric"
    hdr_cells[1].text = "Stress Horizon"
    hdr_cells[2].text = "Minimum Floor"

    row_cells = table.add_row().cells
    row_cells[0].text = "Liquidity Coverage Ratio (LCR)"
    row_cells[1].text = "30 calendar days"
    row_cells[2].text = "100 percent"

    doc.save(path)
    return path


def create_sample_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    
    # Page 1
    page1 = doc.new_page()
    page1.insert_text((50, 72), "FinCEN Advisory Bulletin FIN-2023-A001", fontsize=16)
    page1.insert_text((50, 110), "Section 1: Red Flags for Trade-Based Money Laundering", fontsize=14)
    page1.insert_text((50, 140), "Trade-based money laundering involves the exploitation of international trade transactions to move illicit value.", fontsize=11)
    page1.insert_text((50, 160), "Common red flags include significant discrepancies between invoiced value and fair market value.", fontsize=11)
    
    # Page 2
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Section 2: Shell Company Wire Transfer Monitoring", fontsize=14)
    page2.insert_text((50, 100), "Financial institutions must monitor high-velocity wire transfers through shell companies registered in high-risk jurisdictions.", fontsize=11)
    page2.insert_text((50, 120), "Any pattern of structuring deposits below the $10,000 Currency Transaction Report threshold requires SAR investigation.", fontsize=11)

    doc.save(path)
    doc.close()
    return path


# ==============================================================================
# 15 PHASE 3 POSTGRESQL INTEGRATION TESTS
# ==============================================================================

def test_1_pg_document_ingestion_markdown_and_tables(pg_session: Session):
    """1. Ingest multi-section Markdown document with tables and verify PostgreSQL chunk storage."""
    tenant = Tenant(name="PG Test Ingest Tenant", slug=f"ingest-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"compliance_{uuid.uuid4().hex[:6]}@bank.com", ["COMPLIANCE_OFFICER"])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "bsa_policy.md")
        
        doc_service = DocumentService(pg_session)
        doc = Document(
            tenant_id=tenant.id,
            title="BSA/AML Statutory Policy",
            original_filename="bsa_policy.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            category="REGULATORY_COMPLIANCE",
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()

        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        ingestion = IngestionService(pg_session)
        success = ingestion.process_document(doc.id, version.id, md_file)
        assert success is True

        pg_session.refresh(doc)
        pg_session.refresh(version)
        assert doc.status == ProcessingStatus.INDEXED
        assert version.total_chunks >= 3

        # Directly verify chunks in PostgreSQL table
        chunks = pg_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        assert len(chunks) == version.total_chunks

        # Check vector embedding and search_vector
        for c in chunks:
            assert len(c.embedding) == 384
            assert c.section_heading is not None
            assert c.content_hash is not None

        # Verify generated tsvector column in PostgreSQL
        raw_res = pg_session.execute(
            text("SELECT search_vector FROM document_chunks WHERE document_id = :d_id"),
            {"d_id": doc.id}
        ).fetchall()
        assert len(raw_res) > 0
        assert "5318" in str(raw_res[0][0]) or any("5318" in str(r[0]) for r in raw_res)


def test_2_pg_document_ingestion_docx(pg_session: Session):
    """2. Ingest DOCX file, parse headings and tables, and persist chunks to PostgreSQL."""
    tenant = Tenant(name="DOCX Tenant", slug=f"docx-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"docx_user_{uuid.uuid4().hex[:6]}@bank.com", ["COMPLIANCE_OFFICER"])

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_file = create_sample_docx(Path(tmpdir) / "basel_liquidity.docx")

        doc = Document(
            tenant_id=tenant.id,
            title="Basel III Liquidity Standards",
            original_filename="basel_liquidity.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size_bytes=docx_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()

        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(docx_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        ingestion = IngestionService(pg_session)
        assert ingestion.process_document(doc.id, version.id, docx_file) is True

        chunks = pg_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        assert len(chunks) >= 1
        
        # Verify table content in chunk
        chunk_texts = " ".join(c.content for c in chunks)
        assert "Liquidity Coverage Ratio" in chunk_texts
        assert "Minimum Floor" in chunk_texts or "100 percent" in chunk_texts


def test_3_pg_document_ingestion_pdf(pg_session: Session):
    """3. Ingest multi-page PDF, preserve page numbers, and persist chunks to PostgreSQL."""
    tenant = Tenant(name="PDF Tenant", slug=f"pdf-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"pdf_user_{uuid.uuid4().hex[:6]}@bank.com", ["COMPLIANCE_OFFICER"])

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_file = create_sample_pdf(Path(tmpdir) / "fincen_advisory.pdf")

        doc = Document(
            tenant_id=tenant.id,
            title="FinCEN Advisory FIN-2023-A001",
            original_filename="fincen_advisory.pdf",
            mime_type="application/pdf",
            file_size_bytes=pdf_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()

        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(pdf_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        ingestion = IngestionService(pg_session)
        assert ingestion.process_document(doc.id, version.id, pdf_file) is True

        pg_session.refresh(version)
        assert version.total_pages == 2

        chunks = pg_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        assert len(chunks) >= 2
        pages = {c.page_number for c in chunks}
        assert 1 in pages
        assert 2 in pages


def test_4_pg_dense_search_pgvector_cosine(pg_session: Session):
    """4. Execute dense semantic retrieval with pgvector cosine distance (<=>) in PostgreSQL."""
    tenant = Tenant(name="Dense Search Tenant", slug=f"dense-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"analyst_{uuid.uuid4().hex[:6]}@bank.com", ["ANALYST"])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "policy.md")
        doc = Document(
            tenant_id=tenant.id,
            title="BSA Policy Document",
            original_filename="policy.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        IngestionService(pg_session).process_document(doc.id, version.id, md_file)

        search_service = HybridSearchService(pg_session)
        results = search_service.dense_search(
            query="suspicious activity reporting obligations",
            user=user,
            limit=5
        )

        assert len(results) > 0
        assert results[0]["dense_score"] > 0.0
        assert results[0]["cosine_distance"] is not None
        assert "dense" in results[0]["retrieval_sources"]
        # Verify sorted ascending by cosine distance (descending by dense_score)
        scores = [r["dense_score"] for r in results]
        assert scores == sorted(scores, reverse=True)


def test_5_pg_sparse_search_exact_regulatory_identifiers(pg_session: Session):
    """5. Execute sparse keyword search using PostgreSQL Full-Text Search with exact regulatory IDs."""
    tenant = Tenant(name="Sparse Search Tenant", slug=f"sparse-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"auditor_{uuid.uuid4().hex[:6]}@bank.com", ["AUDITOR"])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "policy.md")
        doc = Document(
            tenant_id=tenant.id,
            title="BSA Compliance Master",
            original_filename="policy.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        IngestionService(pg_session).process_document(doc.id, version.id, md_file)

        search_service = HybridSearchService(pg_session)

        # 1. Exact regulatory statute
        sar_results = search_service.sparse_search(query="BSA Section 5318(g)", user=user, limit=5)
        assert len(sar_results) > 0
        assert any("5318(g)" in r["content"] or "5318(g)" in (r["section_heading"] or "") for r in sar_results)
        assert sar_results[0]["sparse_score"] > 0.0

        # 2. Exact regulatory form
        form_results = search_service.sparse_search(query="FinCEN Form 111", user=user, limit=5)
        assert len(form_results) > 0
        assert any("Form 111" in r["content"] for r in form_results)

        # 3. Exact GDPR timeframe
        gdpr_results = search_service.sparse_search(query="72 hours breach", user=user, limit=5)
        assert len(gdpr_results) > 0
        assert any("72 hours" in r["content"] for r in gdpr_results)


def test_6_pg_hybrid_search_reciprocal_rank_fusion(pg_session: Session):
    """6. Execute hybrid search combining dense and sparse candidates with Reciprocal Rank Fusion."""
    tenant = Tenant(name="Hybrid RRF Tenant", slug=f"rrf-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"hybrid_{uuid.uuid4().hex[:6]}@bank.com", ["ANALYST"])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "policy.md")
        doc = Document(
            tenant_id=tenant.id,
            title="BSA Statutory Manual",
            original_filename="policy.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        IngestionService(pg_session).process_document(doc.id, version.id, md_file)

        search_service = HybridSearchService(pg_session)
        hybrid_results = search_service.hybrid_search(
            query="suspicious transaction BSA Section 5318(g) reporting window",
            user=user,
            dense_limit=10,
            sparse_limit=10,
            top_k=5,
            apply_rerank=False
        )

        assert len(hybrid_results) > 0
        # Results must have rrf_score and rrf_rank
        for idx, r in enumerate(hybrid_results, start=1):
            assert r["rrf_rank"] == idx
            assert r["rrf_score"] > 0.0

        # RRF scores must be monotonically non-increasing
        rrf_scores = [r["rrf_score"] for r in hybrid_results]
        assert rrf_scores == sorted(rrf_scores, reverse=True)


def test_7_pg_cross_encoder_reranking(pg_session: Session):
    """7. Apply cross-encoder reranking to hybrid candidate set."""
    tenant = Tenant(name="Rerank Tenant", slug=f"rerank-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"rerank_{uuid.uuid4().hex[:6]}@bank.com", ["ANALYST"])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "policy.md")
        doc = Document(
            tenant_id=tenant.id,
            title="Compliance Policy",
            original_filename="policy.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        IngestionService(pg_session).process_document(doc.id, version.id, md_file)

        search_service = HybridSearchService(pg_session)
        reranked_results = search_service.hybrid_search(
            query="mandatory filing window for SAR under BSA",
            user=user,
            dense_limit=10,
            sparse_limit=10,
            top_k=3,
            apply_rerank=True
        )

        assert len(reranked_results) <= 3
        assert len(reranked_results) > 0
        for r in reranked_results:
            assert "cross_encoder_score" in r
            assert isinstance(r["cross_encoder_score"], float)

        # Cross-encoder scores must be sorted descending
        ce_scores = [r["cross_encoder_score"] for r in reranked_results]
        assert ce_scores == sorted(ce_scores, reverse=True)


def test_8_pg_tenant_isolation_retrieval(pg_session: Session):
    """8. Verify complete tenant isolation across dense, sparse, and hybrid retrieval."""
    tenant_1 = Tenant(name="Bank One Tenant", slug=f"b1-{uuid.uuid4().hex[:6]}")
    tenant_2 = Tenant(name="Bank Two Tenant", slug=f"b2-{uuid.uuid4().hex[:6]}")
    pg_session.add_all([tenant_1, tenant_2])
    pg_session.commit()

    user_1 = make_user(pg_session, tenant_1, f"u1_{uuid.uuid4().hex[:6]}@bankone.com", ["ANALYST"])
    user_2 = make_user(pg_session, tenant_2, f"u2_{uuid.uuid4().hex[:6]}@banktwo.com", ["ANALYST"])

    with tempfile.TemporaryDirectory() as tmpdir:
        # Tenant 1 has a confidential document
        t1_file = Path(tmpdir) / "t1_secret.md"
        t1_file.write_text("# Project Vanguard Alpha\nSecret proprietary high frequency algorithmic trading formula xyz123.", encoding="utf-8")

        doc1 = Document(
            tenant_id=tenant_1.id,
            title="Project Vanguard Alpha",
            original_filename="t1_secret.md",
            mime_type="text/markdown",
            file_size_bytes=t1_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user_1.id
        )
        pg_session.add(doc1)
        pg_session.commit()
        v1 = DocumentVersion(
            document_id=doc1.id,
            version_num=1,
            storage_path=str(t1_file),
            created_by_id=user_1.id
        )
        pg_session.add(v1)
        pg_session.commit()
        IngestionService(pg_session).process_document(doc1.id, v1.id, t1_file)

        # User 2 from Tenant 2 attempts to query Tenant 1's secret keywords
        search_svc = HybridSearchService(pg_session)

        # Dense
        dense_hits = search_svc.dense_search(query="Project Vanguard Alpha algorithmic trading formula xyz123", user=user_2)
        assert len(dense_hits) == 0

        # Sparse
        sparse_hits = search_svc.sparse_search(query="Vanguard xyz123", user=user_2)
        assert len(sparse_hits) == 0

        # Hybrid
        hybrid_hits = search_svc.hybrid_search(query="Project Vanguard Alpha", user=user_2)
        assert len(hybrid_hits) == 0


def test_9_pg_document_acl_enforcement_in_retrieval(pg_session: Session):
    """9. Enforce document-level ACLs: confidential chunks hidden until explicit read grant."""
    tenant = Tenant(name="ACL Bank", slug=f"acl-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()

    admin_user = make_user(pg_session, tenant, f"admin_{uuid.uuid4().hex[:6]}@aclbank.com", ["ADMIN"])
    analyst_user = make_user(pg_session, tenant, f"analyst_{uuid.uuid4().hex[:6]}@aclbank.com", ["ANALYST"])

    with tempfile.TemporaryDirectory() as tmpdir:
        confidential_file = Path(tmpdir) / "confidential_audit.md"
        confidential_file.write_text("# Board Audit Finding 2026\nSevere anti-money laundering internal control deficiencies in international payments corridor.", encoding="utf-8")

        doc = Document(
            tenant_id=tenant.id,
            title="Board Audit Finding 2026",
            original_filename="confidential_audit.md",
            mime_type="text/markdown",
            file_size_bytes=confidential_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.CONFIDENTIAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=admin_user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        v = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(confidential_file),
            created_by_id=admin_user.id
        )
        pg_session.add(v)
        pg_session.commit()
        IngestionService(pg_session).process_document(doc.id, v.id, confidential_file)

        search_svc = HybridSearchService(pg_session)

        # 1. Analyst cannot retrieve chunks before permission grant
        hits_before = search_svc.hybrid_search(query="control deficiencies international payments", user=analyst_user)
        assert len(hits_before) == 0

        # 2. Grant explicit READ permission to Analyst
        perm_svc = PermissionService(pg_session)
        perm_svc.grant_permission(
            document_id=doc.id,
            grant=PermissionGrant(user_id=analyst_user.id, can_read=True),
            actor=admin_user
        )
        pg_session.commit()

        # 3. Analyst can now retrieve the confidential chunks
        hits_after = search_svc.hybrid_search(query="control deficiencies international payments", user=analyst_user)
        assert len(hits_after) > 0
        assert hits_after[0]["document_id"] == doc.id
        assert hits_after[0]["document_classification"] == "CONFIDENTIAL"


def test_10_pg_duplicate_document_rejection(pg_session: Session):
    """10. Verify duplicate content hash rejection within tenant and multi-tenant coexistence."""
    tenant_1 = Tenant(name="Tenant Dup 1", slug=f"dup1-{uuid.uuid4().hex[:6]}")
    tenant_2 = Tenant(name="Tenant Dup 2", slug=f"dup2-{uuid.uuid4().hex[:6]}")
    pg_session.add_all([tenant_1, tenant_2])
    pg_session.commit()

    u1 = make_user(pg_session, tenant_1, f"u1_{uuid.uuid4().hex[:6]}@t1.com", ["ADMIN"])
    u2 = make_user(pg_session, tenant_2, f"u2_{uuid.uuid4().hex[:6]}@t2.com", ["ADMIN"])

    with tempfile.TemporaryDirectory() as tmpdir:
        sample_file = create_sample_markdown(Path(tmpdir) / "aml.md")
        from app.services.file_validation_service import FileValidationService
        val_svc = FileValidationService()
        f_name, mime, size, f_hash = val_svc.validate_file(sample_file.read_bytes(), "aml.md")

        doc_svc_1 = DocumentService(pg_session)
        from app.schemas.document import DocumentCreate
        
        # First upload in Tenant 1 succeeds
        d1 = doc_svc_1.create_document(
            DocumentCreate(
                title="AML Guidelines",
                original_filename="aml.md",
                content_hash=f_hash,
                file_size_bytes=size,
                mime_type=mime,
                storage_path=str(sample_file),
                classification=DocumentClassification.INTERNAL
            ),
            creator=u1
        )
        assert d1.id is not None

        # Duplicate upload in Tenant 1 raises EntityAlreadyExistsError
        with pytest.raises(EntityAlreadyExistsError):
            doc_svc_1.create_document(
                DocumentCreate(
                    title="AML Guidelines Duplicate",
                    original_filename="aml.md",
                    content_hash=f_hash,
                    file_size_bytes=size,
                    mime_type=mime,
                    storage_path=str(sample_file),
                    classification=DocumentClassification.INTERNAL
                ),
                creator=u1
            )

        # Same file in Tenant 2 succeeds (tenant isolation of content hashes)
        doc_svc_2 = DocumentService(pg_session)
        d2 = doc_svc_2.create_document(
            DocumentCreate(
                title="Tenant 2 AML Copy",
                original_filename="aml.md",
                content_hash=f_hash,
                file_size_bytes=size,
                mime_type=mime,
                storage_path=str(sample_file),
                classification=DocumentClassification.INTERNAL
            ),
            creator=u2
        )
        assert d2.id is not None
        assert d2.tenant_id == tenant_2.id


def test_11_pg_document_reprocessing_idempotency(pg_session: Session):
    """11. Verify document reprocessing replaces chunks atomically without duplicate key errors."""
    tenant = Tenant(name="Reprocess Tenant", slug=f"rep-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"rep_user_{uuid.uuid4().hex[:6]}@bank.com", ["COMPLIANCE_OFFICER"])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "reprocess_doc.md")

        doc = Document(
            tenant_id=tenant.id,
            title="Reprocess Document",
            original_filename="reprocess_doc.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        ingestion = IngestionService(pg_session)
        assert ingestion.process_document(doc.id, version.id, md_file) is True

        initial_chunk_count = pg_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
        assert initial_chunk_count > 0

        # Reprocess document
        reprocessed_doc = ingestion.reprocess_document(doc.id, user)
        assert reprocessed_doc.status == ProcessingStatus.INDEXED

        new_chunk_count = pg_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
        # Chunks were replaced cleanly, exact same count, no duplicates
        assert new_chunk_count == initial_chunk_count


def test_12_pg_cascade_deletion_cleans_chunks(pg_session: Session):
    """12. Verify document deletion cascades to document_chunks table with 0 orphaned rows."""
    tenant = Tenant(name="Cascade Tenant", slug=f"casc-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"admin_{uuid.uuid4().hex[:6]}@bank.com", ["ADMIN"])

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "temp_delete.md")

        doc = Document(
            tenant_id=tenant.id,
            title="Document To Delete",
            original_filename="temp_delete.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()

        IngestionService(pg_session).process_document(doc.id, version.id, md_file)

        # Chunks exist
        chunks_before = pg_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
        assert chunks_before > 0

        # Delete document
        doc_service = DocumentService(pg_session)
        doc_service.delete_document(doc.id, user)
        pg_session.commit()

        # Verify exactly 0 chunks remain in PostgreSQL document_chunks table
        chunks_after = pg_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
        assert chunks_after == 0


def test_13_pg_api_upload_and_status_endpoints(pg_client: TestClient, pg_session: Session):
    """13. Test /api/v1/documents/upload (synchronous), /{id}/status, and /{id}/chunks via FastAPI."""
    tenant = Tenant(name="API Doc Tenant", slug=f"api-doc-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"compliance_{uuid.uuid4().hex[:6]}@bank.com", ["COMPLIANCE_OFFICER"])
    headers = auth_header(user)

    markdown_bytes = b"# Regulatory Notification Rule\nFinancial firms must submit prompt notice for critical cyber breaches."
    
    # 1. Upload Document Synchronously
    upload_resp = pg_client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={
            "title": "Cyber Breach Regulation",
            "classification": "INTERNAL",
            "category": "CYBER_REGULATION",
            "process_sync": "true"
        },
        files={
            "file": ("cyber_rule.md", io.BytesIO(markdown_bytes), "text/markdown")
        }
    )
    assert upload_resp.status_code == 201
    doc_data = upload_resp.json()
    doc_id = doc_data["id"]
    assert doc_data["title"] == "Cyber Breach Regulation"
    assert doc_data["status"] == "INDEXED"

    # 2. Check Document Status
    status_resp = pg_client.get(f"/api/v1/documents/{doc_id}/status", headers=headers)
    assert status_resp.status_code == 200
    stat_data = status_resp.json()
    assert stat_data["status"] == "INDEXED"
    assert stat_data["total_chunks"] >= 1

    # 3. List Document Chunks
    chunks_resp = pg_client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers)
    assert chunks_resp.status_code == 200
    chunk_list = chunks_resp.json()
    assert len(chunk_list) >= 1
    assert "cyber breaches" in chunk_list[0]["content"]


def test_14_pg_api_search_endpoints(pg_client: TestClient, pg_session: Session):
    """14. Test /api/v1/search/dense, /sparse, and /hybrid API endpoints via FastAPI."""
    tenant = Tenant(name="API Search Tenant", slug=f"api-search-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_user(pg_session, tenant, f"analyst_{uuid.uuid4().hex[:6]}@bank.com", ["ANALYST"])
    headers = auth_header(user)

    # Ingest document
    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = create_sample_markdown(Path(tmpdir) / "policy.md")
        doc = Document(
            tenant_id=tenant.id,
            title="Bank Secrecy Act Manual",
            original_filename="policy.md",
            mime_type="text/markdown",
            file_size_bytes=md_file.stat().st_size,
            content_hash=f"hash_{uuid.uuid4().hex}",
            classification=DocumentClassification.INTERNAL,
            status=ProcessingStatus.UPLOADED,
            created_by_id=user.id
        )
        pg_session.add(doc)
        pg_session.commit()
        version = DocumentVersion(
            document_id=doc.id,
            version_num=1,
            storage_path=str(md_file),
            created_by_id=user.id
        )
        pg_session.add(version)
        pg_session.commit()
        IngestionService(pg_session).process_document(doc.id, version.id, md_file)

        # 1. POST /api/v1/search/dense
        d_resp = pg_client.post(
            "/api/v1/search/dense",
            headers=headers,
            json={"query": "suspicious activity reports SAR", "limit": 5}
        )
        assert d_resp.status_code == 200
        d_json = d_resp.json()
        assert d_json["search_mode"] == "dense"
        assert len(d_json["results"]) > 0

        # 2. POST /api/v1/search/sparse
        s_resp = pg_client.post(
            "/api/v1/search/sparse",
            headers=headers,
            json={"query": "BSA Section 5318(g)", "limit": 5}
        )
        assert s_resp.status_code == 200
        s_json = s_resp.json()
        assert s_json["search_mode"] == "sparse"
        assert len(s_json["results"]) > 0

        # 3. POST /api/v1/search/hybrid
        h_resp = pg_client.post(
            "/api/v1/search/hybrid",
            headers=headers,
            json={
                "query": "BSA Section 5318(g) suspicious transaction",
                "top_k": 3,
                "apply_rerank": True
            }
        )
        assert h_resp.status_code == 200
        h_json = h_resp.json()
        assert h_json["search_mode"] == "hybrid_reranked"
        assert len(h_json["results"]) <= 3
        assert len(h_json["results"]) > 0
        assert h_json["results"][0]["cross_encoder_score"] is not None


def test_15_pg_concurrent_chunk_inserts_and_search():
    """15. Verify concurrent chunk processing and hybrid search without deadlocks or connection starvation."""
    setup_db = PGSessionLocal()
    tenant_id = None
    user_id = None
    try:
        tenant = Tenant(name="Concurrency Tenant", slug=f"conc-{uuid.uuid4().hex[:6]}")
        setup_db.add(tenant)
        setup_db.commit()
        setup_db.refresh(tenant)
        tenant_id = tenant.id

        user = make_user(setup_db, tenant, f"conc_user_{uuid.uuid4().hex[:6]}@bank.com", ["ADMIN"])
        user_id = user.id
    finally:
        setup_db.close()

    def worker_task(index: int):
        with PGSessionLocal() as session:
            try:
                thread_user = session.query(User).filter(User.id == user_id).first()
                # 1. Create unique document
                content = f"# Operational Risk Report {index}\nSpecific operational risk loss data for business line {index} under Basel framework."
                with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as f:
                    f.write(content)
                    f.flush()
                    tmp_path = Path(f.name)

                doc = Document(
                    tenant_id=tenant_id,
                    title=f"Risk Report {index}",
                    original_filename=f"risk_{index}.md",
                    mime_type="text/markdown",
                    file_size_bytes=tmp_path.stat().st_size,
                    content_hash=f"hash_conc_{index}_{uuid.uuid4().hex}",
                    classification=DocumentClassification.INTERNAL,
                    status=ProcessingStatus.UPLOADED,
                    created_by_id=thread_user.id
                )
                session.add(doc)
                session.commit()

                ver = DocumentVersion(
                    document_id=doc.id,
                    version_num=1,
                    storage_path=str(tmp_path),
                    created_by_id=thread_user.id
                )
                session.add(ver)
                session.commit()

                # 2. Ingest document
                ingestion = IngestionService(session)
                ingestion.process_document(doc.id, ver.id, tmp_path)

                # 3. Concurrently search
                search_svc = HybridSearchService(session)
                results = search_svc.hybrid_search(
                    query=f"operational risk loss data business line {index}",
                    user=thread_user,
                    top_k=3,
                    apply_rerank=True
                )
                return len(results) > 0
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(results)
        assert len(results) == 5
    finally:
        # Cleanup tenant and cascading documents
        cleanup_db = PGSessionLocal()
        try:
            t_obj = cleanup_db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if t_obj:
                cleanup_db.delete(t_obj)
                cleanup_db.commit()
        finally:
            cleanup_db.close()
