/** Single-trade query + mutations (used by the detail drawer). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { TradeListItem } from './dashboard';

export interface TradeFull extends TradeListItem {
  ht_score_home: number | null;
  ht_score_away: number | null;
  ft_score_home: number | null;
  ft_score_away: number | null;
  cashout_odds: string | null;
  manual_pnl_eur: string | null;
  position_side: 'back' | 'lay' | null;
  strategy_data: Record<string, unknown>;
  notes_md: string | null;
  commission_pct: string;
  tags: { id: string; name: string; color_hex: string | null }[];
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export function useTradeDetail(id: string | null) {
  return useQuery({
    queryKey: ['trades', 'detail', id],
    queryFn: () => api.get<TradeFull>(`/trades/${id}`),
    enabled: Boolean(id),
  });
}

/**
 * Optimistic PATCH. We update the cached trade detail immediately, fire the
 * request, and roll back from the snapshot on error. The server response,
 * once it arrives, is also written into the cache so any backend-side
 * recomputed fields (e.g. computed_pnl_eur) supersede our optimistic guess.
 */
export function usePatchTrade(id: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Record<string, unknown>) =>
      api.patch<TradeFull>(`/trades/${id}`, patch),
    onMutate: async (patch) => {
      if (!id) return undefined;
      await qc.cancelQueries({ queryKey: ['trades', 'detail', id] });
      const previous = qc.getQueryData<TradeFull>(['trades', 'detail', id]);
      if (previous) {
        qc.setQueryData<TradeFull>(['trades', 'detail', id], { ...previous, ...patch });
      }
      return { previous };
    },
    onError: (_err, _patch, ctx) => {
      if (id && ctx?.previous) {
        qc.setQueryData(['trades', 'detail', id], ctx.previous);
      }
    },
    onSuccess: (server) => {
      if (id) qc.setQueryData(['trades', 'detail', id], server);
      qc.invalidateQueries({ queryKey: ['trades'] });
      qc.invalidateQueries({ queryKey: ['analytics'] });
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}

export function useDeleteTrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/trades/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trades'] });
      qc.invalidateQueries({ queryKey: ['analytics'] });
      qc.invalidateQueries({ queryKey: ['bankroll'] });
    },
  });
}
