from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.tests.conftest import auth_header_for_user


def test_document_creation_and_retrieval(
    client: TestClient,
    user_a_admin: User
):
    """Test 11: Create a document and verify metadata, version tracking, and retrieval."""
    payload = {
        "title": "Basel III Liquidity Framework",
        "original_filename": "basel_iii_liquidity.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 1024000,
        "content_hash": "2" * 64,
        "classification": "INTERNAL",
        "category": "CAPITAL_ADEQUACY",
        "storage_path": "/storage/alpha/basel_iii.pdf",
        "total_pages": 45
    }

    create_resp = client.post(
        "/api/v1/documents/",
        json=payload,
        headers=auth_header_for_user(user_a_admin)
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    doc_id = created_data["id"]

    assert created_data["title"] == payload["title"]
    assert created_data["current_version_num"] == 1
    assert created_data["status"] == "PENDING"
    assert created_data["tenant_id"] == str(user_a_admin.tenant_id)

    # Retrieve document detail (including versions)
    get_resp = client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header_for_user(user_a_admin)
    )
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == doc_id
    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["version_num"] == 1
    assert detail["versions"][0]["total_pages"] == 45


def test_duplicate_content_hash_rejection(
    client: TestClient,
    user_a_admin: User
):
    """Verifies that uploading the exact same document hash within the same tenant is rejected with 409 Conflict."""
    payload = {
        "title": "First Upload of Sanctions Policy",
        "original_filename": "sanctions.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 50000,
        "content_hash": "3" * 64,
        "classification": "INTERNAL",
        "category": "SANCTIONS",
        "storage_path": "/storage/alpha/sanctions.pdf",
        "total_pages": 4
    }

    resp1 = client.post(
        "/api/v1/documents/",
        json=payload,
        headers=auth_header_for_user(user_a_admin)
    )
    assert resp1.status_code == 201

    # Second upload with identical content_hash
    resp2 = client.post(
        "/api/v1/documents/",
        json=payload,
        headers=auth_header_for_user(user_a_admin)
    )
    assert resp2.status_code == 409
    assert "already exists in this tenant" in resp2.json()["detail"]


def test_document_metadata_update(
    client: TestClient,
    user_a_admin: User
):
    """Verifies patching title, classification, and status."""
    create_resp = client.post(
        "/api/v1/documents/",
        json={
            "title": "Old Document Title",
            "original_filename": "doc.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 10000,
            "content_hash": "4" * 64,
            "classification": "INTERNAL",
            "category": "GENERAL",
            "storage_path": "/storage/alpha/doc.pdf"
        },
        headers=auth_header_for_user(user_a_admin)
    )
    doc_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/documents/{doc_id}",
        json={
            "title": "Updated Compliance Standard Title",
            "classification": "CONFIDENTIAL",
            "status": "COMPLETED"
        },
        headers=auth_header_for_user(user_a_admin)
    )
    assert patch_resp.status_code == 200
    updated_data = patch_resp.json()
    assert updated_data["title"] == "Updated Compliance Standard Title"
    assert updated_data["classification"] == "CONFIDENTIAL"
    assert updated_data["status"] == "COMPLETED"


def test_document_deletion_rules(
    client: TestClient,
    user_a_admin: User,
    user_a_analyst: User
):
    """Test 12: Document deletion follows authorization rules (analyst rejected, admin permitted)."""
    create_resp = client.post(
        "/api/v1/documents/",
        json={
            "title": "Temporary Draft Policy",
            "original_filename": "draft.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 15000,
            "content_hash": "5" * 64,
            "classification": "INTERNAL",
            "category": "DRAFTS",
            "storage_path": "/storage/alpha/draft.pdf"
        },
        headers=auth_header_for_user(user_a_admin)
    )
    doc_id = create_resp.json()["id"]

    # 1. Analyst cannot delete document
    del_fail = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header_for_user(user_a_analyst)
    )
    assert del_fail.status_code == 403

    # 2. Admin can delete document
    del_ok = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header_for_user(user_a_admin)
    )
    assert del_ok.status_code == 204

    # 3. Document is no longer retrievable
    get_del = client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_header_for_user(user_a_admin)
    )
    assert get_del.status_code == 404
