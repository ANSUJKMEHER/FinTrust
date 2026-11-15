"""
Base agent definition and execution tracing utilities for Phase 5 Multi-Agent System.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import re
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.agentic.state import AgenticWorkflowState, ExecutionTraceItem
from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for specialized agents in FinTrust RAG."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None,
        llm_provider: Optional[BaseLLMProvider] = None
    ) -> Dict[str, Any]:
        """Executes agent-specific task logic and returns state delta."""
        pass

    @staticmethod
    def redact_sensitive_data(data: Any) -> Any:
        """Redacts credentials, tokens, and raw secrets from audit logs and execution traces."""
        if isinstance(data, dict):
            redacted = {}
            for k, v in data.items():
                k_lower = str(k).lower()
                if any(sec in k_lower for sec in ["token", "password", "secret", "key", "authorization"]):
                    redacted[k] = "[REDACTED_CREDENTIAL]"
                else:
                    redacted[k] = BaseAgent.redact_sensitive_data(v)
            return redacted
        elif isinstance(data, list):
            return [BaseAgent.redact_sensitive_data(item) for item in data]
        elif isinstance(data, str):
            # Redact bearer tokens or hex secrets if present
            redacted_str = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer [REDACTED_JWT]', data, flags=re.IGNORECASE)
            return redacted_str
        return data

    def record_trace(
        self,
        state: AgenticWorkflowState,
        action: str,
        inputs: Optional[Dict[str, Any]],
        outputs: Optional[Dict[str, Any]],
        status: str = "SUCCESS",
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error_details: Optional[str] = None
    ) -> ExecutionTraceItem:
        """Appends a sanitized trace record to the shared execution trace list."""
        trace_list = state.setdefault("execution_trace", [])
        step_number = len(trace_list) + 1

        trace_item: ExecutionTraceItem = {
            "step_number": step_number,
            "agent_name": self.name,
            "action": action,
            "inputs_redacted": self.redact_sensitive_data(inputs) if inputs else None,
            "outputs_redacted": self.redact_sensitive_data(outputs) if outputs else None,
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "error_details": error_details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        trace_list.append(trace_item)

        # Update token usage
        token_usage = state.setdefault("token_usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        token_usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0) + prompt_tokens
        token_usage["completion_tokens"] = token_usage.get("completion_tokens", 0) + completion_tokens
        token_usage["total_tokens"] = token_usage.get("total_tokens", 0) + prompt_tokens + completion_tokens

        logger.info(
            f"[AGENT_TRACE] step={step_number} agent={self.name} action={action} "
            f"status={status} latency={latency_ms:.1f}ms tokens={prompt_tokens + completion_tokens}"
        )
        return trace_item
