import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Menu,
  Search,
  Sun,
  Moon,
  Bell,
  Building2,
  ChevronRight,
  Shield,
  LogOut,
  UserCheck,
  CheckCircle2,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { Badge } from '../ui/Badge';

interface TopbarProps {
  onOpenMobile: () => void;
  onOpenSearch: () => void;
  onOpenLoginModal: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  onOpenMobile,
  onOpenSearch,
  onOpenLoginModal,
}) => {
  const { theme, toggleTheme } = useTheme();
  const { user, tenant, logout } = useAuth();
  const location = useLocation();

  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setUserDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Format breadcrumbs from pathname
  const pathParts = location.pathname.split('/').filter(Boolean);
  const breadcrumbName =
    pathParts.length === 0
      ? 'Overview'
      : pathParts[0].charAt(0).toUpperCase() + pathParts[0].slice(1).replace('-', ' ');

  return (
    <header className="h-14 border-b border-fintrust-light-border dark:border-fintrust-dark-border bg-white dark:bg-fintrust-dark-surface px-4 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Left: Mobile hamburger & Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobile}
          className="lg:hidden p-1.5 rounded-md text-fintrust-slate hover:text-fintrust-light-text dark:text-fintrust-dark-muted dark:hover:text-fintrust-dark-text hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <Menu className="w-5 h-5" />
        </button>

        <nav className="flex items-center gap-1.5 text-xs font-medium">
          <span className="text-fintrust-slate dark:text-fintrust-dark-muted">Console</span>
          <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-fintrust-light-text dark:text-fintrust-dark-text font-semibold">
            {breadcrumbName}
          </span>
          {pathParts.length > 1 && (
            <>
              <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
              <span className="font-mono text-gray-500 truncate max-w-[120px]">
                {pathParts[1]}
              </span>
            </>
          )}
        </nav>
      </div>

      {/* Center: Global Search shortcut */}
      <div className="flex-1 max-w-md mx-4 hidden md:block">
        <button
          onClick={onOpenSearch}
          className="w-full flex items-center justify-between px-3 py-1.5 rounded-md border border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated text-xs text-fintrust-slate dark:text-fintrust-dark-muted hover:border-gray-400 dark:hover:border-gray-500 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5" />
            <span>Search policies, clauses, investigations, citations...</span>
          </div>
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded shadow-xs">
            Ctrl+K
          </kbd>
        </button>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2">
        {/* Tenant selector pill */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated border border-fintrust-light-border dark:border-fintrust-dark-border text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text">
          <Building2 className="w-3.5 h-3.5 text-fintrust-primary dark:text-fintrust-primary-dark" />
          <span className="truncate max-w-[130px]">
            {tenant?.name || 'FinTrust Production'}
          </span>
        </div>

        {/* Theme Switcher */}
        <button
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          className="p-1.5 rounded-md text-fintrust-slate hover:text-fintrust-light-text dark:text-fintrust-dark-muted dark:hover:text-fintrust-dark-text hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Notifications */}
        <button
          className="p-1.5 rounded-md text-fintrust-slate hover:text-fintrust-light-text dark:text-fintrust-dark-muted dark:hover:text-fintrust-dark-text hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors relative"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-blue-500" />
        </button>

        {/* User profile dropdown or Sign-in button */}
        {user ? (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setUserDropdownOpen(!userDropdownOpen)}
              className="flex items-center gap-2 pl-2 pr-1.5 py-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <div className="w-7 h-7 rounded-full bg-fintrust-primary/10 border border-fintrust-primary/30 flex items-center justify-center text-xs font-bold text-fintrust-primary dark:text-fintrust-primary-dark">
                {user.email.charAt(0).toUpperCase()}
              </div>
              <div className="hidden sm:flex flex-col text-left">
                <span className="text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text truncate max-w-[120px]">
                  {user.full_name || user.email.split('@')[0]}
                </span>
                <span className="text-[10px] text-fintrust-slate dark:text-fintrust-dark-muted font-mono leading-none">
                  {user.roles[0] || 'USER'}
                </span>
              </div>
            </button>

            {userDropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-md bg-white dark:bg-fintrust-dark-surface border border-fintrust-light-border dark:border-fintrust-dark-border shadow-lg py-1.5 z-50 text-xs">
                <div className="px-3.5 py-2 border-b border-fintrust-light-border dark:border-fintrust-dark-border">
                  <div className="font-semibold text-fintrust-light-text dark:text-fintrust-dark-text truncate">
                    {user.email}
                  </div>
                  <div className="flex items-center gap-1.5 mt-1">
                    <Badge variant="primary" size="sm">
                      {user.roles[0] || 'COMPLIANCE_OFFICER'}
                    </Badge>
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
                      <CheckCircle2 className="w-3 h-3" /> Active
                    </span>
                  </div>
                </div>

                <div className="py-1">
                  <button
                    onClick={() => {
                      setUserDropdownOpen(false);
                      onOpenLoginModal();
                    }}
                    className="w-full flex items-center gap-2.5 px-3.5 py-2 text-fintrust-light-text dark:text-fintrust-dark-text hover:bg-fintrust-light-subtle dark:hover:bg-fintrust-dark-elevated text-left"
                  >
                    <UserCheck className="w-3.5 h-3.5 text-fintrust-slate" />
                    Switch User / Role
                  </button>
                  <button
                    onClick={() => {
                      setUserDropdownOpen(false);
                      logout();
                    }}
                    className="w-full flex items-center gap-2.5 px-3.5 py-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 text-left"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={onOpenLoginModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-fintrust-primary hover:bg-fintrust-primary-hover text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <Shield className="w-3.5 h-3.5" />
            Sign In
          </button>
        )}
      </div>
    </header>
  );
};
