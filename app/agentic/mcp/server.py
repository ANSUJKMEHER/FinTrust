"""
FinTrust RAG - Dedicated MCP Tool Server
Exposes official Model Context Protocol (MCP) server endpoints and tool registry.
"""

from typing import Optional, List, Dict, Any
from mcp.server.mcpserver import MCPServer
from app.agentic.mcp import tools as mcp_tools

# Create official MCPServer instance
fintrust_mcp_server = MCPServer("fintrust-rag-agentic-server")

# ---------------------------------------------------------------------------
# Register Research Tools
# ---------------------------------------------------------------------------

@fintrust_mcp_server.tool()
def search_documents(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Execute hybrid search over documents within the authenticated tenant boundary."""
    return mcp_tools.search_documents(query=query, top_k=top_k, filters=filters)


@fintrust_mcp_server.tool()
def hybrid_search(
    query: str,
    top_k: int = 5,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5
) -> List[Dict[str, Any]]:
    """Perform hybrid vector + full-text search with customizable rank weights."""
    return mcp_tools.hybrid_search(
        query=query, top_k=top_k, dense_weight=dense_weight, sparse_weight=sparse_weight
    )


@fintrust_mcp_server.tool()
def dense_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Perform dense semantic vector retrieval via pgvector embeddings."""
    return mcp_tools.dense_search(query=query, top_k=top_k)


@fintrust_mcp_server.tool()
def sparse_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Perform sparse BM25 / PostgreSQL Full-Text Search over indexed document chunks."""
    return mcp_tools.sparse_search(query=query, top_k=top_k)


@fintrust_mcp_server.tool()
def get_document_metadata(document_id: str) -> Dict[str, Any]:
    """Retrieve document metadata, verifying tenant isolation and document-level permissions."""
    return mcp_tools.get_document_metadata(document_id=document_id)


@fintrust_mcp_server.tool()
def get_document_content(document_id: str) -> str:
    """Retrieve full reconstructed text content of a document from its ordered chunks."""
    return mcp_tools.get_document_content(document_id=document_id)


@fintrust_mcp_server.tool()
def get_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """Retrieve all chunks with metadata for an authorized document."""
    return mcp_tools.get_document_chunks(document_id=document_id)


# ---------------------------------------------------------------------------
# Register Intelligence Tools
# ---------------------------------------------------------------------------

@fintrust_mcp_server.tool()
def summarize_document(document_id: str, focus: Optional[str] = None) -> Dict[str, Any]:
    """Generate an executive summary, key points, and compliance highlights for a document."""
    return mcp_tools.summarize_document(document_id=document_id, focus=focus)


@fintrust_mcp_server.tool()
def compare_documents(
    doc_a_id: str,
    doc_b_id: str,
    comparison_dimension: Optional[str] = None
) -> Dict[str, Any]:
    """Perform section-by-section comparison, change detection, and policy drift analysis."""
    return mcp_tools.compare_documents(
        doc_a_id=doc_a_id, doc_b_id=doc_b_id, comparison_dimension=comparison_dimension
    )


@fintrust_mcp_server.tool()
def extract_regulatory_obligations(
    document_id: str,
    regulation_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Extract statutory and regulatory obligations from a document using mandatory modal verbs."""
    return mcp_tools.extract_regulatory_obligations(
        document_id=document_id, regulation_type=regulation_type
    )


@fintrust_mcp_server.tool()
def identify_financial_thresholds(document_id: str) -> List[Dict[str, Any]]:
    """Identify and extract financial thresholds, currency figures, deadlines, and percentages."""
    return mcp_tools.identify_financial_thresholds(document_id=document_id)


# ---------------------------------------------------------------------------
# Register Verification Tools
# ---------------------------------------------------------------------------

@fintrust_mcp_server.tool()
def verify_claim(claim_text: str, evidence_ids: List[str]) -> Dict[str, Any]:
    """Verify a factual claim against provided evidence chunks."""
    return mcp_tools.verify_claim(claim_text=claim_text, evidence_ids=evidence_ids)


@fintrust_mcp_server.tool()
def verify_citation(citation: str, source_text: str) -> Dict[str, Any]:
    """Verify whether a citation reference accurately matches the source text."""
    return mcp_tools.verify_citation(citation=citation, source_text=source_text)


@fintrust_mcp_server.tool()
def check_numeric_claim(
    claimed_value: str, claimed_metric: str, evidence_id: str
) -> Dict[str, Any]:
    """Verify numeric claim against a specific evidence chunk."""
    return mcp_tools.check_numeric_claim(
        claimed_value=claimed_value, claimed_metric=claimed_metric, evidence_id=evidence_id
    )


@fintrust_mcp_server.tool()
def check_regulatory_reference(statute_code: str, evidence_id: str) -> Dict[str, Any]:
    """Verify whether a statute or regulatory citation actually appears in the referenced chunk."""
    return mcp_tools.check_regulatory_reference(statute_code=statute_code, evidence_id=evidence_id)


@fintrust_mcp_server.tool()
def inspect_evidence_support(finding_id: str) -> Dict[str, Any]:
    """Inspect the audit trail and evidence support for a finding or evidence chunk."""
    return mcp_tools.inspect_evidence_support(finding_id=finding_id)


# ---------------------------------------------------------------------------
# Register Workflow Tools
# ---------------------------------------------------------------------------

@fintrust_mcp_server.tool()
def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """Retrieve workflow execution state, steps, and human approval status."""
    return mcp_tools.get_workflow_status(workflow_id=workflow_id)


@fintrust_mcp_server.tool()
def request_human_approval(
    workflow_id: str,
    reason: str,
    affected_agents: List[str],
    conflict_summary: Optional[str] = None
) -> Dict[str, Any]:
    """Halt autonomous workflow execution and request explicit human approval."""
    return mcp_tools.request_human_approval(
        workflow_id=workflow_id,
        reason=reason,
        affected_agents=affected_agents,
        conflict_summary=conflict_summary,
    )


@fintrust_mcp_server.tool()
def record_agent_finding(
    workflow_id: str,
    agent_name: str,
    finding_type: str,
    finding_content: Dict[str, Any]
) -> Dict[str, Any]:
    """Record an execution trace and finding for auditability and explainability."""
    return mcp_tools.record_agent_finding(
        workflow_id=workflow_id,
        agent_name=agent_name,
        finding_type=finding_type,
        finding_content=finding_content,
    )
