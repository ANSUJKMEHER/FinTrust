import React from 'react';
import clsx from 'clsx';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className,
  disabled,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded-md transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-fintrust-primary/40 disabled:opacity-50 disabled:cursor-not-allowed select-none';

  const variantStyles = {
    primary:
      'bg-fintrust-primary text-white hover:bg-fintrust-primary-hover shadow-sm active:translate-y-[0.5px]',
    secondary:
      'bg-fintrust-light-subtle dark:bg-fintrust-dark-elevated text-fintrust-light-text dark:text-fintrust-dark-text hover:bg-gray-200 dark:hover:bg-gray-700/70 border border-fintrust-light-border dark:border-fintrust-dark-border',
    outline:
      'border border-fintrust-light-border dark:border-fintrust-dark-border text-fintrust-light-text dark:text-fintrust-dark-text hover:bg-fintrust-light-subtle dark:hover:bg-fintrust-dark-elevated',
    danger:
      'bg-red-600 text-white hover:bg-red-700 shadow-sm active:translate-y-[0.5px]',
    ghost:
      'text-fintrust-slate hover:text-fintrust-light-text dark:text-fintrust-dark-muted dark:hover:text-fintrust-dark-text hover:bg-fintrust-light-subtle dark:hover:bg-fintrust-dark-elevated',
  };

  const sizeStyles = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-3.5 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  };

  return (
    <button
      className={clsx(baseStyles, variantStyles[variant], sizeStyles[size], className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        leftIcon && <span className="inline-flex shrink-0">{leftIcon}</span>
      )}
      {children}
      {!isLoading && rightIcon && <span className="inline-flex shrink-0">{rightIcon}</span>}
    </button>
  );
};
