import React from 'react';
import clsx from 'clsx';

interface TabItem {
  id: string;
  label: string;
  badge?: string | number;
  icon?: React.ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (id: string) => void;
  variant?: 'underline' | 'pills';
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  variant = 'underline',
  className,
}) => {
  if (variant === 'pills') {
    return (
      <div className={clsx('flex gap-1.5 p-1 bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated rounded-lg', className)}>
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={clsx(
                'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition-all select-none',
                isActive
                  ? 'bg-white dark:bg-fintrust-dark-surface text-fintrust-primary dark:text-fintrust-primary-dark shadow-sm'
                  : 'text-fintrust-slate dark:text-fintrust-dark-muted hover:text-fintrust-light-text dark:hover:text-fintrust-dark-text'
              )}
            >
              {tab.icon && <span className="w-3.5 h-3.5">{tab.icon}</span>}
              {tab.label}
              {tab.badge !== undefined && (
                <span
                  className={clsx(
                    'text-[10px] px-1.5 py-0.2 rounded-full font-mono font-semibold',
                    isActive
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                      : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                  )}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  // Underline variant
  return (
    <div className={clsx('flex gap-6 border-b border-fintrust-light-border dark:border-fintrust-dark-border', className)}>
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={clsx(
              'flex items-center gap-2 pb-2.5 text-sm font-medium border-b-2 transition-all select-none -mb-px',
              isActive
                ? 'border-fintrust-primary dark:border-fintrust-primary-dark text-fintrust-primary dark:text-fintrust-primary-dark'
                : 'border-transparent text-fintrust-slate dark:text-fintrust-dark-muted hover:text-fintrust-light-text dark:hover:text-fintrust-dark-text hover:border-gray-300 dark:hover:border-gray-600'
            )}
          >
            {tab.icon && <span className="w-4 h-4">{tab.icon}</span>}
            {tab.label}
            {tab.badge !== undefined && (
              <span
                className={clsx(
                  'text-[11px] px-1.5 py-0.5 rounded-full font-mono font-semibold leading-none',
                  isActive
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                    : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                )}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
