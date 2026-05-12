import { useMemo } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatPercent } from '@/lib/format';
import type { RollingPoint } from '@/queries/analytics';

interface Props {
  points: RollingPoint[];
  height?: number;
}

export function RollingChart({ points, height = 240 }: Props) {
  const data = useMemo(
    () =>
      points.map((p) => ({
        idx: p.idx,
        roi: Number(p.roi_pct),
        winRate: Number(p.win_rate_pct),
      })),
    [points],
  );

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-dashed border-border-subtle text-sm text-text-tertiary"
        style={{ height }}
      >
        Need more closed trades than the rolling window to draw the curve.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="idx"
            tick={{ fill: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            yAxisId="roi"
            tick={{ fill: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            width={48}
          />
          <ReferenceLine yAxisId="roi" y={0} stroke="var(--border-strong)" strokeDasharray="2 4" />
          <Tooltip
            cursor={{ stroke: 'var(--border-strong)', strokeDasharray: '2 4' }}
            content={({ active, payload, label }: TooltipPayload) => {
              if (!active || !payload?.length) return null;
              const p = payload[0]?.payload;
              if (!p) return null;
              return (
                <div className="rounded-lg border border-border-subtle bg-bg-overlay px-3 py-2 text-xs shadow-xl">
                  <div className="text-text-tertiary">trade #{label}</div>
                  <div className="mt-1 font-mono tabular-nums text-text-primary">
                    ROI {formatPercent(p.roi, { signed: true })}
                  </div>
                  <div className="font-mono tabular-nums text-text-tertiary">
                    win rate {formatPercent(p.winRate)}
                  </div>
                </div>
              );
            }}
          />
          <Line
            yAxisId="roi"
            type="monotone"
            dataKey="roi"
            stroke="var(--accent-brand)"
            strokeWidth={1.75}
            dot={false}
            isAnimationActive
            animationDuration={600}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface TooltipPayload {
  active?: boolean;
  payload?: readonly { payload?: { roi: number; winRate: number } }[];
  label?: number | string;
}
