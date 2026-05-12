import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  header?: ReactNode;
  footer?: ReactNode;
  padding?: 'sm' | 'md' | 'lg';
}

const PADDING = {
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-6',
} as const;

export function Card({
  header,
  footer,
  padding = 'md',
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border-subtle bg-bg-elevated transition-colors duration-200 hover:border-border-strong',
        className,
      )}
      {...rest}
    >
      {header ? (
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-3 text-sm text-text-secondary">
          {header}
        </div>
      ) : null}
      <div className={PADDING[padding]}>{children}</div>
      {footer ? (
        <div className="flex items-center justify-between border-t border-border-subtle px-5 py-3 text-sm text-text-secondary">
          {footer}
        </div>
      ) : null}
    </div>
  );
}
