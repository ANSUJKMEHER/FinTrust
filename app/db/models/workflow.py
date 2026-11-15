"""
Database models for Phase 5 Agentic Workflows, Human Approval, and Execution Tracing.
"""
from datetime import datetime, timezone
import enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, GUID

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.user import User


class WorkflowTaskType(str, enum.Enum):
    REGULATORY_COMPLIANCE = "REGULATORY_COMPLIANCE"
    POLICY_COMPARISON = "POLICY_COMPARISON"
    RISK_INVESTIGATION = "RISK_INVESTIGATION"
    OBLIGATION_EXTRACTION = "OBLIGATION_EXTRACTION"
    GENERAL_RESEARCH = "GENERAL_RESEARCH"


class WorkflowStatus(str, enum.Enum):
    INITIALIZED = "INITIALIZED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, enum.Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"


class AgenticWorkflow(Base):
    """Stores full agentic workflow instances, intermediate state checkpoints, and final reports."""
    __tablename__ = "agentic_workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    task_type: Mapped[WorkflowTaskType] = mapped_column(
        Enum(WorkflowTaskType, native_enum=False, length=50),
        default=WorkflowTaskType.GENERAL_RESEARCH,
        nullable=False,
        index=True
    )
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, native_enum=False, length=50),
        default=WorkflowStatus.INITIALIZED,
        nullable=False,
        index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    execution_plan: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    selected_agents: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    state_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    final_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Human-in-the-loop approval fields
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, native_enum=False, length=50),
        default=ApprovalStatus.NOT_REQUIRED,
        nullable=False,
        index=True
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    reviewer_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Iteration & token accounting
    iteration_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewer_id])
    traces: Mapped[List["AgenticExecutionTrace"]] = relationship(
        "AgenticExecutionTrace",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="AgenticExecutionTrace.step_number.asc()"
    )

    __table_args__ = (
        Index("idx_agentic_wf_tenant_status", "tenant_id", "workflow_status"),
        Index("idx_agentic_wf_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AgenticWorkflow id={self.id} status={self.workflow_status} type={self.task_type}>"


class AgenticExecutionTrace(Base):
    """Detailed audit trace of individual agent execution steps, tool invocations, and reasoning."""
    __tablename__ = "agentic_execution_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("agentic_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    inputs_redacted: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    outputs_redacted: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    workflow: Mapped["AgenticWorkflow"] = relationship("AgenticWorkflow", back_populates="traces")

    __table_args__ = (
        Index("idx_trace_wf_step", "workflow_id", "step_number"),
    )

    def __repr__(self) -> str:
        return f"<AgenticExecutionTrace id={self.id} wf={self.workflow_id} step={self.step_number} agent={self.agent_name}>"
