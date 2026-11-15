/**
 * FinTrust Design System & Theme Tokens
 * Enterprise Financial Intelligence & Compliance Platform
 * Visual styling aligned with Google Cloud Console, Google Workspace & Material Design 3.
 */

export const THEME_TOKENS = {
  colors: {
    primary: {
      light: '#1A73E8',
      hover: '#1765CC',
      background: '#E8F0FE',
      dark: '#8AB4F8',
      darkHover: '#AECBFA',
    },
    navy: {
      default: '#233044',
      light: '#2C3E55',
      dark: '#1A2332',
    },
    neutral: {
      light: {
        appBg: '#F7F9FC',
        surface: '#FFFFFF',
        subtle: '#F1F3F4',
        border: '#DADCE0',
        textPrimary: '#202124',
        textSecondary: '#5F6368',
      },
      dark: {
        appBg: '#171B24',
        surface: '#202632',
        elevated: '#252D3A',
        border: '#394150',
        textPrimary: '#E8EAED',
        textSecondary: '#BDC1C6',
      },
    },
    semantic: {
      success: {
        light: '#188038',
        bgLight: '#E6F4EA',
        dark: '#81C995',
        bgDark: 'rgba(129, 201, 149, 0.15)',
      },
      warning: {
        light: '#F9AB00',
        bgLight: '#FEF7E0',
        dark: '#FDD663',
        bgDark: 'rgba(253, 214, 99, 0.15)',
      },
      danger: {
        light: '#D93025',
        bgLight: '#FCE8E6',
        dark: '#F28B82',
        bgDark: 'rgba(242, 139, 130, 0.15)',
      },
      info: {
        light: '#1A73E8',
        bgLight: '#E8F0FE',
        dark: '#8AB4F8',
        bgDark: 'rgba(138, 180, 248, 0.15)',
      },
    },
  },
  radii: {
    sm: '6px',
    md: '10px',
    lg: '14px',
    xl: '18px',
  },
} as const;

export type ThemeMode = 'light' | 'dark' | 'system';

export const COMPLIANCE_TAXONOMY = {
  CONFIRMED_REQUIREMENT: {
    label: 'Confirmed Requirement',
    color: 'emerald',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800',
  },
  POTENTIAL_GAP: {
    label: 'Potential Gap',
    color: 'rose',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800',
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'Insufficient Evidence',
    color: 'amber',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800',
  },
  REQUIRES_HUMAN_REVIEW: {
    label: 'Requires Human Review',
    color: 'purple',
    badgeClass: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800',
  },
} as const;
