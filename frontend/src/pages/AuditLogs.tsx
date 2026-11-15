import React, { useState, useEffect } from 'react';
import {
  ClipboardList,
  Search,
  Filter,
  RefreshCw,
  Eye,
  ShieldCheck,
  Clock,
  User,
  Database,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { api } from '../api/client';
import { AuditLog } from '../types';

export const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await api.listAuditLogs(0, 100);
      setLogs(data);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const filteredLogs = logs.filter((log) => {
    const q = searchQuery.toLowerCase();
    return (
      log.action.toLowerCase().includes(q) ||
      log.resource_type.toLowerCase().includes(q) ||
      (log.resource_id && log.resource_id.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
            Enterprise Audit & Telemetry Trail
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            Immutable system audit logs recording document ingestions, agent invocations, and human approvals.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchLogs}
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
        >
          Refresh Logs
        </Button>
      </div>

      {/* Filter and Search */}
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <Input
            placeholder="Search audit logs by action, resource type, or UUID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-4 h-4" />}
          />
        </div>
      </div>

      {/* Audit Log Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/50 dark:bg-fintrust-dark-elevated/50 text-[10px] font-mono text-fintrust-slate dark:text-fintrust-dark-muted uppercase">
                <th className="py-3 px-4 font-semibold">Timestamp</th>
                <th className="py-3 px-4 font-semibold">Action</th>
                <th className="py-3 px-4 font-semibold">Resource Type</th>
                <th className="py-3 px-4 font-semibold">Resource ID</th>
                <th className="py-3 px-4 font-semibold">Actor / User</th>
                <th className="py-3 px-4 font-semibold text-right">Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-fintrust-light-border dark:divide-fintrust-dark-border">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-xs text-fintrust-slate">
                    Loading audit trail from database...
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-xs text-fintrust-slate">
                    <ClipboardList className="w-8 h-8 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
                    <p className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                      No audit events recorded yet.
                    </p>
                    <p className="mt-1">All database mutations and agent executions write to this log.</p>
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr
                    key={log.id}
                    className="hover:bg-fintrust-light-subtle/40 dark:hover:bg-fintrust-dark-elevated/40 transition-colors"
                  >
                    <td className="py-3 px-4 font-mono text-fintrust-slate whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-fintrust-primary dark:text-fintrust-primary-dark">
                      {log.action}
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="slate" size="sm">
                        {log.resource_type}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 font-mono text-fintrust-slate text-[11px] truncate max-w-[120px]">
                      {log.resource_id || '—'}
                    </td>
                    <td className="py-3 px-4 font-mono text-fintrust-slate text-[11px] truncate max-w-[120px]">
                      {log.user_id ? log.user_id.slice(0, 8) + '...' : 'System'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-fintrust-slate hover:text-fintrust-primary"
                        title="Inspect Event Payload"
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

      {/* Inspect Event Payload Modal */}
      <Modal
        isOpen={!!selectedLog}
        onClose={() => setSelectedLog(null)}
        title={`Audit Event: ${selectedLog?.action}`}
        description={`Logged at ${selectedLog ? new Date(selectedLog.created_at).toLocaleString() : ''}`}
        maxWidth="lg"
      >
        <div className="space-y-4 text-xs font-mono">
          <div>
            <div className="font-semibold text-fintrust-slate uppercase text-[10px] mb-1">
              Metadata & IP Telemetry
            </div>
            <div className="p-3 rounded bg-gray-50 dark:bg-fintrust-dark-elevated border border-gray-200 dark:border-gray-700 space-y-1">
              <div>Tenant ID: {selectedLog?.tenant_id}</div>
              <div>Resource Type: {selectedLog?.resource_type}</div>
              <div>Resource ID: {selectedLog?.resource_id || 'N/A'}</div>
              <div>IP Address: {selectedLog?.ip_address || '127.0.0.1'}</div>
            </div>
          </div>

          <div>
            <div className="font-semibold text-fintrust-slate uppercase text-[10px] mb-1">
              Event Payload Details (JSON)
            </div>
            <pre className="p-3 rounded bg-gray-50 dark:bg-fintrust-dark-elevated border border-gray-200 dark:border-gray-700 overflow-x-auto text-[11px]">
              {JSON.stringify(selectedLog?.details || {}, null, 2)}
            </pre>
          </div>
        </div>
      </Modal>
    </div>
  );
};
