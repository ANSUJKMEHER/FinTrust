import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  UploadCloud,
  Search,
  Filter,
  RefreshCw,
  Trash2,
  Eye,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileCheck,
  ChevronRight,
  Layers,
  Sparkles,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { api } from '../api/client';
import { DocumentItem, DocumentChunk, DocumentClassification, ProcessingStatus } from '../types';

export const Documents: React.FC = () => {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [classificationFilter, setClassificationFilter] = useState<string>('ALL');

  // Inspection modal state
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [isChunkModalOpen, setIsChunkModalOpen] = useState(false);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const data = await api.listDocuments({ limit: 100 });
      setDocuments(data);
    } catch (err) {
      console.error('Failed to list documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleInspectChunks = async (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setIsChunkModalOpen(true);
    setChunksLoading(true);
    try {
      const chunkList = await api.getDocumentChunks(doc.id, 0, 50);
      setChunks(chunkList);
    } catch (err) {
      console.error('Failed to load chunks:', err);
      setChunks([]);
    } finally {
      setChunksLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this document from the tenant workspace?')) {
      return;
    }
    try {
      await api.deleteDocument(id);
      await fetchDocuments();
    } catch (err: any) {
      alert(`Deletion failed: ${err.message}`);
    }
  };

  // Filter documents
  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || doc.status === statusFilter;
    const matchesClassification =
      classificationFilter === 'ALL' || doc.classification === classificationFilter;
    return matchesSearch && matchesStatus && matchesClassification;
  });

  const getStatusBadge = (status: ProcessingStatus) => {
    switch (status) {
      case 'INDEXED':
        return <Badge variant="success">INDEXED</Badge>;
      case 'FAILED':
        return <Badge variant="danger">FAILED</Badge>;
      case 'PARSING':
      case 'CHUNKING':
      case 'EMBEDDING':
        return <Badge variant="info">{status}</Badge>;
      default:
        return <Badge variant="warning">{status}</Badge>;
    }
  };

  const getClassificationBadge = (cls: DocumentClassification) => {
    switch (cls) {
      case 'RESTRICTED':
        return <Badge variant="danger">{cls}</Badge>;
      case 'CONFIDENTIAL':
        return <Badge variant="warning">{cls}</Badge>;
      case 'INTERNAL':
        return <Badge variant="primary">{cls}</Badge>;
      default:
        return <Badge variant="slate">{cls}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
            Document Intelligence Library
          </h1>
          <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
            Manage enterprise financial policies, regulatory statutes, and inspect chunk embeddings.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchDocuments}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/upload')}
            leftIcon={<UploadCloud className="w-3.5 h-3.5" />}
          >
            Upload Document
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="w-full sm:flex-1">
          <Input
            placeholder="Search documents by title, filename, or category..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-4 h-4" />}
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40"
          >
            <option value="ALL">All Statuses</option>
            <option value="INDEXED">Indexed</option>
            <option value="PARSING">Parsing</option>
            <option value="EMBEDDING">Embedding</option>
            <option value="FAILED">Failed</option>
          </select>

          {/* Classification Filter */}
          <select
            value={classificationFilter}
            onChange={(e) => setClassificationFilter(e.target.value)}
            className="px-3 py-2 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40"
          >
            <option value="ALL">All Classifications</option>
            <option value="PUBLIC">Public</option>
            <option value="INTERNAL">Internal</option>
            <option value="CONFIDENTIAL">Confidential</option>
            <option value="RESTRICTED">Restricted</option>
          </select>
        </div>
      </div>

      {/* Documents Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/50 dark:bg-fintrust-dark-elevated/50 text-[11px] font-mono text-fintrust-slate dark:text-fintrust-dark-muted uppercase tracking-wider">
                <th className="py-3 px-4 font-semibold">Document Title</th>
                <th className="py-3 px-4 font-semibold">Classification</th>
                <th className="py-3 px-4 font-semibold">Category</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Version</th>
                <th className="py-3 px-4 font-semibold">File Size</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-fintrust-light-border dark:divide-fintrust-dark-border">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-xs text-fintrust-slate">
                    Loading indexed documents...
                  </td>
                </tr>
              ) : filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-xs text-fintrust-slate">
                    <FileText className="w-8 h-8 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
                    <p className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                      No documents found matching filters.
                    </p>
                    <p className="mt-1">Upload a PDF or regulatory doc to initiate parsing.</p>
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr
                    key={doc.id}
                    className="hover:bg-fintrust-light-subtle/40 dark:hover:bg-fintrust-dark-elevated/40 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="p-1.5 rounded bg-blue-50 dark:bg-blue-950/60 text-fintrust-primary shrink-0">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div className="truncate max-w-xs">
                          <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text truncate">
                            {doc.title}
                          </div>
                          <div className="text-[10px] text-fintrust-slate font-mono truncate">
                            {doc.original_filename}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">{getClassificationBadge(doc.classification)}</td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-[11px] text-fintrust-slate">
                        {doc.category}
                      </span>
                    </td>
                    <td className="py-3 px-4">{getStatusBadge(doc.status)}</td>
                    <td className="py-3 px-4 font-mono text-[11px]">v{doc.current_version_num}</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-fintrust-slate">
                      {(doc.file_size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleInspectChunks(doc)}
                          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-fintrust-slate hover:text-fintrust-primary transition-colors"
                          title="Inspect Chunks & Sections"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-950/50 text-fintrust-slate hover:text-red-500 transition-colors"
                          title="Delete Document"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Inspect Chunks Modal */}
      <Modal
        isOpen={isChunkModalOpen}
        onClose={() => setIsChunkModalOpen(false)}
        title={`Chunk Explorer: ${selectedDoc?.title || ''}`}
        description="Inspect heading-aware chunk boundaries, token counts, and section breadcrumbs."
        maxWidth="4xl"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs font-mono text-fintrust-slate border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-2">
            <span>Total Extracted Chunks: {chunks.length}</span>
            <span>Classification: {selectedDoc?.classification}</span>
          </div>

          {chunksLoading ? (
            <div className="py-12 text-center text-xs text-fintrust-slate flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-fintrust-primary" />
              <span>Fetching chunks from PostgreSQL database...</span>
            </div>
          ) : chunks.length === 0 ? (
            <div className="py-8 text-center text-xs text-fintrust-slate">
              No chunks indexed for this document yet.
            </div>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {chunks.map((chk, idx) => (
                <div
                  key={chk.id || idx}
                  className="p-3.5 rounded-lg border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/30 dark:bg-fintrust-dark-elevated/40 space-y-1.5 text-xs"
                >
                  <div className="flex items-center justify-between font-mono text-[11px]">
                    <span className="font-semibold text-fintrust-primary dark:text-fintrust-primary-dark flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5" />
                      Chunk #{chk.chunk_index}
                    </span>
                    <span className="text-fintrust-slate">
                      {chk.token_count} tokens {chk.page_number && `· Page ${chk.page_number}`}
                    </span>
                  </div>

                  {chk.section_heading && (
                    <div className="text-[11px] font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                      Section: {chk.section_heading}
                    </div>
                  )}

                  <p className="text-fintrust-light-text/90 dark:text-fintrust-dark-text/90 font-mono text-[11px] leading-relaxed whitespace-pre-wrap bg-white dark:bg-fintrust-dark-surface p-2.5 rounded border border-gray-100 dark:border-gray-800">
                    {chk.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
