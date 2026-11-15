import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  SearchCheck,
  Plus,
  BrainCircuit,
  FileText,
  Clock,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Bookmark,
  ChevronRight,
  ExternalLink,
  Layers,
  ArrowRight,
  RefreshCw,
  GitCompare,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { api } from '../api/client';
import { AgenticWorkflow, DocumentItem, WorkflowStatus } from '../types';

export const Investigations: React.FC = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<AgenticWorkflow[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedWorkflow, setSelectedWorkflow] = useState<AgenticWorkflow | null>(null);

  // New Investigation Wizard Modal
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [investigationQuery, setInvestigationQuery] = useState('');
  const [investigationType, setInvestigationType] = useState<'RESEARCH' | 'COMPLIANCE' | 'COMPARISON'>('COMPLIANCE');
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [statuteReference, setStatuteReference] = useState('Bank Secrecy Act / AML');
  const [requireApproval, setRequireApproval] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [wfs, docs] = await Promise.all([
        api.listWorkflows({ limit: 50 }),
        api.listDocuments({ limit: 50 }),
      ]);
      setWorkflows(wfs);
      setDocuments(docs);
      if (wfs.length > 0 && !selectedWorkflow) {
        setSelectedWorkflow(wfs[0]);
      }
    } catch (err) {
      console.error('Failed to load investigations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!investigationQuery.trim()) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      let wf: AgenticWorkflow;
      if (investigationType === 'COMPLIANCE') {
        wf = await api.startComplianceAudit(
          investigationQuery.trim(),
          statuteReference,
          selectedDocIds.length > 0 ? selectedDocIds : undefined,
          requireApproval
        );
      } else if (investigationType === 'COMPARISON') {
        if (selectedDocIds.length < 1) {
          throw new Error('Please select at least one document for comparison investigation.');
        }
        wf = await api.startDocumentInvestigation(
          investigationQuery.trim(),
          selectedDocIds[0],
          selectedDocIds.length > 1 ? selectedDocIds[1] : undefined
        );
      } else {
        wf = await api.startResearch(
          investigationQuery.trim(),
          selectedDocIds.length > 0 ? selectedDocIds : undefined,
          requireApproval
        );
      }

      setIsNewModalOpen(false);
      setInvestigationQuery('');
      setSelectedDocIds([]);
      await fetchData();
      setSelectedWorkflow(wf);
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to start investigation.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusBadge = (status: WorkflowStatus) => {
    switch (status) {
      case 'COMPLETED':
        return <Badge variant="success">COMPLETED</Badge>;
      case 'PENDING_APPROVAL':
        return <Badge variant="warning">PENDING APPROVAL</Badge>;
      case 'EXECUTING':
      case 'PLANNING':
      case 'VERIFYING':
        return <Badge variant="info">{status}</Badge>;
      case 'FAILED':
        return <Badge variant="danger">FAILED</Badge>;
      default:
        return <Badge variant="slate">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
            Regulatory Investigation Center
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            Conduct autonomous multi-agent compliance audits, gap analyses, and 14-section evidence reports.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsNewModalOpen(true)}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            New Investigation
          </Button>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Investigation List (4 cols) */}
        <div className="lg:col-span-4 space-y-3">
          <div className="text-xs font-mono font-semibold text-fintrust-slate dark:text-fintrust-dark-muted uppercase px-1">
            Active Investigations ({workflows.length})
          </div>

          <div className="space-y-2.5 max-h-[calc(100vh-16rem)] overflow-y-auto pr-1">
            {loading ? (
              <div className="p-8 text-center text-xs text-fintrust-slate">
                Loading investigations...
              </div>
            ) : workflows.length === 0 ? (
              <div className="p-8 text-center text-xs text-fintrust-slate border border-dashed rounded-lg">
                No investigations launched yet. Click "New Investigation" to start an autonomous audit.
              </div>
            ) : (
              workflows.map((wf) => {
                const isSelected = selectedWorkflow?.workflow_id === wf.workflow_id;
                return (
                  <div
                    key={wf.workflow_id}
                    onClick={() => setSelectedWorkflow(wf)}
                    className={`p-3.5 rounded-lg border text-left cursor-pointer transition-all ${
                      isSelected
                        ? 'border-fintrust-primary dark:border-fintrust-primary-dark bg-blue-50/40 dark:bg-blue-950/20 shadow-xs'
                        : 'border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-surface hover:border-gray-300 dark:hover:border-gray-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text line-clamp-2 leading-snug">
                        {wf.query}
                      </span>
                      {getStatusBadge(wf.workflow_status)}
                    </div>

                    <div className="flex items-center gap-2 mt-2 text-[10px] text-fintrust-slate dark:text-fintrust-dark-muted font-mono">
                      <span>{wf.task_type.replace('_', ' ')}</span>
                      <span>·</span>
                      <span>{wf.iteration_count} iters</span>
                      <span>·</span>
                      <span>{wf.execution_latency_ms}ms</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Detailed 14-Section Compliance Report (8 cols) */}
        <div className="lg:col-span-8">
          {selectedWorkflow ? (
            <Card>
              <CardHeader className="flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="primary" size="sm">
                      {selectedWorkflow.task_type}
                    </Badge>
                    {getStatusBadge(selectedWorkflow.workflow_status)}
                    {selectedWorkflow.approval_status === 'PENDING_APPROVAL' && (
                      <Badge variant="warning" size="sm">
                        HUMAN SIGNOFF REQUIRED
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="text-base">{selectedWorkflow.query}</CardTitle>
                  <CardDescription>
                    Workflow ID: <span className="font-mono">{selectedWorkflow.workflow_id}</span>
                  </CardDescription>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate(`/agent-explorer`)}
                    leftIcon={<Layers className="w-3.5 h-3.5" />}
                  >
                    View Agent Trace
                  </Button>
                  {selectedWorkflow.approval_status === 'PENDING_APPROVAL' && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => navigate('/approvals')}
                    >
                      Review Signoff
                    </Button>
                  )}
                </div>
              </CardHeader>

              <CardContent className="space-y-6">
                {/* 1. Executive Summary */}
                <div className="space-y-1.5">
                  <h4 className="text-xs font-mono uppercase font-bold text-fintrust-slate dark:text-fintrust-dark-muted flex items-center gap-1.5">
                    <BrainCircuit className="w-3.5 h-3.5 text-fintrust-primary" />
                    1. Executive Summary
                  </h4>
                  <div className="p-3.5 rounded-lg bg-fintrust-light-subtle/50 dark:bg-fintrust-dark-elevated/50 border border-fintrust-light-border dark:border-fintrust-dark-border text-xs leading-relaxed text-fintrust-light-text dark:text-fintrust-dark-text whitespace-pre-wrap">
                    {selectedWorkflow.final_report?.executive_summary ||
                      'Executive summary generated by SupervisorAgent after coordinating ResearchAgent and VerificationAgent.'}
                  </div>
                </div>

                {/* 2. Statutory Obligations Identified */}
                {selectedWorkflow.final_report?.statutory_obligations && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-mono uppercase font-bold text-fintrust-slate dark:text-fintrust-dark-muted flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                      2. Confirmed Statutory Obligations
                    </h4>
                    <div className="space-y-1.5">
                      {selectedWorkflow.final_report.statutory_obligations.map((ob, idx) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded-md border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/40 dark:bg-emerald-950/20 text-xs text-emerald-900 dark:text-emerald-300 flex items-start gap-2"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          <span>{ob}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 3. Financial Thresholds & Quantitative Triggers */}
                {selectedWorkflow.final_report?.financial_thresholds && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-mono uppercase font-bold text-fintrust-slate dark:text-fintrust-dark-muted flex items-center gap-1.5">
                      <SearchCheck className="w-3.5 h-3.5 text-indigo-600" />
                      3. Financial Thresholds & Monetary Limits
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {selectedWorkflow.final_report.financial_thresholds.map((ft, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs space-y-1"
                        >
                          <div className="font-bold text-sm font-mono text-fintrust-primary dark:text-fintrust-primary-dark">
                            {ft.threshold}
                          </div>
                          <div className="text-[11px] text-fintrust-slate">{ft.context}</div>
                          {ft.citation && (
                            <div className="text-[10px] text-fintrust-primary font-mono truncate">
                              [{ft.citation}]
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 4. Identified Gaps & Exceptions */}
                {selectedWorkflow.final_report?.identified_gaps && selectedWorkflow.final_report.identified_gaps.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-mono uppercase font-bold text-red-600 dark:text-red-400 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      4. Compliance Gaps & Deficiencies
                    </h4>
                    <div className="space-y-1.5">
                      {selectedWorkflow.final_report.identified_gaps.map((gap, idx) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded-md border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-start gap-2"
                        >
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-red-600" />
                          <span>{gap}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 5. Contradictory Clauses / Conflict Resolution */}
                {selectedWorkflow.final_report?.contradictory_clauses && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-mono uppercase font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                      <GitCompare className="w-3.5 h-3.5" />
                      5. Discrepancy & Conflict Analysis
                    </h4>
                    <div className="space-y-2">
                      {selectedWorkflow.final_report.contradictory_clauses.map((c, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50/30 dark:bg-amber-950/20 text-xs space-y-1.5"
                        >
                          <div className="font-semibold text-amber-900 dark:text-amber-300">
                            Discrepancy Type: {c.conflict_type}
                          </div>
                          <div className="text-[11px] text-fintrust-slate">
                            <strong>Baseline Clause:</strong> {c.clause_a}
                          </div>
                          <div className="text-[11px] text-fintrust-slate">
                            <strong>Contradictory Target:</strong> {c.clause_b}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 6. Execution Plan & Multi-Agent Delegation */}
                <div className="space-y-2">
                  <h4 className="text-xs font-mono uppercase font-bold text-fintrust-slate dark:text-fintrust-dark-muted flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5" />
                    6. Autonomous Execution Plan
                  </h4>
                  <div className="border border-fintrust-light-border dark:border-fintrust-dark-border rounded-lg overflow-hidden text-xs">
                    <table className="w-full text-left">
                      <thead className="bg-fintrust-light-subtle/60 dark:bg-fintrust-dark-elevated/60 text-[10px] font-mono text-fintrust-slate uppercase border-b border-fintrust-light-border dark:border-fintrust-dark-border">
                        <tr>
                          <th className="p-2.5">Step</th>
                          <th className="p-2.5">Agent</th>
                          <th className="p-2.5">Task Objective</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-fintrust-light-border dark:divide-fintrust-dark-border">
                        {selectedWorkflow.execution_plan && selectedWorkflow.execution_plan.length > 0 ? (
                          selectedWorkflow.execution_plan.map((step, idx) => (
                            <tr key={idx} className="hover:bg-fintrust-light-subtle/30">
                              <td className="p-2.5 font-mono">{step.step || idx + 1}</td>
                              <td className="p-2.5 font-semibold text-fintrust-primary dark:text-fintrust-primary-dark">
                                {step.agent}
                              </td>
                              <td className="p-2.5 text-fintrust-slate">{step.description}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={3} className="p-3 text-center text-fintrust-slate">
                              Supervisor orchestrated {selectedWorkflow.iteration_count} iterations across {selectedWorkflow.selected_agents?.join(', ') || 'Research, Compliance, and Verification agents'}.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="p-12 text-center text-xs text-fintrust-slate">
              Select an investigation on the left or create a new investigation to view the structured compliance audit report.
            </Card>
          )}
        </div>
      </div>

      {/* New Investigation Wizard Modal */}
      <Modal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        title="Launch Autonomous Regulatory Investigation"
        description="Select the investigation scope and target policies. LangGraph multi-agent supervisor will coordinate research and verification."
        maxWidth="2xl"
      >
        <form onSubmit={handleCreateInvestigation} className="space-y-4">
          {submitError && (
            <div className="p-3 rounded bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-400 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{submitError}</span>
            </div>
          )}

          {/* Investigation Type */}
          <div>
            <label className="block text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5">
              Investigation Paradigm
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setInvestigationType('COMPLIANCE')}
                className={`p-2.5 rounded-md border text-left text-xs transition-all ${
                  investigationType === 'COMPLIANCE'
                    ? 'border-fintrust-primary bg-blue-50/50 dark:bg-blue-950/30 font-semibold text-fintrust-primary dark:text-fintrust-primary-dark'
                    : 'border-fintrust-light-border dark:border-fintrust-dark-border'
                }`}
              >
                <div className="font-semibold">Compliance Audit</div>
                <div className="text-[10px] text-fintrust-slate mt-0.5">Statutory obligations & gaps</div>
              </button>
              <button
                type="button"
                onClick={() => setInvestigationType('COMPARISON')}
                className={`p-2.5 rounded-md border text-left text-xs transition-all ${
                  investigationType === 'COMPARISON'
                    ? 'border-fintrust-primary bg-blue-50/50 dark:bg-blue-950/30 font-semibold text-fintrust-primary dark:text-fintrust-primary-dark'
                    : 'border-fintrust-light-border dark:border-fintrust-dark-border'
                }`}
              >
                <div className="font-semibold">Policy Drift Comparison</div>
                <div className="text-[10px] text-fintrust-slate mt-0.5">Thresholds & clause diffs</div>
              </button>
              <button
                type="button"
                onClick={() => setInvestigationType('RESEARCH')}
                className={`p-2.5 rounded-md border text-left text-xs transition-all ${
                  investigationType === 'RESEARCH'
                    ? 'border-fintrust-primary bg-blue-50/50 dark:bg-blue-950/30 font-semibold text-fintrust-primary dark:text-fintrust-primary-dark'
                    : 'border-fintrust-light-border dark:border-fintrust-dark-border'
                }`}
              >
                <div className="font-semibold">General Research</div>
                <div className="text-[10px] text-fintrust-slate mt-0.5">Deep multi-doc inquiry</div>
              </button>
            </div>
          </div>

          {/* Inquiry Text */}
          <Input
            label="Investigation Objective / Natural Language Inquiry"
            value={investigationQuery}
            onChange={(e) => setInvestigationQuery(e.target.value)}
            placeholder="e.g. Audit transaction monitoring compliance and verify SAR reporting thresholds..."
            required
          />

          {/* Statute Reference */}
          {investigationType === 'COMPLIANCE' && (
            <Input
              label="Statutory Framework / Regulatory Standard"
              value={statuteReference}
              onChange={(e) => setStatuteReference(e.target.value)}
              placeholder="e.g. Bank Secrecy Act / 31 CFR Chapter X / FINCEN"
            />
          )}

          {/* Target Document Selection */}
          <div>
            <label className="block text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5">
              Target Documents ({documents.length} Available)
            </label>
            <div className="max-h-36 overflow-y-auto border border-fintrust-light-border dark:border-fintrust-dark-border rounded-md divide-y divide-fintrust-light-border dark:divide-fintrust-dark-border text-xs">
              {documents.length === 0 ? (
                <div className="p-3 text-center text-fintrust-slate">
                  No documents in library. Autonomous supervisor will search all available evidence.
                </div>
              ) : (
                documents.map((d) => {
                  const isChecked = selectedDocIds.includes(d.id);
                  return (
                    <label
                      key={d.id}
                      className="p-2.5 flex items-center justify-between hover:bg-fintrust-light-subtle/50 cursor-pointer"
                    >
                      <div className="flex items-center gap-2 truncate max-w-sm">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedDocIds([...selectedDocIds, d.id]);
                            } else {
                              setSelectedDocIds(selectedDocIds.filter((id) => id !== d.id));
                            }
                          }}
                          className="rounded border-gray-300 text-fintrust-primary focus:ring-fintrust-primary"
                        />
                        <span className="truncate font-medium">{d.title}</span>
                      </div>
                      <Badge variant="slate" size="sm">
                        {d.classification}
                      </Badge>
                    </label>
                  );
                })
              )}
            </div>
          </div>

          {/* Human Signoff mandate */}
          <div className="p-3 rounded-lg border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/40 dark:bg-fintrust-dark-elevated/40 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                Mandate Human-in-the-Loop Signoff
              </div>
              <div className="text-[11px] text-fintrust-slate">
                Require compliance officer approval if contradictory thresholds are detected.
              </div>
            </div>
            <input
              type="checkbox"
              checked={requireApproval}
              onChange={(e) => setRequireApproval(e.target.checked)}
              className="w-4 h-4 rounded text-fintrust-primary"
            />
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
            <Button variant="outline" type="button" onClick={() => setIsNewModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              isLoading={isSubmitting}
              leftIcon={<BrainCircuit className="w-4 h-4" />}
            >
              Start Autonomous Run
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
