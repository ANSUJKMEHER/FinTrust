import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.models.document import Document, DocumentClassification, DocumentVersion, ProcessingStatus
from app.db.models.document_chunk import DocumentChunk
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.workflow import AgenticWorkflow, ApprovalStatus, WorkflowStatus, WorkflowTaskType
from app.db.session import get_db, SessionLocal
from app.main import app
from app.schemas.rag import RAGQueryRequest
from app.services.embedding_service import EmbeddingService
from app.services.ingestion_service import IngestionService
from app.services.rag_orchestrator import RAGOrchestrator


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_tenants_and_users():
    """Sets up two isolated enterprise tenants (Alpha Bank & Beta Capital) for E2E scenarios."""
    with SessionLocal() as db:
        # Ensure default roles exist in DB
        required_roles = ["ADMIN", "COMPLIANCE_OFFICER", "ANALYST", "AUDITOR"]
        for r_id in required_roles:
            if not db.query(Role).filter(Role.id == r_id).first():
                db.add(Role(id=r_id, description=f"{r_id} role"))
        db.commit()

        suffix = uuid.uuid4().hex[:6]
        # Tenant A
        tenant_a = Tenant(name=f"Alpha Bank {suffix}", slug=f"alpha-bank-{suffix}")
        db.add(tenant_a)
        db.flush()

        role_admin = db.query(Role).filter(Role.id == "ADMIN").first()
        role_co = db.query(Role).filter(Role.id == "COMPLIANCE_OFFICER").first()
        user_a = User(
            tenant_id=tenant_a.id,
            email=f"compliance_officer@{tenant_a.slug}.com",
            hashed_password=hash_password("SecurePass123!"),
            full_name="Alice Compliance",
            is_active=True,
            roles=[role_admin, role_co]
        )
        db.add(user_a)

        # Tenant B
        tenant_b = Tenant(name=f"Beta Capital {suffix}", slug=f"beta-capital-{suffix}")
        db.add(tenant_b)
        db.flush()

        role_auditor = db.query(Role).filter(Role.id == "AUDITOR").first()
        user_b = User(
            tenant_id=tenant_b.id,
            email=f"auditor@{tenant_b.slug}.com",
            hashed_password=hash_password("SecurePass123!"),
            full_name="Bob Auditor",
            is_active=True,
            roles=[role_auditor]
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)

        token_a = create_access_token(str(user_a.id), str(tenant_a.id), roles=["ADMIN", "COMPLIANCE_OFFICER"])
        token_b = create_access_token(str(user_b.id), str(tenant_b.id), roles=["AUDITOR"])

        return {
            "tenant_a": tenant_a,
            "tenant_b": tenant_b,
            "user_a": user_a,
            "user_b": user_b,
            "token_a": token_a,
            "token_b": token_b
        }


def test_scenario_1_document_ingestion_and_hnsw_indexing(client, test_tenants_and_users, tmp_path):
    """Scenario 1: Document Ingestion, Parsing, Chunking & HNSW Vector Indexing in PostgreSQL."""
    data = test_tenants_and_users
    headers = {"Authorization": f"Bearer {data['token_a']}"}

    # Create regulatory text file
    policy_text = """
    # FinCEN Suspicious Activity Reporting Policy
    ## Section 1: Filing Thresholds
    Financial institutions must file a Suspicious Activity Report (SAR) for any transaction involving $5,000 or more
    when a suspect can be identified, or $25,000 or more regardless of potential suspects.
    
    ## Section 2: Statutory Deadlines
    Under BSA Section 5318(g), reports must be filed within 30 calendar days following initial detection.
    If no suspect was identified on the date of detection, the filing deadline may be extended to 60 days.
    """
    file_path = tmp_path / "fincen_policy.txt"
    file_path.write_text(policy_text, encoding="utf-8")

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("fincen_policy.txt", f, "text/plain")},
            data={
                "title": "FinCEN SAR Compliance Policy 2026",
                "classification": "INTERNAL",
                "category": "REGULATORY_COMPLIANCE",
                "process_sync": "true"
            }
        )

    assert res.status_code == 201, res.text
    doc_data = res.json()
    assert doc_data["title"] == "FinCEN SAR Compliance Policy 2026"
    assert doc_data["status"] in ("COMPLETED", "INDEXED")

    # Verify chunks and vector embeddings in PostgreSQL
    with SessionLocal() as db:
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == uuid.UUID(doc_data["id"])).all()
        assert len(chunks) >= 2
        for chk in chunks:
            assert chk.embedding is not None
            assert len(chk.embedding) == 384  # BAAI/bge-small-en-v1.5 dimension
            assert chk.tenant_id == data["tenant_a"].id
            assert len(chk.content) > 0


def test_scenario_2_grounded_hybrid_rag_and_citation_verification(client, test_tenants_and_users, tmp_path):
    """Scenario 2: Grounded Hybrid RAG Pipeline & Inline Citation Verification."""
    data = test_tenants_and_users
    headers = {"Authorization": f"Bearer {data['token_a']}"}

    # Upload compliance document
    content = """
    # BSA Anti-Money Laundering Framework
    ## Mandatory Record Retention
    Financial institutions are strictly required to maintain all currency transaction reports (CTRs)
    and customer identification records for a minimum duration of 5 years [BSA Section 5318(b)].
    """
    file_path = tmp_path / "aml_framework.txt"
    file_path.write_text(content, encoding="utf-8")

    with open(file_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("aml_framework.txt", f, "text/plain")},
            data={
                "title": "BSA AML Framework",
                "classification": "INTERNAL",
                "process_sync": "true"
            }
        )
    assert upload_res.status_code == 201

    # Execute Grounded RAG Query
    query_payload = {
        "query": "What is the mandatory record retention duration for currency transaction reports?",
        "max_chunks": 5
    }
    rag_res = client.post("/api/v1/rag/query", headers=headers, json=query_payload)
    assert rag_res.status_code == 200, rag_res.text
    rag_data = rag_res.json()

    assert rag_data["is_refusal"] is False
    assert len(rag_data["answer"]) > 20
    assert len(rag_data["citations"]) > 0
    # Confirm citation fidelity and evidence linkage
    first_citation = rag_data["citations"][0]
    assert first_citation["document_title"] == "BSA AML Framework"
    assert first_citation["is_valid"] is True


def test_scenario_3_multi_agent_compliance_investigation(client, test_tenants_and_users):
    """Scenario 3: Autonomous Multi-Agent Regulatory Compliance Workflow with Execution Tracing."""
    data = test_tenants_and_users
    headers = {"Authorization": f"Bearer {data['token_a']}"}

    payload = {
        "query": "Audit cross-border transaction monitoring thresholds under BSA guidelines",
        "statute_reference": "BSA Section 5318(g)",
        "require_human_approval": False,
        "max_iterations": 4
    }
    res = client.post("/api/v1/agentic/compliance-audit", headers=headers, json=payload)
    assert res.status_code == 200, res.text
    wf_data = res.json()

    assert wf_data["workflow_status"] in ("COMPLETED", "APPROVED")
    assert wf_data["final_report"] is not None
    assert len(wf_data["execution_plan"]) > 0

    # Retrieve and verify database execution traces
    workflow_id = wf_data["workflow_id"]
    trace_res = client.get(f"/api/v1/agentic/workflows/{workflow_id}/trace", headers=headers)
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert trace_data["workflow_id"] == workflow_id
    assert len(trace_data["traces"]) >= 1


def test_scenario_4_human_in_the_loop_approval_workflow(client, test_tenants_and_users):
    """Scenario 4: Human-in-the-Loop Signoff Workflow (Pending Approval -> Reviewer Signoff -> Approved)."""
    data = test_tenants_and_users
    headers_author = {"Authorization": f"Bearer {data['token_a']}"}

    # Seed an agentic workflow in PENDING_APPROVAL state in PostgreSQL
    with SessionLocal() as db:
        wf = AgenticWorkflow(
            tenant_id=data["tenant_a"].id,
            user_id=data["user_a"].id,
            task_type=WorkflowTaskType.REGULATORY_COMPLIANCE,
            workflow_status=WorkflowStatus.PENDING_APPROVAL,
            approval_status=ApprovalStatus.PENDING_APPROVAL,
            query="Evaluate cross-border capital liquidity adequacy under Basel III",
            execution_plan=[{"step": 1, "agent": "compliance_auditor"}],
            selected_agents=["compliance_auditor"],
            state_snapshot={"unresolved_conflicts": ["Liquidity buffer conflicting definitions"]},
            final_report={"preliminary_summary": "Requires executive signoff."}
        )
        db.add(wf)
        db.commit()
        db.refresh(wf)
        workflow_id = str(wf.id)

    # Submit Human Signoff Approval via REST API
    approval_payload = {
        "decision": "APPROVED",
        "comments": "Reviewed methodology and regulatory formulas. Approved for compliance signoff."
    }
    approve_res = client.post(
        f"/api/v1/agentic/workflows/{workflow_id}/approval",
        headers=headers_author,
        json=approval_payload
    )
    assert approve_res.status_code == 200, approve_res.text
    approved_wf = approve_res.json()
    assert approved_wf["approval_status"] == "APPROVED"
    assert "Reviewed methodology" in approved_wf["reviewer_comments"]
    assert approved_wf["reviewer_id"] == str(data["user_a"].id)


def test_scenario_5_multi_tenant_isolation_stress(client, test_tenants_and_users, tmp_path):
    """Scenario 5: Multi-Tenant Isolation Stress (Tenant B strictly denied access to Tenant A's documents)."""
    data = test_tenants_and_users
    headers_a = {"Authorization": f"Bearer {data['token_a']}"}
    headers_b = {"Authorization": f"Bearer {data['token_b']}"}

    # Tenant A ingests confidential strategic M&A document
    confidential_text = """
    # Confidential M&A Strategy Alpha 2026
    Target acquisition of Delta Payments Corp for $450 Million. Strictly confidential to Alpha Bank.
    """
    file_path = tmp_path / "confidential_ma.txt"
    file_path.write_text(confidential_text, encoding="utf-8")

    with open(file_path, "rb") as f:
        res_a = client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            files={"file": ("confidential_ma.txt", f, "text/plain")},
            data={"title": "Confidential M&A Strategy", "classification": "CONFIDENTIAL", "process_sync": "true"}
        )
    assert res_a.status_code == 201
    doc_id_a = res_a.json()["id"]

    # 1. Tenant B listing documents must NOT see Tenant A's document
    res_b_list = client.get("/api/v1/documents/", headers=headers_b)
    assert res_b_list.status_code == 200
    tenant_b_doc_ids = [d["id"] for d in res_b_list.json()]
    assert doc_id_a not in tenant_b_doc_ids

    # 2. Tenant B direct document retrieval must fail with 404 or 403
    res_b_direct = client.get(f"/api/v1/documents/{doc_id_a}/status", headers=headers_b)
    assert res_b_direct.status_code in (403, 404)

    # 3. Tenant B querying RAG on confidential terms must return refusal, never leaking Tenant A's context
    rag_res_b = client.post(
        "/api/v1/rag/query",
        headers=headers_b,
        json={"query": "What is the target acquisition price for Delta Payments Corp?", "max_chunks": 5}
    )
    assert rag_res_b.status_code == 200
    rag_data_b = rag_res_b.json()
    assert rag_data_b["is_refusal"] is True
    assert "Delta Payments Corp" not in rag_data_b["answer"]
    assert len(rag_data_b["citations"]) == 0


def test_scenario_6_failure_recovery_and_circuit_breaker(client, test_tenants_and_users, monkeypatch):
    """Scenario 6: Failure Recovery, Error Containment, and Resilient Degradation."""
    data = test_tenants_and_users
    headers = {"Authorization": f"Bearer {data['token_a']}"}

    # Test RAG refusal and graceful handling when evidence is empty or query is irrelevant
    irrelevant_query = {
        "query": "What is the recipe for chocolate lava cake in Paris?",
        "max_chunks": 3
    }
    res = client.post("/api/v1/rag/query", headers=headers, json=irrelevant_query)
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["is_refusal"] is True
    assert settings.RAG_REFUSAL_MESSAGE in res_json["answer"]

    # Test API boundary resilience against malformed inputs
    malformed_res = client.post("/api/v1/rag/query", headers=headers, json={"invalid_field": 123})
    assert malformed_res.status_code == 422  # Unprocessable Entity
