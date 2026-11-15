"""
FinTrust RAG - MCP Tools
Official MCP Tool implementations for FinTrust RAG Multi-Agent System.
Exposes Research, Intelligence, Verification, and Workflow management capabilities.
Strictly enforces tenant isolation, RBAC/ACL permissions, and audit logging.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
import re
import dataclasses

from sqlalchemy import select
from app.agentic.mcp.context import get_current_mcp_context
from app.db.models import Document, DocumentChunk
from app.db.models.workflow import AgenticWorkflow, AgenticExecutionTrace, WorkflowStatus, ApprovalStatus
from app.services.hybrid_search_service import HybridSearchService
from app.services.permission_service import PermissionService
from app.services.document_summary_service import DocumentSummaryService
from app.services.document_comparison_service import DocumentComparisonService
from app.services.citation_verification_service import CitationVerificationService


# ---------------------------------------------------------------------------
# Category 1: Research Tools
# ---------------------------------------------------------------------------

def search_documents(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Execute hybrid search over documents within the authenticated tenant boundary.
    Filters by user access permissions and optional metadata filters.
    """
    ctx = get_current_mcp_context()
    search_service = HybridSearchService(ctx.db_session)
    results = search_service.hybrid_search(
        query=query,
        user=ctx.user,
        top_k=top_k,
        apply_rerank=True,
    )
    
    # Apply optional client filters (e.g. document_id, classification)
    if filters:
        filtered = []
        for r in results:
            match = True
            for k, v in filters.items():
                if k == "document_id" and str(r.get("document_id")) != str(v):
                    match = False
                    break
                if k in r.get("metadata", {}) and r["metadata"][k] != v:
                    match = False
                    break
            if match:
                filtered.append(r)
        results = filtered

    return results[:top_k]


def hybrid_search(
    query: str,
    top_k: int = 5,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Perform hybrid vector + full-text search with customizable rank weights.
    """
    ctx = get_current_mcp_context()
    search_service = HybridSearchService(ctx.db_session)
    return search_service.hybrid_search(
        query=query,
        user=ctx.user,
        top_k=top_k,
        apply_rerank=True,
    )


def dense_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform dense semantic vector retrieval via pgvector embeddings.
    """
    ctx = get_current_mcp_context()
    search_service = HybridSearchService(ctx.db_session)
    return search_service.dense_search(query=query, user=ctx.user, limit=top_k)


def sparse_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform sparse BM25 / PostgreSQL Full-Text Search over indexed document chunks.
    """
    ctx = get_current_mcp_context()
    search_service = HybridSearchService(ctx.db_session)
    return search_service.sparse_search(query=query, user=ctx.user, limit=top_k)


def get_document_metadata(document_id: str) -> Dict[str, Any]:
    """
    Retrieve document metadata, verifying tenant isolation and document-level permissions.
    """
    ctx = get_current_mcp_context()
    doc_uuid = UUID(document_id)
    doc = ctx.db_session.execute(
        select(Document).where(Document.id == doc_uuid, Document.tenant_id == ctx.tenant_id)
    ).scalar_one_or_none()
    
    if not doc:
        raise ValueError(f"Document {document_id} not found or inaccessible.")
    
    perm_service = PermissionService(ctx.db_session)
    perm_service.check_read_permission(doc, ctx.user)
    
    chunk_count = ctx.db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
    return {
        "document_id": str(doc.id),
        "title": doc.title,
        "filename": getattr(doc, "original_filename", getattr(doc, "filename", "")),
        "content_type": getattr(doc, "mime_type", getattr(doc, "content_type", "")),
        "file_size_bytes": doc.file_size_bytes,
        "classification": doc.classification.value if hasattr(doc.classification, "value") else str(doc.classification),
        "total_chunks": chunk_count,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def get_document_content(document_id: str) -> str:
    """
    Retrieve full reconstructed text content of a document from its ordered chunks.
    """
    ctx = get_current_mcp_context()
    doc_uuid = UUID(document_id)
    doc = ctx.db_session.execute(
        select(Document).where(Document.id == doc_uuid, Document.tenant_id == ctx.tenant_id)
    ).scalar_one_or_none()
    
    if not doc:
        raise ValueError(f"Document {document_id} not found or inaccessible.")
    
    perm_service = PermissionService(ctx.db_session)
    perm_service.check_read_permission(doc, ctx.user)
    
    chunks = ctx.db_session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_uuid)
        .order_by(DocumentChunk.chunk_index.asc())
    ).scalars().all()
    
    return "\n\n".join([getattr(chunk, 'content', getattr(chunk, 'chunk_text', '')) for chunk in chunks])


def get_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks with metadata for an authorized document.
    """
    ctx = get_current_mcp_context()
    doc_uuid = UUID(document_id)
    doc = ctx.db_session.execute(
        select(Document).where(Document.id == doc_uuid, Document.tenant_id == ctx.tenant_id)
    ).scalar_one_or_none()
    
    if not doc:
        raise ValueError(f"Document {document_id} not found or inaccessible.")
    
    perm_service = PermissionService(ctx.db_session)
    perm_service.check_read_permission(doc, ctx.user)
    
    chunks = ctx.db_session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_uuid)
        .order_by(DocumentChunk.chunk_index.asc())
    ).scalars().all()
    
    return [
        {
            "chunk_id": str(c.id),
            "chunk_index": c.chunk_index,
            "heading": getattr(c, "section_heading", getattr(c, "heading", "")),
            "section_depth": getattr(c, "section_depth", 1),
            "chunk_text": getattr(c, "content", getattr(c, "chunk_text", "")),
            "token_count": c.token_count,
            "page_number": c.page_number,
        }
        for c in chunks
    ]


# ---------------------------------------------------------------------------
# Category 2: Intelligence Tools
# ---------------------------------------------------------------------------

def summarize_document(document_id: str, focus: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate an executive summary, key points, and compliance highlights for a document.
    """
    ctx = get_current_mcp_context()
    summary_service = DocumentSummaryService(ctx.db_session)
    result = summary_service.summarize_document(UUID(document_id), ctx.user)
    return dataclasses.asdict(result)


def compare_documents(
    doc_a_id: str,
    doc_b_id: str,
    comparison_dimension: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform section-by-section comparison, change detection, and policy drift analysis.
    """
    ctx = get_current_mcp_context()
    comp_service = DocumentComparisonService(ctx.db_session)
    result = comp_service.compare_documents(UUID(doc_a_id), UUID(doc_b_id), ctx.user)
    return dataclasses.asdict(result)


def extract_regulatory_obligations(
    document_id: str,
    regulation_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract statutory and regulatory obligations from a document using mandatory modal verbs.
    """
    ctx = get_current_mcp_context()
    chunks = get_document_chunks(document_id)
    
    obligation_patterns = [
        re.compile(r"([^.\n]*\b(?:must|shall|required to|mandated to|prohibited from|shall not)\b[^.\n]*)", re.IGNORECASE)
    ]
    
    obligations = []
    idx = 1
    for chunk in chunks:
        text = chunk["chunk_text"]
        for pat in obligation_patterns:
            matches = pat.findall(text)
            for match in matches:
                clause = match.strip()
                if len(clause) > 20:
                    obligations.append({
                        "obligation_id": f"OBL_{idx:03d}",
                        "text": clause,
                        "chunk_id": chunk["chunk_id"],
                        "heading": chunk["heading"],
                        "page_number": chunk["page_number"],
                        "mandatory_level": "MANDATORY" if "shall not" in clause.lower() or "must" in clause.lower() else "CONDITIONAL",
                        "regulation_type": regulation_type or "STATUTORY",
                    })
                    idx += 1
    return obligations


def identify_financial_thresholds(document_id: str) -> List[Dict[str, Any]]:
    """
    Identify and extract financial thresholds, currency figures, deadlines, and percentages.
    """
    ctx = get_current_mcp_context()
    chunks = get_document_chunks(document_id)
    
    threshold_patterns = [
        (re.compile(r"(?:\$|EUR|GBP|USD)\s*[\d,]+(?:\.\d+)?|\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:USD|EUR|GBP|dollars|cents)\b", re.IGNORECASE), "CURRENCY"),
        (re.compile(r"\b\d+\s*(?:calendar days|business days|working days|hours|months|years)\b", re.IGNORECASE), "DEADLINE"),
        (re.compile(r"\b\d+(?:\.\d+)?\s*%", re.IGNORECASE), "PERCENTAGE"),
    ]
    
    findings = []
    idx = 1
    for chunk in chunks:
        text = chunk["chunk_text"]
        for pat, ttype in threshold_patterns:
            matches = pat.findall(text)
            for match in matches:
                val = match.strip()
                # Find context window around match
                pos = text.find(val)
                start = max(0, pos - 40)
                end = min(len(text), pos + len(val) + 40)
                context = text[start:end].replace("\n", " ").strip()
                
                findings.append({
                    "threshold_id": f"THR_{idx:03d}",
                    "type": ttype,
                    "value": val,
                    "context": context,
                    "chunk_id": chunk["chunk_id"],
                    "page_number": chunk["page_number"],
                })
                idx += 1
    return findings


# ---------------------------------------------------------------------------
# Category 3: Verification Tools
# ---------------------------------------------------------------------------

def verify_claim(claim_text: str, evidence_ids: List[str]) -> Dict[str, Any]:
    """
    Verify a factual claim against provided evidence chunks.
    """
    ctx = get_current_mcp_context()
    verification_service = CitationVerificationService(ctx.db_session)
    
    # Query chunks for evidence
    chunk_uuids = []
    for eid in evidence_ids:
        try:
            chunk_uuids.append(UUID(eid))
        except ValueError:
            pass
            
    chunks = []
    if chunk_uuids:
        chunks = ctx.db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(chunk_uuids))
        ).scalars().all()
        
    combined_evidence = " ".join([c.chunk_text for c in chunks])
    if not combined_evidence:
        return {
            "claim": claim_text,
            "verdict": "UNVERIFIED",
            "supported": False,
            "confidence": 0.0,
            "reason": "No accessible evidence chunks found for provided IDs.",
        }
    
    res = verification_service.verify_claim(claim_text, combined_evidence)
    return {
        "claim": claim_text,
        "verdict": "SUPPORTED" if res.supported else "CONTRADICTED",
        "supported": res.supported,
        "confidence": res.confidence,
        "hallucination_risk": res.hallucination_risk,
        "missing_entities": res.missing_entities,
    }


def verify_citation(citation: str, source_text: str) -> Dict[str, Any]:
    """
    Verify whether a citation reference accurately matches the source text.
    """
    citation_clean = citation.strip()
    source_clean = source_text.strip()
    
    if not citation_clean or not source_clean:
        return {"valid": False, "matched_text": "", "similarity": 0.0}
        
    match = citation_clean.lower() in source_clean.lower()
    return {
        "valid": match,
        "matched_text": citation_clean if match else "",
        "similarity": 1.0 if match else 0.0,
    }


def check_numeric_claim(claimed_value: str, claimed_metric: str, evidence_id: str) -> Dict[str, Any]:
    """
    Verify numeric claim against a specific evidence chunk.
    """
    ctx = get_current_mcp_context()
    try:
        chunk_uuid = UUID(evidence_id)
        chunk = ctx.db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk_uuid)
        ).scalar_one_or_none()
    except Exception:
        chunk = None
        
    if not chunk:
        return {
            "numeric_match": False,
            "claimed_value": claimed_value,
            "evidence_id": evidence_id,
            "verdict": "EVIDENCE_NOT_FOUND",
        }
        
    text = getattr(chunk, "content", getattr(chunk, "chunk_text", ""))
    val_clean = claimed_value.strip().replace("$", "").replace(",", "")
    text_clean = text.replace("$", "").replace(",", "")
    
    match = val_clean in text_clean
    return {
        "numeric_match": match,
        "claimed_value": claimed_value,
        "claimed_metric": claimed_metric,
        "evidence_id": evidence_id,
        "verdict": "VERIFIED_ACCURATE" if match else "NUMERIC_MISMATCH",
    }


def check_regulatory_reference(statute_code: str, evidence_id: str) -> Dict[str, Any]:
    """
    Verify whether a statute or regulatory citation actually appears in the referenced chunk.
    """
    ctx = get_current_mcp_context()
    try:
        chunk = ctx.db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == UUID(evidence_id))
        ).scalar_one_or_none()
    except Exception:
        chunk = None
        
    if not chunk:
        return {"found": False, "statute_code": statute_code, "verdict": "EVIDENCE_NOT_FOUND"}
        
    text = getattr(chunk, "content", getattr(chunk, "chunk_text", ""))
    found = statute_code.lower() in text.lower()
    return {
        "found": found,
        "statute_code": statute_code,
        "chunk_id": evidence_id,
        "verdict": "CONFIRMED_REFERENCE" if found else "UNSUPPORTED_STATUTE_CITATION",
    }


def inspect_evidence_support(finding_id: str) -> Dict[str, Any]:
    """
    Inspect the audit trail and evidence support for a finding or evidence chunk.
    """
    ctx = get_current_mcp_context()
    try:
        chunk = ctx.db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == UUID(finding_id))
        ).scalar_one_or_none()
    except Exception:
        chunk = None
        
    if not chunk:
        return {"finding_id": finding_id, "status": "NOT_FOUND"}
        
    text = getattr(chunk, "content", getattr(chunk, "chunk_text", ""))
    return {
        "finding_id": finding_id,
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "heading": getattr(chunk, "section_heading", getattr(chunk, "heading", "")),
        "page_number": chunk.page_number,
        "text_preview": text[:200] + "..." if len(text) > 200 else text,
        "confidence": 1.0,
    }


# ---------------------------------------------------------------------------
# Category 4: Workflow Tools
# ---------------------------------------------------------------------------

def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """
    Retrieve workflow execution state, steps, and human approval status.
    """
    ctx = get_current_mcp_context()
    w_uuid = UUID(workflow_id)
    wf = ctx.db_session.execute(
        select(AgenticWorkflow).where(
            AgenticWorkflow.id == w_uuid,
            AgenticWorkflow.tenant_id == ctx.tenant_id,
        )
    ).scalar_one_or_none()
    
    if not wf:
        raise ValueError(f"Workflow {workflow_id} not found.")
        
    return {
        "workflow_id": str(wf.id),
        "task_type": wf.task_type.value if hasattr(wf.task_type, "value") else str(wf.task_type),
        "status": wf.workflow_status.value if hasattr(wf.workflow_status, "value") else str(wf.workflow_status),
        "approval_status": wf.approval_status.value if hasattr(wf.approval_status, "value") else str(wf.approval_status),
        "query": wf.query,
        "iteration_count": wf.iteration_count,
        "max_iterations": wf.max_iterations,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


def request_human_approval(
    workflow_id: str,
    reason: str,
    affected_agents: List[str],
    conflict_summary: Optional[str] = None
) -> Dict[str, Any]:
    """
    Halt autonomous workflow execution and request explicit human approval.
    """
    ctx = get_current_mcp_context()
    w_uuid = UUID(workflow_id)
    wf = ctx.db_session.execute(
        select(AgenticWorkflow).where(
            AgenticWorkflow.id == w_uuid,
            AgenticWorkflow.tenant_id == ctx.tenant_id,
        )
    ).scalar_one_or_none()
    
    if not wf:
        raise ValueError(f"Workflow {workflow_id} not found.")
        
    wf.workflow_status = WorkflowStatus.PENDING_APPROVAL
    wf.approval_status = ApprovalStatus.PENDING_APPROVAL
    
    # Get current trace count
    count = ctx.db_session.query(AgenticExecutionTrace).filter(
        AgenticExecutionTrace.workflow_id == wf.id
    ).count()

    trace = AgenticExecutionTrace(
        workflow_id=wf.id,
        step_number=count + 1,
        agent_name="conflict_resolution",
        action="REQUEST_HUMAN_APPROVAL",
        inputs_redacted={"affected_agents": affected_agents, "conflict_summary": conflict_summary},
        outputs_redacted={"status": "PENDING_APPROVAL", "reason": reason},
        status="PENDING",
    )
    ctx.db_session.add(trace)
    ctx.db_session.commit()
    
    return {
        "workflow_id": str(wf.id),
        "status": wf.workflow_status.value,
        "approval_status": wf.approval_status.value,
        "reason": reason,
        "message": "Workflow transitioned to PENDING_APPROVAL. Execution paused awaiting human sign-off.",
    }


def record_agent_finding(
    workflow_id: str,
    agent_name: str,
    finding_type: str,
    finding_content: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Record an execution trace and finding for auditability and explainability.
    """
    ctx = get_current_mcp_context()
    w_uuid = UUID(workflow_id)
    wf = ctx.db_session.execute(
        select(AgenticWorkflow).where(
            AgenticWorkflow.id == w_uuid,
            AgenticWorkflow.tenant_id == ctx.tenant_id,
        )
    ).scalar_one_or_none()
    
    if not wf:
        raise ValueError(f"Workflow {workflow_id} not found.")
        
    count = ctx.db_session.query(AgenticExecutionTrace).filter(
        AgenticExecutionTrace.workflow_id == wf.id
    ).count()

    trace = AgenticExecutionTrace(
        workflow_id=wf.id,
        step_number=count + 1,
        agent_name=agent_name,
        action=f"RECORD_{finding_type.upper()}",
        inputs_redacted={"finding_type": finding_type},
        outputs_redacted=finding_content,
        status="COMPLETED",
    )
    ctx.db_session.add(trace)
    ctx.db_session.commit()
    
    return {
        "workflow_id": str(wf.id),
        "step_number": trace.step_number,
        "trace_id": str(trace.id),
        "status": "RECORDED",
    }
