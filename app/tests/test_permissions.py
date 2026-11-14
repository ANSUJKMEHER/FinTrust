from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.document import DocumentClassification
from app.db.models.user import User
from app.schemas.document import DocumentCreate
from app.schemas.permission import PermissionGrant
from app.services.document_service import DocumentService
from app.services.permission_service import PermissionService
from app.tests.conftest import auth_header_for_user


def test_unauthorized_confidential_document_access_rejected(
    client: TestClient,
    db: Session,
    user_a_admin: User,
    user_a_analyst: User
):
    """Test 8: CONFIDENTIAL documents reject access by default unless explicitly granted."""
    doc_service = DocumentService(db)

    conf_doc = doc_service.create_document(
        DocumentCreate(
            title="M&A Due Diligence - Strictly Secret",
            original_filename="merger_plans.pdf",
            mime_type="application/pdf",
            file_size_bytes=890000,
            content_hash="e" * 64,
            classification=DocumentClassification.CONFIDENTIAL,
            category="MERGERS_ACQUISITIONS",
            storage_path="/secure/alpha/merger.pdf",
            total_pages=40
        ),
        user_a_admin
    )

    # Analyst without permission is denied
    resp = client.get(
        f"/api/v1/documents/{conf_doc.id}",
        headers=auth_header_for_user(user_a_analyst)
    )
    assert resp.status_code == 403
    assert "not authorized to read" in resp.json()["detail"]


def test_role_specific_permission_grant(
    client: TestClient,
    db: Session,
    user_a_admin: User,
    user_a_analyst: User
):
    """Test 10: Granting read access to the ANALYST role enables access for all analysts."""
    doc_service = DocumentService(db)
    perm_service = PermissionService(db)

    doc = doc_service.create_document(
        DocumentCreate(
            title="Confidential Credit Risk Evaluation",
            original_filename="credit_risk.pdf",
            mime_type="application/pdf",
            file_size_bytes=340000,
            content_hash="f" * 64,
            classification=DocumentClassification.CONFIDENTIAL,
            category="CREDIT_RISK",
            storage_path="/secure/alpha/credit_risk.pdf",
            total_pages=18
        ),
        user_a_admin
    )

    # Grant read access to ANALYST role
    perm_service.grant_permission(
        document_id=doc.id,
        grant=PermissionGrant(role_id="ANALYST", can_read=True, can_write=False),
        actor=user_a_admin
    )

    # Analyst can now read the document
    resp = client.get(
        f"/api/v1/documents/{doc.id}",
        headers=auth_header_for_user(user_a_analyst)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(doc.id)


def test_user_specific_permission_override(
    client: TestClient,
    db: Session,
    user_a_admin: User,
    user_a_analyst: User
):
    """Test 9: User-specific permission explicitly overrides role-level permission."""
    doc_service = DocumentService(db)
    perm_service = PermissionService(db)

    doc = doc_service.create_document(
        DocumentCreate(
            title="Executive Compensation Benchmark",
            original_filename="exec_comp.pdf",
            mime_type="application/pdf",
            file_size_bytes=150000,
            content_hash="1" * 64,
            classification=DocumentClassification.CONFIDENTIAL,
            category="EXECUTIVE_COMPENSATION",
            storage_path="/secure/alpha/exec_comp.pdf",
            total_pages=10
        ),
        user_a_admin
    )

    # 1. Role ANALYST is granted access
    perm_service.grant_permission(
        document_id=doc.id,
        grant=PermissionGrant(role_id="ANALYST", can_read=True, can_write=False),
        actor=user_a_admin
    )

    # Verify analyst can read
    resp_1 = client.get(
        f"/api/v1/documents/{doc.id}",
        headers=auth_header_for_user(user_a_analyst)
    )
    assert resp_1.status_code == 200

    # 2. Specific User Override: Revoke read access for user_a_analyst explicitly
    perm_service.grant_permission(
        document_id=doc.id,
        grant=PermissionGrant(user_id=user_a_analyst.id, can_read=False, can_write=False),
        actor=user_a_admin
    )

    # 3. User-specific override takes precedence over role: now access is rejected!
    resp_2 = client.get(
        f"/api/v1/documents/{doc.id}",
        headers=auth_header_for_user(user_a_analyst)
    )
    assert resp_2.status_code == 403
    assert "not authorized to read" in resp_2.json()["detail"]
