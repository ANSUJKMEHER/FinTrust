from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.document import DocumentClassification
from app.db.models.user import User
from app.schemas.document import DocumentCreate
from app.services.document_service import DocumentService
from app.tests.conftest import auth_header_for_user


def test_analyst_cannot_perform_administrator_operations(
    client: TestClient,
    user_a_analyst: User
):
    """Test 6: Analyst role cannot create users or manage administrative configurations."""
    # Attempt to provision a new user
    resp = client.post(
        "/api/v1/users/",
        json={
            "email": "newbie@alpha.com",
            "password": "ValidPassword123!",
            "full_name": "Newbie Employee",
            "role_names": ["ANALYST"]
        },
        headers=auth_header_for_user(user_a_analyst)
    )
    assert resp.status_code == 403
    assert "forbidden" in resp.json()["detail"].lower()


def test_auditor_cannot_modify_documents(
    client: TestClient,
    db: Session,
    user_a_admin: User,
    user_a_auditor: User
):
    """Test 7: Auditor role has strictly read-only access and cannot PATCH or DELETE documents."""
    doc_service = DocumentService(db)

    doc = doc_service.create_document(
        DocumentCreate(
            title="Q3 Compliance Ledger",
            original_filename="ledger.pdf",
            mime_type="application/pdf",
            file_size_bytes=204800,
            content_hash="c" * 64,
            classification=DocumentClassification.INTERNAL,
            category="COMPLIANCE_LEDGER",
            storage_path="/secure/alpha/ledger.pdf",
            total_pages=8
        ),
        user_a_admin
    )

    # 1. Auditor CAN read the document
    resp_get = client.get(
        f"/api/v1/documents/{doc.id}",
        headers=auth_header_for_user(user_a_auditor)
    )
    assert resp_get.status_code == 200

    # 2. Auditor CANNOT update the document
    resp_patch = client.patch(
        f"/api/v1/documents/{doc.id}",
        json={"title": "Tampered Ledger Title"},
        headers=auth_header_for_user(user_a_auditor)
    )
    assert resp_patch.status_code == 403

    # 3. Auditor CANNOT delete the document
    resp_del = client.delete(
        f"/api/v1/documents/{doc.id}",
        headers=auth_header_for_user(user_a_auditor)
    )
    assert resp_del.status_code == 403
    assert "Auditors have strictly read-only permissions" in resp_del.json()["detail"]


def test_compliance_officer_can_create_compliance_documents(
    client: TestClient,
    user_a_compliance: User
):
    """Verifies that Compliance Officers can successfully upload compliance documents."""
    resp = client.post(
        "/api/v1/documents/",
        json={
            "title": "Anti-Money Laundering Standard Operating Procedure",
            "original_filename": "AML_SOP_v1.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file_size_bytes": 102400,
            "content_hash": "d" * 64,
            "classification": "INTERNAL",
            "category": "AML_POLICY",
            "storage_path": "/secure/alpha/aml_sop.docx",
            "total_pages": 12
        },
        headers=auth_header_for_user(user_a_compliance)
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Anti-Money Laundering Standard Operating Procedure"
