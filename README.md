# FinTrust RAG
## Enterprise Financial Intelligence & Compliance Retrieval Platform

FinTrust RAG is a production-quality enterprise financial intelligence and compliance retrieval platform designed for compliance officers, auditors, financial analysts, and risk managers.

---

## Architecture Overview (Phase 2: Backend Foundation & Multi-Tenant Core)

Phase 2 establishes the core multi-tenant security architecture, database foundations, role-based access control (RBAC), document-level ACLs, and append-only audit logging.

### Key Capabilities Implemented in Phase 2

1. **Deterministic Multi-Tenancy**:
   - Every tenant-owned entity (`User`, `Document`, `DocumentVersion`, `DocumentPermission`, `AuditLog`) is strictly bound to a `tenant_id`.
   - Tenant context is extracted exclusively from cryptographic claims inside verified JWT access tokens.
   - Cross-tenant queries are blocked at both the service layer and the SQL query layer (`WHERE tenant_id = :tenant_id`).

2. **Enterprise RBAC & Document Access Control (ACL)**:
   - System Roles: `ADMIN`, `COMPLIANCE_OFFICER`, `ANALYST`, `AUDITOR`.
   - Conflict Resolution:
     - `ADMIN`: Unrestricted tenant administration and read/write privileges.
     - `AUDITOR`: Strictly read-only access to granted compliance documents and audit trails. Updates and deletes are permanently forbidden.
     - User-Specific Overrides: Explicit user-level permissions override role-level grants on a per-document basis.
     - Document Classification: `PUBLIC`, `INTERNAL` (accessible by default within tenant), `CONFIDENTIAL`, and `STRICTLY_CONFIDENTIAL` (require explicit role or user grant).

3. **Authentication & Cryptography**:
   - Password Hashing: **Argon2id** (RFC 9106 compliant with configurable time cost, memory cost, and parallelism).
   - JWT tokens: HS256 access tokens and refresh tokens with expiration and signature validation.

4. **Document Metadata & Versioning Foundation**:
   - SHA-256 content deduplication per tenant.
   - Automatic creation of initial document version (`version_num=1`) on upload.
   - Processing status state machine (`PENDING`, `PARSING`, `CHUNKING`, `EMBEDDING`, `COMPLETED`, `FAILED`).

5. **Application-Level Append-Only Audit Trail**:
   - Captures authentication events (`AUTH_LOGIN_SUCCESS`, `AUTH_LOGIN_FAILED`), document lifecycle operations (`DOC_CREATE`, `DOC_UPDATE`, `DOC_DELETE`), and permission alterations (`PERMISSION_GRANT`).
   - Audit repository provides no update or delete primitives by design.

---

## Directory Structure

```
FinTrust/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # Main API V1 router aggregation
│   │       ├── auth.py         # Login, token refresh, current user profile
│   │       ├── tenants.py      # Tenant creation and listing
│   │       ├── users.py        # User management and provisioning
│   │       ├── documents.py    # Document metadata CRUD and ACL management
│   │       └── audit.py        # Tenant audit trail inspection
│   ├── core/
│   │   ├── config.py           # Pydantic Settings & environment variables
│   │   ├── security.py         # Argon2id hashing & JWT token handling
│   │   ├── dependencies.py     # FastAPI dependency injection (auth, roles)
│   │   ├── exceptions.py       # Domain-specific exception hierarchy
│   │   └── logging.py          # Structured logging with PII scrubbing
│   ├── db/
│   │   ├── base.py             # SQLAlchemy DeclarativeBase, GUID type, timestamps
│   │   ├── session.py          # Engine and sessionmaker configuration
│   │   └── models/             # SQLAlchemy 2.x declarative models
│   │       ├── tenant.py
│   │       ├── role.py
│   │       ├── user.py
│   │       ├── document.py
│   │       ├── permission.py
│   │       └── audit.py
│   ├── middleware/             # Security headers and request tracking
│   ├── repositories/           # Isolated data access layer
│   ├── schemas/                # Pydantic validation request/response models
│   ├── services/               # Core business logic & authorization checks
│   └── tests/                  # Automated pytest suite (19 test cases)
├── migrations/                 # Alembic migrations for PostgreSQL
│   ├── versions/
│   │   └── 001_initial_schema.py
│   └── env.py
├── alembic.ini
├── docker-compose.yml          # PostgreSQL 16 + pgvector container definition
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## Local Setup & Execution

### 1. Environment Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 2. Running with Docker Compose (Recommended for Production / Staging)

Start PostgreSQL 16 (with `pgvector`) and the backend service:
```bash
docker compose up -d
```
The API will be accessible at `http://localhost:8000`.
- Interactive Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`

### 3. Running Locally (Development Mode)

Install dependencies:
```bash
pip install -r requirements.txt
```

Run database migrations:
```bash
alembic upgrade head
```

Start the FastAPI application:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Running Automated Tests

Run the full automated test suite using `pytest`:
```bash
python -m pytest app/tests -v
```

### Test Suite Coverage (19 Verified Tests)
- `test_auth.py`:
  - `test_successful_user_authentication`
  - `test_invalid_password_rejection`
  - `test_expired_token_rejection`
  - `test_inactive_user_rejection`
  - `test_refresh_token_lifecycle`
- `test_tenant_isolation.py`:
  - `test_cross_tenant_document_access_isolation`
  - `test_cannot_grant_permission_across_tenants`
- `test_rbac.py`:
  - `test_analyst_cannot_perform_administrator_operations`
  - `test_auditor_cannot_modify_documents`
  - `test_compliance_officer_can_create_compliance_documents`
- `test_permissions.py`:
  - `test_unauthorized_confidential_document_access_rejected`
  - `test_role_specific_permission_grant`
  - `test_user_specific_permission_override`
- `test_document_crud.py`:
  - `test_document_creation_and_retrieval`
  - `test_duplicate_content_hash_rejection`
  - `test_document_metadata_update`
  - `test_document_deletion_rules`
- `test_audit.py`:
  - `test_audit_records_created_for_sensitive_operations`
- `test_migrations.py`:
  - `test_alembic_migrations_offline_sql_generation`

---

## API Endpoints Summary

| Method | Endpoint | Description | Access Control |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Authenticate with tenant slug and credentials | Public |
| `POST` | `/api/v1/auth/refresh` | Refresh access token | Public (valid refresh token) |
| `GET` | `/api/v1/auth/me` | Current user profile and role details | Authenticated User |
| `POST` | `/api/v1/tenants/` | Create a new tenant | Admin / System Admin |
| `GET` | `/api/v1/tenants/` | List active tenants | Public / Admin |
| `GET` | `/api/v1/tenants/{id}` | Get tenant details | Authenticated User |
| `POST` | `/api/v1/users/` | Provision a new user in caller's tenant | `ADMIN` only |
| `GET` | `/api/v1/users/` | List users in caller's tenant | `ADMIN`, `COMPLIANCE_OFFICER` |
| `GET` | `/api/v1/users/{id}` | Get user details | Authenticated User (same tenant) |
| `PATCH` | `/api/v1/users/{id}` | Update user details, roles, or active state | `ADMIN` (or self for name) |
| `POST` | `/api/v1/documents/` | Create document metadata (initial v1) | `ADMIN`, `COMPLIANCE_OFFICER` |
| `GET` | `/api/v1/documents/` | List documents in tenant filtered by ACL | Authenticated User |
| `GET` | `/api/v1/documents/{id}` | Get document metadata and versions | Authorized User (ACL checked) |
| `PATCH` | `/api/v1/documents/{id}` | Update document metadata | Authorized User with write permission |
| `DELETE` | `/api/v1/documents/{id}` | Delete document and cascading records | `ADMIN` or authorized `COMPLIANCE_OFFICER` (`AUDITOR` forbidden) |
| `POST` | `/api/v1/documents/{id}/permissions` | Grant or update document permission | `ADMIN`, `COMPLIANCE_OFFICER` |
| `GET` | `/api/v1/documents/{id}/permissions` | List document permissions | `ADMIN`, `COMPLIANCE_OFFICER`, `AUDITOR` |
| `GET` | `/api/v1/audit/` | Inspect audit logs for caller's tenant | `ADMIN`, `COMPLIANCE_OFFICER`, `AUDITOR` |
| `GET` | `/health` | Service health check | Public |

---

## Next Steps: Phase 3 (RAG Engine)
In Phase 3, we build upon this solid backend foundation to implement:
- Document parsing for PDF (with table boundary extraction), DOCX, TXT, and Markdown.
- Intelligent structure-aware and heading-aware chunking with breadcrumb injection.
- Dense embedding generation using SentenceTransformers (`BAAI/bge-small-en-v1.5`).
- Vector storage with `pgvector` HNSW indexes and sparse PostgreSQL full-text search (`tsvector`).
- Reciprocal Rank Fusion (RRF) hybrid retrieval with cross-encoder reranking (`ms-marco-MiniLM-L-6-v2`).
