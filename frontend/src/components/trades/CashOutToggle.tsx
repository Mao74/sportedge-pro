/**
 * 3-state segmented control for the trade close-out flavour:
 *
 * - "No cash out" → MANUAL or AUTO (the user records the final scenario)
 * - "Manual P/L"  → MANUAL with manual_pnl_eur input
 * - "From cashout odds" → CASHOUT_ODDS with live PnL preview from
 *   POST /analytics/whatif-cashout (single source of truth — never compute
 *   client-side).
 *
 * Switching modes preserves the just-computed value where useful (cashout
 * → manual lifts the locked-in P/L into the manual input).
 */

import { useEffect, useState } from 'react';
import { NumberInput, Segmented } from '@/components/primitives';
import { api } from '@/lib/api';
import { formatEur, pnlTone } from '@/lib/format';

export type CashOutMode = 'auto' | 'manual' | 'cashout';
export type PositionSide = 'back' | 'lay';

export interface CashOutValue {
  mode: CashOutMode;
  pnl_mode: 'AUTO' | 'MANUAL' | 'CASHOUT_ODDS';
  manual_pnl_eur?: string | null;
  cashout_odds?: string | null;
  position_side?: PositionSide | null;
  outcome_label?: string | null;
}

interface CashOutToggleProps {
  value: CashOutValue;
  onChange: (v: CashOutValue) => void;
  // Universal trade fields needed by CASHOUT_ODDS preview.
  stakeTotal: string;
  avgOdds: string;
  commissionPct: string;
  marketType: 'exchange' | 'classic';
  /** Outcome options — strategy-driven via field_schema, fall back to universal set. */
  outcomeOptions?: string[];
}

const DEFAULT_OUTCOMES = ['WIN', 'LOSS', 'HALF_WIN', 'HALF_LOSS', 'VOID'];

interface WhatIfResp {
  locked_in_pnl_eur: string;
  breakeven_cashout_odds: string | null;
  pct_of_max_win: string;
  formula_text: string;
}

export function CashOutToggle({
  value,
  onChange,
  stakeTotal,
  avgOdds,
  commissionPct,
  marketType,
  outcomeOptions,
}: CashOutToggleProps) {
  const [preview, setPreview] = useState<WhatIfResp | null>(null);
  const [previewing, setPreviewing] = useState(false);

  // Live preview for the cashout mode — debounced 80ms per docs/strategies.md.
  useEffect(() => {
    if (
      value.mode !== 'cashout' ||
      !value.cashout_odds ||
      !value.position_side ||
      !stakeTotal ||
      !avgOdds
    ) {
      setPreview(null);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setPreviewing(true);
      try {
        const out = await api.post<WhatIfResp>('/analytics/whatif-cashout', {
          stake_total: stakeTotal,
          avg_odds: avgOdds,
          cashout_odds: value.cashout_odds,
          position_side: value.position_side,
          commission_pct: commissionPct,
          market_type: marketType,
        });
        if (!ctrl.signal.aborted) setPreview(out);
      } catch {
        // ignore network blips — preview is best-effort
      } finally {
        if (!ctrl.signal.aborted) setPreviewing(false);
      }
    }, 80);
    return () => {
      ctrl.abort();
      clearTimeout(t);
    };
  }, [value.mode, value.cashout_odds, value.position_side, stakeTotal, avgOdds, commissionPct, marketType]);

  const setMode = (mode: CashOutMode) => {
    if (mode === value.mode) return;
    if (mode === 'manual' && value.mode === 'cashout' && preview) {
      onChange({
        ...value,
        mode,
        pnl_mode: 'MANUAL',
        manual_pnl_eur: preview.locked_in_pnl_eur,
      });
      return;
    }
    onChange({
      ...value,
      mode,
      pnl_mode: mode === 'auto' ? 'AUTO' : mode === 'manual' ? 'MANUAL' : 'CASHOUT_ODDS',
    });
  };

  return (
    <div className="space-y-4 rounded-xl border border-border-subtle bg-bg-overlay p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Outcome</div>
          <div className="text-sm text-text-secondary">How do you want to log the close?</div>
        </div>
        <Segmented<CashOutMode>
          value={value.mode}
          onChange={setMode}
          options={[
            { value: 'auto', label: 'No cash out' },
            { value: 'manual', label: 'Manual P/L' },
            { value: 'cashout', label: 'From cashout odds' },
          ]}
        />
      </div>

      {value.mode === 'auto' ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">
              Position side
            </span>
            <Segmented<PositionSide>
              value={value.position_side ?? 'back'}
              onChange={(v) => onChange({ ...value, position_side: v })}
              options={[
                { value: 'back', label: 'Back' },
                { value: 'lay', label: 'Lay' },
              ]}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Outcome</span>
            <select
              value={value.outcome_label ?? ''}
              onChange={(e) =>
                onChange({ ...value, outcome_label: e.target.value || null })
              }
              className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            >
              <option value="">—</option>
              {(outcomeOptions ?? DEFAULT_OUTCOMES).map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {value.mode === 'manual' ? (
        <NumberInput
          label="Final P/L (€)"
          step="0.01"
          value={value.manual_pnl_eur ?? ''}
          onChange={(e) =>
            onChange({ ...value, manual_pnl_eur: e.target.value === '' ? null : e.target.value })
          }
        />
      ) : null}

      {value.mode === 'cashout' ? (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <NumberInput
              label="Cashout odds"
              step="0.01"
              min="1.01"
              value={value.cashout_odds ?? ''}
              onChange={(e) =>
                onChange({
                  ...value,
                  cashout_odds: e.target.value === '' ? null : e.target.value,
                })
              }
            />
            <label className="flex flex-col gap-1.5">
              <span className="text-2xs uppercase tracking-widest text-text-tertiary">
                Position side
              </span>
              <Segmented<PositionSide>
                value={value.position_side ?? 'back'}
                onChange={(v) => onChange({ ...value, position_side: v })}
                options={[
                  { value: 'back', label: 'Back' },
                  { value: 'lay', label: 'Lay' },
                ]}
              />
            </label>
          </div>
          <CashoutPreview preview={preview} previewing={previewing} />
        </div>
      ) : null}
    </div>
  );
}

function CashoutPreview({
  preview,
  previewing,
}: {
  preview: WhatIfResp | null;
  previewing: boolean;
}) {
  if (!preview) {
    return (
      <div className="rounded-lg border border-dashed border-border-subtle bg-bg-base px-3 py-3 text-xs text-text-tertiary">
        Enter cashout odds + position side to see the locked-in P/L.
      </div>
    );
  }
  const tone = pnlTone(preview.locked_in_pnl_eur);
  return (
    <div className="space-y-1.5 rounded-lg border border-border-subtle bg-bg-base px-3 py-3">
      <div className="flex items-baseline justify-between">
        <span className="text-2xs uppercase tracking-widest text-text-tertiary">Locked in</span>
        <span
          className={`font-mono text-lg tabular-nums ${
            tone === 'gain' ? 'text-accent-gain' : tone === 'loss' ? 'text-accent-loss' : 'text-text-tertiary'
          } ${previewing ? 'opacity-60' : ''}`}
        >
          {Number(preview.locked_in_pnl_eur) >= 0 ? '+' : ''}
          {formatEur(preview.locked_in_pnl_eur)}
        </span>
      </div>
      <div className="font-mono text-xs text-text-tertiary">{preview.formula_text}</div>
      <div className="text-xs text-text-tertiary">
        % of max win: <span className="font-mono text-text-secondary">{preview.pct_of_max_win}%</span>
        {preview.breakeven_cashout_odds ? (
          <>
            {' · '}breakeven @ <span className="font-mono text-text-secondary">{preview.breakeven_cashout_odds}</span>
          </>
        ) : null}
      </div>
    </div>
  );
}
