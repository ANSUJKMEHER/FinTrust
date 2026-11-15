import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  User,
  Building2,
  Cpu,
  Sliders,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Database,
  Layers,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { api } from '../api/client';

export const Settings: React.FC = () => {
  const { user, tenant } = useAuth();
  const { theme, setTheme } = useTheme();

  const [llmHealth, setLlmHealth] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchLLMHealth = async () => {
    setLoading(true);
    try {
      const res = await api.getLLMHealth();
      setLlmHealth(res);
    } catch (err) {
      console.error('Failed to get LLM health:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLLMHealth();
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
          Enterprise Platform Settings
        </h1>
        <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
          Manage user profiles, tenant isolation boundaries, and AI provider configurations.
        </p>
      </div>

      {/* User Profile Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-fintrust-primary" />
            <CardTitle>User Identity & Role-Based Access Control</CardTitle>
          </div>
          <Badge variant="success" size="sm">
            AUTHENTICATED
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-sans">
            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Email Address</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-mono">
                {user?.email || 'compliance@fintrust.internal'}
              </div>
            </div>

            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Full Name</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated">
                {user?.full_name || 'Senior Compliance Officer'}
              </div>
            </div>

            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Assigned RBAC Roles</span>
              <div className="flex gap-1.5 flex-wrap">
                {(user?.roles || ['COMPLIANCE_OFFICER']).map((r) => (
                  <Badge key={r} variant="primary" size="sm">
                    {r}
                  </Badge>
                ))}
              </div>
            </div>

            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">User UUID</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-mono text-[11px] truncate">
                {user?.id || '9f81ca7b-3d62-4217-b088-7e3e7f4c3291'}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tenant Workspace Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-indigo-500" />
            <CardTitle>Tenant Boundary & Data Isolation</CardTitle>
          </div>
          <Badge variant="primary" size="sm">
            STRICT TENANT ISOLATION
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4 text-xs font-sans">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Tenant Name</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-semibold">
                {tenant?.name || 'FinTrust Primary Enterprise'}
              </div>
            </div>

            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Tenant ID (UUID)</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-mono text-[11px] truncate">
                {tenant?.id || user?.tenant_id || '7c9a6321-4f11-4a25-9988-bb31a92e88a0'}
              </div>
            </div>
          </div>
          <p className="text-[11px] text-fintrust-slate dark:text-fintrust-dark-muted">
            All PostgreSQL vector queries, GIN index scans, and document chunk retrievals automatically enforce SQL WHERE filters restricting rows strictly to this tenant UUID.
          </p>
        </CardContent>
      </Card>

      {/* Appearance & Theme Settings */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-amber-500" />
            <CardTitle>Interface Appearance & Theme</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <div>
              <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                Theme Mode
              </div>
              <div className="text-[11px] text-fintrust-slate">
                Select your preferred visual style (Google Material Design 3 inspired).
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant={theme === 'light' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setTheme('light')}
              >
                Light
              </Button>
              <Button
                variant={theme === 'dark' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setTheme('dark')}
              >
                Dark
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI Provider & Embeddings Telemetry */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-500" />
            <CardTitle>LLM Provider & Vector Engine Configuration</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchLLMHealth}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
          >
            Check Provider
          </Button>
        </CardHeader>
        <CardContent className="space-y-4 text-xs font-sans">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">LLM Provider</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-mono">
                {llmHealth?.provider || 'Google Gemini'}
              </div>
            </div>

            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Active Model</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-mono">
                {llmHealth?.model || 'gemini-2.5-pro / mock-fallback'}
              </div>
            </div>

            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Embedding Model</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-mono">
                BAAI/bge-small-en-v1.5 (384 dimensions)
              </div>
            </div>

            <div>
              <span className="font-semibold text-fintrust-slate block mb-1">Vector Index Algorithm</span>
              <div className="p-2.5 rounded border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated font-mono">
                PostgreSQL pgvector HNSW (Cosine Distance)
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
