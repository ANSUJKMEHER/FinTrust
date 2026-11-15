import React, { useState, useEffect } from 'react';
import {
  GitCompare,
  FileText,
  AlertTriangle,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Bookmark,
  Layers,
  Sparkles,
  RefreshCw,
  Clock,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { api } from '../api/client';
import { DocumentItem, DocumentComparisonResponse } from '../types';

export const Comparison: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [doc1Id, setDoc1Id] = useState<string>('');
  const [doc2Id, setDoc2Id] = useState<string>('');
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<DocumentComparisonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDocs = async () => {
      try {
        const docs = await api.listDocuments({ limit: 50 });
        setDocuments(docs);
        if (docs.length >= 2) {
          setDoc1Id(docs[0].id);
          setDoc2Id(docs[1].id);
        } else if (docs.length === 1) {
          setDoc1Id(docs[0].id);
        }
      } catch (err) {
        console.error('Failed to load documents for comparison:', err);
      }
    };
    loadDocs();
  }, []);

  const handleRunComparison = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!doc1Id || !doc2Id) {
      setError('Please select both a baseline and comparison document.');
      return;
    }
    if (doc1Id === doc2Id) {
      setError('Please select two distinct documents or versions to compare.');
      return;
    }

    setIsComparing(true);
    setError(null);
    try {
      const res = await api.compareDocuments(doc1Id, doc2Id);
      setComparisonResult(res);
    } catch (err: any) {
      setError(err.message || 'Document comparison failed.');
    } finally {
      setIsComparing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
          Regulatory Policy & Version Drift Comparison
        </h1>
        <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
          Detect financial threshold changes, deadline modifications, and clause discrepancies between policy versions.
        </p>
      </div>

      {/* Selector Form Card */}
      <Card>
        <CardHeader>
          <CardTitle>Select Policy Documents to Compare</CardTitle>
          <CardDescription>
            Choose baseline policy and target revision to execute cross-encoder discrepancy detection
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRunComparison} className="space-y-4">
            {error && (
              <div className="p-3 rounded-md bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-400 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Doc 1 */}
              <div>
                <label className="block text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5">
                  Document 1 (Baseline / Original)
                </label>
                <select
                  value={doc1Id}
                  onChange={(e) => setDoc1Id(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40"
                >
                  <option value="">Select Baseline Document...</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title} (v{d.current_version_num} · {d.classification})
                    </option>
                  ))}
                </select>
              </div>

              {/* Doc 2 */}
              <div>
                <label className="block text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5">
                  Document 2 (Target Revision / Comparison)
                </label>
                <select
                  value={doc2Id}
                  onChange={(e) => setDoc2Id(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40"
                >
                  <option value="">Select Target Document...</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title} (v{d.current_version_num} · {d.classification})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                type="submit"
                variant="primary"
                isLoading={isComparing}
                disabled={!doc1Id || !doc2Id || isComparing}
                leftIcon={<GitCompare className="w-4 h-4" />}
              >
                Execute Comparative Analysis
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Comparison Results */}
      {comparisonResult && (
        <div className="space-y-6">
          {/* Summary Banner */}
          <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs">
            <div>
              <span className="font-bold text-fintrust-primary dark:text-fintrust-primary-dark">
                Comparative Finding Summary:
              </span>{' '}
              <span className="text-fintrust-light-text dark:text-fintrust-dark-text">
                Identified {comparisonResult.total_findings} modifications between "
                {comparisonResult.doc1_title}" and "{comparisonResult.doc2_title}".
              </span>
            </div>
            <div className="flex gap-2">
              {Object.entries(comparisonResult.findings_by_type || {}).map(([type, count]) => (
                <Badge key={type} variant="primary" size="sm">
                  {type}: {count}
                </Badge>
              ))}
            </div>
          </div>

          {/* Finding Cards */}
          <div className="space-y-4">
            {comparisonResult.findings.map((f, idx) => (
              <Card key={f.finding_id || idx} className="p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        f.finding_type.includes('THRESHOLD')
                          ? 'danger'
                          : f.finding_type.includes('DEADLINE')
                          ? 'warning'
                          : 'primary'
                      }
                      size="sm"
                    >
                      {f.finding_type}
                    </Badge>
                    <span className="text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                      {f.description}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-fintrust-slate">
                    Confidence: {(f.confidence_score * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Side-by-side statement diff */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-sans">
                  {/* Doc 1 Statement */}
                  <div className="p-3 rounded-md bg-gray-50 dark:bg-fintrust-dark-elevated border border-gray-200 dark:border-gray-700 space-y-1.5">
                    <div className="text-[10px] font-mono text-fintrust-slate uppercase font-semibold">
                      Baseline Statement ({comparisonResult.doc1_title})
                    </div>
                    <p className="text-fintrust-light-text dark:text-fintrust-dark-text leading-relaxed">
                      "{f.doc1_statement || 'Clause omitted or not present in baseline.'}"
                    </p>
                    {f.doc1_citation && (
                      <div className="text-[10px] text-fintrust-primary font-mono truncate">
                        Citation: [{f.doc1_citation}]
                      </div>
                    )}
                  </div>

                  {/* Doc 2 Statement */}
                  <div className="p-3 rounded-md bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 space-y-1.5">
                    <div className="text-[10px] font-mono text-fintrust-primary uppercase font-semibold">
                      Revised Target Statement ({comparisonResult.doc2_title})
                    </div>
                    <p className="text-fintrust-light-text dark:text-fintrust-dark-text leading-relaxed">
                      "{f.doc2_statement || 'Clause removed in target revision.'}"
                    </p>
                    {f.doc2_citation && (
                      <div className="text-[10px] text-fintrust-primary font-mono truncate">
                        Citation: [{f.doc2_citation}]
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
