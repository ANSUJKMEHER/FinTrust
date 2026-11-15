"""
FinTrust RAG - MCP Execution Context
Thread-local / ContextVar execution context ensuring multi-tenant isolation,
user identity preservation, and deterministic permission enforcement.
"""

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, List, Generator
from uuid import UUID
from sqlalchemy.orm import Session

from app.db.models.user import User


@dataclass
class MCPExecutionContext:
    """Secure execution context bound to an authenticated session."""
    user: User
    db_session: Session
    tenant_id: UUID
    user_id: UUID
    user_roles: List[str] = field(default_factory=list)
    user_groups: List[str] = field(default_factory=list)
    workflow_id: Optional[UUID] = None


_current_mcp_context: ContextVar[Optional[MCPExecutionContext]] = ContextVar(
    "current_mcp_context", default=None
)


def get_current_mcp_context() -> MCPExecutionContext:
    """
    Retrieve the current authenticated MCP execution context.
    Raises PermissionError if called outside an authenticated context.
    """
    ctx = _current_mcp_context.get()
    if ctx is None:
        raise PermissionError(
            "Access denied: No active authenticated MCP execution context. "
            "MCP tools cannot be called without verified user and tenant credentials."
        )
    return ctx


@contextmanager
def mcp_execution_context(
    user: User,
    db_session: Session,
    workflow_id: Optional[UUID] = None,
) -> Generator[MCPExecutionContext, None, None]:
    """
    Context manager to safely bind an authenticated user and database session
    to the active thread/coroutine context.
    """
    roles = [getattr(r, "id", getattr(r, "name", str(r))) for r in user.roles] if hasattr(user, "roles") and user.roles else []
    groups = [getattr(g, "id", getattr(g, "name", str(g))) for g in user.groups] if hasattr(user, "groups") and user.groups else []
    
    ctx = MCPExecutionContext(
        user=user,
        db_session=db_session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_roles=roles,
        user_groups=groups,
        workflow_id=workflow_id,
    )
    token = _current_mcp_context.set(ctx)
    try:
        yield ctx
    finally:
        _current_mcp_context.reset(token)
