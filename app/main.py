from pathlib import Path
import time
import uuid
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import FinTrustBaseException
from app.core.logging import logger
from app.core.metrics import metrics_registry
from app.db.base import Base
from app.db.session import engine, get_db

# Automatically create tables for SQLite/dev mode if not using external migrations
# (Alembic handles migrations for production PostgreSQL)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.warning(f"Metadata auto-creation skipped or deferred: {str(e)}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Enterprise Financial Intelligence & Compliance Retrieval Platform",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_and_metrics_middleware(request: Request, call_next):
    """Enforces enterprise security headers, request tracing, and latency metrics."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    response = await call_next(request)
    duration = time.time() - start_time

    # Record Prometheus metrics
    try:
        path = request.url.path
        # Normalize IDs in paths for metric cardinality control
        metrics_registry.get("fintrust_http_requests_total").inc(
            labels={"method": request.method, "endpoint": path, "status_code": str(response.status_code)}
        )
        metrics_registry.get("fintrust_http_request_duration_seconds").observe(
            value=duration,
            labels={"method": request.method, "endpoint": path}
        )
    except Exception:
        pass

    # Enterprise Hardened Security Headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["X-Download-Options"] = "noopen"

    return response


# Global Domain Exception Handler
@app.exception_handler(FinTrustBaseException)
async def domain_exception_handler(request: Request, exc: FinTrustBaseException):
    logger.warning(f"Domain exception on {request.method} {request.url}: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message, "error_type": exc.__class__.__name__, "details": exc.details}
    )


# General Unhandled Exception Handler (Never leak database errors or internal stack traces)
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please contact the system administrator."}
    )


# Health Check (Legacy summary)
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }


# Liveness Probe (Kubernetes / Docker healthcheck)
@app.get("/health/live", tags=["Health"])
def liveness_check():
    return {
        "status": "alive",
        "timestamp": time.time()
    }


# Readiness Probe (Checks DB connectivity, pgvector, and storage availability)
@app.get("/health/ready", tags=["Health"])
def readiness_check(response: Response, db: Session = Depends(get_db)):
    checks = {}
    is_ready = True

    # 1. Database Connectivity Check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        is_ready = False

    # 2. Vector Extension Check (for PostgreSQL)
    try:
        if not settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
            res = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).fetchone()
            if res:
                checks["pgvector"] = "ok"
            else:
                checks["pgvector"] = "extension_missing"
                is_ready = False
        else:
            checks["pgvector"] = "sqlite_fallback"
    except Exception as e:
        checks["pgvector"] = f"error: {str(e)}"
        is_ready = False

    # 3. Document Storage Directory Check
    try:
        storage_path = Path(settings.DOCUMENT_STORAGE_DIR)
        storage_path.mkdir(parents=True, exist_ok=True)
        checks["storage"] = "ok"
    except Exception as e:
        checks["storage"] = f"error: {str(e)}"
        is_ready = False

    # 4. LLM Service Configuration
    checks["llm_provider"] = settings.LLM_PROVIDER

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "checks": checks}

    return {"status": "ready", "checks": checks}


# Observability: Prometheus Metrics Exposition
@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    # Update pool gauges if available
    try:
        if hasattr(engine.pool, "checkedin"):
            metrics_registry.get("fintrust_db_pool_checked_in").set(float(engine.pool.checkedin()))
            metrics_registry.get("fintrust_db_pool_checked_out").set(float(engine.pool.checkedout()))
    except Exception:
        pass

    return Response(
        content=metrics_registry.generate_exposition(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# Mount API V1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
