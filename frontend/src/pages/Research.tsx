import React, { useState } from 'react';
import {
  BrainCircuit,
  Search,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  FileText,
  ChevronRight,
  ExternalLink,
  Loader2,
  Bookmark,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Clock,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { api } from '../api/client';
import { RAGQueryResponse, Citation } from '../types';

interface ResearchMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  response?: RAGQueryResponse;
}

const SUGGESTED_QUERIES = [
  'What are the mandatory regulatory deadlines for filing Suspicious Activity Reports (SARs)?',
  'What is the minimum monetary threshold requiring enhanced customer due diligence (EDD)?',
  'Compare transaction monitoring reporting thresholds between Policy Version 1 and Version 2.',
  'What are the penalties or sanctions for willful non-compliance under the Bank Secrecy Act?',
];

export const Research: React.FC = () => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ResearchMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [evidencePanelOpen, setEvidencePanelOpen] = useState(false);

  const handleSubmit = async (q: string) => {
    if (!q.trim() || isLoading) return;

    const userMessage: ResearchMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: q.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuery('');
    setIsLoading(true);

    try {
      const response = await api.queryRAG(q.trim(), 5);

      const assistantMessage: ResearchMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        response,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // If response has citations, auto-select the first citation for inspectability
      if (response.citations && response.citations.length > 0) {
        setSelectedCitation(response.citations[0]);
        setEvidencePanelOpen(true);
      }
    } catch (err: any) {
      const errorMessage: ResearchMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `Error executing research query: ${err.message || 'Service unavailable'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-8.5rem)]">
      {/* Main Conversation Workspace */}
      <div className="flex-1 flex flex-col bg-white dark:bg-fintrust-dark-surface border border-fintrust-light-border dark:border-fintrust-dark-border rounded-lg shadow-sm overflow-hidden">
        {/* Workspace Top Header */}
        <div className="px-5 py-3.5 border-b border-fintrust-light-border dark:border-fintrust-dark-border flex items-center justify-between bg-fintrust-light-subtle/30 dark:bg-fintrust-dark-elevated/30">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-fintrust-primary/10 text-fintrust-primary dark:text-fintrust-primary-dark">
              <BrainCircuit className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                Evidence-Grounded Financial Intelligence
              </h2>
              <p className="text-[11px] text-fintrust-slate dark:text-fintrust-dark-muted font-mono">
                Hybrid Retrieval (pgvector + GIN) · Cross-Encoder Reranked
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="success" size="sm">
              <ShieldCheck className="w-3 h-3 mr-1" />
              Principled Refusal Active
            </Badge>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto py-8">
              <div className="w-12 h-12 rounded-full bg-blue-50 dark:bg-blue-950/60 flex items-center justify-center text-fintrust-primary mb-3">
                <BrainCircuit className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                FinTrust Compliance Research Assistant
              </h3>
              <p className="text-xs text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
                Ask specific questions against indexed regulatory filings, internal compliance manuals, and financial audit reports. Answers cite exact document sections.
              </p>

              {/* Suggested Questions */}
              <div className="w-full mt-6 space-y-2">
                <span className="text-[11px] font-mono text-fintrust-slate uppercase font-semibold block text-left">
                  Suggested inquiries:
                </span>
                {SUGGESTED_QUERIES.map((sq, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSubmit(sq)}
                    className="w-full text-left text-xs p-2.5 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/50 dark:bg-fintrust-dark-elevated/50 hover:border-fintrust-primary dark:hover:border-fintrust-primary-dark hover:bg-blue-50/50 dark:hover:bg-blue-950/30 transition-all flex items-center justify-between group"
                  >
                    <span className="truncate pr-2 text-fintrust-light-text dark:text-fintrust-dark-text">{sq}</span>
                    <ChevronRight className="w-3.5 h-3.5 text-gray-400 group-hover:text-fintrust-primary group-hover:translate-x-0.5 transition-all shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.sender === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                {/* Message Header */}
                <div className="flex items-center gap-2 mb-1 text-[11px] text-fintrust-slate font-mono">
                  <span>{msg.sender === 'user' ? 'You' : 'FinTrust RAG Engine'}</span>
                  <span>·</span>
                  <span>{msg.timestamp}</span>
                </div>

                {/* Bubble Body */}
                <div
                  className={`p-4 rounded-lg max-w-2xl text-xs leading-relaxed ${
                    msg.sender === 'user'
                      ? 'bg-fintrust-primary text-white font-medium'
                      : 'bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated border border-fintrust-light-border dark:border-fintrust-dark-border text-fintrust-light-text dark:text-fintrust-dark-text'
                  }`}
                >
                  {/* If assistant refused due to lack of evidence */}
                  {msg.response && !msg.response.evidence_sufficient && (
                    <div className="mb-3 p-2.5 rounded bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                      <div>
                        <div className="font-semibold">Principled Refusal Triggered</div>
                        <div className="text-[11px] mt-0.5">
                          {msg.response.refusal_reason ||
                            'Retrieved document chunks do not contain sufficient verified evidence to support a factual answer.'}
                        </div>
                      </div>
                    </div>
                  )}

                  <p className="whitespace-pre-wrap">{msg.text}</p>

                  {/* Citation pills attached to answer */}
                  {msg.response && msg.response.citations && msg.response.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-fintrust-light-border/60 dark:border-fintrust-dark-border/60">
                      <div className="text-[10px] font-mono text-fintrust-slate uppercase font-semibold mb-1.5 flex items-center justify-between">
                        <span>Verified Citations ({msg.response.citations.length})</span>
                        <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">
                          {msg.response.valid_citations ?? msg.response.citations.length}/{msg.response.total_citations ?? msg.response.citations.length} Verified
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.response.citations.map((c, cIdx) => (
                          <button
                            key={cIdx}
                            onClick={() => {
                              setSelectedCitation(c);
                              setEvidencePanelOpen(true);
                            }}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded bg-white dark:bg-fintrust-dark-surface border border-fintrust-light-border dark:border-fintrust-dark-border hover:border-fintrust-primary dark:hover:border-fintrust-primary-dark text-[11px] font-mono text-fintrust-primary dark:text-fintrust-primary-dark transition-all hover:shadow-xs"
                          >
                            <Bookmark className="w-3 h-3" />
                            <span>
                              [{c.citation_id || cIdx + 1}] {c.document_title || 'Doc'}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Latency & Telemetry */}
                  {msg.response && (
                    <div className="mt-2 text-[10px] font-mono text-fintrust-slate flex items-center gap-3">
                      <span>Model: {msg.response.model_name || 'gemini-2.5-flash'}</span>
                      <span>·</span>
                      <span>Latency: {msg.response.latency_ms ?? 0}ms</span>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {isLoading && (
            <div className="flex flex-col items-start space-y-1">
              <div className="flex items-center gap-2 text-[11px] text-fintrust-slate font-mono">
                <span>FinTrust RAG Engine</span>
                <span>·</span>
                <Clock className="w-3 h-3 animate-spin" />
              </div>
              <div className="p-4 rounded-lg bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated border border-fintrust-light-border dark:border-fintrust-dark-border text-xs flex items-center gap-3">
                <Loader2 className="w-4 h-4 animate-spin text-fintrust-primary" />
                <span>Retrieving context & running citation verification...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-surface">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit(query);
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a compliance or financial research question..."
              disabled={isLoading}
              className="flex-1 px-3.5 py-2.5 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated text-xs font-sans text-fintrust-light-text dark:text-fintrust-dark-text placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40 focus:border-fintrust-primary"
            />
            <Button
              type="submit"
              size="md"
              disabled={isLoading || !query.trim()}
              isLoading={isLoading}
              leftIcon={<Sparkles className="w-4 h-4" />}
            >
              Analyze
            </Button>
          </form>
        </div>
      </div>

      {/* Expandable Evidence Source Panel */}
      {evidencePanelOpen && (
        <div className="w-full lg:w-96 bg-white dark:bg-fintrust-dark-surface border border-fintrust-light-border dark:border-fintrust-dark-border rounded-lg shadow-sm flex flex-col overflow-hidden transition-all duration-300">
          <div className="px-4 py-3.5 border-b border-fintrust-light-border dark:border-fintrust-dark-border flex items-center justify-between bg-fintrust-light-subtle/30 dark:bg-fintrust-dark-elevated/30">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-fintrust-primary" />
              <h3 className="text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                Evidence Inspector
              </h3>
            </div>
            <button
              onClick={() => setEvidencePanelOpen(false)}
              className="text-xs text-fintrust-slate hover:text-fintrust-light-text p-1 rounded"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            {selectedCitation ? (
              <>
                <div className="space-y-1">
                  <div className="text-[11px] font-mono text-fintrust-slate uppercase font-semibold">
                    Document Source
                  </div>
                  <div className="text-xs font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                    {selectedCitation.document_title || 'Compliance Document'}
                  </div>
                  {selectedCitation.section_heading && (
                    <div className="text-[11px] text-fintrust-primary dark:text-fintrust-primary-dark font-medium">
                      Section: {selectedCitation.section_heading}
                    </div>
                  )}
                  {selectedCitation.page_number && (
                    <div className="text-[10px] text-fintrust-slate font-mono">
                      Page {selectedCitation.page_number}
                    </div>
                  )}
                </div>

                {/* Evidence Verification Status */}
                <div className="p-3 rounded-md bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated border border-fintrust-light-border dark:border-fintrust-dark-border space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-fintrust-slate">Verification Status</span>
                    <Badge variant={selectedCitation.is_valid ? 'success' : 'danger'} size="sm">
                      {selectedCitation.is_valid ? 'CONFIRMED' : 'UNVERIFIED'}
                    </Badge>
                  </div>
                  {selectedCitation.validation_error && (
                    <div className="text-[11px] text-red-500 font-mono">
                      {selectedCitation.validation_error}
                    </div>
                  )}
                </div>

                {/* Supporting Text Span */}
                <div className="space-y-1.5">
                  <div className="text-[11px] font-mono text-fintrust-slate uppercase font-semibold">
                    Verbatim Document Extract
                  </div>
                  <div className="p-3 rounded-md bg-gray-50 dark:bg-fintrust-dark-elevated border border-gray-200 dark:border-gray-700 text-xs font-sans text-fintrust-light-text dark:text-fintrust-dark-text leading-relaxed whitespace-pre-wrap">
                    "{selectedCitation.supporting_text_span || selectedCitation.raw_citation_text}"
                  </div>
                </div>

                {/* Chunk ID */}
                {selectedCitation.chunk_id && (
                  <div className="pt-2 border-t border-fintrust-light-border dark:border-fintrust-dark-border text-[10px] font-mono text-fintrust-slate truncate">
                    Chunk ID: {selectedCitation.chunk_id}
                  </div>
                )}
              </>
            ) : (
              <div className="py-12 text-center text-xs text-fintrust-slate">
                Select a citation pill in the conversation to inspect its supporting source chunk.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
