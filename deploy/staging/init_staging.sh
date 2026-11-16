#!/usr/bin/env bash
# ==============================================================================
# FinTrust RAG - Linux Staging Deployment Automation Script
# Orchestrates Docker Compose, PgBouncer, PostgreSQL 16+pgvector, Redis,
# FastAPI, React Frontend, Nginx Reverse Proxy, Prometheus, and Grafana.
# ==============================================================================
set -euo pipefail

echo "======================================================================"
echo "FINTRUST RAG — STAGING DEPLOYMENT INITIALIZATION"
echo "======================================================================"

# 1. Verify Prerequisites
command -v docker >/dev/null 2>&1 || { echo "[!] Error: Docker is not installed."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "[!] Error: Docker Compose is not installed."; exit 1; }

# 2. Setup Staging SSL Certificates (Self-signed fallback for staging)
CERTS_DIR="deploy/staging/certs"
mkdir -p "${CERTS_DIR}"
if [ ! -f "${CERTS_DIR}/fullchain.pem" ] || [ ! -f "${CERTS_DIR}/privkey.pem" ]; then
    echo "[*] Generating staging TLS certificates..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${CERTS_DIR}/privkey.pem" \
        -out "${CERTS_DIR}/fullchain.pem" \
        -subj "/C=US/ST=FinTrust/L=Staging/O=Enterprise/CN=staging.fintrust.internal" \
        >/dev/null 2>&1
    echo "[+] Staging certificates generated at ${CERTS_DIR}"
fi

# 3. Create persistent directories
mkdir -p storage/documents
mkdir -p pgbouncer

# 4. Pull & Build Stack
echo "[*] Building and starting FinTrust staging services..."
docker compose -f docker-compose.staging.yml build
docker compose -f docker-compose.staging.yml up -d

# 5. Wait for Database & PgBouncer Health
echo "[*] Waiting for PostgreSQL and PgBouncer to become healthy..."
docker compose -f docker-compose.staging.yml exec -T postgres pg_isready -U fintrust_user -d fintrust_db -t 30

# 6. Apply Alembic Migrations
echo "[*] Applying database migrations to latest revision..."
docker compose -f docker-compose.staging.yml exec -T backend python -m alembic upgrade head

# 7. Verify Health Probe
echo "[*] Verifying application readiness probe..."
sleep 5
curl -k -f https://localhost/health/ready || curl -f http://localhost:8000/health/ready

echo ""
echo "======================================================================"
echo "[+] FINTRUST RAG STAGING DEPLOYMENT COMPLETED SUCCESSFULLY"
echo "    Frontend:   https://localhost / http://localhost"
echo "    API Docs:   https://localhost/api/v1/docs"
echo "    Prometheus: http://localhost:9090"
echo "    Grafana:    http://localhost:3001"
echo "======================================================================"
