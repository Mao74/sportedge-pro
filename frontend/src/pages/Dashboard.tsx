import { useMemo, useState } from 'react';
import { Card, Segmented, Skeleton } from '@/components/primitives';
import { AnimatedMetric } from '@/components/dashboard/AnimatedMetric';
import { ByStrategyCard } from '@/components/dashboard/ByStrategyCard';
import { OpenTradesCard } from '@/components/dashboard/OpenTradesCard';
import { EquityCurve } from '@/components/analytics/EquityCurve';
import { pnlTone, formatEur } from '@/lib/format';
import {
  type BankrollRange,
  useAnalyticsSummary,
  useBankrollCurrent,
  useBankrollSeries,
} from '@/queries/dashboard';

export default function Dashboard() {
  const [range, setRange] = useState<BankrollRange>('30d');
  const bankroll = useBankrollCurrent();
  const summary = useAnalyticsSummary();
  const series = useBankrollSeries(range);

  // Sparklines for the metric cards: balance, daily P/L, ROI, win rate are derived
  // from the same daily series — keeps a single source of truth.
  const sparkBalance = useMemo(
    () => (series.data ?? []).slice(-30).map((p) => Number(p.balance_eur)),
    [series.data],
  );
  const sparkDayPnl = useMemo(
    () => (series.data ?? []).slice(-30).map((p) => Number(p.day_pnl_eur)),
    [series.data],
  );

  const sinceInceptionPnl = Number(bankroll.data?.since_inception_pnl_eur ?? 0);
  const sinceInceptionRoi = Number(bankroll.data?.since_inception_roi_pct ?? 0);

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Dashboard</div>
          <h1 className="text-2xl font-medium text-text-primary">Today's snapshot</h1>
        </div>
      </header>

      {/* Hero metric row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {bankroll.isLoading || !bankroll.data ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton height={56} />
            </Card>
          ))
        ) : (
          <>
            <AnimatedMetric
              label="Bankroll"
              value={Number(bankroll.data.balance_eur)}
              format="eur"
              delta={`Since inception ${sinceInceptionPnl >= 0 ? '+' : ''}${formatEur(sinceInceptionPnl)}`}
              deltaTone={pnlTone(sinceInceptionPnl)}
              spark={sparkBalance}
              sparkTone="brand"
            />
            <AnimatedMetric
              label="Total P/L"
              value={Number(summary.data?.total_pnl_eur ?? 0)}
              format="eur"
              signed
              delta={`${summary.data?.n_trades ?? 0} closed trades`}
              deltaTone="zero"
              spark={sparkDayPnl}
              sparkTone={pnlTone(Number(summary.data?.total_pnl_eur ?? 0)) === 'loss' ? 'loss' : 'gain'}
            />
            <AnimatedMetric
              label="ROI"
              value={sinceInceptionRoi}
              format="percent"
              signed
              delta={`Sharpe ${Number(summary.data?.sharpe ?? 0).toFixed(2)}`}
              deltaTone="zero"
              spark={sparkDayPnl}
              sparkTone={pnlTone(sinceInceptionRoi) === 'loss' ? 'loss' : 'gain'}
            />
            <AnimatedMetric
              label="Win rate"
              value={Number(summary.data?.win_rate_pct ?? 0)}
              format="percent"
              delta={`Max DD ${formatEur(Number(summary.data?.max_drawdown_eur ?? 0))}`}
              deltaTone={Number(summary.data?.max_drawdown_eur ?? 0) > 0 ? 'loss' : 'zero'}
              sparkTone="info"
            />
          </>
        )}
      </div>

      {/* Equity curve */}
      <Card
        header={
          <>
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">
              Equity curve
            </span>
            <Segmented<BankrollRange>
              size="sm"
              value={range}
              onChange={setRange}
              options={[
                { value: '7d', label: '7d' },
                { value: '30d', label: '30d' },
                { value: '90d', label: '90d' },
                { value: 'all', label: 'All' },
              ]}
            />
          </>
        }
      >
        {series.isLoading ? (
          <Skeleton height={280} />
        ) : (
          <EquityCurve data={series.data ?? []} />
        )}
      </Card>

      {/* Open trades + by-strategy */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <OpenTradesCard />
        <ByStrategyCard />
      </div>
    </div>
  );
}
