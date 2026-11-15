import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  FileUp,
  ShieldCheck,
  ArrowRight,
  Layers,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { api } from '../api/client';
import { DocumentClassification } from '../types';

export const Upload: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [classification, setClassification] = useState<DocumentClassification>('INTERNAL');
  const [category, setCategory] = useState('GENERAL_COMPLIANCE');
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<any | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      selectFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      selectFile(e.target.files[0]);
    }
  };

  const selectFile = (selectedFile: File) => {
    setFile(selectedFile);
    if (!title) {
      // Auto-populate title from clean filename
      const cleanName = selectedFile.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
      setTitle(cleanName);
    }
    setUploadError(null);
    setUploadSuccess(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setUploadError('Please select a file to upload.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      const doc = await api.uploadDocument(file, title.trim() || undefined, classification, category);
      setUploadSuccess(doc);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload and process document.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b border-fintrust-light-border dark:border-fintrust-dark-border pb-5">
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text">
          Upload & Ingest Document
        </h1>
        <p className="text-xs sm:text-sm text-fintrust-slate dark:text-fintrust-dark-muted mt-1">
          Ingest policies, filings, and audit standards into the tenant vector index with heading-aware chunking.
        </p>
      </div>

      {uploadSuccess ? (
        <Card className="p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 mx-auto flex items-center justify-center">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-fintrust-light-text dark:text-fintrust-dark-text">
              Document Successfully Ingested
            </h3>
            <p className="text-xs text-fintrust-slate dark:text-fintrust-dark-muted mt-1 max-w-md mx-auto">
              "{uploadSuccess.title}" has been parsed, chunked, and embedded into pgvector HNSW with 384-dimensional dense vectors and PostgreSQL Full-Text Search.
            </p>
          </div>

          <div className="flex justify-center gap-3 pt-3">
            <Button
              variant="outline"
              onClick={() => {
                setFile(null);
                setTitle('');
                setUploadSuccess(null);
              }}
            >
              Upload Another
            </Button>
            <Button
              variant="primary"
              onClick={() => navigate('/documents')}
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              View in Library
            </Button>
          </div>
        </Card>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Error Banner */}
          {uploadError && (
            <div className="p-4 rounded-md bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 flex items-start gap-3 text-xs text-red-700 dark:text-red-400">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{uploadError}</span>
            </div>
          )}

          {/* Drag & Drop Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all ${
              isDragging
                ? 'border-fintrust-primary bg-blue-50/50 dark:bg-blue-950/20'
                : 'border-fintrust-light-border dark:border-fintrust-dark-border hover:border-fintrust-primary/60 dark:hover:border-fintrust-primary-dark/60 bg-white dark:bg-fintrust-dark-surface'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
            />
            <div className="flex flex-col items-center justify-center space-y-2">
              <div className="p-3 rounded-full bg-blue-50 dark:bg-blue-950/60 text-fintrust-primary dark:text-fintrust-primary-dark">
                <UploadCloud className="w-7 h-7" />
              </div>
              <div className="text-sm font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">
                {file ? file.name : 'Click to upload or drag & drop financial documents'}
              </div>
              <p className="text-xs text-fintrust-slate dark:text-fintrust-dark-muted">
                Supported formats: PDF, DOCX, TXT, Markdown (Max 50MB)
              </p>
              {file && (
                <div className="mt-2 text-xs font-mono text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                  <FileText className="w-4 h-4" />
                  <span>
                    Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Metadata Card */}
          <Card>
            <CardHeader>
              <CardTitle>Document Metadata & Security Controls</CardTitle>
              <CardDescription>
                Configure tenant access policy and classification tier.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                label="Document Display Title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Bank Secrecy Act AML Policy Manual 2026"
                required
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Classification */}
                <div>
                  <label className="block text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5">
                    Confidentiality Classification
                  </label>
                  <select
                    value={classification}
                    onChange={(e) => setClassification(e.target.value as DocumentClassification)}
                    className="w-full px-3 py-2 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40"
                  >
                    <option value="INTERNAL">INTERNAL (Authorized employees)</option>
                    <option value="CONFIDENTIAL">CONFIDENTIAL (Compliance & Auditors)</option>
                    <option value="RESTRICTED">RESTRICTED (Senior Officers only)</option>
                    <option value="PUBLIC">PUBLIC (Regulatory statutes & public filings)</option>
                  </select>
                </div>

                {/* Category */}
                <div>
                  <label className="block text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5">
                    Regulatory Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-elevated text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40"
                  >
                    <option value="GENERAL_COMPLIANCE">GENERAL_COMPLIANCE</option>
                    <option value="AML_BSA">AML_BSA (Anti-Money Laundering)</option>
                    <option value="LENDING_POLICIES">LENDING_POLICIES (Credit & Risk)</option>
                    <option value="AUDIT_REPORT">AUDIT_REPORT (Internal/External Audit)</option>
                    <option value="INVESTMENT_POLICY">INVESTMENT_POLICY</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Submit */}
          <div className="flex justify-end gap-3">
            <Button variant="outline" type="button" onClick={() => navigate('/documents')}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              isLoading={isUploading}
              disabled={!file || isUploading}
              leftIcon={<FileUp className="w-4 h-4" />}
            >
              Parse, Chunk & Embed Document
            </Button>
          </div>
        </form>
      )}
    </div>
  );
};
