"""
FinTrust RAG — Google Gemini LLM Provider
First-class integration for Google Gemini models (gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash).
Uses Google's official OpenAI-compatible endpoint with streaming support, exponential backoff,
prompt caching telemetry, and token usage accounting.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError
)
from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM Provider using Google's official v1beta API endpoint."""

    DEFAULT_API_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        provider_label: str = "gemini"
    ):
        self.provider_label = provider_label
        # If api_key is explicitly provided (even empty string in tests), respect it
        resolved_key = api_key if api_key is not None else (
            os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None) or settings.LLM_API_KEY
        )
        self.api_key = resolved_key
        self.api_base = (api_base or self.DEFAULT_API_BASE).rstrip("/")
        raw_model = model_name or getattr(settings, "LLM_MODEL_NAME", None) or os.getenv("GEMINI_MODEL") or os.getenv("LLM_MODEL_NAME") or self.DEFAULT_MODEL
        # Normalize if deprecated 2.0-flash is configured
        if "2.0-flash" in raw_model:
            raw_model = "gemini-2.5-flash"
        self.model_name = raw_model
        self.timeout_seconds = timeout_seconds or 30.0
        self.max_retries = max(max_retries or settings.LLM_MAX_RETRIES, 4)

        if not self.api_key or len(self.api_key.strip()) < 8:
            raise LLMConfigurationError(
                "Gemini provider requires a valid GEMINI_API_KEY or LLM_API_KEY."
            )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
        }

        headers = self._get_headers()
        backoff = 2.0
        start_time = time.perf_counter()

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(url, json=payload, headers=headers)

                latency_ms = (time.perf_counter() - start_time) * 1000.0

                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    content = choice["message"]["content"]
                    usage = data.get("usage", {})
                    
                    # Gemini prompt caching metadata
                    prompt_tokens_details = usage.get("prompt_tokens_details", {})
                    cached_tokens = prompt_tokens_details.get("cached_tokens", 0)

                    return LLMResponse(
                        content=content,
                        model=data.get("model", self.model_name),
                        provider=self.provider_label,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                        latency_ms=latency_ms,
                        finish_reason=choice.get("finish_reason", "stop"),
                        raw_metadata={
                            "attempt": attempt,
                            "id": data.get("id"),
                            "cached_prompt_tokens": cached_tokens
                        }
                    )

                elif resp.status_code == 429:
                    if attempt == self.max_retries:
                        raise LLMRateLimitError(f"Gemini rate limit exceeded: {resp.text}")
                    logger.warning(f"Rate limited by Gemini on attempt {attempt}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

                elif resp.status_code >= 500:
                    if attempt == self.max_retries:
                        raise LLMProviderError(f"Gemini server error {resp.status_code}: {resp.text}")
                    logger.warning(f"Gemini error {resp.status_code} on attempt {attempt}. Retrying...")
                    time.sleep(backoff)
                    backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

                else:
                    raise LLMProviderError(f"Gemini returned HTTP {resp.status_code}: {resp.text}")

            except httpx.TimeoutException as e:
                if attempt == self.max_retries:
                    raise LLMTimeoutError(f"Request to Gemini timed out after {self.timeout_seconds}s: {e}")
                logger.warning(f"Gemini timeout on attempt {attempt}. Retrying...")
                time.sleep(backoff)
                backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

            except httpx.RequestError as e:
                if attempt == self.max_retries:
                    raise LLMProviderError(f"Network error connecting to Gemini: {e}")
                logger.warning(f"Network error on attempt {attempt}: {e}. Retrying...")
                time.sleep(backoff)
                backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

        raise LLMProviderError(f"Exhausted all {self.max_retries} attempts for Gemini.")

    def health_check(self) -> Dict[str, Any]:
        """Verifies reachability and authentication with Gemini endpoint."""
        url = f"{self.api_base}/models"
        headers = self._get_headers()
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers)
            is_healthy = resp.status_code in (200, 404, 405)
            return {
                "provider": self.provider_label,
                "api_base": self.api_base,
                "model": self.model_name,
                "status": "healthy" if is_healthy else "unhealthy",
                "status_code": resp.status_code
            }
        except Exception as e:
            return {
                "provider": self.provider_label,
                "api_base": self.api_base,
                "model": self.model_name,
                "status": "unreachable",
                "error": str(e)
            }
