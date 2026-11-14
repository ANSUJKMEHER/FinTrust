import uuid
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import get_db
from app.main import app

# Use in-memory SQLite with StaticPool and foreign keys for deterministic, isolated testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Seed roles
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
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def tenant_a(db: Session) -> Tenant:
    tenant = Tenant(name="Alpha Bank", slug="alpha-bank", is_active=True)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@pytest.fixture
def tenant_b(db: Session) -> Tenant:
    tenant = Tenant(name="Beta Capital", slug="beta-capital", is_active=True)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def create_test_user(
    db: Session,
    tenant_id: uuid.UUID,
    email: str,
    role_names: list[str],
    password: str = "SecurePass123!",
    is_active: bool = True
) -> User:
    roles = db.query(Role).filter(Role.id.in_(role_names)).all()
    user = User(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password(password),
        full_name=f"User {email.split('@')[0]}",
        is_active=is_active,
        roles=roles
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_a_admin(db: Session, tenant_a: Tenant) -> User:
    return create_test_user(db, tenant_a.id, "admin@alpha.com", ["ADMIN"])


@pytest.fixture
def user_a_compliance(db: Session, tenant_a: Tenant) -> User:
    return create_test_user(db, tenant_a.id, "compliance@alpha.com", ["COMPLIANCE_OFFICER"])


@pytest.fixture
def user_a_analyst(db: Session, tenant_a: Tenant) -> User:
    return create_test_user(db, tenant_a.id, "analyst@alpha.com", ["ANALYST"])


@pytest.fixture
def user_a_auditor(db: Session, tenant_a: Tenant) -> User:
    return create_test_user(db, tenant_a.id, "auditor@alpha.com", ["AUDITOR"])


@pytest.fixture
def user_b_admin(db: Session, tenant_b: Tenant) -> User:
    return create_test_user(db, tenant_b.id, "admin@beta.com", ["ADMIN"])


@pytest.fixture
def user_b_analyst(db: Session, tenant_b: Tenant) -> User:
    return create_test_user(db, tenant_b.id, "analyst@beta.com", ["ANALYST"])


def auth_header_for_user(user: User) -> dict:
    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=user.role_names
    )
    return {"Authorization": f"Bearer {token}"}
