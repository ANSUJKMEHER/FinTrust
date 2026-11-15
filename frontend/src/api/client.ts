/**
 * FinTrust Centralized API Client
 * Enterprise-grade REST client with automatic JWT bearer auth, error handling,
 * and endpoint definitions matching the FastAPI backend.
 */

import {
  User,
  Tenant,
  DocumentItem,
  DocumentChunk,
  RAGQueryResponse,
  CitationVerificationResponse,
  DocumentSummaryResponse,
  DocumentComparisonResponse,
  AgenticWorkflow,
  WorkflowTraceResponse,
  MCPToolInfo,
  AuditLog,
  WorkflowTaskType,
  WorkflowStatus,
  ApprovalStatus,
} from '../types';

const BASE_URL = '/api/v1';

class ApiClient {
  private getHeaders(isFormData = false): HeadersInit {
    const headers: Record<string, string> = {};
    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }
    const token = localStorage.getItem('fintrust_access_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  private async handleResponse<T>(res: Response): Promise<T> {
    if (res.status === 401) {
      // Clear token on unauthorized
      localStorage.removeItem('fintrust_access_token');
      // Dispatch custom event so UI can show auth modal or redirect
      window.dispatchEvent(new CustomEvent('fintrust-auth-expired'));
      throw new Error('Authentication expired. Please log in again.');
    }

    if (!res.ok) {
      let errorDetail = `Request failed with status ${res.status}`;
      try {
        const errorJson = await res.json();
        errorDetail = errorJson.detail || errorJson.message || JSON.stringify(errorJson);
      } catch {
        // use status text if JSON parsing fails
        errorDetail = res.statusText || errorDetail;
      }
      throw new Error(errorDetail);
    }

    return res.json() as Promise<T>;
  }

  // --- Auth & Tenant ---
  async login(username: string, password: string):Promise<{ access_token: string; token_type: string }> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });
    const data = await this.handleResponse<{ access_token: string; token_type: string }>(res);
    localStorage.setItem('fintrust_access_token', data.access_token);
    return data;
  }

  async getMe(): Promise<User> {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<User>(res);
  }

  async getCurrentTenant(): Promise<Tenant> {
    const res = await fetch(`${BASE_URL}/tenants/current`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<Tenant>(res);
  }

  logout(): void {
    localStorage.removeItem('fintrust_access_token');
  }

  // --- Documents ---
  async listDocuments(params?: {
    classification?: string;
    category?: string;
    status?: string;
    skip?: number;
    limit?: number;
  }): Promise<DocumentItem[]> {
    const query = new URLSearchParams();
    if (params?.classification) query.append('classification', params.classification);
    if (params?.category) query.append('category', params.category);
    if (params?.status) query.append('status', params.status);
    if (params?.skip !== undefined) query.append('skip', params.skip.toString());
    if (params?.limit !== undefined) query.append('limit', params.limit.toString());

    const res = await fetch(`${BASE_URL}/documents/?${query.toString()}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<DocumentItem[]>(res);
  }

  async getDocument(id: string): Promise<DocumentItem> {
    const res = await fetch(`${BASE_URL}/documents/${id}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<DocumentItem>(res);
  }

  async getDocumentChunks(id: string, skip = 0, limit = 50): Promise<DocumentChunk[]> {
    const res = await fetch(`${BASE_URL}/documents/${id}/chunks?skip=${skip}&limit=${limit}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<DocumentChunk[]>(res);
  }

  async uploadDocument(
    file: File,
    title?: string,
    classification = 'INTERNAL',
    category = 'GENERAL_COMPLIANCE'
  ): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    formData.append('classification', classification);
    formData.append('category', category);

    const res = await fetch(`${BASE_URL}/documents/upload`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: formData,
    });
    return this.handleResponse<DocumentItem>(res);
  }

  async deleteDocument(id: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/documents/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      await this.handleResponse(res);
    }
  }

  // --- Grounded RAG & Search ---
  async queryRAG(query: string, topK = 5): Promise<RAGQueryResponse> {
    const res = await fetch(`${BASE_URL}/rag/query`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ query, top_k: topK }),
    });
    return this.handleResponse<RAGQueryResponse>(res);
  }

  async verifyCitations(answerText: string, chunkIds: string[]): Promise<CitationVerificationResponse> {
    const res = await fetch(`${BASE_URL}/rag/verify`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ answer_text: answerText, chunk_ids: chunkIds }),
    });
    return this.handleResponse<CitationVerificationResponse>(res);
  }

  async hybridSearch(query: string, topK = 5): Promise<any> {
    const res = await fetch(`${BASE_URL}/search/hybrid`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ query, top_k: topK }),
    });
    return this.handleResponse<any>(res);
  }

  // --- Document Intelligence ---
  async summarizeDocument(documentId: string): Promise<DocumentSummaryResponse> {
    const res = await fetch(`${BASE_URL}/intelligence/summarize`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ document_id: documentId }),
    });
    return this.handleResponse<DocumentSummaryResponse>(res);
  }

  async compareDocuments(doc1Id: string, doc2Id: string): Promise<DocumentComparisonResponse> {
    const res = await fetch(`${BASE_URL}/intelligence/compare`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ doc1_id: doc1Id, doc2_id: doc2Id }),
    });
    return this.handleResponse<DocumentComparisonResponse>(res);
  }

  // --- Agentic Multi-Agent Workflows ---
  async listWorkflows(params?: {
    task_type?: WorkflowTaskType;
    status?: WorkflowStatus;
    approval_status?: ApprovalStatus;
    skip?: number;
    limit?: number;
  }): Promise<AgenticWorkflow[]> {
    const query = new URLSearchParams();
    if (params?.task_type) query.append('task_type', params.task_type);
    if (params?.status) query.append('status', params.status);
    if (params?.approval_status) query.append('approval_status', params.approval_status);
    if (params?.skip !== undefined) query.append('skip', params.skip.toString());
    if (params?.limit !== undefined) query.append('limit', params.limit.toString());

    const res = await fetch(`${BASE_URL}/agentic/workflows?${query.toString()}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<AgenticWorkflow[]>(res);
  }

  async getWorkflow(id: string): Promise<AgenticWorkflow> {
    const res = await fetch(`${BASE_URL}/agentic/workflows/${id}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<AgenticWorkflow>(res);
  }

  async getWorkflowTrace(id: string): Promise<WorkflowTraceResponse> {
    const res = await fetch(`${BASE_URL}/agentic/workflows/${id}/trace`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<WorkflowTraceResponse>(res);
  }

  async startResearch(
    query: string,
    documentIds?: string[],
    requireHumanApproval = false,
    maxIterations = 5
  ): Promise<AgenticWorkflow> {
    const res = await fetch(`${BASE_URL}/agentic/research`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        query,
        document_ids: documentIds,
        require_human_approval: requireHumanApproval,
        max_iterations: maxIterations,
      }),
    });
    return this.handleResponse<AgenticWorkflow>(res);
  }

  async startComplianceAudit(
    query: string,
    statuteReference?: string,
    policyDocumentIds?: string[],
    requireHumanApproval = false,
    maxIterations = 5
  ): Promise<AgenticWorkflow> {
    const res = await fetch(`${BASE_URL}/agentic/compliance-audit`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        query,
        statute_reference: statuteReference,
        policy_document_ids: policyDocumentIds,
        require_human_approval: requireHumanApproval,
        max_iterations: maxIterations,
      }),
    });
    return this.handleResponse<AgenticWorkflow>(res);
  }

  async startDocumentInvestigation(
    query: string,
    doc1Id: string,
    doc2Id?: string,
    maxIterations = 5
  ): Promise<AgenticWorkflow> {
    const res = await fetch(`${BASE_URL}/agentic/document-investigation`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        query,
        doc1_id: doc1Id,
        doc2_id: doc2Id,
        max_iterations: maxIterations,
      }),
    });
    return this.handleResponse<AgenticWorkflow>(res);
  }

  async submitHumanApproval(
    workflowId: string,
    decision: 'APPROVED' | 'REJECTED' | 'NEEDS_REVISION',
    comments?: string
  ): Promise<any> {
    const res = await fetch(`${BASE_URL}/agentic/workflows/${workflowId}/approval`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ decision, comments }),
    });
    return this.handleResponse<any>(res);
  }

  async listMCPTools(): Promise<MCPToolInfo[]> {
    const res = await fetch(`${BASE_URL}/agentic/tools`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<MCPToolInfo[]>(res);
  }

  async getAgenticHealth(): Promise<{
    status: string;
    active_agents: string[];
    mcp_tools_available: string[];
    max_workflow_iterations: number;
    supervisor_orchestrator: string;
    checkpointing: string;
  }> {
    const res = await fetch(`${BASE_URL}/agentic/health`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<any>(res);
  }

  // --- Audit Logs ---
  async listAuditLogs(skip = 0, limit = 50): Promise<AuditLog[]> {
    const res = await fetch(`${BASE_URL}/audit/?skip=${skip}&limit=${limit}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<AuditLog[]>(res);
  }

  // --- LLM & System Health ---
  async getLLMHealth(): Promise<{ status: string; provider: string; model: string; healthy: boolean }> {
    const res = await fetch(`${BASE_URL}/llm/health`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<any>(res);
  }

  async getSystemHealth(): Promise<{ status: string; service: string; environment: string; version: string }> {
    const res = await fetch('/health', {
      method: 'GET',
    });
    return this.handleResponse<any>(res);
  }
}

export const api = new ApiClient();
