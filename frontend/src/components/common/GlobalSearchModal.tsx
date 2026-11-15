import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FileText, BrainCircuit, ShieldAlert, ArrowRight, Loader2 } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { api } from '../../api/client';

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GlobalSearchModal: React.FC<GlobalSearchModalProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const searchRes = await api.hybridSearch(query.trim(), 5);
      setResults(searchRes.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const navigateToResult = (path: string) => {
    onClose();
    navigate(path);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="2xl">
      <div className="space-y-4">
        {/* Search input form */}
        <form onSubmit={handleSearch} className="relative flex items-center">
          <Search className="absolute left-3.5 w-4 h-4 text-fintrust-slate dark:text-fintrust-dark-muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type your compliance question or search keyword..."
            autoFocus
            className="w-full pl-10 pr-24 py-2.5 rounded-lg border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-sm text-fintrust-light-text dark:text-fintrust-dark-text placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40 focus:border-fintrust-primary"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="absolute right-2 px-3 py-1 bg-fintrust-primary text-white text-xs font-medium rounded-md hover:bg-fintrust-primary-hover disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Search'}
          </button>
        </form>

        {/* Quick Links */}
        <div className="flex items-center gap-2 pt-1 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-3">
          <span className="text-[11px] font-medium text-fintrust-slate dark:text-fintrust-dark-muted font-mono uppercase">
            Quick Actions:
          </span>
          <button
            onClick={() => navigateToResult('/research')}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated text-fintrust-light-text dark:text-fintrust-dark-text hover:bg-blue-50 dark:hover:bg-blue-950/40 hover:text-fintrust-primary transition-colors"
          >
            <BrainCircuit className="w-3.5 h-3.5 text-blue-500" />
            AI Research Workspace
          </button>
          <button
            onClick={() => navigateToResult('/documents')}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated text-fintrust-light-text dark:text-fintrust-dark-text hover:bg-emerald-50 dark:hover:bg-emerald-950/40 hover:text-emerald-600 transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-emerald-500" />
            Document Library
          </button>
          <button
            onClick={() => navigateToResult('/approvals')}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated text-fintrust-light-text dark:text-fintrust-dark-text hover:bg-amber-50 dark:hover:bg-amber-950/40 hover:text-amber-600 transition-colors"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
            Approval Center
          </button>
        </div>

        {/* Search Results */}
        <div className="space-y-2 max-h-72 overflow-y-auto">
          {loading && (
            <div className="py-8 text-center text-xs text-fintrust-slate dark:text-fintrust-dark-muted flex flex-col items-center justify-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-fintrust-primary" />
              <span>Querying hybrid index (pgvector HNSW + PostgreSQL GIN)...</span>
            </div>
          )}

          {!loading && results.length > 0 && (
            <div className="space-y-2">
              <div className="text-[11px] font-mono text-fintrust-slate dark:text-fintrust-dark-muted px-1">
                Found {results.length} relevant evidence chunks:
              </div>
              {results.map((res: any, idx: number) => (
                <div
                  key={idx}
                  onClick={() => navigateToResult(`/documents`)}
                  className="p-3 rounded-lg border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-surface hover:border-fintrust-primary/60 dark:hover:border-fintrust-primary-dark/60 cursor-pointer transition-all group"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-fintrust-primary" />
                      {res.document_title || `Document Chunk #${res.chunk_index || idx + 1}`}
                    </span>
                    <span className="text-[10px] font-mono text-fintrust-slate dark:text-fintrust-dark-muted">
                      Score: {(res.score || res.relevance_score || 0.85).toFixed(3)}
                    </span>
                  </div>
                  <p className="text-xs text-fintrust-slate dark:text-fintrust-dark-muted mt-1 line-clamp-2">
                    {res.content || res.text || 'Extracted regulatory compliance text span.'}
                  </p>
                  <div className="flex items-center justify-end text-[11px] text-fintrust-primary dark:text-fintrust-primary-dark font-medium mt-1 group-hover:translate-x-1 transition-transform">
                    <span>Inspect Evidence</span>
                    <ArrowRight className="w-3 h-3 ml-1" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && results.length === 0 && query && (
            <div className="py-8 text-center text-xs text-fintrust-slate dark:text-fintrust-dark-muted">
              No matching indexed evidence chunks found for "{query}".
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};
