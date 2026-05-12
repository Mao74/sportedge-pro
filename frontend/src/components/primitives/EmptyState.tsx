import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  size?: 'sm' | 'md';
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  size = 'md',
}: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border-subtle text-center',
        size === 'sm' ? 'p-6' : 'p-10',
        className,
      )}
    >
      {Icon ? (
        <span
          className="flex h-10 w-10 items-center justify-center rounded-full bg-bg-overlay text-text-tertiary"
          aria-hidden
        >
          <Icon size={18} strokeWidth={1.5} />
        </span>
      ) : null}
      <div>
        <h3 className="text-sm font-medium text-text-primary">{title}</h3>
        {description ? (
          <p className="mt-1 max-w-md text-xs text-text-tertiary">{description}</p>
        ) : null}
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
