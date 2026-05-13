/**
 * Standalone WhatIf cash-out page. Live preview via /analytics/whatif-cashout.
 * Different from the trade-form variant: no Apply button (this never closes
 * a trade), but keeps the inputs visible and shows the visual scale.
 */

import { useEffect, useState } from 'react';
import { Calculator } from 'lucide-react';
import { Card, NumberInput, Segmented } from '@/components/primitives';
import { useWhatIfCashout } from '@/queries/analytics';
import { usePreferences } from '@/queries/preferences';
import { useAccounts, type MarketType } from '@/queries/accounts';
import { AccountPicker } from '@/components/accounts/AccountPicker';
import { formatEur, formatPercent, pnlTone } from '@/lib/format';

type Side = 'back' | 'lay';

export default function WhatIf() {
  const prefs = usePreferences();
  const accountsQ = useAccounts();
  const activeAccounts = accountsQ.data?.filter((a) => !a.archived_at) ?? [];
  const [accountId, setAccountId] = useState<string | null>(null);

  const [stake, setStake] = useState('100');
  const [originalOdds, setOriginalOdds] = useState('3.00');
  const [cashoutOdds, setCashoutOdds] = useState('1.50');
  const [side, setSide] = useState<Side>('back');
  const [commission, setCommission] = useState('5.00');
  const [marketType, setMarketType] = useState<MarketType>('exchange');

  // Seed commission + market type from the default account once loaded.
  useEffect(() => {
    if (!activeAccounts.length) return;
    if (accountId) return; // user has already picked one
    const seedId = prefs.data?.default_account_id ?? activeAccounts[0]?.id ?? null;
    setAccountId(seedId);
    const seed = activeAccounts.find((a) => a.id === seedId);
    if (seed) {
      setCommission(seed.commission_pct);
      setMarketType(seed.market_type);
    }
  }, [prefs.data, activeAccounts, accountId]);

  const onAccountChange = (id: string | null) => {
    setAccountId(id);
    const acc = activeAccounts.find((a) => a.id === id);
    if (acc) {
      setCommission(acc.commission_pct);
      setMarketType(acc.market_type);
    }
  };

  const mutation = useWhatIfCashout();
  const [result, setResult] = useState<Awaited<ReturnType<typeof mutation.mutateAsync>> | null>(null);

  useEffect(() => {
    if (!stake || !originalOdds || !cashoutOdds) return;
    const t = setTimeout(async () => {
      try {
        const r = await mutation.mutateAsync({
          stake_total: stake,
          avg_odds: originalOdds,
          cashout_odds: cashoutOdds,
          position_side: side,
          commission_pct: commission,
          market_type: marketType,
        });
        setResult(r);
      } catch {
        /* ignore — debounced preview */
      }
    }, 80);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stake, originalOdds, cashoutOdds, side, commission, marketType]);

  const tone = result ? pnlTone(result.locked_in_pnl_eur) : 'zero';

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <div className="flex items-center gap-2 text-2xs uppercase tracking-widest text-text-tertiary">
          <Calculator size={12} strokeWidth={1.5} />
          <span>What-if</span>
        </div>
        <h1 className="text-2xl font-medium text-text-primary">Cash-out simulator</h1>
        <p className="text-sm text-text-secondary">
          Stateless math — same source of truth as the trade entry form. Drag
          the cashout odds to see how the locked-in P/L moves.
        </p>
      </header>

      {activeAccounts.length > 1 ? (
        <Card header={<span>Seed from account</span>}>
          <AccountPicker
            accounts={activeAccounts}
            value={accountId}
            onChange={onAccountChange}
          />
        </Card>
      ) : null}

      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <NumberInput
            label="Stake total (€)"
            step="0.01"
            value={stake}
            onChange={(e) => setStake(e.target.value)}
          />
          <NumberInput
            label="Original odds"
            step="0.01"
            min="1.01"
            value={originalOdds}
            onChange={(e) => setOriginalOdds(e.target.value)}
          />
          <NumberInput
            label="Cashout odds"
            step="0.01"
            min="1.01"
            value={cashoutOdds}
            onChange={(e) => setCashoutOdds(e.target.value)}
          />
          <NumberInput
            label="Commission (%)"
            step="0.01"
            min="0"
            max="100"
            value={commission}
            onChange={(e) => setCommission(e.target.value)}
            disabled={marketType === 'classic'}
            hint={
              marketType === 'classic'
                ? 'Classic — quoted odds already net'
                : undefined
            }
          />
          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">
              Market type
            </span>
            <Segmented<MarketType>
              value={marketType}
              onChange={(v) => {
                setMarketType(v);
                if (v === 'classic') setCommission('0.00');
              }}
              options={[
                { value: 'exchange', label: 'Exchange (commission applies)' },
                { value: 'classic',  label: 'Classic (no commission)' },
              ]}
            />
          </label>
          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">
              Position side
            </span>
            <Segmented<Side>
              value={side}
              onChange={setSide}
              options={[
                { value: 'back', label: 'Back' },
                { value: 'lay', label: 'Lay' },
              ]}
            />
          </label>
          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">
              Cashout odds slider
            </span>
            <input
              type="range"
              min="1.01"
              max="10"
              step="0.01"
              value={cashoutOdds}
              onChange={(e) => setCashoutOdds(e.target.value)}
              className="accent-accent-brand"
            />
          </label>
        </div>
      </Card>

      <Card header={<span>Locked in</span>}>
        <div className="text-center">
          <div
            className={
              'font-mono text-5xl tabular-nums ' +
              (tone === 'gain'
                ? 'text-accent-gain'
                : tone === 'loss'
                  ? 'text-accent-loss'
                  : 'text-text-primary')
            }
          >
            {result
              ? `${Number(result.locked_in_pnl_eur) >= 0 ? '+' : ''}${formatEur(result.locked_in_pnl_eur)}`
              : '—'}
          </div>
          {result ? (
            <>
              <div className="mt-2 font-mono text-sm text-text-tertiary">{result.formula_text}</div>
              <div className="mt-3 flex flex-wrap items-center justify-center gap-x-6 gap-y-1 text-xs text-text-tertiary">
                <span>
                  Breakeven @{' '}
                  <span className="font-mono text-text-secondary">
                    {result.breakeven_cashout_odds ?? '—'}
                  </span>
                </span>
                <span>
                  % of max win:{' '}
                  <span className="font-mono text-text-secondary">
                    {formatPercent(result.pct_of_max_win)}
                  </span>
                </span>
              </div>
            </>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
