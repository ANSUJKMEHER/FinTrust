import React, { useEffect } from 'react';
import clsx from 'clsx';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '4xl';
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = 'lg',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidthStyles = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '4xl': 'max-w-4xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-[2px] transition-opacity"
        onClick={onClose}
      />

      {/* Modal Dialog */}
      <div
        className={clsx(
          'relative w-full bg-white dark:bg-fintrust-dark-surface border border-fintrust-light-border dark:border-fintrust-dark-border rounded-lg shadow-xl z-10 overflow-hidden transform transition-all duration-200',
          maxWidthStyles[maxWidth]
        )}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border flex items-start justify-between">
          <div>
            {title && (
              <h3 className="text-base font-semibold text-fintrust-light-text dark:text-fintrust-dark-text tracking-tight">
                {title}
              </h3>
            )}
            {description && (
              <p className="text-xs text-fintrust-slate dark:text-fintrust-dark-muted mt-0.5">
                {description}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-fintrust-slate hover:text-fintrust-light-text dark:text-fintrust-dark-muted dark:hover:text-fintrust-dark-text p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[75vh] overflow-y-auto">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="px-6 py-3.5 border-t border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/50 dark:bg-fintrust-dark-elevated/50 flex items-center justify-end gap-2.5">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
