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
from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Provider for OpenAI and OpenAI-compatible endpoints (vLLM, LiteLLM, Ollama-v1, Groq)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        provider_label: str = "openai"
    ):
        self.provider_label = provider_label
        self.api_key = api_key or settings.LLM_API_KEY
        self.api_base = (api_base or settings.LLM_API_BASE or "https://api.openai.com/v1").rstrip("/")
        self.model_name = model_name or settings.LLM_MODEL_NAME
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.LLM_MAX_RETRIES

        # If pointing to standard OpenAI public API, API key is strictly required
        if "api.openai.com" in self.api_base and not self.api_key:
            raise LLMConfigurationError("OpenAI provider requires a valid LLM_API_KEY environment variable.")

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
        backoff = 1.0
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
                    return LLMResponse(
                        content=content,
                        model=data.get("model", self.model_name),
                        provider=self.provider_label,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                        latency_ms=latency_ms,
                        finish_reason=choice.get("finish_reason", "stop"),
                        raw_metadata={"attempt": attempt, "id": data.get("id")}
                    )

                elif resp.status_code == 429:
                    if attempt == self.max_retries:
                        raise LLMRateLimitError(f"{self.provider_label} rate limit exceeded: {resp.text}")
                    logger.warning(f"Rate limited by {self.provider_label} on attempt {attempt}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

                elif resp.status_code >= 500:
                    if attempt == self.max_retries:
                        raise LLMProviderError(f"{self.provider_label} server error {resp.status_code}: {resp.text}")
                    logger.warning(f"Server error {resp.status_code} from {self.provider_label} on attempt {attempt}. Retrying...")
                    time.sleep(backoff)
                    backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

                else:
                    raise LLMProviderError(f"{self.provider_label} returned error HTTP {resp.status_code}: {resp.text}")

            except httpx.TimeoutException as e:
                if attempt == self.max_retries:
                    raise LLMTimeoutError(f"Request to {self.provider_label} timed out after {self.timeout_seconds}s: {e}")
                logger.warning(f"Timeout on attempt {attempt} to {self.provider_label}. Retrying...")
                time.sleep(backoff)
                backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

            except httpx.RequestError as e:
                if attempt == self.max_retries:
                    raise LLMProviderError(f"Network error connecting to {self.provider_label}: {e}")
                logger.warning(f"Network error on attempt {attempt}: {e}. Retrying...")
                time.sleep(backoff)
                backoff *= settings.LLM_RETRY_BACKOFF_FACTOR

        raise LLMProviderError(f"Exhausted all {self.max_retries} attempts for {self.provider_label}.")

    def health_check(self) -> Dict[str, Any]:
        """Verifies reachability and authentication with the model endpoint."""
        url = f"{self.api_base}/models"
        headers = self._get_headers()
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers)
            is_healthy = resp.status_code in (200, 404, 405)  # 404/405 means endpoint reachable even if /models isn't implemented
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
