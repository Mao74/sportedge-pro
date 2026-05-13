/**
 * Filter chips above the trade table. Each active filter is a removable chip;
 * the search input writes the `q` filter (debounced); a "Filters" button
 * opens an expandable row with strategy, status, pnl_mode, league, date range
 * and pnl range inputs.
 */

import { useEffect, useState } from 'react';
import { Filter, Search, X } from 'lucide-react';
import { Button, Chip, Input, NumberInput } from '@/components/primitives';
import { useStrategies } from '@/queries/dashboard';
import { useAccounts } from '@/queries/accounts';
import type {
  PnlModeFilter,
  TradeFilters,
  TradeStatusFilter,
} from '@/queries/trades';

interface FilterBarProps {
  filters: TradeFilters;
  setFilter: <K extends keyof TradeFilters>(key: K, value: TradeFilters[K]) => void;
  reset: () => void;
  total: number;
}

const STATUSES: TradeStatusFilter[] = ['OPEN', 'CLOSED', 'VOID'];
const PNL_MODES: PnlModeFilter[] = ['AUTO', 'MANUAL', 'CASHOUT_ODDS'];

export function FilterBar({ filters, setFilter, reset, total }: FilterBarProps) {
  const [expanded, setExpanded] = useState(false);
  const [qDraft, setQDraft] = useState(filters.q ?? '');
  const { data: strategies } = useStrategies();
  const { data: accountsList } = useAccounts();
  const activeAccounts = accountsList?.filter((a) => !a.archived_at) ?? [];

  // Debounce the search input.
  useEffect(() => {
    const t = setTimeout(() => {
      if ((filters.q ?? '') !== qDraft) setFilter('q', qDraft || undefined);
    }, 200);
    return () => clearTimeout(t);
  }, [qDraft]);

  // Keep local input in sync with external resets.
  useEffect(() => {
    setQDraft(filters.q ?? '');
  }, [filters.q]);

  const activeChips: { key: keyof TradeFilters; label: string; value?: string }[] = [];
  if (filters.strategy_id) {
    const name =
      strategies?.find((s) => s.id === filters.strategy_id)?.name ?? filters.strategy_id;
    activeChips.push({ key: 'strategy_id', label: 'Strategy', value: name });
  }
  if (filters.account_id) {
    const name =
      activeAccounts.find((a) => a.id === filters.account_id)?.name ?? filters.account_id;
    activeChips.push({ key: 'account_id', label: 'Account', value: name });
  }
  if (filters.status) activeChips.push({ key: 'status', label: 'Status', value: filters.status });
  if (filters.pnl_mode) activeChips.push({ key: 'pnl_mode', label: 'Mode', value: filters.pnl_mode });
  if (filters.outcome_label) activeChips.push({ key: 'outcome_label', label: 'Outcome', value: filters.outcome_label });
  if (filters.league) activeChips.push({ key: 'league', label: 'League', value: filters.league });
  if (filters.date_from) activeChips.push({ key: 'date_from', label: 'From', value: filters.date_from });
  if (filters.date_to) activeChips.push({ key: 'date_to', label: 'To', value: filters.date_to });
  if (filters.pnl_min) activeChips.push({ key: 'pnl_min', label: 'P/L ≥', value: filters.pnl_min });
  if (filters.pnl_max) activeChips.push({ key: 'pnl_max', label: 'P/L ≤', value: filters.pnl_max });
  if (filters.kickoff_dow !== undefined) {
    const dow = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][filters.kickoff_dow] ?? String(filters.kickoff_dow);
    activeChips.push({ key: 'kickoff_dow', label: 'Day', value: dow });
  }
  if (filters.kickoff_hour !== undefined) {
    activeChips.push({ key: 'kickoff_hour', label: 'Hour', value: `${filters.kickoff_hour}:00` });
  }
  for (const t of filters.tag ?? []) {
    activeChips.push({ key: 'tag', label: 'tag', value: t });
  }

  const removeChip = (key: keyof TradeFilters, value?: string) => {
    if (key === 'tag' && value) {
      const next = (filters.tag ?? []).filter((t) => t !== value);
      setFilter('tag', next.length ? next : undefined);
      return;
    }
    setFilter(key, undefined);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-overlay px-3 py-1.5 text-sm">
          <Search size={14} strokeWidth={1.5} className="text-text-tertiary" />
          <input
            value={qDraft}
            onChange={(e) => setQDraft(e.target.value)}
            placeholder="Search team or notes…"
            className="w-56 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary outline-none"
          />
        </span>
        <Button
          variant="secondary"
          size="md"
          onClick={() => setExpanded((v) => !v)}
        >
          <Filter size={14} strokeWidth={1.5} />
          <span>Filters{expanded ? ' (hide)' : ''}</span>
        </Button>
        <span className="ml-auto text-xs text-text-tertiary">
          {total} trade{total === 1 ? '' : 's'} match
        </span>
        {(activeChips.length > 0 || filters.q) ? (
          <Button variant="ghost" size="md" onClick={reset}>
            <X size={12} strokeWidth={1.5} /> Clear
          </Button>
        ) : null}
      </div>

      {activeChips.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {activeChips.map((c, i) => (
            <Chip
              key={`${String(c.key)}-${c.value ?? ''}-${i}`}
              tone="brand"
              onDismiss={() => removeChip(c.key, c.value)}
            >
              {c.label}: <span className="font-mono">{c.value ?? '✓'}</span>
            </Chip>
          ))}
        </div>
      ) : null}

      {expanded ? (
        <div className="grid grid-cols-1 gap-3 rounded-lg border border-border-subtle bg-bg-overlay p-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Strategy</span>
            <select
              value={filters.strategy_id ?? ''}
              onChange={(e) => setFilter('strategy_id', e.target.value || undefined)}
              className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            >
              <option value="">— Any —</option>
              {strategies?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Account</span>
            <select
              value={filters.account_id ?? ''}
              onChange={(e) => setFilter('account_id', e.target.value || undefined)}
              className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            >
              <option value="">— Any —</option>
              {activeAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Status</span>
            <select
              value={filters.status ?? ''}
              onChange={(e) =>
                setFilter('status', (e.target.value || undefined) as TradeStatusFilter | undefined)
              }
              className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            >
              <option value="">— Any —</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">PnL mode</span>
            <select
              value={filters.pnl_mode ?? ''}
              onChange={(e) =>
                setFilter('pnl_mode', (e.target.value || undefined) as PnlModeFilter | undefined)
              }
              className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            >
              <option value="">— Any —</option>
              {PNL_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <Input
            label="League"
            value={filters.league ?? ''}
            onChange={(e) => setFilter('league', e.target.value || undefined)}
          />
          <Input
            label="Outcome label"
            value={filters.outcome_label ?? ''}
            onChange={(e) => setFilter('outcome_label', e.target.value || undefined)}
          />
          <NumberInput
            label="P/L min (€)"
            step="0.01"
            value={filters.pnl_min ?? ''}
            onChange={(e) => setFilter('pnl_min', e.target.value || undefined)}
          />
          <NumberInput
            label="P/L max (€)"
            step="0.01"
            value={filters.pnl_max ?? ''}
            onChange={(e) => setFilter('pnl_max', e.target.value || undefined)}
          />
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Date from</span>
            <input
              type="date"
              value={filters.date_from?.slice(0, 10) ?? ''}
              onChange={(e) =>
                setFilter('date_from', e.target.value ? `${e.target.value}T00:00:00+00:00` : undefined)
              }
              className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Date to</span>
            <input
              type="date"
              value={filters.date_to?.slice(0, 10) ?? ''}
              onChange={(e) =>
                setFilter('date_to', e.target.value ? `${e.target.value}T23:59:59+00:00` : undefined)
              }
              className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            />
          </label>
        </div>
      ) : null}
    </div>
  );
}
