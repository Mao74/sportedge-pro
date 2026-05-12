import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { Card, Skeleton } from '@/components/primitives';
import { formatEur, formatPercent, pnlTone } from '@/lib/format';
import { useByStrategy, useStrategies } from '@/queries/dashboard';

export function ByStrategyCard() {
  const { data: rows, isLoading } = useByStrategy();
  const { data: strategies } = useStrategies();

  const colorBySlug = new Map<string, string>();
  const nameBySlug = new Map<string, string>();
  for (const s of strategies ?? []) {
    if (s.color_hex) colorBySlug.set(s.slug, s.color_hex);
    nameBySlug.set(s.slug, s.name);
  }

  return (
    <Card
      header={
        <>
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">
            By strategy
          </span>
          <Link
            to="/analytics"
            className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary"
          >
            More <ArrowUpRight size={12} strokeWidth={1.5} />
          </Link>
        </>
      }
    >
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} height={32} />
          ))}
        </div>
      ) : !rows || rows.length === 0 ? (
        <div className="py-6 text-center text-sm text-text-tertiary">
          No closed trades yet.
        </div>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => {
            const tone = pnlTone(r.total_pnl_eur);
            const color = colorBySlug.get(r.key) ?? 'var(--accent-brand)';
            const name = nameBySlug.get(r.key) ?? r.key;
            return (
              <li key={r.key} className="space-y-1.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: color }}
                      aria-hidden
                    />
                    <span className="truncate text-sm text-text-primary">{name}</span>
                    <span className="text-xs text-text-tertiary">· {r.n_trades} trade{r.n_trades === 1 ? '' : 's'}</span>
                  </div>
                  <div className="flex shrink-0 items-baseline gap-3 font-mono tabular-nums">
                    <span
                      className={
                        tone === 'gain'
                          ? 'text-accent-gain'
                          : tone === 'loss'
                            ? 'text-accent-loss'
                            : 'text-text-tertiary'
                      }
                    >
                      {Number(r.total_pnl_eur) >= 0 ? '+' : ''}
                      {formatEur(r.total_pnl_eur)}
                    </span>
                    <span className="text-xs text-text-tertiary">
                      ROI {formatPercent(r.roi_pct, { signed: true })}
                    </span>
                  </div>
                </div>
                <RoiBar value={Number(r.roi_pct)} color={color} />
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function RoiBar({ value, color }: { value: number; color: string }) {
  // Map -100..+100 → 0..1 width, centered at 50%.
  const clamped = Math.max(-100, Math.min(100, value));
  const width = `${Math.abs(clamped) / 2}%`;
  const positive = value >= 0;
  return (
    <div className="relative h-1 overflow-hidden rounded-full bg-bg-hover">
      <div
        className="absolute top-0 h-full rounded-full"
        style={{
          backgroundColor: color,
          width,
          left: positive ? '50%' : `${50 - Math.abs(clamped) / 2}%`,
          opacity: 0.9,
        }}
      />
      <div className="absolute left-1/2 top-0 h-full w-px bg-border-strong" />
    </div>
  );
}
