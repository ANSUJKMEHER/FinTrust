"""
FinTrust RAG - Agentic Workflow Orchestrator
Coordinates graph execution, state persistence, audit tracing, and human approval workflows.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal
import time
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy import select
from langgraph.checkpoint.memory import MemorySaver

from app.agentic.state import AgenticWorkflowState
from app.agentic.workflow import build_agentic_workflow_graph
from app.agentic.mcp.context import mcp_execution_context
from app.core.config import settings
from app.services.cost_service import cost_service
from app.db.models.user import User
from app.db.models.workflow import (
    AgenticWorkflow,
    AgenticExecutionTrace,
    WorkflowTaskType,
    WorkflowStatus,
    ApprovalStatus,
)

logger = logging.getLogger(__name__)


class AgenticOrchestrator:
    """
    High-level orchestrator managing LangGraph multi-agent lifecycles,
    database persistence, trace auditing, and human-in-the-loop approvals.
    """

    def __init__(self, db: Session):
        self.db = db
        # Shared in-memory checkpointer across invocations within the process
        self.checkpointer = MemorySaver()
        self.graph = build_agentic_workflow_graph(checkpointer=self.checkpointer)

    def _sanitize_state_for_persistence(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Strip non-serializable objects (db_session, user) before persisting state snapshot."""
        safe_state = {}
        for k, v in state.items():
            if k in ["db_session", "user"]:
                continue
            try:
                # Test json serializability
                json.dumps(v, default=str)
                safe_state[k] = v
            except Exception:
                safe_state[k] = str(v)
        return safe_state

    def execute_workflow(
        self,
        task_type: WorkflowTaskType,
        query: str,
        user: User,
        max_iterations: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgenticWorkflow:
        """
        Instantiate, persist, and run a multi-agent workflow to completion or pause.
        """
        start_time = time.time()
        workflow_id = uuid4()
        
        # 1. Create DB record
        workflow = AgenticWorkflow(
            id=workflow_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            task_type=task_type,
            workflow_status=WorkflowStatus.EXECUTING,
            approval_status=ApprovalStatus.NOT_REQUIRED,
            query=query,
            max_iterations=max_iterations,
            iteration_count=0,
            total_tokens_used=0,
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)

        # 2. Build initial typed state
        user_roles = [getattr(r, "id", getattr(r, "name", str(r))) for r in user.roles] if hasattr(user, "roles") and user.roles else []
        user_groups = [getattr(g, "id", getattr(g, "name", str(g))) for g in user.groups] if hasattr(user, "groups") and user.groups else []
        
        initial_state: AgenticWorkflowState = {
            "workflow_id": str(workflow.id),
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "user_roles": user_roles,
            "user_groups": user_groups,
            "user_query": query,
            "task_type": task_type.value,
            "workflow_phase": "PLANNING",
            "metadata": metadata or {},
            "execution_plan": [],
            "selected_agents": [],
            "evidence_registry": {},
            "research_findings": [],
            "compliance_findings": [],
            "comparison_findings": [],
            "identified_conflicts": [],
            "verification_results": [],
            "human_approval_status": "NOT_REQUIRED",
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "execution_trace": [],
            "final_report": None,
            "total_tokens_used": 0,
        }

        # 3. Invoke compiled graph with thread_id for checkpointing
        thread_id = str(workflow.id)
        config = {"configurable": {"thread_id": thread_id}}

        try:
            with mcp_execution_context(user=user, db_session=self.db, workflow_id=workflow.id):
                final_state = self.graph.invoke(initial_state, config=config)

            # 4. Sync traces and outcome
            latency_ms = int((time.time() - start_time) * 1000)
            self._sync_workflow_output(workflow, final_state, latency_ms)

        except Exception as e:
            logger.error(f"Error executing agentic workflow {workflow.id}: {e}", exc_info=True)
            workflow.workflow_status = WorkflowStatus.FAILED
            workflow.error_message = str(e)
            self.db.commit()
            raise e

        return workflow

    def _sync_workflow_output(
        self,
        workflow: AgenticWorkflow,
        state: Dict[str, Any],
        latency_ms: int,
    ) -> None:
        """Persist traces and update workflow state after graph run."""
        traces = state.get("execution_trace", [])
        
        # Persist new traces
        existing_step_numbers = set(
            self.db.execute(
                select(AgenticExecutionTrace.step_number).where(
                    AgenticExecutionTrace.workflow_id == workflow.id
                )
            ).scalars().all()
        )

        for t in traces:
            step_num = t.get("step_number", 1)
            if step_num not in existing_step_numbers:
                p_tokens = t.get("prompt_tokens", 0)
                c_tokens = t.get("completion_tokens", 0)
                cached_tokens = t.get("cached_prompt_tokens", 0)
                prov = t.get("llm_provider", settings.LLM_PROVIDER)
                mod = t.get("llm_model", settings.LLM_MODEL_NAME)

                cost_info = cost_service.calculate_cost(
                    provider=prov,
                    model=mod,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    cached_prompt_tokens=cached_tokens
                )

                trace_obj = AgenticExecutionTrace(
                    workflow_id=workflow.id,
                    step_number=step_num,
                    agent_name=t.get("agent_name", "unknown"),
                    action=t.get("action", "EXECUTE"),
                    inputs_redacted=t.get("input_payload", {}),
                    outputs_redacted=t.get("output_payload", {}),
                    status="COMPLETED",
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    cached_prompt_tokens=cached_tokens,
                    llm_provider=prov,
                    llm_model=mod,
                    pricing_version=cost_info.pricing_version,
                    input_cost=cost_info.input_cost,
                    output_cost=cost_info.output_cost,
                    total_cost=cost_info.total_cost,
                )
                self.db.add(trace_obj)
                existing_step_numbers.add(step_num)

        # Flush new traces so aggregation query includes them
        self.db.flush()

        # Update Workflow metadata and aggregate total cost across all traces (prevent double counting)
        workflow_traces = self.db.execute(
            select(AgenticExecutionTrace).where(
                AgenticExecutionTrace.workflow_id == workflow.id
            )
        ).scalars().all()

        total_cost = sum((t.total_cost for t in workflow_traces), start=Decimal("0.000000"))

        workflow.execution_plan = state.get("execution_plan", [])
        workflow.selected_agents = state.get("selected_agents", [])
        workflow.iteration_count = state.get("iteration_count", 0)
        workflow.total_tokens_used = state.get("total_tokens_used", 0)
        workflow.total_estimated_cost = total_cost
        workflow.llm_provider = settings.LLM_PROVIDER
        workflow.llm_model = settings.LLM_MODEL_NAME
        workflow.execution_latency_ms = latency_ms
        workflow.final_report = state.get("final_report")
        workflow.state_snapshot = self._sanitize_state_for_persistence(state)

        # Handle status
        approval_status_str = state.get("human_approval_status", "NOT_REQUIRED")
        if approval_status_str == "PENDING_APPROVAL":
            workflow.workflow_status = WorkflowStatus.PENDING_APPROVAL
            workflow.approval_status = ApprovalStatus.PENDING_APPROVAL
        elif state.get("final_report"):
            workflow.workflow_status = WorkflowStatus.COMPLETED
            if workflow.approval_status == ApprovalStatus.PENDING_APPROVAL:
                workflow.approval_status = ApprovalStatus.APPROVED
        else:
            workflow.workflow_status = WorkflowStatus.EXECUTING

        self.db.commit()
        self.db.refresh(workflow)

    def handle_approval(
        self,
        workflow_id: UUID,
        user: User,
        action: str,
        feedback: Optional[str] = None,
    ) -> AgenticWorkflow:
        """
        Handle human approval (APPROVED, REJECTED, NEEDS_REVISION).
        Resumes graph execution if approved.
        """
        workflow = self.db.execute(
            select(AgenticWorkflow).where(
                AgenticWorkflow.id == workflow_id,
                AgenticWorkflow.tenant_id == user.tenant_id,
            )
        ).scalar_one_or_none()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found.")

        if workflow.workflow_status != WorkflowStatus.PENDING_APPROVAL:
            raise ValueError(f"Workflow is in state {workflow.workflow_status.value}, not PENDING_APPROVAL.")

        action_upper = action.upper()
        now = datetime.now(timezone.utc)
        workflow.reviewer_id = user.id
        workflow.reviewer_comments = feedback
        workflow.reviewed_at = now

        thread_id = str(workflow.id)
        config = {"configurable": {"thread_id": thread_id}}

        if action_upper == "APPROVED":
            workflow.approval_status = ApprovalStatus.APPROVED
            workflow.workflow_status = WorkflowStatus.EXECUTING

            # Update state in graph checkpointer and resume
            # Reconstruct state from snapshot
            saved_state = dict(workflow.state_snapshot or {})
            saved_state["human_approval_status"] = "APPROVED"

            # Trace the approval
            traces = saved_state.get("execution_trace", [])
            traces.append({
                "step_number": len(traces) + 1,
                "agent_name": "human_reviewer",
                "action": "APPROVAL_GRANTED",
                "decision": feedback or "Approved by compliance officer.",
                "input_payload": {"reviewer_id": str(user.id)},
                "output_payload": {"status": "APPROVED"},
            })
            saved_state["execution_trace"] = traces

            start_time = time.time()
            with mcp_execution_context(user=user, db_session=self.db, workflow_id=workflow.id):
                final_state = self.graph.invoke(saved_state, config=config)

            latency_ms = int((time.time() - start_time) * 1000)
            self._sync_workflow_output(workflow, final_state, latency_ms)

        elif action_upper == "REJECTED":
            workflow.approval_status = ApprovalStatus.REJECTED
            workflow.workflow_status = WorkflowStatus.COMPLETED

            # Add trace
            trace_obj = AgenticExecutionTrace(
                workflow_id=workflow.id,
                step_number=self.db.query(AgenticExecutionTrace).filter(
                    AgenticExecutionTrace.workflow_id == workflow.id
                ).count() + 1,
                agent_name="human_reviewer",
                action="APPROVAL_REJECTED",
                inputs_redacted={"reviewer_id": str(user.id), "comments": feedback},
                outputs_redacted={"status": "REJECTED"},
                status="COMPLETED",
            )
            self.db.add(trace_obj)
            self.db.commit()
            self.db.refresh(workflow)

        elif action_upper == "NEEDS_REVISION":
            workflow.approval_status = ApprovalStatus.NEEDS_REVISION
            workflow.workflow_status = WorkflowStatus.EXECUTING

            saved_state = dict(workflow.state_snapshot or {})
            saved_state["human_approval_status"] = "NEEDS_REVISION"
            saved_state["iteration_count"] = 0  # Allow another loop

            traces = saved_state.get("execution_trace", [])
            traces.append({
                "step_number": len(traces) + 1,
                "agent_name": "human_reviewer",
                "action": "REVISION_REQUESTED",
                "decision": feedback or "Revision requested by reviewer.",
                "input_payload": {"reviewer_id": str(user.id)},
                "output_payload": {"status": "NEEDS_REVISION"},
            })
            saved_state["execution_trace"] = traces

            start_time = time.time()
            with mcp_execution_context(user=user, db_session=self.db, workflow_id=workflow.id):
                final_state = self.graph.invoke(saved_state, config=config)

            latency_ms = int((time.time() - start_time) * 1000)
            self._sync_workflow_output(workflow, final_state, latency_ms)

        else:
            raise ValueError(f"Invalid approval action: {action}. Must be APPROVED, REJECTED, or NEEDS_REVISION.")

        return workflow

    def get_workflow(self, workflow_id: UUID, user: User) -> Optional[AgenticWorkflow]:
        """Retrieve workflow ensuring strict tenant isolation."""
        return self.db.execute(
            select(AgenticWorkflow).where(
                AgenticWorkflow.id == workflow_id,
                AgenticWorkflow.tenant_id == user.tenant_id,
            )
        ).scalar_one_or_none()

    def get_workflow_traces(self, workflow_id: UUID, user: User) -> List[AgenticExecutionTrace]:
        """Retrieve execution traces for workflow ensuring tenant isolation."""
        # Check workflow tenant
        wf = self.get_workflow(workflow_id, user)
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found or access denied.")

        return self.db.execute(
            select(AgenticExecutionTrace)
            .where(AgenticExecutionTrace.workflow_id == workflow_id)
            .order_by(AgenticExecutionTrace.step_number.asc())
        ).scalars().all()

    def list_workflows(
        self,
        user: User,
        task_type: Optional[WorkflowTaskType] = None,
        workflow_status: Optional[WorkflowStatus] = None,
        approval_status: Optional[ApprovalStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AgenticWorkflow]:
        """List workflows ensuring strict tenant isolation."""
        stmt = select(AgenticWorkflow).where(AgenticWorkflow.tenant_id == user.tenant_id)
        if task_type:
            stmt = stmt.where(AgenticWorkflow.task_type == task_type)
        if workflow_status:
            stmt = stmt.where(AgenticWorkflow.workflow_status == workflow_status)
        if approval_status:
            stmt = stmt.where(AgenticWorkflow.approval_status == approval_status)
        stmt = stmt.order_by(AgenticWorkflow.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
