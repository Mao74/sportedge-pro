/**
 * MetricCard with count-up on first render. Composes the primitive MetricCard
 * with our useCountUp hook so dashboards animate gracefully without making
 * the primitive opinionated.
 */

import { MetricCard } from '@/components/primitives';
import { useCountUp } from '@/hooks/useCountUp';
import { formatEur, formatPercent } from '@/lib/format';

interface AnimatedMetricProps {
  label: string;
  value: number;
  format: 'eur' | 'percent' | 'integer';
  signed?: boolean;
  delta?: string;
  deltaTone?: 'gain' | 'loss' | 'zero';
  spark?: number[];
  sparkTone?: 'gain' | 'loss' | 'brand' | 'info';
}

const intFmt = new Intl.NumberFormat('it-IT');

export function AnimatedMetric({
  label,
  value,
  format,
  signed,
  delta,
  deltaTone,
  spark,
  sparkTone,
}: AnimatedMetricProps) {
  const animated = useCountUp(value);
  let display: string;
  if (format === 'eur') display = formatEur(animated, signed ? { signed: true } : undefined);
  else if (format === 'percent')
    display = formatPercent(animated, signed ? { signed: true } : undefined);
  else display = intFmt.format(Math.round(animated));

  return (
    <MetricCard
      label={label}
      value={display}
      delta={delta}
      deltaTone={deltaTone}
      spark={spark}
      sparkTone={sparkTone}
    />
  );
}
