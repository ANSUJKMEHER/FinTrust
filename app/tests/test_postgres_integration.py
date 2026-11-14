import concurrent.futures
from datetime import timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.document import Document, DocumentClassification, DocumentVersion, ProcessingStatus
from app.db.models.permission import DocumentPermission
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.audit import AuditLog
from app.db.session import get_db
from app.main import app
from app.schemas.document import DocumentCreate
from app.schemas.permission import PermissionGrant
from app.services.document_service import DocumentService
from app.services.permission_service import PermissionService

# Explicitly use the real PostgreSQL database for this test suite
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
    """Ensures PostgreSQL is reachable, extensions exist, and tables are created."""
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
    """Provides an isolated database transaction on real PostgreSQL."""
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


def make_pg_user(
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


# ==============================================================================
# 15 MANDATORY POSTGRESQL INTEGRATION TESTS
# ==============================================================================

def test_1_pg_successful_authentication(pg_client: TestClient, pg_session: Session):
    """1. Successful authentication against real PostgreSQL with Argon2id."""
    tenant = Tenant(name="PG Bank A", slug=f"pg-bank-a-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    make_pg_user(pg_session, tenant, "user1@pgbanka.com", ["ANALYST"], password="CorrectPassword123!")

    resp = pg_client.post(
        "/api/v1/auth/login",
        json={
            "email": "user1@pgbanka.com",
            "password": "CorrectPassword123!",
            "tenant_slug": tenant.slug
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_2_pg_invalid_password_rejection(pg_client: TestClient, pg_session: Session):
    """2. Invalid password rejection with 401."""
    tenant = Tenant(name="PG Bank B", slug=f"pg-bank-b-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    make_pg_user(pg_session, tenant, "user2@pgbankb.com", ["ANALYST"], password="ValidPassword123!")

    resp = pg_client.post(
        "/api/v1/auth/login",
        json={
            "email": "user2@pgbankb.com",
            "password": "WrongPassword999!",
            "tenant_slug": tenant.slug
        }
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]


def test_3_pg_jwt_expiration(pg_client: TestClient, pg_session: Session):
    """3. Expired token rejection."""
    tenant = Tenant(name="PG Bank C", slug=f"pg-bank-c-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    user = make_pg_user(pg_session, tenant, "user3@pgbankc.com", ["ANALYST"])

    expired_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=user.role_names,
        expires_delta=timedelta(minutes=-30)
    )
    resp = pg_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


def test_4_pg_refresh_token_rotation(pg_client: TestClient, pg_session: Session):
    """4. Refresh token rotation."""
    tenant = Tenant(name="PG Bank D", slug=f"pg-bank-d-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    make_pg_user(pg_session, tenant, "user4@pgbankd.com", ["ANALYST"], password="MySecretPassword123!")

    login_resp = pg_client.post(
        "/api/v1/auth/login",
        json={"email": "user4@pgbankd.com", "password": "MySecretPassword123!", "tenant_slug": tenant.slug}
    )
    refresh_token = login_resp.json()["refresh_token"]

    rot_resp = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert rot_resp.status_code == 200
    assert "access_token" in rot_resp.json()
    assert "refresh_token" in rot_resp.json()


def test_5_pg_tenant_isolation(pg_client: TestClient, pg_session: Session):
    """5. Tenant isolation: Tenant B user cannot list Tenant A documents."""
    tenant_a = Tenant(name="Tenant A", slug=f"ten-a-{uuid.uuid4().hex[:6]}")
    tenant_b = Tenant(name="Tenant B", slug=f"ten-b-{uuid.uuid4().hex[:6]}")
    pg_session.add_all([tenant_a, tenant_b])
    pg_session.commit()

    admin_a = make_pg_user(pg_session, tenant_a, "admin@tena.com", ["ADMIN"])
    analyst_b = make_pg_user(pg_session, tenant_b, "analyst@tenb.com", ["ANALYST"])

    doc_service = DocumentService(pg_session)
    doc_a = doc_service.create_document(
        DocumentCreate(
            title="Tenant A Private Audit",
            original_filename="a_audit.pdf",
            mime_type="application/pdf",
            file_size_bytes=50000,
            content_hash=uuid.uuid4().hex * 2,
            classification=DocumentClassification.INTERNAL,
            category="AUDIT",
            storage_path="/storage/a/audit.pdf"
        ),
        admin_a
    )

    resp_b = pg_client.get("/api/v1/documents", headers=auth_header(analyst_b))
    assert resp_b.status_code == 200
    assert str(doc_a.id) not in [d["id"] for d in resp_b.json()]


def test_6_pg_cross_tenant_document_access_rejection(pg_client: TestClient, pg_session: Session):
    """6. Direct cross-tenant document lookup returns 404 (no information leakage)."""
    tenant_a = Tenant(name="Tenant A2", slug=f"ten-a2-{uuid.uuid4().hex[:6]}")
    tenant_b = Tenant(name="Tenant B2", slug=f"ten-b2-{uuid.uuid4().hex[:6]}")
    pg_session.add_all([tenant_a, tenant_b])
    pg_session.commit()

    admin_a = make_pg_user(pg_session, tenant_a, "admin@tena2.com", ["ADMIN"])
    analyst_b = make_pg_user(pg_session, tenant_b, "analyst@tenb2.com", ["ANALYST"])

    doc_service = DocumentService(pg_session)
    doc_a = doc_service.create_document(
        DocumentCreate(
            title="Confidential Liquidity Assessment",
            original_filename="liquidity.pdf",
            mime_type="application/pdf",
            file_size_bytes=120000,
            content_hash=uuid.uuid4().hex * 2,
            classification=DocumentClassification.CONFIDENTIAL,
            category="LIQUIDITY",
            storage_path="/storage/a/liquidity.pdf"
        ),
        admin_a
    )

    resp = pg_client.get(f"/api/v1/documents/{doc_a.id}", headers=auth_header(analyst_b))
    assert resp.status_code == 404


def test_7_pg_rbac_restrictions(pg_client: TestClient, pg_session: Session):
    """7. RBAC restrictions: Analyst cannot provision users; Auditor cannot delete documents."""
    tenant = Tenant(name="RBAC Bank", slug=f"rbac-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()

    admin = make_pg_user(pg_session, tenant, "admin@rbac.com", ["ADMIN"])
    analyst = make_pg_user(pg_session, tenant, "analyst@rbac.com", ["ANALYST"])
    auditor = make_pg_user(pg_session, tenant, "auditor@rbac.com", ["AUDITOR"])

    # 1. Analyst cannot create user
    user_fail = pg_client.post(
        "/api/v1/users/",
        json={"email": "hacked@rbac.com", "password": "Password123!", "full_name": "Bad Actor", "role_names": ["ADMIN"]},
        headers=auth_header(analyst)
    )
    assert user_fail.status_code == 403

    # 2. Auditor cannot delete document
    doc_service = DocumentService(pg_session)
    doc = doc_service.create_document(
        DocumentCreate(
            title="Protected Ledger",
            original_filename="ledger.pdf",
            mime_type="application/pdf",
            file_size_bytes=40000,
            content_hash=uuid.uuid4().hex * 2,
            classification=DocumentClassification.INTERNAL,
            category="LEDGER",
            storage_path="/storage/ledger.pdf"
        ),
        admin
    )
    del_fail = pg_client.delete(f"/api/v1/documents/{doc.id}", headers=auth_header(auditor))
    assert del_fail.status_code == 403


def test_8_pg_user_specific_document_permissions(pg_client: TestClient, pg_session: Session):
    """8. User-specific permissions override role permissions."""
    tenant = Tenant(name="Perm Bank", slug=f"perm-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()

    admin = make_pg_user(pg_session, tenant, "admin@perm.com", ["ADMIN"])
    analyst = make_pg_user(pg_session, tenant, "analyst@perm.com", ["ANALYST"])

    doc_service = DocumentService(pg_session)
    perm_service = PermissionService(pg_session)

    doc = doc_service.create_document(
        DocumentCreate(
            title="Classified M&A Strategy",
            original_filename="strategy.pdf",
            mime_type="application/pdf",
            file_size_bytes=30000,
            content_hash=uuid.uuid4().hex * 2,
            classification=DocumentClassification.CONFIDENTIAL,
            category="STRATEGY",
            storage_path="/storage/strategy.pdf"
        ),
        admin
    )

    # Initially denied
    assert pg_client.get(f"/api/v1/documents/{doc.id}", headers=auth_header(analyst)).status_code == 403

    # Explicit user-level grant
    perm_service.grant_permission(
        document_id=doc.id,
        grant=PermissionGrant(user_id=analyst.id, can_read=True, can_write=False),
        actor=admin
    )
    assert pg_client.get(f"/api/v1/documents/{doc.id}", headers=auth_header(analyst)).status_code == 200


def test_9_pg_role_specific_document_permissions(pg_client: TestClient, pg_session: Session):
    """9. Role-specific permissions grant access to all users having that role."""
    tenant = Tenant(name="Role Bank", slug=f"role-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()

    admin = make_pg_user(pg_session, tenant, "admin@role.com", ["ADMIN"])
    analyst1 = make_pg_user(pg_session, tenant, "analyst1@role.com", ["ANALYST"])
    analyst2 = make_pg_user(pg_session, tenant, "analyst2@role.com", ["ANALYST"])

    doc_service = DocumentService(pg_session)
    perm_service = PermissionService(pg_session)

    doc = doc_service.create_document(
        DocumentCreate(
            title="Analyst Group Policy",
            original_filename="group.pdf",
            mime_type="application/pdf",
            file_size_bytes=25000,
            content_hash=uuid.uuid4().hex * 2,
            classification=DocumentClassification.CONFIDENTIAL,
            category="GROUP_POLICY",
            storage_path="/storage/group.pdf"
        ),
        admin
    )

    perm_service.grant_permission(
        document_id=doc.id,
        grant=PermissionGrant(role_id="ANALYST", can_read=True, can_write=False),
        actor=admin
    )
    assert pg_client.get(f"/api/v1/documents/{doc.id}", headers=auth_header(analyst1)).status_code == 200
    assert pg_client.get(f"/api/v1/documents/{doc.id}", headers=auth_header(analyst2)).status_code == 200


def test_10_pg_document_crud(pg_client: TestClient, pg_session: Session):
    """10. Full document lifecycle (Create, Read, Update, Delete) in PostgreSQL."""
    tenant = Tenant(name="CRUD Bank", slug=f"crud-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    admin = make_pg_user(pg_session, tenant, "admin@crud.com", ["ADMIN"])

    # Create
    create_resp = pg_client.post(
        "/api/v1/documents/",
        json={
            "title": "Initial Title",
            "original_filename": "policy.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 100000,
            "content_hash": uuid.uuid4().hex * 2,
            "classification": "INTERNAL",
            "category": "COMPLIANCE",
            "storage_path": "/storage/policy.pdf",
            "total_pages": 5
        },
        headers=auth_header(admin)
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["id"]

    # Read
    read_resp = pg_client.get(f"/api/v1/documents/{doc_id}", headers=auth_header(admin))
    assert read_resp.status_code == 200
    assert len(read_resp.json()["versions"]) == 1

    # Update
    patch_resp = pg_client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"title": "Updated Regulatory Title", "status": "COMPLETED"},
        headers=auth_header(admin)
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Regulatory Title"

    # Delete
    del_resp = pg_client.delete(f"/api/v1/documents/{doc_id}", headers=auth_header(admin))
    assert del_resp.status_code == 204
    assert pg_client.get(f"/api/v1/documents/{doc_id}", headers=auth_header(admin)).status_code == 404


def test_11_pg_duplicate_content_hash_rejection(pg_client: TestClient, pg_session: Session):
    """11. Unique constraint uq_tenant_doc_content_hash prevents duplicate upload within tenant."""
    tenant = Tenant(name="Hash Bank", slug=f"hash-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    admin = make_pg_user(pg_session, tenant, "admin@hash.com", ["ADMIN"])

    h = uuid.uuid4().hex * 2
    payload = {
        "title": "Document Hash Test",
        "original_filename": "hash_test.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 1000,
        "content_hash": h,
        "classification": "INTERNAL",
        "category": "TEST",
        "storage_path": "/storage/test.pdf"
    }
    resp1 = pg_client.post("/api/v1/documents/", json=payload, headers=auth_header(admin))
    assert resp1.status_code == 201

    resp2 = pg_client.post("/api/v1/documents/", json=payload, headers=auth_header(admin))
    assert resp2.status_code == 409


def test_12_pg_audit_record_creation(pg_client: TestClient, pg_session: Session):
    """12. Audit records are persisted in PostgreSQL."""
    tenant = Tenant(name="Audit Bank", slug=f"audit-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()
    admin = make_pg_user(pg_session, tenant, "admin@audit.com", ["ADMIN"])

    # Document creation generates audit record
    pg_client.post(
        "/api/v1/documents/",
        json={
            "title": "Audited Document",
            "original_filename": "audited.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 1234,
            "content_hash": uuid.uuid4().hex * 2,
            "classification": "INTERNAL",
            "category": "AUDIT",
            "storage_path": "/storage/audited.pdf"
        },
        headers=auth_header(admin)
    )

    logs_resp = pg_client.get("/api/v1/audit/", headers=auth_header(admin))
    assert logs_resp.status_code == 200
    assert len(logs_resp.json()) >= 1
    actions = [l["action"] for l in logs_resp.json()]
    assert "DOC_CREATE" in actions


def test_13_pg_concurrent_document_creation():
    """13. Concurrent document creation verifies connection pooling and thread safety."""
    setup_db = PGSessionLocal()
    tenant_id = None
    try:
        tenant = Tenant(name="Concurrent Bank", slug=f"conc-{uuid.uuid4().hex[:6]}")
        setup_db.add(tenant)
        setup_db.commit()
        setup_db.refresh(tenant)
        tenant_id = tenant.id
        admin = make_pg_user(setup_db, tenant, "admin@conc.com", ["ADMIN"])
        admin_id = admin.id

        def create_single_doc(i: int):
            thread_db = PGSessionLocal()
            try:
                thread_admin = thread_db.query(User).filter(User.id == admin_id).first()
                svc = DocumentService(thread_db)
                doc = svc.create_document(
                    DocumentCreate(
                        title=f"Concurrent Doc {i}",
                        original_filename=f"doc_{i}.pdf",
                        mime_type="application/pdf",
                        file_size_bytes=1000 + i,
                        content_hash=uuid.uuid4().hex * 2,
                        classification=DocumentClassification.INTERNAL,
                        category="CONCURRENCY",
                        storage_path=f"/storage/doc_{i}.pdf"
                    ),
                    thread_admin
                )
                return str(doc.id)
            finally:
                thread_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_single_doc, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 10
        assert len(set(results)) == 10
    finally:
        if tenant_id:
            cleanup_db = PGSessionLocal()
            try:
                t = cleanup_db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if t:
                    cleanup_db.delete(t)
                    cleanup_db.commit()
            finally:
                cleanup_db.close()
        setup_db.close()


def test_14_pg_transaction_rollback_behavior(pg_session: Session):
    """14. Transaction rollback behavior leaves no orphan rows on failure."""
    tenant = Tenant(name="Rollback Bank", slug=f"rb-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()

    try:
        with pg_session.begin_nested():
            user = User(
                tenant_id=tenant.id,
                email="fail_user@rb.com",
                hashed_password="pw",
                full_name="Fail User",
                is_active=True
            )
            pg_session.add(user)
            # Force integrity error (insert duplicate)
            dup_user = User(
                tenant_id=tenant.id,
                email="fail_user@rb.com",
                hashed_password="pw",
                full_name="Fail User Dup",
                is_active=True
            )
            pg_session.add(dup_user)
            pg_session.flush()
    except IntegrityError:
        pass  # Expected rollback

    # Verify no user exists with this email
    assert pg_session.query(User).filter(User.email == "fail_user@rb.com").first() is None


def test_15_pg_foreign_key_and_cascade_enforcement(pg_session: Session):
    """15. Foreign key and cascade deletion enforcement in PostgreSQL."""
    tenant = Tenant(name="FK Bank", slug=f"fk-{uuid.uuid4().hex[:6]}")
    pg_session.add(tenant)
    pg_session.commit()

    admin = make_pg_user(pg_session, tenant, "admin@fk.com", ["ADMIN"])
    doc_service = DocumentService(pg_session)
    doc = doc_service.create_document(
        DocumentCreate(
            title="Cascade Target",
            original_filename="target.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            content_hash=uuid.uuid4().hex * 2,
            classification=DocumentClassification.INTERNAL,
            category="TEST",
            storage_path="/storage/target.pdf"
        ),
        admin
    )
    doc_id = doc.id

    # Verify version and permission exist
    version = pg_session.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).first()
    assert version is not None

    # Delete tenant: cascades to delete document, version, and user
    pg_session.delete(tenant)
    pg_session.commit()

    assert pg_session.query(Document).filter(Document.id == doc_id).first() is None
    assert pg_session.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).first() is None
    assert pg_session.query(User).filter(User.id == admin.id).first() is None
