import React from 'react';
import { NavLink } from 'react-router-dom';
import clsx from 'clsx';
import {
  LayoutDashboard,
  BrainCircuit,
  SearchCheck,
  FileCheck2,
  FolderArchive,
  UploadCloud,
  GitCompare,
  Network,
  History,
  Wrench,
  ShieldAlert,
  ClipboardList,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

interface NavGroup {
  label: string;
  items: {
    name: string;
    path: string;
    icon: React.ElementType;
    badge?: string;
  }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'WORKSPACE',
    items: [
      { name: 'Overview', path: '/', icon: LayoutDashboard },
      { name: 'AI Research', path: '/research', icon: BrainCircuit },
      { name: 'Investigations', path: '/investigations', icon: SearchCheck },
      { name: 'Compliance Audits', path: '/compliance', icon: FileCheck2 },
    ],
  },
  {
    label: 'DOCUMENTS',
    items: [
      { name: 'Document Library', path: '/documents', icon: FolderArchive },
      { name: 'Upload Documents', path: '/upload', icon: UploadCloud },
      { name: 'Version Comparison', path: '/comparison', icon: GitCompare },
    ],
  },
  {
    label: 'AGENT INTELLIGENCE',
    items: [
      { name: 'Agent Explorer', path: '/agent-explorer', icon: Network },
      { name: 'Workflow History', path: '/workflow-history', icon: History },
      { name: 'MCP Tool Activity', path: '/mcp-activity', icon: Wrench, badge: '19' },
    ],
  },
  {
    label: 'GOVERNANCE',
    items: [
      { name: 'Approval Center', path: '/approvals', icon: ShieldAlert },
      { name: 'Audit Logs', path: '/audit-logs', icon: ClipboardList },
    ],
  },
  {
    label: 'SYSTEM',
    items: [
      { name: 'Evaluation Studio', path: '/evaluation', icon: BarChart3 },
      { name: 'Settings', path: '/settings', icon: Settings },
    ],
  },
];

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}) => {
  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={clsx(
          'fixed top-0 bottom-0 left-0 z-40 flex flex-col bg-white dark:bg-fintrust-dark-surface border-r border-fintrust-light-border dark:border-fintrust-dark-border transition-all duration-300 ease-in-out select-none',
          collapsed ? 'w-16' : 'w-64',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Brand Header */}
        <div className="h-14 flex items-center justify-between px-3.5 border-b border-fintrust-light-border dark:border-fintrust-dark-border">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex items-center justify-center w-8 h-8 rounded-md bg-fintrust-primary text-white shrink-0 shadow-sm">
              <ShieldCheck className="w-5 h-5" />
            </div>
            {!collapsed && (
              <div className="flex flex-col truncate">
                <span className="text-sm font-bold tracking-tight text-fintrust-light-text dark:text-fintrust-dark-text font-sans">
                  FinTrust <span className="text-fintrust-primary dark:text-fintrust-primary-dark font-mono text-xs font-semibold">RAG</span>
                </span>
                <span className="text-[10px] text-fintrust-slate dark:text-fintrust-dark-muted truncate -mt-0.5">
                  Compliance & Intelligence
                </span>
              </div>
            )}
          </div>
          <button
            onClick={onToggleCollapse}
            className="hidden lg:flex items-center justify-center w-6 h-6 rounded text-fintrust-slate hover:text-fintrust-light-text dark:text-fintrust-dark-muted dark:hover:text-fintrust-dark-text hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-5">
          {NAV_GROUPS.map((group, groupIdx) => (
            <div key={groupIdx} className="space-y-1">
              {!collapsed && (
                <div className="px-2.5 pb-1 text-[10px] font-bold tracking-wider text-fintrust-slate/80 dark:text-fintrust-dark-muted/80 font-mono uppercase">
                  {group.label}
                </div>
              )}
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => {
                      if (window.innerWidth < 1024) onCloseMobile();
                    }}
                    title={collapsed ? item.name : undefined}
                    className={({ isActive }) =>
                      clsx(
                        'flex items-center gap-3 px-2.5 py-2 rounded-md text-xs font-medium transition-all group relative',
                        isActive
                          ? 'bg-fintrust-primary-light dark:bg-fintrust-primary/15 text-fintrust-primary dark:text-fintrust-primary-dark font-semibold'
                          : 'text-fintrust-light-text/80 dark:text-fintrust-dark-text/80 hover:bg-fintrust-light-subtle dark:hover:bg-fintrust-dark-elevated hover:text-fintrust-light-text dark:hover:text-fintrust-dark-text'
                      )
                    }
                  >
                    <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105" />
                    {!collapsed && (
                      <span className="flex-1 truncate tracking-tight">{item.name}</span>
                    )}
                    {!collapsed && item.badge && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-mono font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </div>

        {/* Environment / Tenant status footer */}
        <div className="p-3 border-t border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/40 dark:bg-fintrust-dark-elevated/40">
          {!collapsed ? (
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[11px] font-mono text-fintrust-slate dark:text-fintrust-dark-muted truncate">
                  PostgreSQL 16 · Online
                </span>
              </div>
              <span className="text-[10px] font-mono px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-300">
                v1.0
              </span>
            </div>
          ) : (
            <div className="flex justify-center">
              <span className="w-2 h-2 rounded-full bg-emerald-500" title="System Online" />
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
