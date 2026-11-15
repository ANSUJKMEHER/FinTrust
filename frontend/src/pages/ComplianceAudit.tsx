import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileCheck2,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  AlertCircle,
  Plus,
  RefreshCw,
  Search,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Filter,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Tabs } from '../components/ui/Tabs';
import { COMPLIANCE_TAXONOMY } from '../tokens/theme';
import { api } from '../api/client';
import { AgenticWorkflow } from '../types';

export const ComplianceAudit: React.FC = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<AgenticWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTier, setActiveTier] = useState<string>('ALL');

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const data = await api.listWorkflows({
        task_type: 'REGULATORY_COMPLIANCE',
        limit: 50,
      });
      setWorkflows(data);
    } catch (err) {
      console.error('Failed to load compliance workflows:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  // Aggregate findings across workflows into the 4 taxonomy tiers
  const confirmedObligations: any[] = [];
  const potentialGaps: any[] = [];
  const insufficientEvidence: any[] = [];
  const requiresReview: any[] = [];

  workflows.forEach((wf) => {
    const report = wf.final_report;
    if (!report) return;

    // Confirmed obligations
    (report.statutory_obligations || []).forEach((ob) => {
      confirmedObligations.push({
        title: ob,
        workflowId: wf.workflow_id,
        query: wf.query,
        tier: 'CONFIRMED_REQUIREMENT',
        date: wf.created_at,
      });
    });

    // Potential gaps
    (report.identified_gaps || []).forEach((gap) => {
      potentialGaps.push({
        title: gap,
        workflowId: wf.workflow_id,
        query: wf.query,
        tier: 'POTENTIAL_GAP',
        date: wf.created_at,
      });
    });

    // Requires review (contradictions or approval requests)
    (report.contradictory_clauses || []).forEach((c) => {
      requiresReview.push({
        title: `Discrepancy: ${c.conflict_type} between "${c.clause_a}" and "${c.clause_b}"`,
        workflowId: wf.workflow_id,
        query: wf.query,
        tier: 'REQUIRES_HUMAN_REVIEW',
        date: wf.created_at,
      });
    });

    // If workflow was refused or had insufficient evidence
    if (wf.workflow_status === 'REFUSED') {
      insufficientEvidence.push({
        title: wf.query,
        workflowId: wf.workflow_id,
        query: wf.query,
        tier: 'INSUFFICIENT_EVIDENCE',
        date: wf.created_at,
      });
    }
  });

  const totalFindings =
    confirmedObligations.length +
    potentialGaps.length +
    insufficientEvidence.length +
    requiresReview.length;

  const allFindings = [
    ...confirmedObligations,
    ...potentialGaps,
    ...insufficientEvidence,
    ...requiresReview,
  ];

  const filteredFindings = allFindings.filter((f) => {
    if (activeTier === 'ALL') return true;
    return f.tier === activeTier;
  });

  const getTierBadge = (tier: string) => {
    switch (tier) {
      case 'CONFIRMED_REQUIREMENT':
        return <Badge variant="success">CONFIRMED REQUIREMENT</Badge>;
      case 'POTENTIAL_GAP':
        return <Badge variant="danger">POTENTIAL GAP</Badge>;
      case 'REQUIRES_HUMAN_REVIEW':
        return <Badge variant="warning">REQUIRES HUMAN REVIEW</Badge>;
      case 'INSUFFICIENT_EVIDENCE':
        return <Badge variant="info">INSUFFICIENT EVIDENCE</Badge>;
      default:
        return <Badge variant="slate">{tier}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
            Compliance Audit & Obligation Governance
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            4-Tier statutory compliance taxonomy, deficit tracking, and audit-ready obligation registry.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchWorkflows}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/investigations')}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            Launch Audit Run
          </Button>
        </div>
      </div>

      {/* 4-Tier Taxonomy KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Tier 1 */}
        <Card
          className={`p-4 border-l-4 border-l-emerald-500 cursor-pointer transition-all ${
            activeTier === 'CONFIRMED_REQUIREMENT' ? 'ring-2 ring-emerald-500/30' : ''
          }`}
          onClick={() => setActiveTier('CONFIRMED_REQUIREMENT')}
        >
          <div className="flex items-center justify-between text-emerald-700 dark:text-emerald-400 mb-1">
            <span className="text-xs font-semibold">Confirmed Requirements</span>
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {confirmedObligations.length}
          </div>
          <div className="text-[11px] text-fintrust-slate mt-1">Verified with statutory citations</div>
        </Card>

        {/* Tier 2 */}
        <Card
          className={`p-4 border-l-4 border-l-red-500 cursor-pointer transition-all ${
            activeTier === 'POTENTIAL_GAP' ? 'ring-2 ring-red-500/30' : ''
          }`}
          onClick={() => setActiveTier('POTENTIAL_GAP')}
        >
          <div className="flex items-center justify-between text-red-700 dark:text-red-400 mb-1">
            <span className="text-xs font-semibold">Potential Gaps</span>
            <AlertCircle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold font-mono text-red-600 dark:text-red-400">
            {potentialGaps.length}
          </div>
          <div className="text-[11px] text-fintrust-slate mt-1">Missing clauses or coverage deficits</div>
        </Card>

        {/* Tier 3 */}
        <Card
          className={`p-4 border-l-4 border-l-purple-500 cursor-pointer transition-all ${
            activeTier === 'REQUIRES_HUMAN_REVIEW' ? 'ring-2 ring-purple-500/30' : ''
          }`}
          onClick={() => setActiveTier('REQUIRES_HUMAN_REVIEW')}
        >
          <div className="flex items-center justify-between text-purple-700 dark:text-purple-400 mb-1">
            <span className="text-xs font-semibold">Requires Human Review</span>
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold font-mono text-purple-600 dark:text-purple-400">
            {requiresReview.length}
          </div>
          <div className="text-[11px] text-fintrust-slate mt-1">Conflicting thresholds or clauses</div>
        </Card>

        {/* Tier 4 */}
        <Card
          className={`p-4 border-l-4 border-l-sky-500 cursor-pointer transition-all ${
            activeTier === 'INSUFFICIENT_EVIDENCE' ? 'ring-2 ring-sky-500/30' : ''
          }`}
          onClick={() => setActiveTier('INSUFFICIENT_EVIDENCE')}
        >
          <div className="flex items-center justify-between text-sky-700 dark:text-sky-400 mb-1">
            <span className="text-xs font-semibold">Insufficient Evidence</span>
            <HelpCircle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold font-mono text-sky-600 dark:text-sky-400">
            {insufficientEvidence.length}
          </div>
          <div className="text-[11px] text-fintrust-slate mt-1">Unsubstantiated or refused queries</div>
        </Card>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between">
        <Tabs
          variant="pills"
          tabs={[
            { id: 'ALL', label: 'All Findings', badge: totalFindings },
            { id: 'CONFIRMED_REQUIREMENT', label: 'Confirmed', badge: confirmedObligations.length },
            { id: 'POTENTIAL_GAP', label: 'Gaps', badge: potentialGaps.length },
            { id: 'REQUIRES_HUMAN_REVIEW', label: 'Review Needed', badge: requiresReview.length },
            { id: 'INSUFFICIENT_EVIDENCE', label: 'Insufficient Evidence', badge: insufficientEvidence.length },
          ]}
          activeTab={activeTier}
          onChange={setActiveTier}
        />
      </div>

      {/* Findings List */}
      <Card>
        <CardHeader>
          <CardTitle>Audited Findings Registry</CardTitle>
          <CardDescription>
            Evidence-grounded obligations and discrepancies extracted across authorized policy documents
          </CardDescription>
        </CardHeader>
        <div className="divide-y divide-fintrust-light-border dark:divide-fintrust-dark-border">
          {loading ? (
            <div className="p-8 text-center text-xs text-fintrust-slate">
              Aggregating compliance findings...
            </div>
          ) : filteredFindings.length === 0 ? (
            <div className="p-8 text-center text-xs text-fintrust-slate">
              No findings recorded under this taxonomy tier.
            </div>
          ) : (
            filteredFindings.map((finding, idx) => (
              <div
                key={idx}
                className="p-4 hover:bg-fintrust-light-subtle/30 dark:hover:bg-fintrust-dark-elevated/30 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1 max-w-2xl">
                  <div className="flex items-center gap-2">
                    {getTierBadge(finding.tier)}
                    <span className="text-[10px] text-fintrust-slate font-mono">
                      Workflow: {finding.query.slice(0, 45)}...
                    </span>
                  </div>
                  <p className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text leading-relaxed">
                    {finding.title}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate('/investigations')}
                    rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
                  >
                    View Report
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
};
