// FinTrust TypeScript Domain Definitions

export interface User {
  id: string;
  email: string;
  full_name?: string;
  tenant_id: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export type DocumentClassification = 'PUBLIC' | 'INTERNAL' | 'CONFIDENTIAL' | 'RESTRICTED';
export type ProcessingStatus = 'PENDING' | 'PARSING' | 'CHUNKING' | 'EMBEDDING' | 'INDEXED' | 'FAILED';

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_num: number;
  storage_path: string;
  total_pages?: number;
  total_chunks: number;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  tenant_id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  content_hash: string;
  classification: DocumentClassification;
  category: string;
  current_version_num: number;
  status: ProcessingStatus;
  error_message?: string;
  created_at: string;
  updated_at: string;
  versions?: DocumentVersion[];
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  document_version_id: string;
  chunk_index: number;
  page_number?: number;
  section_heading?: string;
  heading_breadcrumb?: string;
  content: string;
  token_count: number;
  document_title?: string;
  document_classification?: DocumentClassification;
  relevance_score?: number;
}

export interface Citation {
  citation_id: string;
  raw_citation_text: string;
  is_valid: boolean;
  evidence_id?: string;
  document_id?: string;
  document_version_id?: string;
  chunk_id?: string;
  document_title?: string;
  section_heading?: string;
  page_number?: number;
  supporting_text_span?: string;
  validation_error?: string;
}

export interface RAGQueryResponse {
  query: string;
  answer: string;
  evidence_sufficient: boolean;
  refusal_reason?: string;
  model_name: string;
  total_citations: number;
  valid_citations: number;
  latency_ms: number;
  citations: Citation[];
}

export interface VerifiedClaim {
  claim_id: string;
  claim_text: string;
  status: 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'CONTRADICTED' | 'UNSUPPORTED' | 'UNVERIFIABLE';
  confidence_score: number;
  supporting_evidence_ids: string[];
  explanation: string;
}

export interface VerificationSummary {
  total_claims: number;
  supported_claims: number;
  partially_supported_claims: number;
  contradicted_claims: number;
  unsupported_claims: number;
  unverifiable_claims: number;
  overall_faithfulness_score: number;
  is_faithful: boolean;
  claims: VerifiedClaim[];
}

export interface CitationVerificationResponse {
  summary: VerificationSummary;
}

export interface KeyObligation {
  obligation_text: string;
  section_heading?: string;
  citation?: string;
  evidence_id?: string;
}

export interface FinancialThreshold {
  metric_name: string;
  threshold_value: string;
  section_heading?: string;
  citation?: string;
}

export interface ComplianceDeadline {
  event_trigger: string;
  filing_window: string;
  section_heading?: string;
  citation?: string;
}

export interface DocumentSummaryResponse {
  document_id: string;
  document_title: string;
  document_classification: string;
  total_pages?: number;
  total_chunks: number;
  executive_summary: string;
  key_obligations: KeyObligation[];
  financial_thresholds: FinancialThreshold[];
  compliance_deadlines: ComplianceDeadline[];
  regulatory_references: string[];
  identified_risks_and_exceptions: string[];
  citations: Citation[];
}

export interface ComparisonFinding {
  finding_id: string;
  finding_type: string;
  description: string;
  doc1_statement?: string;
  doc1_citation?: string;
  doc2_statement?: string;
  doc2_citation?: string;
  confidence_score: number;
}

export interface DocumentComparisonResponse {
  doc1_id: string;
  doc1_title: string;
  doc2_id: string;
  doc2_title: string;
  total_findings: number;
  findings_by_type: Record<string, number>;
  findings: ComparisonFinding[];
}

export type WorkflowTaskType =
  | 'REGULATORY_COMPLIANCE'
  | 'POLICY_COMPARISON'
  | 'RISK_INVESTIGATION'
  | 'OBLIGATION_EXTRACTION'
  | 'GENERAL_RESEARCH';

export type WorkflowStatus =
  | 'INITIALIZED'
  | 'PLANNING'
  | 'EXECUTING'
  | 'VERIFYING'
  | 'PENDING_APPROVAL'
  | 'COMPLETED'
  | 'REFUSED'
  | 'FAILED'
  | 'CANCELLED';

export type ApprovalStatus =
  | 'NOT_REQUIRED'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'NEEDS_REVISION';

export interface AgenticWorkflow {
  workflow_id: string;
  tenant_id: string;
  user_id: string;
  query: string;
  task_type: WorkflowTaskType;
  workflow_status: WorkflowStatus;
  approval_status: ApprovalStatus;
  iteration_count: number;
  max_iterations: number;
  total_tokens_used: number;
  execution_latency_ms: number;
  selected_agents?: string[];
  execution_plan?: Array<{
    step: number;
    agent: string;
    description: string;
    tool?: string;
  }>;
  final_report?: {
    investigation_objective?: string;
    executive_summary?: string;
    statutory_obligations?: string[];
    financial_thresholds?: Array<{
      threshold: string;
      context: string;
      citation?: string;
    }>;
    identified_gaps?: string[];
    contradictory_clauses?: Array<{
      clause_a: string;
      clause_b: string;
      conflict_type: string;
    }>;
    human_approval_required?: boolean;
    approval_reasons?: string[];
    verified_claims_count?: number;
    unsupported_claims_count?: number;
    citations?: Citation[];
  };
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTraceItem {
  step_number: number;
  agent_name: string;
  action: string;
  inputs_redacted?: Record<string, any>;
  outputs_redacted?: Record<string, any>;
  status: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  error_details?: string;
  timestamp: string;
}

export interface WorkflowTraceResponse {
  workflow_id: string;
  total_steps: number;
  total_tokens: number;
  total_latency_ms: number;
  traces: WorkflowTraceItem[];
}

export interface MCPToolInfo {
  name: string;
  category: string;
  description: string;
  parameters: Record<string, any>;
  is_safe: boolean;
}

export interface AuditLog {
  id: string;
  tenant_id: string;
  user_id?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  ip_address?: string;
  user_agent?: string;
  details?: Record<string, any>;
  created_at: string;
}
