/**
 * Virtualized trade table. TanStack Table for column model + sort, TanStack
 * Virtual for row windowing. Sticky header, keyboard nav (j/k/Enter), and a
 * focused-row indicator. Click or Enter opens the detail drawer.
 */

import { useMemo, useRef, useEffect } from 'react';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ChevronDown, ChevronUp, ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatEur, formatOdds, pnlTone } from '@/lib/format';
import type { TradeListItem } from '@/queries/trades';
import type { SortKey } from '@/queries/trades';

interface TradeTableProps {
  rows: TradeListItem[];
  sort: SortKey;
  onSortChange: (s: SortKey) => void;
  focusIdx: number;
  onFocusIdx: (i: number) => void;
  onOpenRow: (id: string) => void;
}

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

function statusToneClass(status: string): string {
  if (status === 'OPEN') return 'bg-accent-info-bg text-accent-info';
  if (status === 'CLOSED') return 'bg-bg-overlay text-text-secondary';
  return 'bg-bg-overlay text-text-tertiary';
}

export function TradeTable({
  rows,
  sort,
  onSortChange,
  focusIdx,
  onFocusIdx,
  onOpenRow,
}: TradeTableProps) {
  const sorting = useMemo<SortingState>(() => sortKeyToState(sort), [sort]);

  const columns = useMemo<ColumnDef<TradeListItem>[]>(
    () => [
      {
        id: 'kickoff_at',
        header: 'Kickoff',
        accessorFn: (r) => r.kickoff_at,
        cell: ({ row }) => (
          <span className="font-mono tabular-nums text-text-secondary">
            {dateFmt.format(new Date(row.original.kickoff_at))}
          </span>
        ),
        size: 140,
      },
      {
        id: 'match',
        header: 'Match',
        accessorFn: (r) => `${r.home_team} vs ${r.away_team}`,
        cell: ({ row }) => (
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: row.original.strategy.color_hex ?? 'var(--accent-brand)' }}
              aria-hidden
            />
            <div className="min-w-0">
              <div className="truncate text-sm text-text-primary">
                {row.original.home_team} <span className="text-text-tertiary">vs</span>{' '}
                {row.original.away_team}
              </div>
              <div className="truncate text-xs text-text-tertiary">
                {row.original.league} · {row.original.strategy.name}
              </div>
            </div>
          </div>
        ),
        size: 280,
        enableSorting: false,
      },
      {
        id: 'stake',
        header: 'Stake',
        accessorFn: (r) => Number(r.stake_total),
        cell: ({ row }) => (
          <span className="font-mono tabular-nums text-text-secondary">
            {formatEur(row.original.stake_total)}
          </span>
        ),
        size: 100,
      },
      {
        id: 'odds',
        header: 'Odds',
        accessorFn: (r) => Number(r.avg_odds),
        cell: ({ row }) => (
          <span className="font-mono tabular-nums text-text-tertiary">
            {formatOdds(row.original.avg_odds)}
          </span>
        ),
        size: 80,
        enableSorting: false,
      },
      {
        id: 'pnl',
        header: 'P/L',
        accessorFn: (r) => Number(r.computed_pnl_eur),
        cell: ({ row }) => {
          const tone = pnlTone(row.original.computed_pnl_eur);
          const v = Number(row.original.computed_pnl_eur);
          return (
            <span
              className={cn(
                'font-mono tabular-nums',
                tone === 'gain'
                  ? 'text-accent-gain'
                  : tone === 'loss'
                    ? 'text-accent-loss'
                    : 'text-text-tertiary',
              )}
            >
              {v >= 0 ? '+' : ''}
              {formatEur(row.original.computed_pnl_eur)}
            </span>
          );
        },
        size: 110,
      },
      {
        id: 'outcome',
        header: 'Outcome',
        accessorFn: (r) => r.outcome_label ?? '',
        cell: ({ row }) => (
          <span className="text-xs text-text-tertiary font-mono">
            {row.original.outcome_label ?? '—'}
          </span>
        ),
        size: 130,
        enableSorting: false,
      },
      {
        id: 'status',
        header: 'Status',
        accessorFn: (r) => r.status,
        cell: ({ row }) => (
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs font-medium',
              statusToneClass(row.original.status),
            )}
          >
            {row.original.status === 'OPEN' ? (
              <span className="h-1.5 w-1.5 rounded-full bg-accent-info pulse-dot" aria-hidden />
            ) : null}
            {row.original.status}
          </span>
        ),
        size: 90,
        enableSorting: false,
      },
    ],
    [],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: (updater) => {
      const next = typeof updater === 'function' ? updater(sorting) : updater;
      onSortChange(stateToSortKey(next));
    },
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 56,
    overscan: 8,
  });

  // Keep the focused row visible while pressing j/k.
  useEffect(() => {
    if (focusIdx < 0 || focusIdx >= rows.length) return;
    virtualizer.scrollToIndex(focusIdx, { align: 'auto' });
  }, [focusIdx, virtualizer, rows.length]);

  const totalSize = virtualizer.getTotalSize();
  const items = virtualizer.getVirtualItems();

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-elevated">
      <div ref={containerRef} className="max-h-[70vh] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-bg-elevated">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-border-subtle">
                {hg.headers.map((h) => {
                  const sortable = h.column.getCanSort();
                  const dir = h.column.getIsSorted();
                  return (
                    <th
                      key={h.id}
                      style={{ width: h.column.columnDef.size }}
                      className="h-10 px-3 text-left text-2xs uppercase tracking-widest text-text-tertiary font-medium"
                    >
                      {sortable ? (
                        <button
                          type="button"
                          onClick={h.column.getToggleSortingHandler()}
                          className="flex items-center gap-1.5 hover:text-text-secondary"
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {dir === 'asc' ? (
                            <ChevronUp size={10} strokeWidth={1.5} />
                          ) : dir === 'desc' ? (
                            <ChevronDown size={10} strokeWidth={1.5} />
                          ) : (
                            <ArrowUpDown size={10} strokeWidth={1.5} className="opacity-40" />
                          )}
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody style={{ height: totalSize, position: 'relative' }}>
            {items.map((vi) => {
              const row = table.getRowModel().rows[vi.index];
              if (!row) return null;
              const focused = vi.index === focusIdx;
              return (
                <tr
                  key={row.id}
                  data-index={vi.index}
                  ref={virtualizer.measureElement}
                  onClick={() => {
                    onFocusIdx(vi.index);
                    onOpenRow(row.original.id);
                  }}
                  className={cn(
                    'absolute left-0 right-0 cursor-pointer border-b border-border-subtle/60 hover:bg-bg-hover',
                    focused && 'bg-bg-hover ring-1 ring-inset ring-accent-brand-bg',
                  )}
                  style={{ transform: `translateY(${vi.start}px)` }}
                >
                  {row.getVisibleCells().map((c) => (
                    <td
                      key={c.id}
                      style={{ width: c.column.columnDef.size }}
                      className="h-14 px-3"
                    >
                      {flexRender(c.column.columnDef.cell, c.getContext())}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- sort key bridge -------------------------------------------------------


function sortKeyToState(key: SortKey): SortingState {
  if (key.startsWith('-')) return [{ id: key.slice(1), desc: true }];
  return [{ id: key, desc: false }];
}

function stateToSortKey(state: SortingState): SortKey {
  if (!state[0]) return '-kickoff_at';
  const id = state[0].id as 'kickoff_at' | 'pnl' | 'stake';
  return state[0].desc ? (`-${id}` as SortKey) : (id as SortKey);
}
