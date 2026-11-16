"""
FinTrust RAG - Phase 7.6 Tests: Production LLM Configuration Validation
Verifies:
1. Production + mock provider: startup rejected with clear error.
2. Production + valid real provider (OpenAI, Anthropic): accepted.
3. Development + mock provider: accepted.
4. Testing + mock provider: accepted.
5. Missing API credentials for commercial providers in production: rejected.
6. Error messages never leak API credentials.
7. Factory get_llm_provider defense-in-depth rejects mock in production.
"""

import pytest
from pydantic import ValidationError
from app.core.config import Settings
from app.core.exceptions import LLMConfigurationError
from app.llm.factory import get_llm_provider
from app.llm.mock_provider import MockLLMProvider


def test_production_with_mock_rejected():
    """Verify that ENVIRONMENT='production' with LLM_PROVIDER='mock' raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY="a" * 32,
            POSTGRES_PASSWORD="secure_pg_password_123",
            LLM_PROVIDER="mock",
            LLM_API_KEY=""
        )
    error_str = str(exc_info.value)
    assert "In production, LLM_PROVIDER cannot be 'mock'" in error_str
    assert "mock" in error_str.lower()


def test_production_with_alternative_mock_markers_rejected():
    """Verify that alternative mock names ('dummy', 'fake', 'test', 'none') are rejected in production."""
    for marker in ["dummy", "fake", "test", "none", ""]:
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                ENVIRONMENT="production",
                DEBUG=False,
                JWT_SECRET_KEY="a" * 32,
                POSTGRES_PASSWORD="secure_pg_password_123",
                LLM_PROVIDER=marker,
                LLM_API_KEY=""
            )
        assert "In production, LLM_PROVIDER cannot be 'mock'" in str(exc_info.value)


def test_production_with_missing_credentials_rejected():
    """Verify that commercial providers (openai, anthropic) without API keys are rejected in production."""
    # OpenAI without API key
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY="a" * 32,
            POSTGRES_PASSWORD="secure_pg_password_123",
            LLM_PROVIDER="openai",
            LLM_API_KEY=""
        )
    assert "LLM_API_KEY must be configured for provider 'openai'" in str(exc_info.value)

    # Anthropic without API key
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY="a" * 32,
            POSTGRES_PASSWORD="secure_pg_password_123",
            LLM_PROVIDER="anthropic",
            LLM_API_KEY=""
        )
    assert "LLM_API_KEY must be configured for provider 'anthropic'" in str(exc_info.value)


def test_production_with_valid_commercial_provider_accepted():
    """Verify that production mode is accepted when valid commercial provider and credentials are configured."""
    fake_secret_key = "sk-proj-super-secret-production-key-12345"
    s = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_SECRET_KEY="a" * 32,
        POSTGRES_PASSWORD="secure_pg_password_123",
        LLM_PROVIDER="openai",
        LLM_API_KEY=fake_secret_key,
        LLM_MODEL_NAME="gpt-4o"
    )
    assert s.ENVIRONMENT == "production"
    assert s.LLM_PROVIDER == "openai"
    assert s.LLM_MODEL_NAME == "gpt-4o"


def test_development_with_mock_accepted():
    """Verify that development mode accepts mock provider cleanly."""
    s = Settings(
        ENVIRONMENT="development",
        DEBUG=True,
        LLM_PROVIDER="mock",
        LLM_API_KEY=""
    )
    assert s.ENVIRONMENT == "development"
    assert s.LLM_PROVIDER == "mock"


def test_testing_with_mock_accepted():
    """Verify that testing mode accepts mock provider cleanly."""
    s = Settings(
        ENVIRONMENT="testing",
        DEBUG=True,
        LLM_PROVIDER="mock",
        LLM_API_KEY=""
    )
    assert s.ENVIRONMENT == "testing"
    assert s.LLM_PROVIDER == "mock"


def test_credentials_never_leaked_in_errors():
    """Verify that error messages do not expose API keys even when formatting error context."""
    secret_key = "sk-ant-live-real-secret-key-do-not-leak"
    try:
        # Pass a bogus provider name with the secret key present
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY="a" * 32,
            POSTGRES_PASSWORD="secure_pg_password_123",
            LLM_PROVIDER="invalid_unknown_provider",
            LLM_API_KEY=secret_key
        )
    except Exception as exc:
        assert secret_key not in str(exc), "CRITICAL: Secret API key leaked in error string!"


def test_factory_defense_in_depth_rejects_mock_in_production(monkeypatch):
    """Verify that get_llm_provider refuses to instantiate MockLLMProvider when ENVIRONMENT='production'."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(LLMConfigurationError) as exc_info:
        get_llm_provider("mock")
    assert "Mock LLM provider is strictly prohibited in production" in str(exc_info.value)
