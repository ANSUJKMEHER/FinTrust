from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, List, Optional


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    role: MessageRole
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: Optional[str] = "stop"
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseLLMProvider(ABC):
    """Abstract interface for all FinTrust LLM providers."""

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generates a completion from an ordered list of chat messages."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Performs a provider connectivity and configuration health check."""
        pass
