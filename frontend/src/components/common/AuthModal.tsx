import React, { useState } from 'react';
import { ShieldCheck, UserCheck, KeyRound, AlertCircle } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { useAuth } from '../../context/AuthContext';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login } = useAuth();
  const [username, setUsername] = useState('admin@fintrust.com');
  const [password, setPassword] = useState('FinTrustAdmin2026!');
  const [tenantSlug, setTenantSlug] = useState('fintrust-demo');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);

    try {
      await login(username, password, tenantSlug);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Invalid credentials or tenant.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPreconfiguredUser = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setTenantSlug('fintrust-demo');
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="FinTrust Enterprise Authentication"
      description="Sign in to your organization's workspace to access compliance intelligence."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {errorMessage && (
          <div className="p-3 rounded-md bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 flex items-start gap-2.5 text-xs text-red-700 dark:text-red-400">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        <Input
          label="Email Address / Username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="compliance@fintrust.internal"
          leftIcon={<UserCheck className="w-4 h-4" />}
          required
        />

        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••••••"
          leftIcon={<KeyRound className="w-4 h-4" />}
          required
        />

        <Input
          label="Organization / Tenant Slug"
          type="text"
          value={tenantSlug}
          onChange={(e) => setTenantSlug(e.target.value)}
          placeholder="fintrust-demo"
          required
        />

        {/* Quick Role Selectors for convenience during verification */}
        <div className="pt-2 border-t border-fintrust-light-border dark:border-fintrust-dark-border">
          <span className="text-[11px] font-semibold text-fintrust-slate dark:text-fintrust-dark-muted block mb-2 font-mono uppercase">
            Quick Persona Login (Demo):
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <button
              type="button"
              onClick={() => handleSelectPreconfiguredUser('admin@fintrust.com', 'FinTrustAdmin2026!')}
              className="p-2 rounded border border-fintrust-light-border dark:border-fintrust-dark-border text-left hover:border-fintrust-primary dark:hover:border-fintrust-primary-dark transition-colors"
            >
              <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">System Admin</div>
              <div className="text-[10px] text-fintrust-slate truncate">admin@fintrust.com</div>
            </button>
            <button
              type="button"
              onClick={() => handleSelectPreconfiguredUser('compliance@fintrust.com', 'FinTrustCompliance2026!')}
              className="p-2 rounded border border-fintrust-light-border dark:border-fintrust-dark-border text-left hover:border-fintrust-primary dark:hover:border-fintrust-primary-dark transition-colors"
            >
              <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">Compliance Officer</div>
              <div className="text-[10px] text-fintrust-slate truncate">compliance@fintrust.com</div>
            </button>
            <button
              type="button"
              onClick={() => handleSelectPreconfiguredUser('analyst@fintrust.com', 'FinTrustAnalyst2026!')}
              className="p-2 rounded border border-fintrust-light-border dark:border-fintrust-dark-border text-left hover:border-fintrust-primary dark:hover:border-fintrust-primary-dark transition-colors"
            >
              <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">Risk Analyst</div>
              <div className="text-[10px] text-fintrust-slate truncate">analyst@fintrust.com</div>
            </button>
            <button
              type="button"
              onClick={() => handleSelectPreconfiguredUser('auditor@fintrust.com', 'FinTrustAuditor2026!')}
              className="p-2 rounded border border-fintrust-light-border dark:border-fintrust-dark-border text-left hover:border-fintrust-primary dark:hover:border-fintrust-primary-dark transition-colors"
            >
              <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text">Internal Auditor</div>
              <div className="text-[10px] text-fintrust-slate truncate">auditor@fintrust.com</div>
            </button>
          </div>
        </div>

        <div className="pt-3 flex justify-end gap-2.5">
          <Button variant="outline" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" isLoading={isLoading} leftIcon={<ShieldCheck className="w-4 h-4" />}>
            Authenticate Session
          </Button>
        </div>
      </form>
    </Modal>
  );
};
