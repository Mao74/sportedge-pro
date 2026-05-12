/** Preferences + bankroll snapshots queries used by the Settings page. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export type MarketType = 'exchange' | 'classic';

export interface Preferences {
  default_commission_pct: string;
  betting_exchange: string;        // legacy column name; actually a "venue"
  default_market_type: MarketType;
}

/** Per-venue defaults. ``market_type`` is the recommended classification but
 *  the user can always override it on a per-trade basis. */
export const KNOWN_VENUES: ReadonlyArray<{
  value: string;
  label: string;
  market_type: MarketType;
  default_commission: string;
}> = [
  { value: 'betfair',     label: 'Betfair Exchange', market_type: 'exchange', default_commission: '5.00' },
  { value: 'smarkets',    label: 'Smarkets',         market_type: 'exchange', default_commission: '2.00' },
  { value: 'matchbook',   label: 'Matchbook',        market_type: 'exchange', default_commission: '2.00' },
  { value: 'betdaq',      label: 'BetDAQ',           market_type: 'exchange', default_commission: '3.00' },
  { value: 'snai',        label: 'Snai',             market_type: 'classic',  default_commission: '0.00' },
  { value: 'bet365',      label: 'Bet365',           market_type: 'classic',  default_commission: '0.00' },
  { value: 'sisal',       label: 'Sisal',            market_type: 'classic',  default_commission: '0.00' },
  { value: 'lottomatica', label: 'Lottomatica',      market_type: 'classic',  default_commission: '0.00' },
  { value: 'eurobet',     label: 'Eurobet',          market_type: 'classic',  default_commission: '0.00' },
  { value: 'goldbet',     label: 'Goldbet',          market_type: 'classic',  default_commission: '0.00' },
  { value: 'other',       label: 'Other',            market_type: 'exchange', default_commission: '4.50' },
];

export function usePreferences() {
  return useQuery({
    queryKey: ['preferences'],
    queryFn: () => api.get<Preferences>('/preferences'),
  });
}

export function usePatchPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Preferences>) => api.patch<Preferences>('/preferences', body),
    onSuccess: (data) => qc.setQueryData(['preferences'], data),
  });
}


// --- Bankroll snapshots --------------------------------------------------

export interface BankrollSnapshot {
  id: string;
  taken_at: string;
  balance_eur: string;
  deposit_eur: string;
  withdrawal_eur: string;
  notes: string | null;
}

export function useBankrollSnapshots(limit = 10) {
  return useQuery({
    queryKey: ['bankroll', 'snapshots', limit],
    queryFn: () => api.get<BankrollSnapshot[]>('/bankroll/snapshots', { limit }),
  });
}

export function useAdjustBankroll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { amount_eur: string; kind: 'deposit' | 'withdrawal'; notes?: string }) =>
      api.post<BankrollSnapshot>('/bankroll/adjust', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}
