/**
 * Trade filter state synchronized with the URL query string. Reading the
 * URL means a filtered table is sharable and survives reload; writing
 * back means filter changes are reflected in the breadcrumb / address bar.
 */

import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type {
  PnlModeFilter,
  SortKey,
  TradeFilters,
  TradeStatusFilter,
} from '@/queries/trades';

const ARRAY_KEYS = new Set<keyof TradeFilters>(['tag']);

export function useTradeFilters(): {
  filters: TradeFilters;
  setFilter: <K extends keyof TradeFilters>(key: K, value: TradeFilters[K]) => void;
  reset: () => void;
} {
  const [params, setParams] = useSearchParams();

  const filters = useMemo<TradeFilters>(() => {
    const f: TradeFilters = {};
    const get = (k: string) => params.get(k) || undefined;
    f.strategy_id = get('strategy_id');
    f.league = get('league');
    f.outcome_label = get('outcome_label');
    f.q = get('q');
    f.date_from = get('date_from');
    f.date_to = get('date_to');
    f.pnl_min = get('pnl_min');
    f.pnl_max = get('pnl_max');
    const status = get('status') as TradeStatusFilter | undefined;
    if (status === 'OPEN' || status === 'CLOSED' || status === 'VOID') f.status = status;
    const pnlMode = get('pnl_mode') as PnlModeFilter | undefined;
    if (pnlMode === 'AUTO' || pnlMode === 'MANUAL' || pnlMode === 'CASHOUT_ODDS') f.pnl_mode = pnlMode;
    const sort = get('sort') as SortKey | undefined;
    if (sort) f.sort = sort;
    const tags = params.getAll('tag').filter(Boolean);
    if (tags.length) f.tag = tags;
    const page = Number(get('page'));
    if (Number.isFinite(page) && page > 0) f.page = page;
    const ps = Number(get('page_size'));
    if (Number.isFinite(ps) && ps > 0) f.page_size = ps;
    const dow = get('kickoff_dow');
    if (dow !== undefined) {
      const n = Number(dow);
      if (Number.isInteger(n) && n >= 0 && n <= 6) f.kickoff_dow = n;
    }
    const hh = get('kickoff_hour');
    if (hh !== undefined) {
      const n = Number(hh);
      if (Number.isInteger(n) && n >= 0 && n <= 23) f.kickoff_hour = n;
    }
    return f;
  }, [params]);

  const setFilter = useCallback(
    <K extends keyof TradeFilters>(key: K, value: TradeFilters[K]) => {
      const next = new URLSearchParams(params);
      next.delete(key as string);
      // Reset pagination on any non-page filter change.
      if (key !== 'page') next.delete('page');
      if (value === undefined || value === null || value === '') {
        // already deleted
      } else if (ARRAY_KEYS.has(key)) {
        for (const v of value as unknown as string[]) next.append(key as string, v);
      } else {
        next.set(key as string, String(value));
      }
      setParams(next, { replace: false });
    },
    [params, setParams],
  );

  const reset = useCallback(() => setParams(new URLSearchParams(), { replace: false }), [setParams]);

  return { filters, setFilter, reset };
}
