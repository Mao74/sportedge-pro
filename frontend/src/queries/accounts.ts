/** Trading accounts CRUD queries. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export type MarketType = 'exchange' | 'classic';

export interface Account {
  id: string;
  name: string;
  venue: string;
  market_type: MarketType;
  commission_pct: string;
  opening_balance: string;
  opened_at: string;
  is_active: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountCreate {
  name: string;
  venue: string;
  market_type: MarketType;
  commission_pct: string;
  opening_balance: string;
  opened_at?: string;
}

export interface AccountUpdate {
  name?: string;
  venue?: string;
  market_type?: MarketType;
  commission_pct?: string;
  opened_at?: string;
  is_active?: boolean;
}

/** Per-venue defaults — used by the new-account form's autosuggest.
 *  ``market_type`` is the recommended classification but the user can
 *  always override it on a per-account basis. */
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
  { value: 'betflag',     label: 'Betflag',          market_type: 'classic',  default_commission: '0.00' },
  { value: 'snai',        label: 'Snai',             market_type: 'classic',  default_commission: '0.00' },
  { value: 'bet365',      label: 'Bet365',           market_type: 'classic',  default_commission: '0.00' },
  { value: 'sisal',       label: 'Sisal',            market_type: 'classic',  default_commission: '0.00' },
  { value: 'lottomatica', label: 'Lottomatica',      market_type: 'classic',  default_commission: '0.00' },
  { value: 'eurobet',     label: 'Eurobet',          market_type: 'classic',  default_commission: '0.00' },
  { value: 'goldbet',     label: 'Goldbet',          market_type: 'classic',  default_commission: '0.00' },
  { value: 'other',       label: 'Other',            market_type: 'exchange', default_commission: '4.50' },
];

export function useAccounts(opts: { includeArchived?: boolean } = {}) {
  const includeArchived = opts.includeArchived ?? false;
  return useQuery({
    queryKey: ['accounts', { includeArchived }],
    queryFn: () =>
      api.get<Account[]>('/accounts', { include_archived: includeArchived }),
  });
}

export function useAccount(accountId: string | null | undefined) {
  return useQuery({
    queryKey: ['accounts', accountId],
    queryFn: () => api.get<Account>(`/accounts/${accountId}`),
    enabled: Boolean(accountId),
  });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AccountCreate) => api.post<Account>('/accounts', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] });
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}

export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: AccountUpdate }) =>
      api.patch<Account>(`/accounts/${id}`, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] });
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}

export function useArchiveAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Account>(`/accounts/${id}/archive`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] });
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}

export function useUnarchiveAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Account>(`/accounts/${id}/unarchive`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] });
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete<void>(`/accounts/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] });
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}
