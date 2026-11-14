import logging
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
from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, MessageRole

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Provider for Anthropic Claude Messages API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.api_base = (api_base or settings.LLM_API_BASE or "https://api.anthropic.com/v1").rstrip("/")
        self.model_name = model_name or settings.LLM_MODEL_NAME or "claude-3-5-sonnet-20241022"
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.LLM_MAX_RETRIES

        if not self.api_key:
            raise LLMConfigurationError("Anthropic provider requires a valid LLM_API_KEY environment variable.")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        url = f"{self.api_base}/messages"

        # Separate system message from conversation history per Anthropic spec
        system_prompt = ""
        chat_messages = []
        for m in messages:
            if m.role == MessageRole.SYSTEM:
                system_prompt += m.content + "\n"
            else:
                chat_messages.append({"role": m.role.value, "content": m.content})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": chat_messages,
            "max_tokens": max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
        }
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()

        headers = self._get_headers()
        backoff = 1.0
        start_time = time.perf_counter()

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(url, json=payload, headers=headers)

                latency_ms = (time.perf_counter() - start_time) * 1000.0

                if resp.status_code == 200:
                    data = resp.json()
                    content_blocks = data.get("content", [])
                    content = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("input_tokens", 0)
                    completion_tokens = usage.get("output_tokens", 0)

                    return LLMResponse(
                        content=content,
                        model=data.get("model", self.model_name),
                        provider="anthropic",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                        latency_ms=latency_ms,
                        finish_reason=data.get("stop_reason", "end_turn"),
                        raw_metadata={"id": data.get("id"), "attempt": attempt}
                    )

                elif resp.status_code == 429:
                    if attempt == self.max_retries:
                        raise LLMRateLimitError(f"Anthropic rate limit exceeded: {resp.text}")
                    time.sleep(backoff)
                    backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

                elif resp.status_code >= 500:
                    if attempt == self.max_retries:
                        raise LLMProviderError(f"Anthropic server error {resp.status_code}: {resp.text}")
                    time.sleep(backoff)
                    backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

                else:
                    raise LLMProviderError(f"Anthropic error HTTP {resp.status_code}: {resp.text}")

            except httpx.TimeoutException as e:
                if attempt == self.max_retries:
                    raise LLMTimeoutError(f"Request to Anthropic timed out after {self.timeout_seconds}s: {e}")
                time.sleep(backoff)
                backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

            except httpx.RequestError as e:
                if attempt == self.max_retries:
                    raise LLMProviderError(f"Network error connecting to Anthropic: {e}")
                time.sleep(backoff)
                backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

        raise LLMProviderError(f"Exhausted all {self.max_retries} attempts for Anthropic.")

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": "anthropic",
            "model": self.model_name,
            "status": "configured" if self.api_key else "missing_api_key"
        }
