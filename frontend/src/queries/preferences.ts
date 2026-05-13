/** Preferences + bankroll snapshots queries used by the Settings page. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

// Re-export so legacy import paths (`@/queries/preferences`) keep resolving
// while components migrate to the accounts module.
export type { MarketType } from '@/queries/accounts';
export { KNOWN_VENUES } from '@/queries/accounts';

export interface Preferences {
  default_account_id: string | null;
}

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
  account_id: string;
  taken_at: string;
  balance_eur: string;
  deposit_eur: string;
  withdrawal_eur: string;
  notes: string | null;
}

export function useBankrollSnapshots(limit = 10, accountId?: string | null) {
  return useQuery({
    queryKey: ['bankroll', 'snapshots', limit, accountId ?? null],
    queryFn: () =>
      api.get<BankrollSnapshot[]>(
        '/bankroll/snapshots',
        accountId ? { limit, account_id: accountId } : { limit },
      ),
  });
}

export function useAdjustBankroll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      amount_eur: string;
      kind: 'deposit' | 'withdrawal';
      notes?: string;
      account_id?: string;
    }) => api.post<BankrollSnapshot>('/bankroll/adjust', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}
