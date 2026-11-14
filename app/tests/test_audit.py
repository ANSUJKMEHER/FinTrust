from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.document import DocumentClassification
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.schemas.document import DocumentCreate
from app.services.document_service import DocumentService
from app.tests.conftest import auth_header_for_user


def test_audit_records_created_for_sensitive_operations(
    client: TestClient,
    db: Session,
    tenant_a: Tenant,
    user_a_admin: User
):
    """Test 13: Verifies that sensitive operations create persistent audit entries."""
    doc_service = DocumentService(db)

    # 1. Document creation event
    doc = doc_service.create_document(
        DocumentCreate(
            title="Audit Verification Policy",
            original_filename="audit_ver.pdf",
            mime_type="application/pdf",
            file_size_bytes=42000,
            content_hash="6" * 64,
            classification=DocumentClassification.INTERNAL,
            category="AUDIT_POLICY",
            storage_path="/storage/alpha/audit_ver.pdf"
        ),
        user_a_admin
    )

    # 2. Permission grant event
    client.post(
        f"/api/v1/documents/{doc.id}/permissions",
        json={"role_id": "AUDITOR", "can_read": True},
        headers=auth_header_for_user(user_a_admin)
    )

    # 3. Query audit logs via API
    resp = client.get(
        "/api/v1/audit/",
        headers=auth_header_for_user(user_a_admin)
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 2

    actions = [log["action"] for log in logs]
    assert "DOC_CREATE" in actions
    assert "PERMISSION_GRANT" in actions

    # Verify that tenant_id is preserved across all audit logs
    for log in logs:
        assert log["tenant_id"] == str(tenant_a.id)
