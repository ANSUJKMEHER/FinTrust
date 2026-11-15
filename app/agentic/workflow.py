"""
FinTrust RAG - LangGraph Multi-Agent Workflow
Stateful supervisor-orchestrated graph coordinates specialized worker agents,
evidence verification, conflict resolution, and human approval checkpoints.
"""

from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agentic.state import AgenticWorkflowState
from app.agentic.agents.supervisor import SupervisorAgent
from app.agentic.agents.research import ResearchAgent
from app.agentic.agents.compliance import ComplianceAnalysisAgent
from app.agentic.agents.doc_intelligence import DocumentIntelligenceAgent
from app.agentic.agents.verification import VerificationAgent
from app.agentic.conflict_resolution import ConflictResolutionEngine


# ---------------------------------------------------------------------------
# Node Functions
# ---------------------------------------------------------------------------

def supervisor_plan_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Supervisor decomposes the inquiry, determines plan, and selects worker agents."""
    supervisor = SupervisorAgent()
    return supervisor.plan_task(state)


def research_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Research worker agent retrieves evidence and populates evidence registry."""
    agent = ResearchAgent()
    return agent.execute(state)


def doc_intelligence_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Document intelligence worker handles summarization and cross-document comparison."""
    agent = DocumentIntelligenceAgent()
    return agent.execute(state)


def compliance_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Compliance worker extracts statutory obligations and financial thresholds."""
    agent = ComplianceAnalysisAgent()
    return agent.execute(state)


def conflict_resolution_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Detects and documents regulatory and threshold conflicts across documents."""
    engine = ConflictResolutionEngine()
    conflicts = engine.detect_conflicts(state)
    trace = state.get("execution_trace", [])
    trace.append({
        "step_number": len(trace) + 1,
        "agent_name": "conflict_resolution",
        "action": "DETECT_CONFLICTS",
        "decision": f"Identified {len(conflicts)} potential conflicts.",
        "input_payload": {"finding_counts": len(state.get("compliance_findings", []))},
        "output_payload": {"conflict_count": len(conflicts)},
    })
    return {
        "identified_conflicts": conflicts,
        "execution_trace": trace,
    }


def verification_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Independent verification agent validates claims, citations, and hallucination risks."""
    agent = VerificationAgent()
    return agent.execute(state)


def supervisor_evaluate_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Supervisor evaluates verification results and evidence sufficiency."""
    supervisor = SupervisorAgent()
    eval_res = supervisor.evaluate_evidence_sufficiency(state)
    return {
        "sufficiency_assessment": eval_res,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def human_approval_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Pause point for human compliance officer review and sign-off."""
    trace = state.get("execution_trace", [])
    trace.append({
        "step_number": len(trace) + 1,
        "agent_name": "supervisor",
        "action": "AWAIT_HUMAN_APPROVAL",
        "decision": "Execution paused awaiting human review of unresolved regulatory conflicts.",
        "input_payload": {"conflicts": state.get("identified_conflicts", [])},
        "output_payload": {"status": "PENDING_APPROVAL"},
    })
    return {
        "human_approval_status": "PENDING_APPROVAL",
        "workflow_phase": "HUMAN_APPROVAL",
        "execution_trace": trace,
    }


def supervisor_report_node(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Supervisor synthesizes the comprehensive 14-section compliance report."""
    supervisor = SupervisorAgent()
    report_output = supervisor.generate_final_report(state)
    report_dict = report_output.get("final_report") if isinstance(report_output, dict) and "final_report" in report_output else report_output
    return {
        "final_report": report_dict,
        "workflow_phase": "COMPLETED",
    }


# ---------------------------------------------------------------------------
# Conditional Routing Functions
# ---------------------------------------------------------------------------

def route_after_planning(state: AgenticWorkflowState) -> Literal["research_node", "doc_intelligence_node", "compliance_node", "verification_node"]:
    """Route from supervisor planning to the first selected worker agent."""
    selected = state.get("selected_agents", [])
    if "research" in selected:
        return "research_node"
    if "doc_intelligence" in selected:
        return "doc_intelligence_node"
    if "compliance" in selected:
        return "compliance_node"
    return "verification_node"


def route_after_research(state: AgenticWorkflowState) -> Literal["doc_intelligence_node", "compliance_node", "conflict_resolution_node"]:
    """Route from research agent to next worker or conflict resolution."""
    selected = state.get("selected_agents", [])
    if "doc_intelligence" in selected:
        return "doc_intelligence_node"
    if "compliance" in selected:
        return "compliance_node"
    return "conflict_resolution_node"


def route_after_doc_intelligence(state: AgenticWorkflowState) -> Literal["compliance_node", "conflict_resolution_node"]:
    """Route from doc intelligence to compliance or conflict resolution."""
    selected = state.get("selected_agents", [])
    if "compliance" in selected:
        return "compliance_node"
    return "conflict_resolution_node"


def route_after_evaluation(state: AgenticWorkflowState) -> Literal["human_approval_node", "research_node", "supervisor_report_node"]:
    """
    Decide whether to pause for human approval, iterate research, or generate report.
    """
    # 1. Check for human approval requirement
    conflicts = state.get("identified_conflicts", [])
    unresolved_conflicts = [c for c in conflicts if c.get("resolution_strategy") == "ESCALATE_TO_HUMAN"]
    approval_status = state.get("human_approval_status", "NOT_REQUIRED")
    
    if unresolved_conflicts and approval_status not in ["APPROVED", "REJECTED"]:
        return "human_approval_node"
        
    # 2. Check if iterative refinement is required and allowed
    sufficiency = state.get("sufficiency_assessment", {})
    is_sufficient = sufficiency.get("is_sufficient", True)
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if not is_sufficient and iteration < max_iterations:
        return "research_node"
        
    # 3. Otherwise proceed to final synthesis
    return "supervisor_report_node"


# ---------------------------------------------------------------------------
# Graph Construction & Compilation
# ---------------------------------------------------------------------------

def build_agentic_workflow_graph(checkpointer: Any = None):
    """
    Construct and compile the full FinTrust Agentic StateGraph.
    """
    workflow = StateGraph(AgenticWorkflowState)
    
    # Add Nodes
    workflow.add_node("supervisor_plan", supervisor_plan_node)
    workflow.add_node("research_node", research_node)
    workflow.add_node("doc_intelligence_node", doc_intelligence_node)
    workflow.add_node("compliance_node", compliance_node)
    workflow.add_node("conflict_resolution_node", conflict_resolution_node)
    workflow.add_node("verification_node", verification_node)
    workflow.add_node("supervisor_evaluate", supervisor_evaluate_node)
    workflow.add_node("human_approval_node", human_approval_node)
    workflow.add_node("supervisor_report", supervisor_report_node)
    
    # Add Edges
    workflow.add_edge(START, "supervisor_plan")
    
    workflow.add_conditional_edges(
        "supervisor_plan",
        route_after_planning,
        {
            "research_node": "research_node",
            "doc_intelligence_node": "doc_intelligence_node",
            "compliance_node": "compliance_node",
            "verification_node": "verification_node",
        }
    )
    
    workflow.add_conditional_edges(
        "research_node",
        route_after_research,
        {
            "doc_intelligence_node": "doc_intelligence_node",
            "compliance_node": "compliance_node",
            "conflict_resolution_node": "conflict_resolution_node",
        }
    )
    
    workflow.add_conditional_edges(
        "doc_intelligence_node",
        route_after_doc_intelligence,
        {
            "compliance_node": "compliance_node",
            "conflict_resolution_node": "conflict_resolution_node",
        }
    )
    
    workflow.add_edge("compliance_node", "conflict_resolution_node")
    workflow.add_edge("conflict_resolution_node", "verification_node")
    workflow.add_edge("verification_node", "supervisor_evaluate")
    
    workflow.add_conditional_edges(
        "supervisor_evaluate",
        route_after_evaluation,
        {
            "human_approval_node": "human_approval_node",
            "research_node": "research_node",
            "supervisor_report_node": "supervisor_report",
        }
    )
    
    workflow.add_edge("human_approval_node", END)
    workflow.add_edge("supervisor_report", END)
    
    return workflow.compile(checkpointer=checkpointer)
