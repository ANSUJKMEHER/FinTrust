import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  FileText,
  Clock,
  UserCheck,
  RefreshCw,
  GitCompare,
  MessageSquare,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { api } from '../api/client';
import { AgenticWorkflow } from '../types';

export const Approvals: React.FC = () => {
  const [workflows, setWorkflows] = useState<AgenticWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedWorkflow, setSelectedWorkflow] = useState<AgenticWorkflow | null>(null);

  // Decision Modal
  const [isDecisionModalOpen, setIsDecisionModalOpen] = useState(false);
  const [decisionType, setDecisionType] = useState<'APPROVED' | 'REJECTED' | 'NEEDS_REVISION'>('APPROVED');
  const [reviewerComments, setReviewerComments] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const data = await api.listWorkflows({
        approval_status: 'PENDING_APPROVAL',
        limit: 50,
      });
      setWorkflows(data);
      if (data.length > 0 && !selectedWorkflow) {
        setSelectedWorkflow(data[0]);
      } else if (data.length === 0) {
        setSelectedWorkflow(null);
      }
    } catch (err) {
      console.error('Failed to load pending approvals:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const openDecisionModal = (type: 'APPROVED' | 'REJECTED' | 'NEEDS_REVISION') => {
    setDecisionType(type);
    setReviewerComments('');
    setActionError(null);
    setIsDecisionModalOpen(true);
  };

  const handleConfirmDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWorkflow) return;

    setIsSubmitting(true);
    setActionError(null);

    try {
      await api.submitHumanApproval(
        selectedWorkflow.workflow_id,
        decisionType,
        reviewerComments.trim() || undefined
      );
      setIsDecisionModalOpen(false);
      await fetchWorkflows();
    } catch (err: any) {
      setActionError(err.message || 'Failed to submit approval decision.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
            Human-in-the-Loop Governance & Approval Center
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            Mandatory signoff gate for regulatory threshold conflicts, policy discrepancies, and compliance reports.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchWorkflows}
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
        >
          Refresh Queue
        </Button>
      </div>

      {/* Main Two-Column Approval Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Pending List (4 cols) */}
        <div className="lg:col-span-4 space-y-3">
          <div className="text-xs font-mono font-semibold text-fintrust-slate dark:text-fintrust-dark-muted uppercase px-1">
            Pending Human Signoff ({workflows.length})
          </div>

          <div className="space-y-2.5 max-h-[calc(100vh-16rem)] overflow-y-auto pr-1">
            {loading ? (
              <div className="p-8 text-center text-xs text-fintrust-slate">
                Checking approval queue...
              </div>
            ) : workflows.length === 0 ? (
              <div className="p-8 text-center text-xs text-fintrust-slate border border-dashed rounded-lg">
                <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500 mb-2" />
                <p className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                  Zero Pending Approvals
                </p>
                <p className="mt-1">All agent workflows have been reviewed or required no escalation.</p>
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
                        ? 'border-amber-500 bg-amber-50/40 dark:bg-amber-950/20 shadow-xs'
                        : 'border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-surface hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text line-clamp-2 leading-snug">
                        {wf.query}
                      </span>
                      <Badge variant="warning" size="sm">
                        SIGNOFF
                      </Badge>
                    </div>

                    <div className="flex items-center gap-2 mt-2 text-[10px] text-fintrust-slate font-mono">
                      <span>{wf.task_type.replace('_', ' ')}</span>
                      <span>·</span>
                      <span>{wf.execution_latency_ms}ms</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Detail & Signoff Action (8 cols) */}
        <div className="lg:col-span-8">
          {selectedWorkflow ? (
            <Card className="space-y-6">
              <CardHeader className="flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-fintrust-light-border dark:border-fintrust-dark-border">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="warning">SIGNOFF REQUIRED</Badge>
                    <Badge variant="slate">{selectedWorkflow.task_type}</Badge>
                  </div>
                  <CardTitle className="text-base">{selectedWorkflow.query}</CardTitle>
                  <CardDescription>
                    Workflow ID: <span className="font-mono">{selectedWorkflow.workflow_id}</span>
                  </CardDescription>
                </div>

                {/* Reviewer Action Buttons */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openDecisionModal('NEEDS_REVISION')}
                  >
                    Needs Revision
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => openDecisionModal('REJECTED')}
                  >
                    Reject Findings
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => openDecisionModal('APPROVED')}
                    leftIcon={<CheckCircle2 className="w-4 h-4" />}
                  >
                    Approve Report
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="space-y-5">
                {/* Reason for Escalation */}
                <div className="p-4 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200 space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    Autonomous Escalation Trigger:
                  </div>
                  <p className="leading-relaxed">
                    This workflow flagged potential threshold discrepancies or conflicting compliance clauses requiring explicit officer concurrence before report dissemination.
                  </p>
                </div>

                {/* Contradictory Clauses or Discrepancies */}
                {selectedWorkflow.final_report?.contradictory_clauses &&
                  selectedWorkflow.final_report.contradictory_clauses.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-mono uppercase font-bold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                        <GitCompare className="w-3.5 h-3.5" />
                        Conflicting Clauses Requiring Adjudication
                      </h4>
                      <div className="space-y-2">
                        {selectedWorkflow.final_report.contradictory_clauses.map((c, idx) => (
                          <div
                            key={idx}
                            className="p-3.5 rounded-lg border border-amber-200 dark:border-amber-800 bg-white dark:bg-fintrust-dark-elevated text-xs space-y-2"
                          >
                            <div className="font-bold text-amber-900 dark:text-amber-300">
                              Discrepancy: {c.conflict_type}
                            </div>
                            <div className="p-2.5 rounded bg-gray-50 dark:bg-gray-800 border text-fintrust-light-text dark:text-fintrust-dark-text">
                              <strong>Clause A:</strong> {c.clause_a}
                            </div>
                            <div className="p-2.5 rounded bg-gray-50 dark:bg-gray-800 border text-fintrust-light-text dark:text-fintrust-dark-text">
                              <strong>Clause B:</strong> {c.clause_b}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Executive Summary */}
                <div className="space-y-1.5">
                  <h4 className="text-xs font-mono uppercase font-bold text-fintrust-slate dark:text-fintrust-dark-muted">
                    Executive Findings Summary
                  </h4>
                  <div className="p-3 rounded-md bg-fintrust-light-subtle/40 dark:bg-fintrust-dark-elevated/40 border text-xs leading-relaxed text-fintrust-light-text dark:text-fintrust-dark-text whitespace-pre-wrap">
                    {selectedWorkflow.final_report?.executive_summary ||
                      'Executive summary generated by multi-agent research team.'}
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="p-12 text-center text-xs text-fintrust-slate">
              Select a pending item on the left to review contradictory evidence and submit a compliance signoff.
            </Card>
          )}
        </div>
      </div>

      {/* Confirmation Dialog Modal */}
      <Modal
        isOpen={isDecisionModalOpen}
        onClose={() => setIsDecisionModalOpen(false)}
        title={`Confirm Consequential Decision: ${decisionType}`}
        description="Your review decision and comments will be permanently recorded in the immutable audit log."
        maxWidth="md"
      >
        <form onSubmit={handleConfirmDecision} className="space-y-4">
          {actionError && (
            <div className="p-3 rounded bg-red-50 text-xs text-red-700 border border-red-200">
              {actionError}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5">
              Reviewer Justification / Feedback Comments
            </label>
            <textarea
              value={reviewerComments}
              onChange={(e) => setReviewerComments(e.target.value)}
              placeholder="e.g. Approved following review of updated regulatory guidance in FinCEN advisory..."
              rows={4}
              required
              className="w-full p-3 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-sans text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary"
            />
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
            <Button variant="outline" type="button" onClick={() => setIsDecisionModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant={decisionType === 'APPROVED' ? 'primary' : decisionType === 'REJECTED' ? 'danger' : 'secondary'}
              type="submit"
              isLoading={isSubmitting}
            >
              Confirm {decisionType}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
