/**
 * Monte Carlo widget. Param inputs at the top, big risk-of-ruin number,
 * percentile callouts, and a histogram of ending bankrolls. Recompute is
 * triggered manually with the "Run simulation" button (10k×100 typically
 * completes in ~700-1200ms).
 */

import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Play } from 'lucide-react';
import { Button, Card, NumberInput } from '@/components/primitives';
import { formatEur, formatPercent, pnlTone } from '@/lib/format';
import {
  type AnalyticsFilters,
  type MonteCarloResponse,
  useMonteCarlo,
} from '@/queries/analytics';

interface Props {
  filters: AnalyticsFilters;
  defaultStartingBankroll: string;
}

export function MonteCarloWidget({ filters, defaultStartingBankroll }: Props) {
  const [starting, setStarting] = useState(defaultStartingBankroll);
  const [nSims, setNSims] = useState('10000');
  const [horizon, setHorizon] = useState('100');
  const [ruinPct, setRuinPct] = useState('50');
  const [seed, setSeed] = useState('');

  const mc = useMonteCarlo(filters);
  const [last, setLast] = useState<MonteCarloResponse | null>(null);
  const [tookMs, setTookMs] = useState<number | null>(null);

  useEffect(() => {
    setStarting(defaultStartingBankroll);
  }, [defaultStartingBankroll]);

  const run = async () => {
    const t0 = performance.now();
    const result = await mc.mutateAsync({
      starting_bankroll: starting || '0',
      n_simulations: Number(nSims) || 10_000,
      horizon_trades: Number(horizon) || 100,
      ruin_threshold_pct: ruinPct || '50',
      seed: seed ? Number(seed) : undefined,
    });
    setLast(result);
    setTookMs(performance.now() - t0);
  };

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[300px_1fr]">
      {/* Inputs */}
      <Card header={<span>Parameters</span>}>
        <div className="space-y-3">
          <NumberInput
            label="Starting bankroll (€)"
            step="0.01"
            value={starting}
            onChange={(e) => setStarting(e.target.value)}
          />
          <NumberInput
            label="Simulations"
            step="1"
            value={nSims}
            onChange={(e) => setNSims(e.target.value)}
            hint="10k typical"
          />
          <NumberInput
            label="Horizon (trades)"
            step="1"
            value={horizon}
            onChange={(e) => setHorizon(e.target.value)}
          />
          <NumberInput
            label="Ruin threshold (%)"
            step="0.1"
            min="0"
            max="100"
            value={ruinPct}
            onChange={(e) => setRuinPct(e.target.value)}
            hint="% loss from starting that counts as ruin"
          />
          <NumberInput
            label="Seed (optional)"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            hint="leave blank for non-deterministic"
          />
          <Button variant="primary" size="lg" className="w-full" onClick={run} loading={mc.isPending}>
            <Play size={14} strokeWidth={1.5} />
            Run simulation
          </Button>
          {tookMs !== null && last ? (
            <div className="text-2xs text-text-tertiary font-mono">
              {last.n_simulations.toLocaleString('it-IT')} sims × {last.horizon_trades} trades in{' '}
              {(tookMs / 1000).toFixed(2)}s · sampled from {last.n_historical_pnls} historical pnls
            </div>
          ) : null}
        </div>
      </Card>

      {/* Results */}
      <div className="space-y-4">
        <Card>
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <div className="text-2xs uppercase tracking-widest text-text-tertiary">
                Risk of ruin
              </div>
              <div
                className={
                  'mt-1 font-mono text-4xl tabular-nums ' +
                  (last && Number(last.risk_of_ruin_pct) > 0
                    ? 'text-accent-loss'
                    : 'text-text-primary')
                }
              >
                {last ? formatPercent(last.risk_of_ruin_pct) : '—'}
              </div>
            </div>
            <Percentile label="P10" value={last?.p10_ending_bankroll} />
            <Percentile label="P50" value={last?.p50_ending_bankroll} />
            <Percentile label="P90" value={last?.p90_ending_bankroll} />
            <Percentile label="Mean" value={last?.mean_ending_bankroll} />
          </div>
        </Card>
        <Card header={<span>Ending bankroll distribution</span>}>
          <Histogram result={last} startingBankroll={starting} />
        </Card>
      </div>
    </div>
  );
}

function Percentile({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div>
      <div className="text-2xs uppercase tracking-widest text-text-tertiary">{label}</div>
      <div className="font-mono text-lg tabular-nums text-text-primary">
        {value ? formatEur(value) : '—'}
      </div>
    </div>
  );
}

interface HistProps {
  result: MonteCarloResponse | null;
  startingBankroll: string;
}

function Histogram({ result, startingBankroll }: HistProps) {
  if (!result) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-text-tertiary">
        Run a simulation to populate the histogram.
      </div>
    );
  }
  const data = result.distribution.map((b) => ({
    label: formatEur(b.bucket_low),
    mid: (Number(b.bucket_low) + Number(b.bucket_high)) / 2,
    count: b.count,
  }));
  const startNum = Number(startingBankroll);
  return (
    <div style={{ width: '100%', height: 260 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
            tickLine={false}
            minTickGap={32}
          />
          <YAxis
            tick={{ fill: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <ReferenceLine
            x={data.reduce((acc, d, i) =>
              Math.abs(d.mid - startNum) < Math.abs((data[acc]?.mid ?? Infinity) - startNum) ? i : acc,
            0)}
            stroke="var(--accent-info)"
            strokeDasharray="2 4"
            label={{ value: 'start', position: 'top', fontSize: 10, fill: 'var(--accent-info)' }}
          />
          <Tooltip
            cursor={{ fill: 'var(--bg-hover)' }}
            content={({ active, payload }: TooltipPayload) => {
              if (!active || !payload?.length) return null;
              const p = payload[0]?.payload;
              if (!p) return null;
              return (
                <div className="rounded-lg border border-border-subtle bg-bg-overlay px-3 py-2 text-xs shadow-xl">
                  <div className="text-text-tertiary">~{formatEur(p.mid)}</div>
                  <div className="mt-1 font-mono tabular-nums text-text-primary">
                    {p.count} sims (
                    {((p.count / result.n_simulations) * 100).toFixed(1)}%)
                  </div>
                </div>
              );
            }}
          />
          <Bar
            dataKey="count"
            fill="var(--accent-brand)"
            opacity={0.8}
            radius={[3, 3, 0, 0]}
            isAnimationActive
            animationDuration={500}
          />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-4 text-xs text-text-tertiary">
        <span>
          tone:{' '}
          <span
            className={
              pnlTone(Number(result.p50_ending_bankroll) - startNum) === 'gain'
                ? 'text-accent-gain'
                : pnlTone(Number(result.p50_ending_bankroll) - startNum) === 'loss'
                  ? 'text-accent-loss'
                  : 'text-text-secondary'
            }
          >
            P50 {pnlTone(Number(result.p50_ending_bankroll) - startNum) === 'gain' ? 'above' : 'below'}{' '}
            starting
          </span>
        </span>
        <span>
          min {formatEur(result.min_ending_bankroll)} · max {formatEur(result.max_ending_bankroll)}
        </span>
      </div>
    </div>
  );
}

interface TooltipPayload {
  active?: boolean;
  payload?: readonly { payload?: { mid: number; count: number } }[];
}
