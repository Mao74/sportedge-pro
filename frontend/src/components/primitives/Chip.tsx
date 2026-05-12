import { type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';

export type ChipTone = 'neutral' | 'gain' | 'loss' | 'warn' | 'info' | 'brand';

interface ChipProps {
  children: ReactNode;
  tone?: ChipTone;
  onDismiss?: () => void;
  dot?: boolean | string;
  className?: string;
}

const TONE: Record<ChipTone, string> = {
  neutral: 'bg-bg-overlay text-text-secondary border-border-subtle',
  gain: 'bg-accent-gain-bg text-accent-gain border-transparent',
  loss: 'bg-accent-loss-bg text-accent-loss border-transparent',
  warn: 'bg-accent-warn-bg text-accent-warn border-transparent',
  info: 'bg-accent-info-bg text-accent-info border-transparent',
  brand: 'bg-accent-brand-bg text-accent-brand border-transparent',
};

const DOT: Record<ChipTone, string> = {
  neutral: 'bg-text-secondary',
  gain: 'bg-accent-gain',
  loss: 'bg-accent-loss',
  warn: 'bg-accent-warn',
  info: 'bg-accent-info',
  brand: 'bg-accent-brand',
};

export function Chip({ children, tone = 'neutral', onDismiss, dot, className }: ChipProps) {
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium',
        TONE[tone],
        className,
      )}
    >
      {dot ? (
        <span
          className={cn('h-1.5 w-1.5 rounded-full', typeof dot === 'string' ? '' : DOT[tone])}
          style={typeof dot === 'string' ? { backgroundColor: dot } : undefined}
        />
      ) : null}
      <span className="leading-none">{children}</span>
      {onDismiss ? (
        <button
          type="button"
          aria-label="Dismiss"
          onClick={onDismiss}
          className="-mr-1 rounded p-0.5 hover:bg-bg-hover"
        >
          <X size={12} strokeWidth={1.5} />
        </button>
      ) : null}
    </span>
  );
}
