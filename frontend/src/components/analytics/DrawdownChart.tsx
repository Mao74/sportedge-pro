/**
 * Underwater drawdown chart. Mirrored area (always negative or zero,
 * shaded red) so the user immediately sees how deep and how often the
 * curve dips below the running peak.
 */

import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatEur } from '@/lib/format';
import type { DrawdownPoint } from '@/queries/analytics';

interface Props {
  points: DrawdownPoint[];
  height?: number;
}

const dateFmt = new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: 'short' });

export function DrawdownChart({ points, height = 280 }: Props) {
  const data = useMemo(
    () =>
      points.map((p) => ({
        x: new Date(p.closed_at).getTime(),
        date: dateFmt.format(new Date(p.closed_at)),
        underwater: -Math.abs(Number(p.underwater_eur)),
      })),
    [points],
  );

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-dashed border-border-subtle text-sm text-text-tertiary"
        style={{ height }}
      >
        No closed trades yet.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-loss)" stopOpacity={0} />
              <stop offset="100%" stopColor="var(--accent-loss)" stopOpacity={0.32} />
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
          />
          <Tooltip
            cursor={{ stroke: 'var(--border-strong)', strokeDasharray: '2 4' }}
            content={({ active, payload, label }: TooltipPayload) => {
              if (!active || !payload?.length) return null;
              const p = payload[0]?.payload;
              if (!p) return null;
              return (
                <div className="rounded-lg border border-border-subtle bg-bg-overlay px-3 py-2 text-xs shadow-xl">
                  <div className="text-text-tertiary">{label}</div>
                  <div className="mt-1 font-mono tabular-nums text-accent-loss">
                    {formatEur(p.underwater)} underwater
                  </div>
                </div>
              );
            }}
          />
          <Area
            type="monotone"
            dataKey="underwater"
            stroke="var(--accent-loss)"
            strokeWidth={1.5}
            fill="url(#ddFill)"
            isAnimationActive
            animationDuration={600}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

interface TooltipPayload {
  active?: boolean;
  payload?: readonly { payload?: { underwater: number } }[];
  label?: string | number;
}
