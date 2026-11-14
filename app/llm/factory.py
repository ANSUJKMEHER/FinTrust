import logging
from typing import Optional

from app.core.config import settings
from app.core.exceptions import LLMConfigurationError
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import BaseLLMProvider
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

    if selected == "openai":
        return OpenAICompatibleProvider(
            api_key=api_key,
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
        return AnthropicProvider(
            api_key=api_key,
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
    elif selected == "mock":
        return MockLLMProvider(**kwargs)
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{selected}'. "
            f"Supported providers are: 'openai', 'anthropic', 'ollama', 'vllm', 'mock'."
        )
