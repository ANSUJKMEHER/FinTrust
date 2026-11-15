# Hardened Production Dockerfile for FinTrust RAG Backend
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim as runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN groupadd -g 10001 fintrust && \
    useradd -u 10001 -g fintrust -s /bin/false -m appuser

RUN mkdir -p /app/storage/documents && \
    chown -R appuser:fintrust /app

COPY --chown=appuser:fintrust app /app/app
COPY --chown=appuser:fintrust alembic.ini /app/alembic.ini
COPY --chown=appuser:fintrust migrations /app/migrations

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
