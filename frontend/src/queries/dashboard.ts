/**
 * TanStack Query hooks for the dashboard. Strongly-typed over the backend
 * shapes — these will be replaced by openapi-typescript generated types
 * later but the call sites won't change.
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

// --- Bankroll --------------------------------------------------------------

export interface BankrollCurrent {
  balance_eur: string;
  last_snapshot_at: string | null;
  since_inception_pnl_eur: string;
  since_inception_roi_pct: string;
}

export interface BankrollSeriesPoint {
  taken_at: string;
  balance_eur: string;
  day_pnl_eur: string;
}

export type BankrollRange = '7d' | '30d' | '90d' | 'all';

export function useBankrollCurrent() {
  return useQuery({
    queryKey: ['bankroll', 'current'],
    queryFn: () => api.get<BankrollCurrent>('/bankroll/current'),
  });
}

export function useBankrollSeries(range: BankrollRange = '30d') {
  return useQuery({
    queryKey: ['bankroll', 'series', range],
    queryFn: () => api.get<BankrollSeriesPoint[]>('/bankroll/series', { range }),
  });
}

// --- Analytics summary -----------------------------------------------------

export interface AnalyticsSummary {
  n_trades: number;
  total_pnl_eur: string;
  total_stake_eur: string;
  roi_pct: string;
  win_rate_pct: string;
  sharpe: string;
  max_drawdown_pct: string;
  max_drawdown_eur: string;
}

export function useAnalyticsSummary() {
  return useQuery({
    queryKey: ['analytics', 'summary'],
    queryFn: () => api.get<AnalyticsSummary>('/analytics/summary'),
  });
}

// --- By-strategy breakdown -------------------------------------------------

export interface BreakdownRow {
  key: string;
  n_trades: number;
  total_pnl_eur: string;
  total_stake_eur: string;
  roi_pct: string;
  win_rate_pct: string;
}

export function useByStrategy() {
  return useQuery({
    queryKey: ['analytics', 'by-strategy'],
    queryFn: () => api.get<BreakdownRow[]>('/analytics/by-strategy'),
  });
}

// --- Open trades -----------------------------------------------------------

export interface TradeStrategyEmbed {
  id: string;
  name: string;
  slug: string;
  kind: 'builtin' | 'custom';
  template_key: string | null;
  color_hex: string | null;
}

export interface TradeListItem {
  id: string;
  strategy: TradeStrategyEmbed;
  home_team: string;
  away_team: string;
  league: string;
  kickoff_at: string;
  stake_total: string;
  avg_odds: string;
  computed_pnl_eur: string;
  pnl_mode: string;
  market_type: 'exchange' | 'classic';
  outcome_label: string | null;
  status: string;
  closed_at: string | null;
}

export interface TradeAggregates {
  n_trades: number;
  sum_pnl_eur: string;
  sum_stake_eur: string;
  roi_pct: string;
  win_rate_pct: string;
}

export interface TradeListResponse {
  items: TradeListItem[];
  total: number;
  page: number;
  page_size: number;
  aggregates: TradeAggregates;
}

export function useOpenTrades(limit = 10) {
  return useQuery({
    queryKey: ['trades', 'open', limit],
    queryFn: () =>
      api.get<TradeListResponse>('/trades', {
        status: 'OPEN',
        page_size: limit,
        sort: '-kickoff_at',
      }),
  });
}

// --- Strategies (palette lookup for color) ---------------------------------

export interface StrategyOut {
  id: string;
  name: string;
  slug: string;
  kind: 'builtin' | 'custom';
  template_key: string | null;
  color_hex: string | null;
  is_active: boolean;
}

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: () => api.get<StrategyOut[]>('/strategies'),
  });
}
