/**
 * Analytics query hooks. All endpoints share the same trade-filter shape so
 * the user can carry filter chips from the trade log into analytics.
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

// --- Filters shared with /trades -----------------------------------------

export interface AnalyticsFilters {
  strategy_id?: string;
  league?: string;
  status?: 'OPEN' | 'CLOSED' | 'VOID';
  outcome_label?: string;
  pnl_mode?: 'AUTO' | 'MANUAL' | 'CASHOUT_ODDS';
  date_from?: string;
  date_to?: string;
  pnl_min?: string;
  pnl_max?: string;
  tag?: string[];
  q?: string;
}

function asParams(f: AnalyticsFilters): Record<string, string | number | string[] | undefined> {
  const params: Record<string, string | number | string[] | undefined> = {};
  for (const [k, v] of Object.entries(f)) {
    if (v === undefined || v === null || v === '') continue;
    if (Array.isArray(v) && v.length === 0) continue;
    params[k] = v as string | number | string[];
  }
  return params;
}

// --- Summary --------------------------------------------------------------

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

export function useSummary(f: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'summary', asParams(f)],
    queryFn: () => api.get<AnalyticsSummary>('/analytics/summary', asParams(f)),
  });
}

// --- Breakdowns -----------------------------------------------------------

export interface BreakdownRow {
  key: string;
  n_trades: number;
  total_pnl_eur: string;
  total_stake_eur: string;
  roi_pct: string;
  win_rate_pct: string;
}

export function useByStrategy(f: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'by-strategy', asParams(f)],
    queryFn: () => api.get<BreakdownRow[]>('/analytics/by-strategy', asParams(f)),
  });
}

export function useByLeague(f: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'by-league', asParams(f)],
    queryFn: () => api.get<BreakdownRow[]>('/analytics/by-league', asParams(f)),
  });
}

export function useByOutcome(f: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'by-outcome', asParams(f)],
    queryFn: () => api.get<BreakdownRow[]>('/analytics/by-outcome', asParams(f)),
  });
}

// --- Rolling -------------------------------------------------------------

export interface RollingPoint {
  idx: number;
  roi_pct: string;
  win_rate_pct: string;
}

export function useRolling(f: AnalyticsFilters, window = 20) {
  return useQuery({
    queryKey: ['analytics', 'rolling', window, asParams(f)],
    queryFn: () => api.get<RollingPoint[]>('/analytics/rolling', { ...asParams(f), window }),
  });
}

// --- Drawdown ------------------------------------------------------------

export interface DrawdownPoint {
  closed_at: string;
  cum_pnl_eur: string;
  underwater_eur: string;
  underwater_pct: string;
}

export interface DrawdownSeries {
  points: DrawdownPoint[];
  max_drawdown_pct: string;
  max_drawdown_eur: string;
  max_dd_started_at: string | null;
  max_dd_ended_at: string | null;
}

export function useDrawdown(f: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'drawdown', asParams(f)],
    queryFn: () => api.get<DrawdownSeries>('/analytics/drawdown', asParams(f)),
  });
}

// --- Calendar ------------------------------------------------------------

export interface CalendarCell {
  day_of_week: number;
  hour: number;
  n_trades: number;
  pnl_eur: string;
}

export function useCalendar(f: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'calendar', asParams(f)],
    queryFn: () => api.get<{ cells: CalendarCell[] }>('/analytics/calendar', asParams(f)),
  });
}

// --- Monte Carlo (mutation: triggered on demand) -------------------------

export interface MonteCarloRequest {
  starting_bankroll: string;
  n_simulations: number;
  horizon_trades: number;
  ruin_threshold_pct: string;
  n_buckets?: number;
  seed?: number;
}

export interface DistributionBucket {
  bucket_low: string;
  bucket_high: string;
  count: number;
}

export interface MonteCarloResponse {
  risk_of_ruin_pct: string;
  p10_ending_bankroll: string;
  p50_ending_bankroll: string;
  p90_ending_bankroll: string;
  mean_ending_bankroll: string;
  min_ending_bankroll: string;
  max_ending_bankroll: string;
  distribution: DistributionBucket[];
  n_simulations: number;
  horizon_trades: number;
  n_historical_pnls: number;
}

export function useMonteCarlo(f: AnalyticsFilters) {
  return useMutation({
    mutationFn: (body: MonteCarloRequest) =>
      api.post<MonteCarloResponse>('/analytics/monte-carlo', body, asParams(f)),
  });
}

// --- WhatIf (mutation: keystroke-debounced from the widget) --------------

export interface WhatIfCashoutRequest {
  stake_total: string;
  avg_odds: string;
  cashout_odds: string;
  position_side: 'back' | 'lay';
  commission_pct: string;
  market_type?: 'exchange' | 'classic';
}

export interface WhatIfCashoutResponse {
  locked_in_pnl_eur: string;
  breakeven_cashout_odds: string | null;
  pct_of_max_win: string;
  formula_text: string;
}

export function useWhatIfCashout() {
  return useMutation({
    mutationFn: (body: WhatIfCashoutRequest) =>
      api.post<WhatIfCashoutResponse>('/analytics/whatif-cashout', body),
  });
}
