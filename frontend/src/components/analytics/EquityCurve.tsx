/**
 * Equity curve. Recharts AreaChart with gradient fill (no stroke gradient
 * per CSS rule), thin axes, brush for zoom, hover crosshair tooltip.
 */

import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  Brush,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatEur } from '@/lib/format';
import type { BankrollSeriesPoint } from '@/queries/dashboard';

interface EquityCurveProps {
  data: BankrollSeriesPoint[];
  height?: number;
}

const dateFmt = new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: 'short' });

interface ChartPoint {
  x: number;
  date: string;
  balance: number;
  dayPnl: number;
}

export function EquityCurve({ data, height = 280 }: EquityCurveProps) {
  const points = useMemo<ChartPoint[]>(
    () =>
      data.map((p) => ({
        x: new Date(p.taken_at).getTime(),
        date: dateFmt.format(new Date(p.taken_at)),
        balance: Number(p.balance_eur),
        dayPnl: Number(p.day_pnl_eur),
      })),
    [data],
  );

  if (points.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-xl border border-dashed border-border-subtle text-sm text-text-tertiary">
        No closed trades yet — log your first to bring the equity curve to life.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <AreaChart data={points} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-brand)" stopOpacity={0.32} />
              <stop offset="100%" stopColor="var(--accent-brand)" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            tick={{ fill: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
            width={64}
            tickFormatter={(v: number) => formatEur(v)}
            domain={['dataMin - 50', 'dataMax + 50']}
          />
          <Tooltip
            cursor={{ stroke: 'var(--border-strong)', strokeDasharray: '2 4' }}
            content={<CustomTooltip />}
          />
          <Area
            type="monotone"
            dataKey="balance"
            stroke="var(--accent-brand)"
            strokeWidth={2}
            fill="url(#equityFill)"
            isAnimationActive
            animationDuration={700}
          />
          {points.length > 12 ? (
            <Brush
              dataKey="date"
              height={22}
              stroke="var(--border-strong)"
              fill="var(--bg-overlay)"
              travellerWidth={8}
              tickFormatter={() => ''}
            />
          ) : null}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

interface TooltipProps {
  active?: boolean;
  label?: string;
  payload?: { payload: ChartPoint }[];
}

function CustomTooltip({ active, label, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const p = payload[0]!.payload;
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-overlay px-3 py-2 text-xs shadow-xl">
      <div className="text-text-tertiary">{label}</div>
      <div className="mt-1 font-mono tabular-nums text-text-primary">{formatEur(p.balance)}</div>
      <div
        className={`mt-0.5 font-mono tabular-nums ${p.dayPnl > 0 ? 'text-accent-gain' : p.dayPnl < 0 ? 'text-accent-loss' : 'text-text-tertiary'}`}
      >
        {p.dayPnl >= 0 ? '+' : ''}
        {formatEur(p.dayPnl)} day
      </div>
    </div>
  );
}
