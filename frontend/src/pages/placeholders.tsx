/**
 * Placeholder pages for routes whose real implementation lands in steps 9-13.
 * Each shows a one-line hint about what arrives next so the navigation
 * doesn't feel broken in the meantime.
 */

import { useEffect, useState } from 'react';
import { Card, MetricCard, Skeleton } from '@/components/primitives';
import { api } from '@/lib/api';

interface HealthResp {
  status: string;
  api: string;
  database: string;
  version: string;
}

interface BankrollCurrent {
  balance_eur: string;
  last_snapshot_at: string | null;
  since_inception_pnl_eur: string;
  since_inception_roi_pct: string;
}

const _placeholderCopy = {
  trades: {
    title: 'Trade log',
    body: 'TanStack table with virtualization, filter chips and detail drawer arrives in step 11.',
  },
  newTrade: {
    title: 'New trade',
    body: 'Strategy-aware dynamic form with cash-out toggle arrives in step 10.',
  },
  strategies: {
    title: 'Strategies',
    body: 'List + visual field-schema builder arrives in step 12.',
  },
  analytics: {
    title: 'Analytics',
    body: 'Tabs (Overview, Drawdown, Monte Carlo, Calendar, Per-strategy) arrive in step 13.',
  },
  whatif: {
    title: 'What-if cash-out',
    body: 'The standalone widget arrives alongside Analytics in step 13.',
  },
  settings: {
    title: 'Settings',
    body: 'Bankroll adjustments, theme, Obsidian config arrive in step 14b.',
  },
};

function PlaceholderCard({ title, body }: { title: string; body: string }) {
  return (
    <Card>
      <div className="space-y-2">
        <div className="text-2xs uppercase tracking-widest text-text-tertiary">Coming up</div>
        <h2 className="text-lg font-medium text-text-primary">{title}</h2>
        <p className="text-sm text-text-secondary">{body}</p>
      </div>
    </Card>
  );
}

export function DashboardPlaceholder() {
  const [health, setHealth] = useState<HealthResp | null>(null);
  const [bankroll, setBankroll] = useState<BankrollCurrent | null>(null);

  useEffect(() => {
    api.get<HealthResp>('/health').then(setHealth).catch(() => {});
    api.get<BankrollCurrent>('/bankroll/current').then(setBankroll).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <div className="text-2xs uppercase tracking-widest text-text-tertiary">Bootstrap</div>
        <h1 className="text-2xl font-medium text-text-primary">Welcome, trader.</h1>
        <p className="text-text-secondary text-sm">
          Backend, database and frontend are running. The full dashboard arrives in step 9.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <MetricCard
          label="Bankroll"
          value={bankroll ? `€${bankroll.balance_eur}` : <Skeleton width="60%" height={28} />}
          delta={bankroll ? `Since inception ${bankroll.since_inception_pnl_eur}` : undefined}
          deltaTone="zero"
          sparkTone="brand"
        />
        <MetricCard
          label="Backend health"
          value={health?.status ?? <Skeleton width="40%" height={28} />}
          delta={health ? `version ${health.version}` : undefined}
          deltaTone="zero"
        />
        <MetricCard
          label="Database"
          value={health?.database ?? <Skeleton width="40%" height={28} />}
          delta={health ? 'connected' : undefined}
          deltaTone={health?.database === 'ok' ? 'gain' : 'zero'}
          sparkTone="info"
        />
      </div>

      <PlaceholderCard {...{
        title: 'Dashboard build is up next',
        body: 'Step 9 wires the equity curve, open trades list and by-strategy breakdown to the live data shown above.',
      }} />
    </div>
  );
}

export function TradesPlaceholder() {
  return <PlaceholderCard {..._placeholderCopy.trades} />;
}
export function NewTradePlaceholder() {
  return <PlaceholderCard {..._placeholderCopy.newTrade} />;
}
export function StrategiesPlaceholder() {
  return <PlaceholderCard {..._placeholderCopy.strategies} />;
}
export function AnalyticsPlaceholder() {
  return <PlaceholderCard {..._placeholderCopy.analytics} />;
}
export function WhatIfPlaceholder() {
  return <PlaceholderCard {..._placeholderCopy.whatif} />;
}
export function SettingsPlaceholder() {
  return <PlaceholderCard {..._placeholderCopy.settings} />;
}
