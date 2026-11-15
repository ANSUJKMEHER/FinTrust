import React from 'react';
import clsx from 'clsx';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  hoverEffect?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className,
  hoverEffect = false,
  ...props
}) => {
  return (
    <div
      className={clsx(
        'bg-white dark:bg-fintrust-dark-surface border border-fintrust-light-border dark:border-fintrust-dark-border rounded-md shadow-[0_1px_2px_rgba(0,0,0,0.04)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.3)] transition-all duration-200',
        hoverEffect && 'hover:border-fintrust-primary/60 dark:hover:border-fintrust-primary-dark/60 hover:shadow-sm',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div
      className={clsx('px-5 py-4 border-b border-fintrust-light-border dark:border-fintrust-dark-border flex items-center justify-between', className)}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <h3
      className={clsx('text-base font-semibold text-fintrust-light-text dark:text-fintrust-dark-text tracking-tight', className)}
      {...props}
    >
      {children}
    </h3>
  );
};

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <p
      className={clsx('text-xs text-fintrust-slate dark:text-fintrust-dark-muted mt-0.5', className)}
      {...props}
    >
      {children}
    </p>
  );
};

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div className={clsx('p-5', className)} {...props}>
      {children}
    </div>
  );
};

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div
      className={clsx('px-5 py-3 border-t border-fintrust-light-border dark:border-fintrust-dark-border bg-fintrust-light-subtle/40 dark:bg-fintrust-dark-elevated/40 rounded-b-md flex items-center justify-between', className)}
      {...props}
    >
      {children}
    </div>
  );
};
