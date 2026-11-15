import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  History,
  BrainCircuit,
  Search,
  Filter,
  RefreshCw,
  Clock,
  Coins,
  ChevronRight,
  ExternalLink,
  Layers,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { api } from '../api/client';
import { AgenticWorkflow, WorkflowStatus } from '../types';

export const WorkflowHistory: React.FC = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<AgenticWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const data = await api.listWorkflows({ limit: 100 });
      setWorkflows(data);
    } catch (err) {
      console.error('Failed to load workflow history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const filteredWorkflows = workflows.filter((wf) => {
    const matchesSearch =
      wf.query.toLowerCase().includes(searchQuery.toLowerCase()) ||
      wf.task_type.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || wf.workflow_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

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
            Multi-Agent Workflow History
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            Historical audit log of all LangGraph agent runs, iteration counts, token costs, and report outcomes.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchWorkflows}
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
        >
          Refresh History
        </Button>
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="w-full sm:flex-1">
          <Input
            placeholder="Search workflows by inquiry, task type, or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-4 h-4 text-fintrust-slate" />}
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary"
        >
          <option value="ALL">All Statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="PENDING_APPROVAL">Pending Approval</option>
          <option value="EXECUTING">Executing</option>
          <option value="FAILED">Failed</option>
        </select>
      </div>

      {/* Workflow Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/50 dark:bg-fintrust-dark-elevated/50 text-[10px] font-mono text-fintrust-slate dark:text-fintrust-dark-muted uppercase">
                <th className="py-3 px-4 font-semibold">Workflow Objective</th>
                <th className="py-3 px-4 font-semibold">Task Type</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Iterations</th>
                <th className="py-3 px-4 font-semibold">Tokens</th>
                <th className="py-3 px-4 font-semibold">Latency</th>
                <th className="py-3 px-4 font-semibold">Created At</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-fintrust-light-border dark:divide-fintrust-dark-border">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-xs text-fintrust-slate">
                    Loading workflow history...
                  </td>
                </tr>
              ) : filteredWorkflows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-xs text-fintrust-slate">
                    <History className="w-8 h-8 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
                    <p className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                      No workflows found.
                    </p>
                    <p className="mt-1">Launch an investigation or research inquiry to record execution runs.</p>
                  </td>
                </tr>
              ) : (
                filteredWorkflows.map((wf) => (
                  <tr
                    key={wf.workflow_id}
                    className="hover:bg-fintrust-light-subtle/40 dark:hover:bg-fintrust-dark-elevated/40 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="p-1.5 rounded bg-blue-50 dark:bg-blue-950/60 text-fintrust-primary shrink-0">
                          <BrainCircuit className="w-4 h-4" />
                        </div>
                        <div className="truncate max-w-sm">
                          <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text truncate">
                            {wf.query}
                          </div>
                          <div className="text-[10px] text-fintrust-slate font-mono truncate">
                            {wf.workflow_id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="slate" size="sm">
                        {wf.task_type}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">{getStatusBadge(wf.workflow_status)}</td>
                    <td className="py-3 px-4 font-mono text-fintrust-slate">
                      {wf.iteration_count}
                    </td>
                    <td className="py-3 px-4 font-mono text-fintrust-slate">
                      {wf.total_tokens_used}
                    </td>
                    <td className="py-3 px-4 font-mono text-fintrust-slate">
                      {wf.execution_latency_ms} ms
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-fintrust-slate whitespace-nowrap">
                      {new Date(wf.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate('/investigations')}
                          title="View 14-Section Report"
                        >
                          Report
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate('/agent-explorer')}
                          title="View Agent Graph Trace"
                        >
                          Trace
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
