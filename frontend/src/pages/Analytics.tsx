import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Skeleton } from '@/components/primitives';
import { AnimatedMetric } from '@/components/dashboard/AnimatedMetric';
import { ByStrategyCard } from '@/components/dashboard/ByStrategyCard';
import { RollingChart } from '@/components/analytics/RollingChart';
import { DrawdownChart } from '@/components/analytics/DrawdownChart';
import { CalendarHeatmap } from '@/components/analytics/CalendarHeatmap';
import { MonteCarloWidget } from '@/components/analytics/MonteCarloWidget';
import {
  type AnalyticsFilters,
  useByLeague,
  useByOutcome,
  useByStrategy,
  useCalendar,
  useDrawdown,
  useRolling,
  useSummary,
} from '@/queries/analytics';
import { useBankrollCurrent, useStrategies } from '@/queries/dashboard';
import { formatEur, formatPercent, pnlTone } from '@/lib/format';
import { cn } from '@/lib/cn';

type Tab = 'overview' | 'drawdown' | 'monte_carlo' | 'calendar' | 'per_strategy';

const TABS: { value: Tab; label: string }[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'drawdown', label: 'Drawdown' },
  { value: 'monte_carlo', label: 'Monte Carlo' },
  { value: 'calendar', label: 'Calendar' },
  { value: 'per_strategy', label: 'Per-strategy' },
];

export default function AnalyticsPage() {
  const [tab, setTab] = useState<Tab>('overview');
  // Analytics page doesn't surface its own filter bar yet; uses the empty
  // filter set so it shows the full history. Step 14a polish can wire the
  // shared FilterBar here for parity with the trade log.
  const filters: AnalyticsFilters = {};

  return (
    <div className="space-y-6">
      <header>
        <div className="text-2xs uppercase tracking-widest text-text-tertiary">Analytics</div>
        <h1 className="text-2xl font-medium text-text-primary">Performance</h1>
        <p className="text-sm text-text-secondary">
          Whole-history aggregates. Use the trade log filters to narrow down a
          set, then jump back here from the breadcrumb.
        </p>
      </header>

      <div className="flex gap-1 border-b border-border-subtle">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            className={cn(
              'relative px-4 py-2 text-sm transition-colors',
              tab === t.value
                ? 'text-text-primary'
                : 'text-text-tertiary hover:text-text-secondary',
            )}
          >
            {t.label}
            {tab === t.value ? (
              <span className="absolute inset-x-3 -bottom-px h-px bg-accent-brand" />
            ) : null}
          </button>
        ))}
      </div>

      {tab === 'overview' ? <OverviewTab filters={filters} /> : null}
      {tab === 'drawdown' ? <DrawdownTab filters={filters} /> : null}
      {tab === 'monte_carlo' ? <MonteCarloTab filters={filters} /> : null}
      {tab === 'calendar' ? <CalendarTab filters={filters} /> : null}
      {tab === 'per_strategy' ? <PerStrategyTab filters={filters} /> : null}
    </div>
  );
}

// --- Overview --------------------------------------------------------------

function OverviewTab({ filters }: { filters: AnalyticsFilters }) {
  const summary = useSummary(filters);
  const rolling = useRolling(filters, 20);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {summary.isLoading || !summary.data ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton height={56} />
            </Card>
          ))
        ) : (
          <>
            <AnimatedMetric
              label="Total P/L"
              value={Number(summary.data.total_pnl_eur)}
              format="eur"
              signed
              delta={`${summary.data.n_trades} closed`}
              deltaTone="zero"
            />
            <AnimatedMetric
              label="ROI"
              value={Number(summary.data.roi_pct)}
              format="percent"
              signed
              delta={`Stake ${formatEur(summary.data.total_stake_eur)}`}
              deltaTone="zero"
            />
            <AnimatedMetric
              label="Win rate"
              value={Number(summary.data.win_rate_pct)}
              format="percent"
              delta={`Sharpe ${Number(summary.data.sharpe).toFixed(2)}`}
              deltaTone="zero"
            />
            <AnimatedMetric
              label="Max DD"
              value={Number(summary.data.max_drawdown_eur)}
              format="eur"
              delta={formatPercent(summary.data.max_drawdown_pct)}
              deltaTone={Number(summary.data.max_drawdown_eur) > 0 ? 'loss' : 'zero'}
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card header={<span>Rolling (window 20)</span>} className="lg:col-span-2">
          {rolling.isLoading ? <Skeleton height={240} /> : <RollingChart points={rolling.data ?? []} />}
        </Card>
        <ByStrategyCard />
      </div>
    </div>
  );
}

// --- Drawdown --------------------------------------------------------------

function DrawdownTab({ filters }: { filters: AnalyticsFilters }) {
  const dd = useDrawdown(filters);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Max drawdown €</div>
          <div className="mt-1 font-mono text-2xl tabular-nums text-accent-loss">
            {dd.data ? formatEur(dd.data.max_drawdown_eur) : '—'}
          </div>
        </Card>
        <Card>
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Max drawdown %</div>
          <div className="mt-1 font-mono text-2xl tabular-nums text-text-primary">
            {dd.data ? formatPercent(dd.data.max_drawdown_pct) : '—'}
          </div>
        </Card>
        <Card>
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Period</div>
          <div className="mt-1 font-mono text-sm text-text-secondary">
            {dd.data?.max_dd_started_at
              ? `${new Date(dd.data.max_dd_started_at).toLocaleDateString('it-IT')} → ${
                  dd.data.max_dd_ended_at
                    ? new Date(dd.data.max_dd_ended_at).toLocaleDateString('it-IT')
                    : '…'
                }`
              : '—'}
          </div>
        </Card>
      </div>
      <Card header={<span>Underwater curve</span>}>
        {dd.isLoading ? <Skeleton height={280} /> : <DrawdownChart points={dd.data?.points ?? []} />}
      </Card>
    </div>
  );
}

// --- Monte Carlo -----------------------------------------------------------

function MonteCarloTab({ filters }: { filters: AnalyticsFilters }) {
  const bankroll = useBankrollCurrent();
  return (
    <MonteCarloWidget
      filters={filters}
      defaultStartingBankroll={bankroll.data?.balance_eur ?? '1000.00'}
    />
  );
}

// --- Calendar --------------------------------------------------------------

function CalendarTab({ filters }: { filters: AnalyticsFilters }) {
  const cal = useCalendar(filters);
  return (
    <Card
      header={
        <>
          <span>Calendar heatmap (kickoff time)</span>
          <span className="text-xs text-text-tertiary">Click a cell to filter the trade log</span>
        </>
      }
    >
      {cal.isLoading ? (
        <Skeleton height={220} />
      ) : (
        <CalendarHeatmap cells={cal.data?.cells ?? []} />
      )}
    </Card>
  );
}

// --- Per-strategy ---------------------------------------------------------

function PerStrategyTab({ filters }: { filters: AnalyticsFilters }) {
  const byStrat = useByStrategy(filters);
  const byLeague = useByLeague(filters);
  const byOutcome = useByOutcome(filters);
  const { data: strategies } = useStrategies();
  const colorBySlug = new Map<string, string | null>();
  const nameBySlug = new Map<string, string>();
  for (const s of strategies ?? []) {
    colorBySlug.set(s.slug, s.color_hex);
    nameBySlug.set(s.slug, s.name);
  }

  return (
    <div className="space-y-4">
      <Card header={<span>By strategy</span>}>
        <BreakdownTable
          rows={byStrat.data ?? []}
          loading={byStrat.isLoading}
          colorByKey={(k) => colorBySlug.get(k) ?? 'var(--accent-brand)'}
          labelByKey={(k) => nameBySlug.get(k) ?? k}
          linkByKey={(k) => {
            const id = strategies?.find((s) => s.slug === k)?.id;
            return id ? `/trades?strategy_id=${id}` : null;
          }}
        />
      </Card>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card header={<span>By league</span>}>
          <BreakdownTable
            rows={byLeague.data ?? []}
            loading={byLeague.isLoading}
            linkByKey={(k) => `/trades?league=${encodeURIComponent(k)}`}
          />
        </Card>
        <Card header={<span>By outcome label</span>}>
          <BreakdownTable
            rows={byOutcome.data ?? []}
            loading={byOutcome.isLoading}
            linkByKey={(k) => (k === '(unset)' ? null : `/trades?outcome_label=${encodeURIComponent(k)}`)}
          />
        </Card>
      </div>
    </div>
  );
}

interface BreakdownProps {
  rows: { key: string; n_trades: number; total_pnl_eur: string; total_stake_eur: string; roi_pct: string; win_rate_pct: string }[];
  loading: boolean;
  colorByKey?: (k: string) => string;
  labelByKey?: (k: string) => string;
  linkByKey?: (k: string) => string | null;
}

function BreakdownTable({ rows, loading, colorByKey, labelByKey, linkByKey }: BreakdownProps) {
  if (loading) return <Skeleton height={120} />;
  if (rows.length === 0)
    return <div className="py-6 text-center text-sm text-text-tertiary">No closed trades.</div>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-2xs uppercase tracking-widest text-text-tertiary">
          <th className="px-2 py-1.5 text-left font-medium">Key</th>
          <th className="px-2 py-1.5 text-right font-medium">N</th>
          <th className="px-2 py-1.5 text-right font-medium">Stake</th>
          <th className="px-2 py-1.5 text-right font-medium">P/L</th>
          <th className="px-2 py-1.5 text-right font-medium">ROI</th>
          <th className="px-2 py-1.5 text-right font-medium">Win rate</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border-subtle">
        {rows.map((r) => {
          const tone = pnlTone(r.total_pnl_eur);
          const link = linkByKey?.(r.key);
          const KeyCell = (
            <span className="flex items-center gap-2">
              {colorByKey ? (
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: colorByKey(r.key) }}
                  aria-hidden
                />
              ) : null}
              <span className="text-text-primary">{labelByKey?.(r.key) ?? r.key}</span>
            </span>
          );
          return (
            <tr key={r.key} className="hover:bg-bg-hover">
              <td className="px-2 py-2">
                {link ? (
                  <Link to={link} className="hover:underline">
                    {KeyCell}
                  </Link>
                ) : (
                  KeyCell
                )}
              </td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-text-secondary">
                {r.n_trades}
              </td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-text-secondary">
                {formatEur(r.total_stake_eur)}
              </td>
              <td
                className={cn(
                  'px-2 py-2 text-right font-mono tabular-nums',
                  tone === 'gain' ? 'text-accent-gain' : tone === 'loss' ? 'text-accent-loss' : 'text-text-tertiary',
                )}
              >
                {Number(r.total_pnl_eur) >= 0 ? '+' : ''}
                {formatEur(r.total_pnl_eur)}
              </td>
              <td
                className={cn(
                  'px-2 py-2 text-right font-mono tabular-nums',
                  pnlTone(r.roi_pct) === 'gain'
                    ? 'text-accent-gain'
                    : pnlTone(r.roi_pct) === 'loss'
                      ? 'text-accent-loss'
                      : 'text-text-tertiary',
                )}
              >
                {formatPercent(r.roi_pct, { signed: true })}
              </td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-text-secondary">
                {formatPercent(r.win_rate_pct)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
