from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.document import DocumentClassification
from app.db.models.user import User
from app.schemas.document import DocumentCreate
from app.services.document_service import DocumentService
from app.tests.conftest import auth_header_for_user


def test_cross_tenant_document_access_isolation(
    client: TestClient,
    db: Session,
    user_a_admin: User,
    user_b_analyst: User
):
    """Test 5: Tenant B cannot access, read, or list Tenant A's documents."""
    doc_service = DocumentService(db)

    # Tenant A Admin creates a document
    doc_a_payload = DocumentCreate(
        title="Alpha Proprietary Risk Matrix",
        original_filename="alpha_risk.pdf",
        mime_type="application/pdf",
        file_size_bytes=1048576,
        content_hash="a" * 64,
        classification=DocumentClassification.INTERNAL,
        category="RISK_POLICY",
        storage_path="/secure/alpha/alpha_risk.pdf",
        total_pages=15
    )
    doc_a = doc_service.create_document(doc_a_payload, user_a_admin)

    # 1. Tenant B user attempts direct GET /documents/{id}
    resp_get = client.get(
        f"/api/v1/documents/{doc_a.id}",
        headers=auth_header_for_user(user_b_analyst)
    )
    # Must return 404 Not Found to prevent resource enumeration across tenants
    assert resp_get.status_code == 404

    # 2. Tenant B user lists documents
    resp_list = client.get(
        "/api/v1/documents",
        headers=auth_header_for_user(user_b_analyst)
    )
    assert resp_list.status_code == 200
    listed_ids = [d["id"] for d in resp_list.json()]
    assert str(doc_a.id) not in listed_ids

    # 3. Tenant B user attempts to update Tenant A's document
    resp_patch = client.patch(
        f"/api/v1/documents/{doc_a.id}",
        json={"title": "Malicious Tamper Attempt"},
        headers=auth_header_for_user(user_b_analyst)
    )
    assert resp_patch.status_code == 404

    # 4. Tenant B user attempts to delete Tenant A's document
    resp_del = client.delete(
        f"/api/v1/documents/{doc_a.id}",
        headers=auth_header_for_user(user_b_analyst)
    )
    assert resp_del.status_code == 404


def test_cannot_grant_permission_across_tenants(
    client: TestClient,
    db: Session,
    user_a_admin: User,
    user_b_analyst: User
):
    """Verifies that an Admin from Tenant A cannot grant permissions to a user from Tenant B."""
    doc_service = DocumentService(db)
    doc_a = doc_service.create_document(
        DocumentCreate(
            title="Alpha Confidential Audit",
            original_filename="alpha_audit.pdf",
            mime_type="application/pdf",
            file_size_bytes=500000,
            content_hash="b" * 64,
            classification=DocumentClassification.CONFIDENTIAL,
            category="AUDIT_REPORT",
            storage_path="/secure/alpha/audit.pdf",
            total_pages=5
        ),
        user_a_admin
    )

    # Attempt to grant permission to user_b_analyst on doc_a
    resp = client.post(
        f"/api/v1/documents/{doc_a.id}/permissions",
        json={"user_id": str(user_b_analyst.id), "can_read": True},
        headers=auth_header_for_user(user_a_admin)
    )
    assert resp.status_code == 403
    assert "tenant" in resp.json()["detail"].lower()
