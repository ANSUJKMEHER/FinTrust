# FinTrust RAG — Enterprise Production Deployment & Operations Guide

**Platform:** FinTrust RAG — Enterprise Financial Intelligence & Compliance Retrieval Platform  
**Target Environment:** Docker / Kubernetes / Cloud VM (AWS, GCP, Azure, On-Premises)  
**Database:** PostgreSQL 16 with pgvector extension  
**Web Server / Proxy:** Nginx 1.27 (Alpine)  
**Application Server:** FastAPI + Uvicorn (Multi-Worker)  

---

## 1. System Architecture Overview

```
                                [ Enterprise Clients / Browsers ]
                                                │
                                                ▼  HTTPS (443) / HTTP (80)
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ NGINX REVERSE PROXY CONTAINER (Alpine Linux)                                                │
│  - TLS Termination & HTTP/2                                                                 │
│  - Security Headers (CSP, HSTS, X-Frame-Options, Permissions-Policy)                        │
│  - Static Asset Serving & 1-Year Immutable Caching (/assets/*)                              │
│  - Rate Limiting Zones (Auth: 5 req/s burst=10; API: 30 req/s burst=30)                      │
│  - Gzip Compression & Buffer Management                                                     │
└──────────────────────────────┬───────────────────────────────┬──────────────────────────────┘
                               │                               │
        Proxy Pass (/api/*)    │                               │ Proxy Pass (/health, /metrics)
                               ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ FASTAPI APPLICATION CONTAINER (Python 3.11 Slim, Non-Root User: appuser UID 10001)           │
│  - Workers: 4 Uvicorn processes with proxy-headers enabled                                  │
│  - Sliding Window Rate Limiting & DoS Protection                                            │
│  - Ingestion, Parsing, Chunking & HNSW Embedding Generation                                 │
│  - Hybrid Search & Reciprocal Rank Fusion (RRF k=60)                                        │
│  - Grounded RAG Orchestrator & Inline Citation Verifier                                     │
│  - Multi-Agent LangGraph Compliance Workflows & MCP Server                                  │
│  - Observability: Native Prometheus Exporter (/metrics)                                     │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │
                                               │ Connection Pool (SQLAlchemy QueuePool: 20+10)
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ POSTGRESQL 16 + PGVECTOR CONTAINER / MANAGED SERVICE (Cloud SQL / RDS / Aurora)             │
│  - pgvector 0.8.6: HNSW Cosine Distance Index (`idx_chunks_embedding_hnsw`)                  │
│  - Full-Text Search: GIN Index on `search_vector` tsvector                                  │
│  - Multi-Tenant Schema & Compound Tenant Isolation Indexes                                  │
│  - Write-Ahead Logging (WAL) & Automated Snapshot Backups                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Production Environment Prerequisites

| Component | Minimum Version | Recommended Cloud Equivalent |
|---|---|---|
| **Linux Host / VM** | Ubuntu 22.04 LTS / Debian 12 | AWS EC2 (t3.xlarge) / GCP e2-standard-4 (4 vCPU, 16 GB RAM) |
| **Container Engine**| Docker Engine 24+ & Docker Compose v2 | Amazon ECS / Google Cloud Run / EKS / GKE |
| **PostgreSQL**      | PostgreSQL 16.2+ | AWS RDS for PostgreSQL 16 / GCP Cloud SQL with pgvector |
| **Vector Extension**| pgvector 0.8.0+ | Compiled or cloud extension enabled (`CREATE EXTENSION vector;`) |
| **TLS Certificates**| Let's Encrypt / Enterprise PKI | AWS Certificate Manager / Cloudflare / Certbot |

---

## 3. Configuration & Secrets Management

Production configurations are strictly loaded from environment variables or secure cloud secret stores (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault). **FinTrust RAG validates configuration on boot and refuses to start if insecure defaults are detected.**

### Step 1: Create Production Configuration (`.env.production`)
```bash
cp .env.example .env.production
chmod 600 .env.production
```

### Step 2: Configure Environment Variables
```ini
ENVIRONMENT=production
DEBUG=false
PROJECT_NAME="FinTrust RAG"

# Database Credentials
POSTGRES_SERVER=postgres
POSTGRES_PORT=5432
POSTGRES_USER=fintrust_user
POSTGRES_PASSWORD=GENERATE_STRONG_RANDOM_PASSWORD_MIN_16_CHARS
POSTGRES_DB=fintrust_db
DATABASE_URL=postgresql://fintrust_user:GENERATE_STRONG_RANDOM_PASSWORD_MIN_16_CHARS@postgres:5432/fintrust_db

# Connection Pool Tuning
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

# Cryptographic Keys (Generate with `openssl rand -hex 32`)
JWT_SECRET_KEY=9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_AUTH_PER_MINUTE=15
RATE_LIMIT_RAG_PER_MINUTE=60
RATE_LIMIT_GENERAL_PER_MINUTE=120

# Structured Logging & Observability
AUDIT_LOG_ENABLED=true
LOG_FORMAT=json

# Storage Directory
MAX_UPLOAD_SIZE_BYTES=52428800
DOCUMENT_STORAGE_DIR=/app/storage/documents

# LLM Provider Configuration
LLM_PROVIDER=openai # Options: "mock", "openai", "anthropic"
LLM_MODEL_NAME=gpt-4o-mini
LLM_API_KEY=sk-prod-your-api-key-here
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=1500
```

---

## 4. Production Container Build & Hardening

FinTrust uses multi-stage, hardened Docker builds to guarantee minimal image attack surfaces and zero root execution privileges.

### Backend Container (`Dockerfile.backend`)
- **Stage 1 (Builder):** Compiles native C wheels and installs Python packages to an isolated prefix.
- **Stage 2 (Runner):** Minimal `python:3.11-slim` base, non-root user `appuser` (UID 10001), healthcheck testing `/health/live`.

```bash
docker build -t fintrust-backend:1.0.0 -f Dockerfile.backend .
```

### Frontend Container (`Dockerfile.frontend`)
- **Stage 1 (Builder):** Uses `node:20-alpine`, runs `npm ci` and `npm run build` with type checking.
- **Stage 2 (Runner):** Copies compiled bundle to `nginx:1.27-alpine`, mounts hardened configuration, runs healthcheck.

```bash
docker build -t fintrust-frontend:1.0.0 -f Dockerfile.frontend .
```

---

## 5. Deployment with Docker Compose

Deploy the complete multi-tier production stack with network segregation:

```bash
# 1. Start database container
docker compose -f docker-compose.prod.yml up -d postgres

# 2. Wait for postgres healthy status
docker compose -f docker-compose.prod.yml ps

# 3. Apply database migrations
docker compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head

# 4. Start backend and frontend services
docker compose -f docker-compose.prod.yml up -d

# 5. Verify all services are healthy
docker compose -f docker-compose.prod.yml ps
```

---

## 6. Database Migrations Runbook

Database schema evolution is managed via Alembic.

### Apply Migrations
```bash
python -m alembic upgrade head
```

### Verify Current Migration Revision
```bash
python -m alembic current
```

### Rollback Last Migration (If Necessary)
```bash
python -m alembic downgrade -1
```

---

## 7. Automated Backup & Disaster Recovery Runbook

FinTrust includes verified database backup and restore automation.

### Create Timestamped Backup
```bash
python -m scripts.backup_db --output-dir backups --keep 10
```
- Produces compressed custom PostgreSQL archive (`fintrust_backup_YYYYMMDD_HHMMSS.dump`).
- Computes SHA-256 integrity checksum and saves metadata JSON.
- Automatically purges backups older than the retention threshold.

### Restore Database from Backup
```bash
python -m scripts.restore_db --backup-file backups/fintrust_backup_YYYYMMDD_HHMMSS.dump --target-db fintrust_db --verify
```
- Automatically verifies SHA-256 checksum prior to execution.
- Restores all tables, indexes, and views via `pg_restore`.
- Executes table validation query verifying row counts post-restore.

### Non-Destructive Disaster Recovery Drill
```bash
python -m scripts.restore_db --target-db fintrust_recovery_drill --create-target --verify
```

---

## 8. Observability & Monitoring Runbook

### Health Probes for Kubernetes / Load Balancers

1. **Liveness Probe** (`/health/live`):
   - Fast, non-blocking HTTP GET endpoint.
   - Used by Kubernetes kubelet or Docker healthcheck to detect thread deadlocks.
   - Returns: `{"status": "alive", "timestamp": ...}` with HTTP 200.

2. **Readiness Probe** (`/health/ready`):
   - Comprehensive readiness check.
   - Verifies active PostgreSQL connection (`SELECT 1`).
   - Verifies pgvector extension availability.
   - Verifies document storage directory writeability.
   - Returns HTTP 200 (`{"status": "ready"}`) or HTTP 503 (`{"status": "unhealthy"}`).

### Prometheus Metrics Scraping (`/metrics`)

Add FinTrust to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'fintrust-rag'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['backend:8000']
```

Key Prometheus Metrics Exported:
- `fintrust_http_requests_total{method, endpoint, status_code}`
- `fintrust_http_request_duration_seconds{method, endpoint}`
- `fintrust_db_pool_checked_in`
- `fintrust_db_pool_checked_out`
- `fintrust_rag_queries_total`
- `fintrust_rag_retrieval_duration_seconds`
- `fintrust_agent_executions_total`
- `fintrust_rate_limit_hits_total`
- `fintrust_token_usage_total`
