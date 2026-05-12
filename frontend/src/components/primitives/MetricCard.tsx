import { type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Sparkline } from './Sparkline';

interface MetricCardProps {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  deltaTone?: 'gain' | 'loss' | 'zero';
  spark?: number[];
  sparkTone?: 'gain' | 'loss' | 'brand' | 'info';
  className?: string;
}

const DELTA_TONE = {
  gain: 'text-accent-gain',
  loss: 'text-accent-loss',
  zero: 'text-text-tertiary',
} as const;

const SPARK_TONE = {
  gain: 'text-accent-gain',
  loss: 'text-accent-loss',
  brand: 'text-accent-brand',
  info: 'text-accent-info',
} as const;

export function MetricCard({
  label,
  value,
  delta,
  deltaTone = 'zero',
  spark,
  sparkTone = 'brand',
  className,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border-subtle bg-bg-elevated p-5',
        'transition-colors duration-200 hover:border-border-strong',
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="text-2xs uppercase tracking-widest text-text-tertiary">{label}</div>
        {spark && spark.length > 1 ? (
          <Sparkline values={spark} className={SPARK_TONE[sparkTone]} />
        ) : null}
      </div>
      <div className="mt-3 font-mono text-2xl font-medium tabular-nums tracking-tight text-text-primary">
        {value}
      </div>
      {delta ? (
        <div className={cn('mt-1 font-mono text-xs tabular-nums', DELTA_TONE[deltaTone])}>
          {delta}
        </div>
      ) : null}
    </div>
  );
}
