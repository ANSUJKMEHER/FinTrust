import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.exceptions import LLMProviderError, LLMTimeoutError
from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Provider for local Ollama deployments."""

    def __init__(
        self,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None
    ):
        self.api_base = (api_base or settings.LLM_API_BASE or "http://localhost:11434").rstrip("/")
        self.model_name = model_name or settings.LLM_MODEL_NAME or "llama3.2"
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        url = f"{self.api_base}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
                "num_predict": max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
            }
        }

        start_time = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload)

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("message", {})
                content = msg.get("content", "")
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)

                return LLMResponse(
                    content=content,
                    model=self.model_name,
                    provider="ollama",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=latency_ms,
                    raw_metadata=data
                )
            else:
                raise LLMProviderError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama request timed out after {self.timeout_seconds}s: {e}")
        except httpx.RequestError as e:
            raise LLMProviderError(f"Could not connect to Ollama at {self.api_base}: {e}")

    def health_check(self) -> Dict[str, Any]:
        url = f"{self.api_base}/api/tags"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
            return {
                "provider": "ollama",
                "api_base": self.api_base,
                "model": self.model_name,
                "status": "healthy" if resp.status_code == 200 else "unhealthy"
            }
        except Exception as e:
            return {
                "provider": "ollama",
                "api_base": self.api_base,
                "model": self.model_name,
                "status": "unreachable",
                "error": str(e)
            }
