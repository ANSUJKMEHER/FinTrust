import React from 'react';
import clsx from 'clsx';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  error?: string;
  label?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, leftIcon, rightIcon, error, label, id, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={id}
            className="block text-xs font-medium text-fintrust-light-text dark:text-fintrust-dark-text mb-1.5"
          >
            {label}
          </label>
        )}
        <div className="relative flex items-center w-full">
          {leftIcon && (
            <span className="absolute left-3 text-fintrust-slate dark:text-fintrust-dark-muted pointer-events-none">
              {leftIcon}
            </span>
          )}
          <input
            id={id}
            ref={ref}
            className={clsx(
              'w-full rounded-md border text-sm font-sans px-3 py-2 bg-white dark:bg-fintrust-dark-elevated text-fintrust-light-text dark:text-fintrust-dark-text placeholder:text-gray-400 dark:placeholder:text-gray-500 transition-colors focus:outline-none focus:ring-2 focus:ring-fintrust-primary/30 focus:border-fintrust-primary dark:focus:border-fintrust-primary-dark',
              error
                ? 'border-red-500 focus:ring-red-500/20'
                : 'border-fintrust-light-border dark:border-fintrust-dark-border',
              leftIcon && 'pl-9',
              rightIcon && 'pr-9',
              className
            )}
            {...props}
          />
          {rightIcon && (
            <span className="absolute right-3 text-fintrust-slate dark:text-fintrust-dark-muted">
              {rightIcon}
            </span>
          )}
        </div>
        {error && <p className="text-xs text-red-500 mt-1 font-sans">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
