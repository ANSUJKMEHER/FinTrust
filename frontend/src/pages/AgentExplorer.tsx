import React, { useState, useEffect } from 'react';
import {
  Network,
  Layers,
  BrainCircuit,
  Search,
  ShieldCheck,
  GitMerge,
  Clock,
  CheckCircle2,
  AlertTriangle,
  PlayCircle,
  Eye,
  RefreshCw,
  Cpu,
  Coins,
  ChevronRight,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { api } from '../api/client';
import { AgenticWorkflow, WorkflowTraceItem, WorkflowTraceResponse } from '../types';

export const AgentExplorer: React.FC = () => {
  const [workflows, setWorkflows] = useState<AgenticWorkflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [traceResponse, setTraceResponse] = useState<WorkflowTraceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [tracesLoading, setTracesLoading] = useState(false);

  // Payload inspect modal
  const [inspectStep, setInspectStep] = useState<WorkflowTraceItem | null>(null);

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const data = await api.listWorkflows({ limit: 50 });
      setWorkflows(data);
      if (data.length > 0 && !selectedWorkflowId) {
        setSelectedWorkflowId(data[0].workflow_id);
      }
    } catch (err) {
      console.error('Failed to load workflows:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  useEffect(() => {
    if (!selectedWorkflowId) return;

    const fetchTraces = async () => {
      setTracesLoading(true);
      try {
        const trace = await api.getWorkflowTrace(selectedWorkflowId);
        setTraceResponse(trace);
      } catch (err) {
        console.error('Failed to load workflow trace:', err);
        setTraceResponse(null);
      } finally {
        setTracesLoading(false);
      }
    };

    fetchTraces();
  }, [selectedWorkflowId]);

  const activeWorkflow = workflows.find((w) => w.workflow_id === selectedWorkflowId);

  // Registered Agent Nodes for the supervisor graph
  const GRAPH_NODES = [
    {
      id: 'supervisor',
      name: 'Supervisor Agent',
      role: 'Orchestrator & Task Planner',
      icon: BrainCircuit,
      color: 'blue',
    },
    {
      id: 'research',
      name: 'Research Agent',
      role: 'Document & Evidence Retrieval',
      icon: Search,
      color: 'emerald',
    },
    {
      id: 'compliance_analysis',
      name: 'Compliance Analysis Agent',
      role: 'Statutory Obligations & Gaps',
      icon: ShieldCheck,
      color: 'indigo',
    },
    {
      id: 'document_intelligence',
      name: 'Document Intelligence Agent',
      role: 'Section & Threshold Analysis',
      icon: Layers,
      color: 'purple',
    },
    {
      id: 'verification',
      name: 'Verification Agent',
      role: 'Citation & Claim Faithfulness',
      icon: CheckCircle2,
      color: 'teal',
    },
    {
      id: 'conflict_resolution',
      name: 'Conflict Resolution',
      role: 'Clause Discrepancy & Threshold Drift',
      icon: GitMerge,
      color: 'amber',
    },
  ];

  const isAgentActiveInWorkflow = (nodeId: string) => {
    if (!activeWorkflow) return false;
    if (nodeId === 'supervisor') return true;
    return (activeWorkflow.selected_agents || []).some(
      (a) => a.toLowerCase().includes(nodeId) || nodeId.includes(a.toLowerCase())
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
            Multi-Agent Execution Explorer
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            Real-time telemetry, LangGraph state graph routing, and step-level token consumption.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Workflow Picker */}
          <select
            value={selectedWorkflowId || ''}
            onChange={(e) => setSelectedWorkflowId(e.target.value)}
            className="px-3 py-1.5 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40 max-w-xs truncate"
          >
            {workflows.map((wf) => (
              <option key={wf.workflow_id} value={wf.workflow_id}>
                {wf.query.slice(0, 45)}... ({wf.workflow_status})
              </option>
            ))}
          </select>

          <Button
            variant="outline"
            size="sm"
            onClick={fetchWorkflows}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Overview Telemetry Ribbon */}
      {activeWorkflow && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <Card className="p-3.5">
            <div className="flex items-center justify-between text-fintrust-slate mb-1">
              <span className="text-xs">Workflow Status</span>
              <PlayCircle className="w-4 h-4 text-fintrust-primary" />
            </div>
            <div className="text-base font-bold font-mono text-fintrust-light-text dark:text-fintrust-dark-text">
              {activeWorkflow.workflow_status}
            </div>
            <div className="text-[10px] text-fintrust-slate mt-0.5">
              Task: {activeWorkflow.task_type}
            </div>
          </Card>

          <Card className="p-3.5">
            <div className="flex items-center justify-between text-fintrust-slate mb-1">
              <span className="text-xs">Supervisor Iterations</span>
              <RefreshCw className="w-4 h-4 text-emerald-500" />
            </div>
            <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {activeWorkflow.iteration_count} / {activeWorkflow.max_iterations}
            </div>
            <div className="text-[10px] text-fintrust-slate mt-0.5">Re-planning cycles</div>
          </Card>

          <Card className="p-3.5">
            <div className="flex items-center justify-between text-fintrust-slate mb-1">
              <span className="text-xs">Total Tokens</span>
              <Coins className="w-4 h-4 text-purple-500" />
            </div>
            <div className="text-base font-bold font-mono text-fintrust-light-text dark:text-fintrust-dark-text">
              {traceResponse?.total_tokens || activeWorkflow.total_tokens_used || 0}
            </div>
            <div className="text-[10px] text-fintrust-slate mt-0.5">Prompt & completion</div>
          </Card>

          <Card className="p-3.5">
            <div className="flex items-center justify-between text-fintrust-slate mb-1">
              <span className="text-xs">Execution Latency</span>
              <Clock className="w-4 h-4 text-amber-500" />
            </div>
            <div className="text-base font-bold font-mono text-fintrust-light-text dark:text-fintrust-dark-text">
              {activeWorkflow.execution_latency_ms} ms
            </div>
            <div className="text-[10px] text-fintrust-slate mt-0.5">Total workflow runtime</div>
          </Card>
        </div>
      )}

      {/* LangGraph Architecture Graph Display */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Autonomous Multi-Agent Coordination Graph</CardTitle>
            <CardDescription>
              LangGraph StateGraph topological layout depicting delegation flow & active sub-agents
            </CardDescription>
          </div>
          <Badge variant="primary" size="sm">
            LangGraph StateGraph v1.0
          </Badge>
        </CardHeader>
        <CardContent>
          <div className="p-6 rounded-lg bg-fintrust-light-subtle/30 dark:bg-fintrust-dark-elevated/30 border border-fintrust-light-border dark:border-fintrust-dark-border">
            {/* Top Central Node: Supervisor */}
            <div className="flex flex-col items-center">
              <div className="p-4 rounded-xl border-2 border-fintrust-primary dark:border-fintrust-primary-dark bg-white dark:bg-fintrust-dark-surface shadow-md max-w-xs w-full text-center">
                <BrainCircuit className="w-6 h-6 text-fintrust-primary mx-auto mb-1.5" />
                <div className="text-xs font-bold text-fintrust-light-text dark:text-fintrust-dark-text">
                  Supervisor Agent
                </div>
                <div className="text-[10px] text-fintrust-slate mt-0.5">
                  Plan, Delegate, Synthesize & Validate
                </div>
                <div className="mt-2">
                  <Badge variant="success" size="sm">
                    ACTIVE CONTROLLER
                  </Badge>
                </div>
              </div>

              {/* Connecting Trunk Line */}
              <div className="w-0.5 h-8 bg-gray-300 dark:bg-gray-600 my-1" />

              {/* Horizontal Distribution Line */}
              <div className="w-3/4 h-0.5 bg-gray-300 dark:bg-gray-600" />

              {/* Sub-agents Fan-out Grid */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 w-full mt-3">
                {GRAPH_NODES.slice(1).map((node) => {
                  const Icon = node.icon;
                  const isActive = isAgentActiveInWorkflow(node.id);
                  return (
                    <div
                      key={node.id}
                      className={`p-3 rounded-lg border text-center transition-all ${
                        isActive
                          ? 'border-fintrust-primary/80 dark:border-fintrust-primary-dark/80 bg-white dark:bg-fintrust-dark-surface shadow-sm'
                          : 'border-dashed border-gray-300 dark:border-gray-700 bg-transparent opacity-60'
                      }`}
                    >
                      <Icon className="w-5 h-5 mx-auto mb-1 text-fintrust-slate" />
                      <div className="text-[11px] font-semibold text-fintrust-light-text dark:text-fintrust-dark-text truncate">
                        {node.name}
                      </div>
                      <div className="text-[9px] text-fintrust-slate mt-0.5 line-clamp-1">
                        {node.role}
                      </div>
                      <div className="mt-2">
                        <Badge variant={isActive ? 'success' : 'slate'} size="sm">
                          {isActive ? 'INVOKED' : 'STANDBY'}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Execution Trace Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Execution Traces & Tool Telemetry</CardTitle>
            <CardDescription>
              Step-by-step audit trail of agent decisions, tool invocations, and token metrics
            </CardDescription>
          </div>
          <span className="text-xs font-mono text-fintrust-slate">
            {traceResponse?.total_steps || 0} Trace Events
          </span>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/50 dark:bg-fintrust-dark-elevated/50 text-[10px] font-mono text-fintrust-slate dark:text-fintrust-dark-muted uppercase">
                <th className="py-2.5 px-4 font-semibold">Step</th>
                <th className="py-2.5 px-4 font-semibold">Agent</th>
                <th className="py-2.5 px-4 font-semibold">Action / Tool Call</th>
                <th className="py-2.5 px-4 font-semibold">Status</th>
                <th className="py-2.5 px-4 font-semibold">Latency</th>
                <th className="py-2.5 px-4 font-semibold">Prompt Tokens</th>
                <th className="py-2.5 px-4 font-semibold">Completion Tokens</th>
                <th className="py-2.5 px-4 font-semibold text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-fintrust-light-border dark:divide-fintrust-dark-border">
              {tracesLoading ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-xs text-fintrust-slate">
                    Loading workflow traces...
                  </td>
                </tr>
              ) : !traceResponse || traceResponse.traces.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-xs text-fintrust-slate">
                    No execution traces recorded for this workflow yet.
                  </td>
                </tr>
              ) : (
                traceResponse.traces.map((trace) => (
                  <tr
                    key={trace.step_number}
                    className="hover:bg-fintrust-light-subtle/40 dark:hover:bg-fintrust-dark-elevated/40 transition-colors"
                  >
                    <td className="py-2.5 px-4 font-mono">{trace.step_number}</td>
                    <td className="py-2.5 px-4 font-semibold text-fintrust-primary dark:text-fintrust-primary-dark">
                      {trace.agent_name}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-fintrust-light-text dark:text-fintrust-dark-text">
                      {trace.action}
                    </td>
                    <td className="py-2.5 px-4">
                      <Badge
                        variant={trace.status === 'COMPLETED' ? 'success' : 'info'}
                        size="sm"
                      >
                        {trace.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-4 font-mono text-fintrust-slate">
                      {trace.latency_ms} ms
                    </td>
                    <td className="py-2.5 px-4 font-mono text-fintrust-slate">
                      {trace.prompt_tokens}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-fintrust-slate">
                      {trace.completion_tokens}
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <button
                        onClick={() => setInspectStep(trace)}
                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-fintrust-slate hover:text-fintrust-primary"
                        title="Inspect Inputs/Outputs"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Inspect Step Payload Modal */}
      <Modal
        isOpen={!!inspectStep}
        onClose={() => setInspectStep(null)}
        title={`Trace Step #${inspectStep?.step_number}: ${inspectStep?.action}`}
        description={`Executed by ${inspectStep?.agent_name} (${inspectStep?.latency_ms}ms)`}
        maxWidth="2xl"
      >
        <div className="space-y-4 text-xs font-mono">
          <div>
            <div className="font-semibold text-fintrust-slate uppercase text-[10px] mb-1">
              Inputs (Sanitized & Redacted)
            </div>
            <pre className="p-3 rounded bg-gray-50 dark:bg-fintrust-dark-elevated border border-gray-200 dark:border-gray-700 overflow-x-auto text-[11px]">
              {JSON.stringify(inspectStep?.inputs_redacted || {}, null, 2)}
            </pre>
          </div>

          <div>
            <div className="font-semibold text-fintrust-slate uppercase text-[10px] mb-1">
              Outputs (Sanitized & Redacted)
            </div>
            <pre className="p-3 rounded bg-gray-50 dark:bg-fintrust-dark-elevated border border-gray-200 dark:border-gray-700 overflow-x-auto text-[11px]">
              {JSON.stringify(inspectStep?.outputs_redacted || {}, null, 2)}
            </pre>
          </div>

          {inspectStep?.error_details && (
            <div>
              <div className="font-semibold text-red-500 uppercase text-[10px] mb-1">
                Error Details
              </div>
              <pre className="p-3 rounded bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-[11px]">
                {inspectStep.error_details}
              </pre>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
