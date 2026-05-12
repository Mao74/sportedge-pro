/**
 * Trade-log queries + types. Builds the full filter param object that the
 * backend /trades endpoint accepts, plus a small helper to update a single
 * filter chip immutably.
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { TradeListResponse } from './dashboard';

export type TradeStatusFilter = 'OPEN' | 'CLOSED' | 'VOID';
export type PnlModeFilter = 'AUTO' | 'MANUAL' | 'CASHOUT_ODDS';
export type SortKey = '-kickoff_at' | 'kickoff_at' | 'pnl' | '-pnl' | 'stake' | '-stake';

export interface TradeFilters {
  strategy_id?: string;
  league?: string;
  status?: TradeStatusFilter;
  outcome_label?: string;
  pnl_mode?: PnlModeFilter;
  date_from?: string;
  date_to?: string;
  pnl_min?: string;
  pnl_max?: string;
  tag?: string[];
  q?: string;
  kickoff_dow?: number;   // 0=Mon..6=Sun
  kickoff_hour?: number;  // 0..23
  sort?: SortKey;
  page?: number;
  page_size?: number;
}

export const DEFAULT_PAGE_SIZE = 50;

export function useTradeList(filters: TradeFilters) {
  // Drop empties so the backend gets a clean query.
  const params: Record<string, string | number | string[] | undefined> = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v === undefined || v === null || v === '') continue;
    if (Array.isArray(v) && v.length === 0) continue;
    params[k] = v as string | number | string[];
  }
  return useQuery({
    queryKey: ['trades', 'list', params],
    queryFn: () => api.get<TradeListResponse>('/trades', params),
    placeholderData: (prev) => prev,
  });
}

export type { TradeListItem, TradeListResponse } from './dashboard';
