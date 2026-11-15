import React, { useState, useEffect } from 'react';
import {
  Wrench,
  Search,
  BrainCircuit,
  ShieldCheck,
  Layers,
  CheckCircle2,
  Lock,
  RefreshCw,
  ExternalLink,
  Code,
  Terminal,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Tabs } from '../components/ui/Tabs';
import { Modal } from '../components/ui/Modal';
import { api } from '../api/client';
import { MCPToolInfo } from '../types';

export const MCPActivity: React.FC = () => {
  const [tools, setTools] = useState<MCPToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string>('ALL');
  const [selectedTool, setSelectedTool] = useState<MCPToolInfo | null>(null);

  const fetchTools = async () => {
    setLoading(true);
    try {
      const data = await api.listMCPTools();
      setTools(data);
    } catch (err) {
      console.error('Failed to load MCP tools:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTools();
  }, []);

  const categories = ['ALL', 'Research', 'Intelligence', 'Verification', 'Workflow'];

  const filteredTools = tools.filter(
    (t) => activeCategory === 'ALL' || t.category.toLowerCase() === activeCategory.toLowerCase()
  );

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'Research':
        return <Search className="w-4 h-4 text-emerald-500" />;
      case 'Intelligence':
        return <BrainCircuit className="w-4 h-4 text-blue-500" />;
      case 'Verification':
        return <ShieldCheck className="w-4 h-4 text-purple-500" />;
      case 'Workflow':
        return <Layers className="w-4 h-4 text-amber-500" />;
      default:
        return <Wrench className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
            Model Context Protocol (MCP) Tool Registry
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            Official Model Context Protocol server exposing 19 verified tools to autonomous sub-agents.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchTools}
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
        >
          Refresh Registry
        </Button>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center justify-between">
        <Tabs
          variant="pills"
          tabs={categories.map((c) => ({
            id: c,
            label: c,
            badge: c === 'ALL' ? tools.length : tools.filter((t) => t.category.toLowerCase() === c.toLowerCase()).length,
          }))}
          activeTab={activeCategory}
          onChange={setActiveCategory}
        />

        <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-fintrust-slate">
          <Lock className="w-3.5 h-3.5 text-emerald-500" />
          <span>Tenant Boundary Guard Enforced</span>
        </div>
      </div>

      {/* Tool Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="p-4 space-y-2">
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 animate-pulse" />
              <div className="h-10 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
            </Card>
          ))
        ) : filteredTools.length === 0 ? (
          <div className="col-span-full py-12 text-center text-xs text-fintrust-slate">
            No tools found for category "{activeCategory}".
          </div>
        ) : (
          filteredTools.map((tool) => (
            <Card
              key={tool.name}
              className="p-4 hoverEffect flex flex-col justify-between cursor-pointer"
              onClick={() => setSelectedTool(tool)}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {getCategoryIcon(tool.category)}
                    <Badge variant="primary" size="sm">
                      {tool.category}
                    </Badge>
                  </div>
                  <Badge variant="success" size="sm">
                    VERIFIED SAFE
                  </Badge>
                </div>

                <h3 className="text-sm font-bold font-mono text-fintrust-light-text dark:text-fintrust-dark-text">
                  {tool.name}
                </h3>
                <p className="text-xs text-fintrust-slate dark:text-fintrust-dark-muted mt-1 leading-relaxed">
                  {tool.description}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-fintrust-light-border dark:border-fintrust-dark-border flex items-center justify-between text-[11px] font-mono text-fintrust-slate">
                <span>{Object.keys(tool.parameters).length} Parameters</span>
                <span className="text-fintrust-primary dark:text-fintrust-primary-dark font-medium flex items-center gap-1">
                  Inspect Spec <Code className="w-3.5 h-3.5" />
                </span>
              </div>
            </Card>
          ))
        )}
      </div>

      {/* Tool Parameter Specification Modal */}
      <Modal
        isOpen={!!selectedTool}
        onClose={() => setSelectedTool(null)}
        title={`MCP Tool: ${selectedTool?.name || ''}`}
        description={`Domain: ${selectedTool?.category} · Official FinTrust MCP Protocol`}
        maxWidth="lg"
      >
        <div className="space-y-4 text-xs font-sans">
          <div>
            <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text mb-1">
              Description
            </div>
            <p className="text-fintrust-slate dark:text-fintrust-dark-muted leading-relaxed">
              {selectedTool?.description}
            </p>
          </div>

          <div>
            <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5 flex items-center justify-between">
              <span>Expected JSON Schema Parameters</span>
              <span className="font-mono text-[10px] text-emerald-600">Strict Type Validation</span>
            </div>
            <div className="p-3 rounded-md bg-gray-50 dark:bg-fintrust-dark-elevated border border-gray-200 dark:border-gray-700 font-mono text-[11px] space-y-2">
              {selectedTool &&
                Object.entries(selectedTool.parameters).map(([key, val]) => (
                  <div key={key} className="flex items-start justify-between">
                    <span className="font-bold text-fintrust-primary dark:text-fintrust-primary-dark">
                      {key}:
                    </span>
                    <span className="text-fintrust-slate">{String(val)}</span>
                  </div>
                ))}
            </div>
          </div>

          <div className="p-3 rounded-md bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-[11px] text-blue-800 dark:text-blue-300">
            <strong>Security Sandbox:</strong> This tool executes inside an isolated Python ContextVar boundary tied to the authenticated tenant UUID and active workflow ID.
          </div>
        </div>
      </Modal>
    </div>
  );
};
