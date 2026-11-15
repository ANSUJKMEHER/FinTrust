import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.core.logging import redact_sensitive_data
from app.core.rate_limiter import limiter
from app.main import app
from app.services.file_validation_service import FileValidationError, FileValidationService


@pytest.fixture
def client():
    return TestClient(app)


def test_health_live_endpoint(client):
    """Verifies lightweight Kubernetes/Docker liveness probe."""
    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_health_ready_endpoint(client):
    """Verifies comprehensive readiness probe verifying DB, pgvector, and storage."""
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["storage"] == "ok"
    assert "llm_provider" in data["checks"]


def test_prometheus_metrics_endpoint(client):
    """Verifies Prometheus exposition format on /metrics."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    text = res.text
    assert "fintrust_http_requests_total" in text
    assert "fintrust_http_request_duration_seconds" in text
    assert "fintrust_db_pool_checked_in" in text


def test_security_headers_enforced(client):
    """Verifies enterprise security headers are attached to all API responses."""
    res = client.get("/health")
    assert res.status_code == 200
    headers = res.headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "max-age=31536000" in headers["Strict-Transport-Security"]
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["Permissions-Policy"]
    assert headers["X-Permitted-Cross-Domain-Policies"] == "none"
    assert headers["X-Download-Options"] == "noopen"
    assert "X-Request-ID" in headers


def test_rate_limiter_brute_force_protection():
    """Verifies sliding window rate limiter blocks excessive requests."""
    limiter.reset()
    key = "test_auth:192.168.1.50"
    max_reqs = 3
    window = 10

    # First 3 requests should be allowed
    for i in range(max_reqs):
        allowed, remaining, retry = limiter.check(key, max_requests=max_reqs, window_seconds=window)
        assert allowed is True
        assert remaining == (max_reqs - i - 1)

    # 4th request must be rejected with 429 condition
    allowed, remaining, retry = limiter.check(key, max_requests=max_reqs, window_seconds=window)
    assert allowed is False
    assert remaining == 0
    assert retry > 0.0

    limiter.reset()


def test_file_validation_hardening():
    """Verifies security controls on file upload: double extensions, traversal, magic bytes."""
    # 1. Valid PDF with %PDF- header
    valid_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj"
    name, mime, size, h = FileValidationService.validate_file(valid_pdf, "report.pdf")
    assert name == "report.pdf"
    assert mime == "application/pdf"
    assert size == len(valid_pdf)

    # 2. Corrupt/spoofed PDF (missing %PDF- header)
    with pytest.raises(FileValidationError, match="missing valid PDF signature"):
        FileValidationService.validate_file(b"MZ\x90\x00\x03fake_executable", "malware.pdf")

    # 3. Dangerous double extension (e.g., payload.exe.pdf)
    with pytest.raises(FileValidationError, match="Dangerous file extension"):
        FileValidationService.validate_file(valid_pdf, "payload.exe.pdf")

    # 4. Path traversal filename sanitization
    sanitized = FileValidationService.sanitize_filename("../../../etc/passwd.txt")
    assert sanitized == "passwd.txt"

    sanitized_win = FileValidationService.sanitize_filename("..\\..\\windows\\system32\\calc.txt")
    assert sanitized_win == "calc.txt"


def test_production_configuration_fail_fast():
    """Verifies that production environment fails fast if secrets or debug flags are insecure."""
    # Insecure secret in production must fail
    with pytest.raises(ValueError, match="JWT_SECRET_KEY cannot contain default or insecure placeholders"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="insecure_default_secret_that_is_long_enough_32_bytes",
            DEBUG=False,
            POSTGRES_PASSWORD="secure_strong_password_123"
        )

    # Short secret in production must fail
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="short_prod_secret",
            DEBUG=False,
            POSTGRES_PASSWORD="secure_strong_password_123"
        )

    # DEBUG=True in production must fail
    with pytest.raises(ValueError, match="DEBUG must be set to False"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a" * 35,
            DEBUG=True,
            POSTGRES_PASSWORD="secure_strong_password_123"
        )


def test_log_redaction_scrubs_pii_and_secrets():
    """Verifies that PII and sensitive tokens are scrubbed from log strings."""
    raw_log = "User with SSN 123-45-6789 and Card 4532-1234-5678-9012 auth with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.do_not_leak and password='MySuperSecretPassword123!'"
    redacted = redact_sensitive_data(raw_log)
    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "4532-1234-5678-9012" not in redacted
    assert "[REDACTED_CC]" in redacted
    assert "Bearer [REDACTED_TOKEN]" in redacted
    assert "MySuperSecretPassword123!" not in redacted
    assert "[REDACTED]" in redacted
