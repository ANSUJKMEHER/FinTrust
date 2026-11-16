import pytest
from app.core.exceptions import LLMConfigurationError, LLMProviderError
from app.llm.base import LLMMessage, MessageRole
from app.llm.factory import get_llm_provider
from app.llm.mock_provider import MockLLMProvider
from app.llm.openai_provider import OpenAICompatibleProvider
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider


def test_mock_provider_generation_and_tokens():
    provider = MockLLMProvider(canned_response="Grounded response [Policy A, Sec 1, Page 2].")
    messages = [
        LLMMessage(role=MessageRole.SYSTEM, content="You are a compliance assistant."),
        LLMMessage(role=MessageRole.USER, content="What is the policy?")
    ]
    resp = provider.generate(messages)
    assert resp.content == "Grounded response [Policy A, Sec 1, Page 2]."
    assert resp.provider == "mock"
    assert resp.model == "fintrust-mock-v1"
    assert resp.total_tokens > 0
    assert resp.latency_ms >= 0.0

    health = provider.health_check()
    assert health["status"] == "healthy"


def test_factory_resolves_all_providers():
    # Mock
    p_mock = get_llm_provider("mock")
    assert isinstance(p_mock, MockLLMProvider)

    # vLLM (local endpoint with dummy key)
    p_vllm = get_llm_provider("vllm", api_base="http://localhost:8000/v1")
    assert isinstance(p_vllm, OpenAICompatibleProvider)
    assert p_vllm.provider_label == "vllm"

    # Ollama
    p_ollama = get_llm_provider("ollama", api_base="http://localhost:11434")
    assert isinstance(p_ollama, OllamaProvider)

    # Gemini
    p_gemini = get_llm_provider("gemini", api_key="test_gemini_key_12345")
    assert isinstance(p_gemini, GeminiProvider)
    assert p_gemini.provider_label == "gemini"


def test_factory_unsupported_provider_raises_error():
    with pytest.raises(LLMConfigurationError) as exc_info:
        get_llm_provider("unsupported_provider_xyz")
    assert "Unsupported LLM provider" in str(exc_info.value)


def test_openai_missing_api_key_raises_configuration_error():
    with pytest.raises(LLMConfigurationError) as exc_info:
        OpenAICompatibleProvider(api_key="", api_base="https://api.openai.com/v1")
    assert "LLM_API_KEY" in str(exc_info.value)


def test_anthropic_missing_api_key_raises_configuration_error():
    with pytest.raises(LLMConfigurationError) as exc_info:
        AnthropicProvider(api_key="")
    assert "LLM_API_KEY" in str(exc_info.value)


def test_gemini_missing_api_key_raises_configuration_error():
    with pytest.raises(LLMConfigurationError) as exc_info:
        GeminiProvider(api_key="")
    assert "GEMINI_API_KEY" in str(exc_info.value)
