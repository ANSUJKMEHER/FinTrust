"""
FinTrust RAG - Phase 5 MCP Server & Tool Registry Tests
Tests tool registration, schema adherence, context isolation,
and execution across research, intelligence, verification, and workflow tools.
"""

import uuid
import pytest
from app.agentic.mcp import fintrust_mcp_server, mcp_execution_context, get_current_mcp_context
from app.agentic.mcp import tools as mcp_tools
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.document import Document, DocumentClassification, DocumentVersion, ProcessingStatus
from app.db.models.document_chunk import DocumentChunk
from app.db.models.workflow import AgenticWorkflow, WorkflowTaskType, WorkflowStatus, ApprovalStatus


def test_mcp_server_registered_tools():
    """Verify that all 19 required tools are registered in MCPServer."""
    import asyncio
    tools = asyncio.run(fintrust_mcp_server.list_tools())
    tool_names = [t.name for t in tools]

    expected_tools = [
        # Research
        "search_documents", "hybrid_search", "dense_search", "sparse_search",
        "get_document_metadata", "get_document_content", "get_document_chunks",
        # Intelligence
        "summarize_document", "compare_documents",
        "extract_regulatory_obligations", "identify_financial_thresholds",
        # Verification
        "verify_claim", "verify_citation", "check_numeric_claim",
        "check_regulatory_reference", "inspect_evidence_support",
        # Workflow
        "get_workflow_status", "request_human_approval", "record_agent_finding",
    ]

    for tool in expected_tools:
        assert tool in tool_names, f"Missing MCP tool registration: {tool}"


def test_mcp_context_enforcement():
    """Verify that calling MCP tools outside an authenticated context raises PermissionError."""
    with pytest.raises(PermissionError) as exc_info:
        mcp_tools.search_documents(query="test query")
    assert "Access denied: No active authenticated MCP execution context" in str(exc_info.value)


def test_mcp_research_and_document_tools(db, tenant_a, user_a_admin):
    """Test document metadata, content, and chunk extraction via MCP tools."""
    doc = Document(
        tenant_id=tenant_a.id,
        title="AML Compliance Policy 2024",
        original_filename="aml_2024.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        content_hash="mock_hash_1",
        classification=DocumentClassification.CONFIDENTIAL,
        status=ProcessingStatus.COMPLETED,
        created_by_id=user_a_admin.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_num=1,
        storage_path=f"/storage/{doc.id}_v1.pdf",
        total_pages=2,
        total_chunks=2,
    )
    db.add(version)
    db.commit()

    chunk1 = DocumentChunk(
        tenant_id=doc.tenant_id,
        document_id=doc.id,
        document_version_id=version.id,
        chunk_index=0,
        section_heading="1. Scope and Thresholds",
        content="Financial institutions must report currency transactions exceeding $10,000 within 15 calendar days.",
        content_hash="mock_hash_chunk1",
        token_count=20,
        page_number=1,
    )
    chunk2 = DocumentChunk(
        tenant_id=doc.tenant_id,
        document_id=doc.id,
        document_version_id=version.id,
        chunk_index=1,
        section_heading="2. Record Retention",
        content="All BSA compliance documentation shall be retained for at least 5 years.",
        content_hash="mock_hash_chunk2",
        token_count=18,
        page_number=2,
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    with mcp_execution_context(user=user_a_admin, db_session=db):
        # 1. Metadata
        meta = mcp_tools.get_document_metadata(str(doc.id))
        assert meta["title"] == "AML Compliance Policy 2024"
        assert meta["total_chunks"] == 2

        # 2. Content
        content = mcp_tools.get_document_content(str(doc.id))
        assert "$10,000" in content
        assert "5 years" in content

        # 3. Chunks
        chunks = mcp_tools.get_document_chunks(str(doc.id))
        assert len(chunks) == 2

        # 4. Regulatory Obligations
        obligations = mcp_tools.extract_regulatory_obligations(str(doc.id))
        assert len(obligations) >= 1
        assert any("must report" in o["text"].lower() or "shall be retained" in o["text"].lower() for o in obligations)

        # 5. Financial Thresholds
        thresholds = mcp_tools.identify_financial_thresholds(str(doc.id))
        assert any(t["value"] == "$10,000" for t in thresholds)
        assert any("15 calendar days" in t["value"] for t in thresholds)


def test_mcp_verification_tools(db, tenant_a, user_a_admin):
    """Test claim verification, citation verification, and numeric checks."""
    doc = Document(
        tenant_id=tenant_a.id,
        title="BSA Manual",
        original_filename="bsa.pdf",
        mime_type="application/pdf",
        file_size_bytes=512,
        content_hash="mock_hash_2",
        classification=DocumentClassification.INTERNAL,
        status=ProcessingStatus.COMPLETED,
        created_by_id=user_a_admin.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_num=1,
        storage_path=f"/storage/{doc.id}_v1.pdf",
        total_pages=4,
        total_chunks=1,
    )
    db.add(version)
    db.commit()

    chunk = DocumentChunk(
        tenant_id=doc.tenant_id,
        document_id=doc.id,
        document_version_id=version.id,
        chunk_index=0,
        section_heading="Section 4",
        content="Institutions are required to maintain SAR records for 5 years under 31 CFR 1010.311.",
        content_hash="mock_hash_chunk_v",
        token_count=16,
        page_number=4,
    )
    db.add(chunk)
    db.commit()

    with mcp_execution_context(user=user_a_admin, db_session=db):
        # Citation check
        cit_res = mcp_tools.verify_citation("maintain SAR records for 5 years", chunk.content)
        assert cit_res["valid"] is True

        # Numeric claim check
        num_res = mcp_tools.check_numeric_claim("5", "years", str(chunk.id))
        assert num_res["numeric_match"] is True

        # Regulatory statute check
        stat_res = mcp_tools.check_regulatory_reference("31 CFR 1010.311", str(chunk.id))
        assert stat_res["found"] is True

        # Evidence support inspection
        insp = mcp_tools.inspect_evidence_support(str(chunk.id))
        assert insp["document_id"] == str(doc.id)


def test_mcp_workflow_tools(db, tenant_a, user_a_admin):
    """Test workflow status retrieval, approval request, and finding recording."""
    wf = AgenticWorkflow(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a_admin.id,
        task_type=WorkflowTaskType.REGULATORY_COMPLIANCE,
        workflow_status=WorkflowStatus.EXECUTING,
        approval_status=ApprovalStatus.NOT_REQUIRED,
        query="Compliance audit of SAR retention.",
        max_iterations=3,
        iteration_count=1,
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)

    with mcp_execution_context(user=user_a_admin, db_session=db, workflow_id=wf.id):
        # 1. Get status
        status_info = mcp_tools.get_workflow_status(str(wf.id))
        assert status_info["status"] == "EXECUTING"
        assert status_info["query"] == "Compliance audit of SAR retention."

        # 2. Request human approval
        appr_info = mcp_tools.request_human_approval(
            workflow_id=str(wf.id),
            reason="Unresolved threshold conflict between policy versions.",
            affected_agents=["compliance", "verification"],
            conflict_summary="$10,000 in Central vs $5,000 in Branch",
        )
        assert appr_info["status"] == "PENDING_APPROVAL"
        assert appr_info["approval_status"] == "PENDING_APPROVAL"

        # 3. Record finding
        rec_info = mcp_tools.record_agent_finding(
            workflow_id=str(wf.id),
            agent_name="compliance_agent",
            finding_type="statutory_obligation",
            finding_content={"obligation": "SAR retention for 5 years"},
        )
        assert rec_info["status"] == "RECORDED"
