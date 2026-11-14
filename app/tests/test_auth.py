from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.tests.conftest import create_test_user


def test_successful_user_authentication(client: TestClient, db: Session, tenant_a: Tenant):
    """Test 1: Valid credentials against registered tenant returns JWT tokens."""
    create_test_user(db, tenant_a.id, "login_test@alpha.com", ["ANALYST"], password="CorrectPassword123!")

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login_test@alpha.com",
            "password": "CorrectPassword123!",
            "tenant_slug": tenant_a.slug
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_invalid_password_rejection(client: TestClient, db: Session, tenant_a: Tenant):
    """Test 2: Incorrect password results in 401 Unauthorized."""
    create_test_user(db, tenant_a.id, "wrong_pw@alpha.com", ["ANALYST"], password="RealPassword123!")

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrong_pw@alpha.com",
            "password": "WrongPassword999!",
            "tenant_slug": tenant_a.slug
        }
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_expired_token_rejection(client: TestClient, db: Session, tenant_a: Tenant):
    """Test 3: Access token with past expiration is rejected with 401."""
    user = create_test_user(db, tenant_a.id, "expired@alpha.com", ["ANALYST"])
    
    # Generate token that expired 10 minutes ago
    expired_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=user.role_names,
        expires_delta=timedelta(minutes=-10)
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


def test_inactive_user_rejection(client: TestClient, db: Session, tenant_a: Tenant):
    """Test 4: Deactivated user account is rejected upon login with 403."""
    create_test_user(
        db,
        tenant_a.id,
        "inactive@alpha.com",
        ["ANALYST"],
        password="MyPassword123!",
        is_active=False
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@alpha.com",
            "password": "MyPassword123!",
            "tenant_slug": tenant_a.slug
        }
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


def test_refresh_token_lifecycle(client: TestClient, db: Session, tenant_a: Tenant):
    """Verify refresh token issuance and token rotation."""
    user = create_test_user(db, tenant_a.id, "refresh_test@alpha.com", ["ANALYST"], password="TestPassword123!")

    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "refresh_test@alpha.com",
            "password": "TestPassword123!",
            "tenant_slug": tenant_a.slug
        }
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
