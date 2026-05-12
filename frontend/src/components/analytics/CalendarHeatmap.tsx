/**
 * 7×24 day-of-week × hour-of-day heatmap. Color intensity scaled by |pnl|;
 * hue picks gain/loss. Clicking a cell navigates to /trades filtered by
 * the corresponding kickoff window.
 */

import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatEur } from '@/lib/format';
import type { CalendarCell } from '@/queries/analytics';

const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface Props {
  cells: CalendarCell[];
}

export function CalendarHeatmap({ cells }: Props) {
  const navigate = useNavigate();

  const lookup = useMemo(() => {
    const m = new Map<string, CalendarCell>();
    for (const c of cells) m.set(`${c.day_of_week}-${c.hour}`, c);
    return m;
  }, [cells]);

  const maxAbs = useMemo(() => {
    let m = 0;
    for (const c of cells) {
      const v = Math.abs(Number(c.pnl_eur));
      if (v > m) m = v;
    }
    return m || 1;
  }, [cells]);

  const onCellClick = (dow: number, hour: number, cell: CalendarCell | undefined) => {
    if (!cell) return;
    navigate(`/trades?kickoff_dow=${dow}&kickoff_hour=${hour}`);
  };

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="border-separate" style={{ borderSpacing: 2 }}>
          <thead>
            <tr>
              <th className="w-10"></th>
              {Array.from({ length: 24 }).map((_, h) => (
                <th
                  key={h}
                  className="text-center text-2xs font-mono text-text-tertiary"
                  style={{ width: 22 }}
                >
                  {h % 3 === 0 ? h : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DOW_LABELS.map((label, dow) => (
              <tr key={dow}>
                <th className="pr-2 text-right text-2xs font-mono text-text-tertiary">{label}</th>
                {Array.from({ length: 24 }).map((_, h) => {
                  const cell = lookup.get(`${dow}-${h}`);
                  const v = cell ? Number(cell.pnl_eur) : 0;
                  const abs = Math.abs(v);
                  const intensity = abs / maxAbs;
                  const isPos = v > 0;
                  const isNeg = v < 0;
                  const bg =
                    !cell || v === 0
                      ? 'var(--bg-overlay)'
                      : isPos
                        ? `color-mix(in srgb, var(--accent-gain) ${Math.round(8 + 92 * intensity)}%, transparent)`
                        : isNeg
                          ? `color-mix(in srgb, var(--accent-loss) ${Math.round(8 + 92 * intensity)}%, transparent)`
                          : 'var(--bg-overlay)';
                  return (
                    <td
                      key={h}
                      className="cursor-pointer rounded-sm border border-border-subtle/30 transition-transform hover:scale-110"
                      style={{ width: 22, height: 22, background: bg }}
                      title={
                        cell
                          ? `${label} ${h}:00 — ${cell.n_trades} trades · ${formatEur(cell.pnl_eur)}`
                          : `${label} ${h}:00 — no trades`
                      }
                      onClick={() => onCellClick(dow, h, cell)}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center gap-4 text-2xs text-text-tertiary">
        <span>Less ←</span>
        <Legend />
        <span>→ More</span>
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex items-center gap-1">
      {[0.1, 0.3, 0.55, 0.8, 1].map((i) => (
        <span
          key={i}
          className="block h-3 w-6 rounded-sm"
          style={{
            background: `color-mix(in srgb, var(--accent-gain) ${Math.round(100 * i)}%, transparent)`,
          }}
        />
      ))}
    </div>
  );
}
