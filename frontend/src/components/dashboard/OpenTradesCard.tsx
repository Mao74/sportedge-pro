import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { Card, Chip, Skeleton } from '@/components/primitives';
import { formatEur, formatOdds } from '@/lib/format';
import { useOpenTrades } from '@/queries/dashboard';

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

export function OpenTradesCard({ accountId }: { accountId?: string | null } = {}) {
  const { data, isLoading } = useOpenTrades(8, accountId);

  return (
    <Card
      header={
        <>
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">Open trades</span>
          <Link
            to="/trades?status=OPEN"
            className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary"
          >
            View all <ArrowUpRight size={12} strokeWidth={1.5} />
          </Link>
        </>
      }
    >
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} height={36} />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="py-6 text-center text-sm text-text-tertiary">
          Nothing live right now.
        </div>
      ) : (
        <ul className="-my-2 divide-y divide-border-subtle">
          {data.items.map((t) => (
            <li key={t.id}>
              <Link
                to={`/trades?focus=${t.id}`}
                className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-bg-hover"
              >
                <span
                  className="flex h-2 w-2 shrink-0 rounded-full pulse-dot"
                  style={{ backgroundColor: t.strategy.color_hex ?? 'var(--accent-brand)' }}
                  aria-hidden
                />
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm text-text-primary">
                    {t.home_team} <span className="text-text-tertiary">vs</span> {t.away_team}
                  </div>
                  <div className="text-xs text-text-tertiary">
                    {t.league} · {dateFmt.format(new Date(t.kickoff_at))}
                  </div>
                </div>
                <div className="text-right font-mono tabular-nums">
                  <div className="text-xs text-text-secondary">stake {formatEur(t.stake_total)}</div>
                  <div className="text-xs text-text-tertiary">@ {formatOdds(t.avg_odds)}</div>
                </div>
                <Chip tone="brand" dot={t.strategy.color_hex ?? true}>
                  {t.strategy.name}
                </Chip>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
