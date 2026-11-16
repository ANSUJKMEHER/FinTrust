import logging
import os
from typing import Optional

from app.core.config import settings
from app.core.exceptions import LLMConfigurationError
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import BaseLLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model_name: Optional[str] = None,
    **kwargs
) -> BaseLLMProvider:
    """Factory creating configured LLM provider instances.
    
    Adheres strictly to the rule: Never silently switch to a mock provider in production.
    If an external provider is specified but misconfigured, raises LLMConfigurationError.
    """
    selected = (provider_name or settings.LLM_PROVIDER or "mock").lower().strip()

    # Defense-in-depth: Refuse mock provider in production environment regardless of invocation path
    if settings.ENVIRONMENT.lower() in ("production", "prod"):
        if selected in ("mock", "fake", "dummy", "test", "none", ""):
            raise LLMConfigurationError(
                "Mock LLM provider is strictly prohibited in production environment."
            )

    if selected == "openai":
        resolved_key = api_key or settings.LLM_API_KEY
        if not resolved_key:
            raise LLMConfigurationError("OpenAI provider requires a valid LLM_API_KEY.")
        return OpenAICompatibleProvider(
            api_key=resolved_key,
            api_base=api_base,
            model_name=model_name,
            provider_label="openai",
            **kwargs
        )
    elif selected == "vllm":
        return OpenAICompatibleProvider(
            api_key=api_key or "EMPTY",
            api_base=api_base or settings.LLM_API_BASE or "http://localhost:8000/v1",
            model_name=model_name,
            provider_label="vllm",
            **kwargs
        )
    elif selected == "anthropic":
        resolved_key = api_key or settings.LLM_API_KEY
        if not resolved_key:
            raise LLMConfigurationError("Anthropic provider requires a valid LLM_API_KEY.")
        return AnthropicProvider(
            api_key=resolved_key,
            api_base=api_base,
            model_name=model_name,
            **kwargs
        )
    elif selected == "ollama":
        return OllamaProvider(
            api_base=api_base,
            model_name=model_name,
            **kwargs
        )
    elif selected in ("gemini", "google"):
        resolved_key = api_key or getattr(settings, "GEMINI_API_KEY", None) or settings.LLM_API_KEY or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise LLMConfigurationError("Gemini provider requires a valid GEMINI_API_KEY or LLM_API_KEY.")
        return GeminiProvider(
            api_key=resolved_key,
            api_base=api_base,
            model_name=model_name,
            **kwargs
        )
    elif selected == "mock":
        return MockLLMProvider(**kwargs)
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{selected}'. "
            f"Supported providers are: 'gemini', 'openai', 'anthropic', 'ollama', 'vllm', 'mock'."
        )
