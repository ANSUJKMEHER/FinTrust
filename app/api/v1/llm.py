from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.llm.factory import get_llm_provider

router = APIRouter(prefix="/llm", tags=["LLM Provider Management"])


@router.get("/health")
def llm_health_check(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Inspects active LLM provider configuration, connection health, and model parameters."""
    provider = get_llm_provider()
    check = provider.health_check()
    return {
        "active_provider": settings.LLM_PROVIDER,
        "configured_model": settings.LLM_MODEL_NAME,
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": settings.LLM_MAX_TOKENS,
        "timeout_seconds": settings.LLM_TIMEOUT_SECONDS,
        "health": check
    }
