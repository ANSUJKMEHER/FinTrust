# FINTRUST RAG — LINUX STAGING DEPLOYMENT REPORT

**Author**: Principal DevSecOps Engineer & Site Reliability Engineer (SRE)  
**Date**: November 15, 2026  
**System**: FinTrust RAG — Orchestration & Infrastructure  
**Milestone**: Phase 7.6 Staging Deployment Specifications  

---

## 1. ORCHESTRATION TOPOLOGY

In Phase 7.6, a multi-container Linux staging topology was designed to replicate a production-grade enterprise deployment. The architecture comprises 8 isolated, orchestrated services configured via `docker-compose.staging.yml`:

```
                           [ Internet / Clients ]
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │    Nginx 1.25 (Reverse Proxy) │
                      │    Port: 80 / 443 (TLS)       │
                      │    Security Headers, TLS 1.3  │
                      └───────┬───────────────┬───────┘
                              │               │
            ┌─────────────────┘               └─────────────────┐
            ▼                                                   ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│     Frontend (Vite/React)     │               │     Backend (FastAPI)         │
│     Internal Port: 80         │               │     Internal Port: 8000       │
│     Multi-stage Nginx unpriv  │               │     Gunicorn/Uvicorn Workers  │
└───────────────────────────────┘               └───────┬───────────────┬───────┘
                                                        │               │
                                       ┌────────────────┘               └───────────────┐
                                       ▼                                                ▼
                        ┌─────────────────────────────┐                  ┌─────────────────────────────┐
                        │   PgBouncer (Pooling)       │                  │       Redis 7 (Cache)       │
                        │   Internal Port: 6432       │                  │   Internal Port: 6379       │
                        │   Transaction Mode          │                  │   Protected Session/Token   │
                        └──────────────┬──────────────┘                  └─────────────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │  PostgreSQL 16.6 + pgvector │
                        │  Internal Port: 5432        │
                        │  Enterprise Data Storage    │
                        └─────────────────────────────┘

                        ┌─────────────────────────────┐
                        │   Observability Services    │
                        │   Prometheus (Port: 9090)   │
                        │   Grafana (Port: 3001)      │
                        └─────────────────────────────┘
```

---

## 2. ARTIFACT INVENTORY & SPECIFICATIONS

### 2.1 Multi-Stage Frontend Container (`frontend/Dockerfile`)
- **Stage 1 (Builder)**: `node:20-alpine` installs dependencies and compiles optimized static assets using Vite (`npm run build` completed cleanly in 2.72s).
- **Stage 2 (Runtime)**: `nginxinc/nginx-unprivileged:alpine-slim` serves static assets with non-root security principles, minimal attack surface, and SPA routing support.

### 2.2 Orchestration File (`docker-compose.staging.yml`)
- **Services (8)**: `postgres`, `pgbouncer`, `redis`, `backend`, `frontend`, `nginx`, `prometheus`, `grafana`.
- **Networks**: Two isolated bridge networks:
  - `fintrust-public`: Connects `nginx`, `frontend`, `backend`, `prometheus`, and `grafana`.
  - `fintrust-internal`: Restricts database (`postgres`, `pgbouncer`) and cache (`redis`) traffic exclusively to the backend. Databases are never exposed to the public network.
- **Resource Limits**: CPU and memory limits defined for each container to prevent resource contention.
- **Healthchecks**: Comprehensive `test`, `interval`, `timeout`, and `retries` specified on all services.

### 2.3 Edge Security & Reverse Proxy (`deploy/staging/nginx_staging.conf`)
- **TLS Termination**: Modern TLS 1.2 and 1.3 configuration, ECDHE ciphers.
- **Enterprise Security Headers**:
  - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; ...`
- **Rate Limiting Zones**:
  - `auth_limit`: 15 requests/min for login and registration.
  - `api_limit`: 120 requests/min for general API traffic.
- **Request Buffering**: `client_max_body_size 50M` with request streaming.

### 2.4 Monitoring Configuration (`deploy/staging/prometheus.yml`)
- Scrapes backend metrics (`/metrics`) and PgBouncer metrics every 15 seconds.

### 2.5 Automated Lifecycle Scripts
- `deploy/staging/init_staging.sh`: Generates SSL certificates, sets directory permissions, starts PostgreSQL, executes Alembic migrations, boots the full 8-service stack, and verifies service health.
- `deploy/staging/verify_staging.sh`: Executes automated end-to-end smoke tests against `/health/ready`, `/metrics`, security headers, and frontend asset delivery.

---

## 3. HOST EXECUTION AUDIT STATEMENT

- **Configuration & Build Verification**: All configuration files, Dockerfiles, Nginx configurations, and migration scripts were statically and programmatically validated. The frontend production build was verified via `npm run build` (0 errors).
- **Runtime Container Execution Status**: The local development machine is running Windows 11 where the Linux Docker daemon is not active. In strict compliance with audit integrity standards, runtime container execution is recorded as **NOT TESTED (Host Limitation)**.

---

## 4. VERIFICATION VERDICT

- **Staging Infrastructure, Dockerfile & Configuration**: **VERIFIED**
- **Live Multi-Container Runtime on this Workstation**: **NOT TESTED (Host Limitation)**
