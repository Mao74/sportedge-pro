import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Inbox } from 'lucide-react';
import { Button, Card, EmptyState, Skeleton } from '@/components/primitives';
import { FilterBar } from '@/components/trades/FilterBar';
import { TradeTable } from '@/components/trades/TradeTable';
import { TradeDetailDrawer } from '@/components/trades/TradeDetailDrawer';
import { useTradeFilters } from '@/hooks/useTradeFilters';
import { useTradeList, type SortKey, DEFAULT_PAGE_SIZE } from '@/queries/trades';
import { useHotkey } from '@/hooks/useHotkey';
import { formatEur, formatPercent, pnlTone } from '@/lib/format';

export default function TradeLog() {
  const navigate = useNavigate();
  const { filters, setFilter, reset } = useTradeFilters();
  const list = useTradeList({
    ...filters,
    page: filters.page ?? 1,
    page_size: filters.page_size ?? DEFAULT_PAGE_SIZE,
    sort: filters.sort ?? '-kickoff_at',
  });

  const rows = list.data?.items ?? [];
  const aggregates = list.data?.aggregates;
  const total = list.data?.total ?? 0;
  const page = list.data?.page ?? 1;
  const pageSize = list.data?.page_size ?? DEFAULT_PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const [focusIdx, setFocusIdx] = useState(-1);
  const [drawerId, setDrawerId] = useState<string | null>(null);

  // Reset focus when the row set changes.
  useEffect(() => {
    setFocusIdx(rows.length > 0 ? 0 : -1);
  }, [rows.length]);

  const move = useCallback(
    (delta: number) => {
      if (rows.length === 0) return;
      setFocusIdx((curr) => {
        const next = curr < 0 ? 0 : Math.max(0, Math.min(rows.length - 1, curr + delta));
        return next;
      });
    },
    [rows.length],
  );

  // j / k / Enter / e / n
  useHotkey('j', () => move(1), { preventDefault: true });
  useHotkey('k', () => move(-1), { preventDefault: true });
  useHotkey(
    'Enter',
    () => {
      const r = rows[focusIdx];
      if (r) setDrawerId(r.id);
    },
    { preventDefault: false },
  );
  useHotkey(
    'e',
    () => {
      const r = rows[focusIdx];
      if (r) setDrawerId(r.id);
    },
    { preventDefault: true },
  );
  useHotkey('n', () => navigate('/trades/new'), { preventDefault: true });

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between gap-4">
        <div>
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Trades</div>
          <h1 className="text-2xl font-medium text-text-primary">Trade log</h1>
          <p className="text-sm text-text-secondary">
            <kbd className="rounded border border-border-subtle bg-bg-overlay px-1.5 py-0.5 font-mono text-2xs">j</kbd>{' '}
            /{' '}
            <kbd className="rounded border border-border-subtle bg-bg-overlay px-1.5 py-0.5 font-mono text-2xs">k</kbd>{' '}
            navigate ·{' '}
            <kbd className="rounded border border-border-subtle bg-bg-overlay px-1.5 py-0.5 font-mono text-2xs">Enter</kbd>{' '}
            open ·{' '}
            <kbd className="rounded border border-border-subtle bg-bg-overlay px-1.5 py-0.5 font-mono text-2xs">n</kbd>{' '}
            new trade
          </p>
        </div>
        <Button variant="primary" size="lg" onClick={() => navigate('/trades/new')}>
          New trade
        </Button>
      </header>

      <FilterBar filters={filters} setFilter={setFilter} reset={reset} total={total} />

      {list.isLoading ? (
        <Card>
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} height={48} />
            ))}
          </div>
        </Card>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No trades match these filters"
          description="Clear them to see everything, or log your first trade."
          action={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={reset}>
                Clear filters
              </Button>
              <Button variant="primary" onClick={() => navigate('/trades/new')}>
                Add trade
              </Button>
            </div>
          }
        />
      ) : (
        <TradeTable
          rows={rows}
          sort={(filters.sort ?? '-kickoff_at') as SortKey}
          onSortChange={(s) => setFilter('sort', s)}
          focusIdx={focusIdx}
          onFocusIdx={setFocusIdx}
          onOpenRow={(id) => setDrawerId(id)}
        />
      )}

      {/* Footer aggregates + pagination */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-subtle bg-bg-elevated px-4 py-3">
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm">
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Filtered set</div>
          {aggregates ? (
            <>
              <Stat label="Closed" value={String(aggregates.n_trades)} />
              <Stat
                label="Sum P/L"
                value={`${Number(aggregates.sum_pnl_eur) >= 0 ? '+' : ''}${formatEur(aggregates.sum_pnl_eur)}`}
                tone={pnlTone(aggregates.sum_pnl_eur)}
              />
              <Stat label="Stake" value={formatEur(aggregates.sum_stake_eur)} />
              <Stat
                label="ROI"
                value={formatPercent(aggregates.roi_pct, { signed: true })}
                tone={pnlTone(aggregates.roi_pct)}
              />
              <Stat label="Win rate" value={formatPercent(aggregates.win_rate_pct)} />
            </>
          ) : (
            <Skeleton width={300} height={18} />
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-tertiary font-mono tabular-nums">
            page {page} of {totalPages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onClick={() => setFilter('page', Math.max(1, page - 1))}
          >
            <ChevronLeft size={14} strokeWidth={1.5} />
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setFilter('page', page + 1)}
          >
            <ChevronRight size={14} strokeWidth={1.5} />
          </Button>
        </div>
      </div>

      <TradeDetailDrawer
        tradeId={drawerId}
        open={drawerId !== null}
        onClose={() => setDrawerId(null)}
      />
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'gain' | 'loss' | 'zero';
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-xs text-text-tertiary uppercase tracking-widest">{label}</span>
      <span
        className={
          'font-mono tabular-nums text-sm ' +
          (tone === 'gain'
            ? 'text-accent-gain'
            : tone === 'loss'
              ? 'text-accent-loss'
              : 'text-text-primary')
        }
      >
        {value}
      </span>
    </div>
  );
}
