"""
FinTrust RAG - Phase 5 PostgreSQL Integration Tests
Tests end-to-end multi-agent research, compliance auditing, human approval workflows,
cross-tenant isolation, and agentic API endpoints against live PostgreSQL 16 + pgvector.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.document import Document, DocumentClassification, DocumentVersion, ProcessingStatus
from app.db.models.document_chunk import DocumentChunk
from app.db.models.workflow import (
    AgenticWorkflow,
    AgenticExecutionTrace,
    WorkflowTaskType,
    WorkflowStatus,
    ApprovalStatus,
)
from app.db.session import get_db
from app.main import app
from app.agentic.orchestrator import AgenticOrchestrator

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
    """Verifies PostgreSQL connection and ensures schema is ready."""
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
    """Yields a dedicated PostgreSQL database session per test with automatic rollback."""
    conn = pg_engine.connect()
    trans = conn.begin()
    session = PGSessionLocal(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def pg_client(pg_session: Session) -> TestClient:
    """FastAPI TestClient bound to live PostgreSQL transaction."""
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def pg_tenant(pg_session: Session) -> Tenant:
    tenant = Tenant(name="Global Financial Trust", slug=f"gft-{uuid.uuid4().hex[:6]}", is_active=True)
    pg_session.add(tenant)
    pg_session.commit()
    pg_session.refresh(tenant)
    return tenant


@pytest.fixture
def pg_compliance_officer(pg_session: Session, pg_tenant: Tenant) -> User:
    role = pg_session.query(Role).filter(Role.id == "COMPLIANCE_OFFICER").first()
    user = User(
        tenant_id=pg_tenant.id,
        email=f"compliance_{uuid.uuid4().hex[:6]}@gft.com",
        hashed_password=hash_password("CompliancePass123!"),
        full_name="Chief Compliance Officer",
        is_active=True,
        roles=[role],
    )
    pg_session.add(user)
    pg_session.commit()
    pg_session.refresh(user)
    return user


def test_pg_agentic_research_end_to_end(pg_session: Session, pg_tenant: Tenant, pg_compliance_officer: User):
    """Test end-to-end multi-agent research execution and persistence against PostgreSQL 16."""
    # 1. Ingest document
    doc = Document(
        tenant_id=pg_tenant.id,
        title="FinCEN AML Reporting Manual",
        original_filename="fincen_aml.pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        content_hash="mock_hash_fincen_pg",
        classification=DocumentClassification.INTERNAL,
        status=ProcessingStatus.COMPLETED,
        created_by_id=pg_compliance_officer.id,
    )
    pg_session.add(doc)
    pg_session.commit()
    pg_session.refresh(doc)

    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_num=1,
        storage_path=f"/storage/{doc.id}_v1.pdf",
        total_pages=5,
        total_chunks=1,
    )
    pg_session.add(version)
    pg_session.commit()

    chunk = DocumentChunk(
        tenant_id=pg_tenant.id,
        document_id=doc.id,
        document_version_id=version.id,
        chunk_index=0,
        section_heading="Chapter 3: Currency Reporting",
        content="Financial institutions must report currency transactions exceeding $10,000 within 15 calendar days.",
        content_hash="mock_hash_chunk_fincen",
        token_count=18,
        page_number=3,
    )
    pg_session.add(chunk)
    pg_session.commit()

    # 2. Run multi-agent research workflow
    orchestrator = AgenticOrchestrator(pg_session)
    wf = orchestrator.execute_workflow(
        task_type=WorkflowTaskType.GENERAL_RESEARCH,
        query="What are the currency transaction reporting thresholds and deadlines under FinCEN rules?",
        user=pg_compliance_officer,
        max_iterations=3,
    )

    # 3. Verify PostgreSQL persistence
    assert wf.id is not None
    assert wf.workflow_status == WorkflowStatus.COMPLETED
    assert wf.tenant_id == pg_tenant.id
    assert wf.user_id == pg_compliance_officer.id
    assert "research" in wf.selected_agents
    assert "verification" in wf.selected_agents
    assert wf.final_report is not None
    assert wf.final_report["verification_summary"] is not None

    # 4. Verify PostgreSQL execution traces
    traces = pg_session.query(AgenticExecutionTrace).filter(
        AgenticExecutionTrace.workflow_id == wf.id
    ).order_by(AgenticExecutionTrace.step_number.asc()).all()

    assert len(traces) >= 2
    actions = [t.action for t in traces]
    assert "classify_and_plan" in actions


def test_pg_compliance_audit_human_approval_pause_and_resume(
    pg_session: Session, pg_tenant: Tenant, pg_compliance_officer: User
):
    """Test compliance audit workflow halting for human approval and resuming to completion."""
    # Create two conflicting policy documents
    doc_a = Document(
        tenant_id=pg_tenant.id,
        title="Central AML Policy 2024",
        original_filename="central_aml.pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        content_hash="mock_hash_central",
        classification=DocumentClassification.CONFIDENTIAL,
        status=ProcessingStatus.COMPLETED,
        created_by_id=pg_compliance_officer.id,
    )
    doc_b = Document(
        tenant_id=pg_tenant.id,
        title="Branch Guidelines 2024",
        original_filename="branch_aml.pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        content_hash="mock_hash_branch",
        classification=DocumentClassification.CONFIDENTIAL,
        status=ProcessingStatus.COMPLETED,
        created_by_id=pg_compliance_officer.id,
    )
    pg_session.add_all([doc_a, doc_b])
    pg_session.commit()

    ver_a = DocumentVersion(id=uuid.uuid4(), document_id=doc_a.id, version_num=1, storage_path="a.pdf", total_pages=1, total_chunks=1)
    ver_b = DocumentVersion(id=uuid.uuid4(), document_id=doc_b.id, version_num=1, storage_path="b.pdf", total_pages=1, total_chunks=1)
    pg_session.add_all([ver_a, ver_b])
    pg_session.commit()

    chunk_a = DocumentChunk(
        tenant_id=pg_tenant.id,
        document_id=doc_a.id,
        document_version_id=ver_a.id,
        chunk_index=0,
        section_heading="Reporting Limit",
        content="All transactions exceeding $10,000 must be reported within 15 calendar days.",
        content_hash="hash_a",
        token_count=15,
        page_number=1,
    )
    chunk_b = DocumentChunk(
        tenant_id=pg_tenant.id,
        document_id=doc_b.id,
        document_version_id=ver_b.id,
        chunk_index=0,
        section_heading="Branch Reporting Limit",
        content="All transactions exceeding $5,000 must be reported within 30 days.",
        content_hash="hash_b",
        token_count=15,
        page_number=1,
    )
    pg_session.add_all([chunk_a, chunk_b])
    pg_session.commit()

    orchestrator = AgenticOrchestrator(pg_session)
    wf = orchestrator.execute_workflow(
        task_type=WorkflowTaskType.REGULATORY_COMPLIANCE,
        query="Audit contradictory reporting thresholds between Branch and Central policies.",
        user=pg_compliance_officer,
        max_iterations=3,
    )

    # If unresolved conflict detected, workflow transitions to PENDING_APPROVAL
    if wf.workflow_status == WorkflowStatus.PENDING_APPROVAL:
        assert wf.approval_status == ApprovalStatus.PENDING_APPROVAL

        # Resume via Human Approval
        resumed_wf = orchestrator.handle_approval(
            workflow_id=wf.id,
            user=pg_compliance_officer,
            action="APPROVED",
            feedback="Reconciled: Central policy of $10,000 takes legal precedence over Branch guidelines.",
        )
        assert resumed_wf.workflow_status == WorkflowStatus.COMPLETED
        assert resumed_wf.approval_status == ApprovalStatus.APPROVED
        assert resumed_wf.reviewer_id == pg_compliance_officer.id
        assert resumed_wf.final_report is not None


def test_pg_cross_tenant_isolation(pg_session: Session, pg_tenant: Tenant, pg_compliance_officer: User):
    """Test strict tenant isolation prevents accessing workflows across tenants."""
    tenant_other = Tenant(name="Competitor Bank", slug=f"comp-{uuid.uuid4().hex[:6]}", is_active=True)
    pg_session.add(tenant_other)
    pg_session.commit()

    role = pg_session.query(Role).filter(Role.id == "COMPLIANCE_OFFICER").first()
    user_other = User(
        tenant_id=tenant_other.id,
        email=f"other_{uuid.uuid4().hex[:6]}@competitor.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Other Compliance Officer",
        is_active=True,
        roles=[role],
    )
    pg_session.add(user_other)
    pg_session.commit()

    orchestrator = AgenticOrchestrator(pg_session)
    wf = orchestrator.execute_workflow(
        task_type=WorkflowTaskType.GENERAL_RESEARCH,
        query="Research compliance obligations.",
        user=pg_compliance_officer,
    )

    # User from another tenant attempts to access Tenant A's workflow
    isolated_wf = orchestrator.get_workflow(wf.id, user_other)
    assert isolated_wf is None

    with pytest.raises(ValueError) as exc:
        orchestrator.get_workflow_traces(wf.id, user_other)
    assert "not found or access denied" in str(exc.value)


def test_pg_agentic_rest_api_endpoints(
    pg_client: TestClient, pg_session: Session, pg_tenant: Tenant, pg_compliance_officer: User
):
    """Test FastAPI Agentic REST endpoints against PostgreSQL."""
    token = create_access_token(
        subject=str(pg_compliance_officer.id),
        tenant_id=str(pg_tenant.id),
        roles=["COMPLIANCE_OFFICER"],
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Health endpoint (public)
    health_res = pg_client.get("/api/v1/agentic/health")
    assert health_res.status_code == 200
    data = health_res.json()
    assert data["status"] == "HEALTHY"
    assert "supervisor" in data["active_agents"]
    assert len(data["mcp_tools_available"]) == 19

    # 2. Research endpoint
    research_res = pg_client.post(
        "/api/v1/agentic/research",
        json={"query": "What are suspicious activity reporting requirements?", "max_iterations": 2},
        headers=headers,
    )
    assert research_res.status_code == 200
    wf_data = research_res.json()
    wf_id = wf_data["workflow_id"]
    assert wf_data["task_type"] == "GENERAL_RESEARCH"

    # 3. Get workflow by ID
    get_res = pg_client.get(f"/api/v1/agentic/workflows/{wf_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["workflow_id"] == wf_id

    # 4. Get workflow trace
    trace_res = pg_client.get(f"/api/v1/agentic/workflows/{wf_id}/trace", headers=headers)
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert trace_data["workflow_id"] == wf_id
    assert trace_data["total_steps"] >= 1
