/**
 * Trade-entry form: strategy selector tabs at top, universal fields,
 * dynamic strategy fields, cash-out toggle, notes, tags. Auto-saves a
 * draft to localStorage every 5s and restores it on next visit.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Input, NumberInput, Segmented, useToast } from '@/components/primitives';
import { CashOutToggle, type CashOutValue } from './CashOutToggle';
import { DynamicFieldRenderer, type FieldDef } from '@/components/strategies/DynamicFieldRenderer';
import { MarkdownEditor } from '@/components/notes/MarkdownEditor';
import { TagPicker } from '@/components/notes/TagPicker';
import { AccountPicker } from '@/components/accounts/AccountPicker';
import { ApiError, api } from '@/lib/api';
import type { StrategyOut } from '@/queries/dashboard';
import { usePreferences } from '@/queries/preferences';
import { useAccounts, type Account, type MarketType } from '@/queries/accounts';

const DRAFT_KEY = 'sportedge:trade-draft';
const DRAFT_INTERVAL_MS = 5_000;

interface TradeDraft {
  strategy_id: string;
  account_id: string;
  home_team: string;
  away_team: string;
  league: string;
  kickoff_at: string;
  stake_total: string;
  avg_odds: string;
  commission_pct: string;
  market_type: MarketType;
  strategy_data: Record<string, unknown>;
  cashout: CashOutValue;
  notes_md: string;
  tags: string[];
}

const DEFAULT_DRAFT: Omit<TradeDraft, 'strategy_id' | 'account_id'> = {
  home_team: '',
  away_team: '',
  league: '',
  kickoff_at: '',
  stake_total: '',
  avg_odds: '',
  commission_pct: '5.00',
  market_type: 'exchange',
  strategy_data: {},
  cashout: {
    mode: 'auto',
    pnl_mode: 'AUTO',
    position_side: 'back',
    outcome_label: null,
  },
  notes_md: '',
  tags: [],
};

function applyAccountDefaults(
  draft: Omit<TradeDraft, 'strategy_id' | 'account_id'>,
  acc: Account | undefined,
): Omit<TradeDraft, 'strategy_id' | 'account_id'> {
  if (!acc) return draft;
  return {
    ...draft,
    commission_pct: acc.commission_pct,
    market_type: acc.market_type,
  };
}

interface TradeFormProps {
  strategies: StrategyOut[];
}

export function TradeForm({ strategies }: TradeFormProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();

  const [draft, setDraft] = useState<TradeDraft | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const fieldSchemaCache = useRef<Map<string, FieldDef[]>>(new Map());
  const prefs = usePreferences();
  const accountsQ = useAccounts();
  const activeAccounts = useMemo(
    () => accountsQ.data?.filter((a) => !a.archived_at) ?? [],
    [accountsQ.data],
  );

  // Restore draft (or build a fresh one with the trader's defaults).
  useEffect(() => {
    if (!activeAccounts.length) return;
    const defaultAccountId =
      prefs.data?.default_account_id ?? activeAccounts[0]?.id ?? '';
    const defaultAccount = activeAccounts.find((a) => a.id === defaultAccountId);
    const fresh = applyAccountDefaults({ ...DEFAULT_DRAFT }, defaultAccount);

    const stored = localStorage.getItem(DRAFT_KEY);
    if (stored) {
      try {
        const d = JSON.parse(stored) as TradeDraft;
        if (!d.market_type) d.market_type = fresh.market_type;
        // Re-anchor the stored draft to a currently-existing account.
        if (!d.account_id || !activeAccounts.some((a) => a.id === d.account_id)) {
          d.account_id = defaultAccountId;
        }
        if (strategies.some((s) => s.id === d.strategy_id)) {
          setDraft(d);
          return;
        }
      } catch {
        // fall through to fresh draft
      }
    }
    if (strategies[0]) {
      setDraft({
        strategy_id: strategies[0].id,
        account_id: defaultAccountId,
        ...fresh,
      });
    }
  }, [strategies, prefs.data, activeAccounts]);

  // Auto-save every 5s.
  useEffect(() => {
    if (!draft) return;
    const t = setInterval(() => {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
      setSavedAt(new Date());
    }, DRAFT_INTERVAL_MS);
    return () => clearInterval(t);
  }, [draft]);

  const activeStrategy = strategies.find((s) => s.id === draft?.strategy_id);
  const fields = useMemo<FieldDef[]>(() => {
    if (!activeStrategy) return [];
    const cached = fieldSchemaCache.current.get(activeStrategy.id);
    if (cached) return cached;
    // strategies returned from /strategies don't carry field_schema in the
    // dashboard query — we re-fetch on demand.
    return [];
  }, [activeStrategy]);

  // Fetch the active strategy's full field_schema (lazy).
  const [fullSchemas, setFullSchemas] = useState<Record<string, FieldDef[]>>({});
  useEffect(() => {
    if (!activeStrategy) return;
    if (fullSchemas[activeStrategy.id]) return;
    api
      .get<{ field_schema: { fields?: FieldDef[] } }>(`/strategies/${activeStrategy.id}`)
      .then((s) => {
        const f = s.field_schema?.fields ?? [];
        fieldSchemaCache.current.set(activeStrategy.id, f);
        setFullSchemas((curr) => ({ ...curr, [activeStrategy.id]: f }));
      })
      .catch(() => {});
  }, [activeStrategy, fullSchemas]);

  const activeFields = activeStrategy ? fullSchemas[activeStrategy.id] ?? fields : [];

  const submit = useMutation({
    mutationFn: async (d: TradeDraft) => {
      const body: Record<string, unknown> = {
        strategy_id: d.strategy_id,
        account_id: d.account_id,
        home_team: d.home_team.trim(),
        away_team: d.away_team.trim(),
        league: d.league.trim(),
        kickoff_at: new Date(d.kickoff_at).toISOString(),
        stake_total: d.stake_total,
        avg_odds: d.avg_odds,
        commission_pct: d.commission_pct,
        market_type: d.market_type,
        pnl_mode: d.cashout.pnl_mode,
        position_side: d.cashout.position_side ?? null,
        outcome_label: d.cashout.outcome_label ?? null,
        strategy_data: d.strategy_data,
        notes_md: d.notes_md || null,
        tags: d.tags,
        status: 'OPEN',
      };
      if (d.cashout.pnl_mode === 'MANUAL') body.manual_pnl_eur = d.cashout.manual_pnl_eur;
      if (d.cashout.pnl_mode === 'CASHOUT_ODDS') {
        body.cashout_odds = d.cashout.cashout_odds;
      }
      return api.post<{ id: string }>('/trades', body);
    },
    onSuccess: (data) => {
      toast.push({ tone: 'success', title: 'Trade saved.', description: `#${data.id.slice(0, 8)}` });
      localStorage.removeItem(DRAFT_KEY);
      qc.invalidateQueries();
      navigate('/trades');
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof ApiError
          ? err.problem.detail || err.problem.title
          : 'Submission failed.';
      toast.push({ tone: 'error', title: 'Could not save trade.', description: msg });
    },
  });

  if (!draft || !activeStrategy) return null;

  const upd = <K extends keyof TradeDraft>(key: K, value: TradeDraft[K]) =>
    setDraft({ ...draft, [key]: value });

  const onAccountChange = (id: string | null) => {
    if (!id) return;
    const acc = activeAccounts.find((a) => a.id === id);
    setDraft({
      ...draft,
      account_id: id,
      commission_pct: acc?.commission_pct ?? draft.commission_pct,
      market_type: acc?.market_type ?? draft.market_type,
    });
  };

  const validateBeforeSubmit = (): string | null => {
    if (!draft.account_id) return 'Account is required.';
    if (!draft.home_team.trim() || !draft.away_team.trim()) return 'Match teams are required.';
    if (!draft.league.trim()) return 'League is required.';
    if (!draft.kickoff_at) return 'Kickoff time is required.';
    if (!draft.stake_total || Number(draft.stake_total) <= 0) return 'Stake must be > 0.';
    if (!draft.avg_odds || Number(draft.avg_odds) < 1.01) return 'Average odds must be ≥ 1.01.';
    if (draft.cashout.pnl_mode === 'MANUAL' && !draft.cashout.manual_pnl_eur) {
      return 'Manual P/L is required.';
    }
    if (draft.cashout.pnl_mode === 'CASHOUT_ODDS' && !draft.cashout.cashout_odds) {
      return 'Cashout odds are required.';
    }
    if (draft.cashout.pnl_mode === 'AUTO' && !draft.cashout.outcome_label) {
      return 'Outcome label is required for AUTO mode.';
    }
    return null;
  };

  return (
    <div className="space-y-4">
      {/* Account selector */}
      {activeAccounts.length > 1 ? (
        <Card header={<span>Account</span>}>
          <AccountPicker
            accounts={activeAccounts}
            value={draft.account_id || null}
            onChange={onAccountChange}
          />
        </Card>
      ) : null}

      {/* Strategy selector tabs */}
      <div className="flex flex-wrap gap-2">
        {strategies.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => upd('strategy_id', s.id)}
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              s.id === draft.strategy_id
                ? 'border-accent-brand bg-accent-brand-bg text-accent-brand'
                : 'border-border-subtle text-text-secondary hover:border-border-strong hover:text-text-primary'
            }`}
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: s.color_hex ?? 'var(--accent-brand)' }}
              aria-hidden
            />
            <span>{s.name}</span>
            <span className="text-text-tertiary">· {s.kind}</span>
          </button>
        ))}
      </div>

      <Card header={<span>Match</span>}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Home team"
            value={draft.home_team}
            onChange={(e) => upd('home_team', e.target.value)}
          />
          <Input
            label="Away team"
            value={draft.away_team}
            onChange={(e) => upd('away_team', e.target.value)}
          />
          <Input
            label="League"
            value={draft.league}
            onChange={(e) => upd('league', e.target.value)}
          />
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Kickoff</span>
            <input
              type="datetime-local"
              value={draft.kickoff_at}
              onChange={(e) => upd('kickoff_at', e.target.value)}
              className="h-9 rounded-lg border border-border-subtle bg-bg-overlay px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
            />
          </label>
        </div>
      </Card>

      <Card header={<span>Stake & odds</span>}>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <NumberInput
              label="Stake total (€)"
              step="0.01"
              min="0"
              value={draft.stake_total}
              onChange={(e) => upd('stake_total', e.target.value)}
            />
            <NumberInput
              label="Average odds"
              step="0.01"
              min="1.01"
              value={draft.avg_odds}
              onChange={(e) => upd('avg_odds', e.target.value)}
            />
            <NumberInput
              label="Commission (%)"
              step="0.01"
              min="0"
              max="100"
              value={draft.commission_pct}
              onChange={(e) => upd('commission_pct', e.target.value)}
              disabled={draft.market_type === 'classic'}
              hint={
                draft.market_type === 'classic'
                  ? 'Classic — quoted odds already net'
                  : undefined
              }
            />
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">
              Market type
            </span>
            <Segmented<MarketType>
              value={draft.market_type}
              onChange={(v) => {
                upd('market_type', v);
                if (v === 'classic') upd('commission_pct', '0.00');
              }}
              options={[
                { value: 'exchange', label: 'Exchange (commission applies)' },
                { value: 'classic',  label: 'Classic (no commission)' },
              ]}
            />
          </label>
        </div>
      </Card>

      {activeFields.length > 0 ? (
        <Card header={<span>{activeStrategy.name} fields</span>}>
          <DynamicFieldRenderer
            fields={activeFields}
            values={draft.strategy_data}
            onChange={(k, v) =>
              upd('strategy_data', { ...draft.strategy_data, [k]: v })
            }
          />
        </Card>
      ) : null}

      <CashOutToggle
        value={draft.cashout}
        onChange={(v) => upd('cashout', v)}
        stakeTotal={draft.stake_total}
        avgOdds={draft.avg_odds}
        commissionPct={draft.commission_pct}
        marketType={draft.market_type}
      />

      <Card header={<span>Notes</span>}>
        <MarkdownEditor value={draft.notes_md} onChange={(v) => upd('notes_md', v)} />
      </Card>

      <Card header={<span>Tags</span>}>
        <TagPicker value={draft.tags} onChange={(v) => upd('tags', v)} />
      </Card>

      <div className="flex items-center justify-between gap-4 sticky bottom-0 -mx-6 -mb-6 border-t border-border-subtle bg-bg-base/95 px-6 py-3 backdrop-blur">
        <div className="text-xs text-text-tertiary">
          {savedAt ? (
            <>Draft saved {savedAt.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</>
          ) : (
            'Draft autosaves every 5s'
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={() => {
              localStorage.removeItem(DRAFT_KEY);
              const defaultAccountId =
                prefs.data?.default_account_id ?? activeAccounts[0]?.id ?? '';
              const defaultAccount = activeAccounts.find(
                (a) => a.id === defaultAccountId,
              );
              setDraft({
                strategy_id: strategies[0]!.id,
                account_id: defaultAccountId,
                ...applyAccountDefaults({ ...DEFAULT_DRAFT }, defaultAccount),
              });
              toast.push({ tone: 'info', title: 'Draft cleared.' });
            }}
          >
            Clear draft
          </Button>
          <Button
            variant="primary"
            size="lg"
            loading={submitting}
            onClick={async () => {
              const err = validateBeforeSubmit();
              if (err) {
                toast.push({ tone: 'warn', title: 'Form incomplete.', description: err });
                return;
              }
              setSubmitting(true);
              try {
                await submit.mutateAsync(draft);
              } finally {
                setSubmitting(false);
              }
            }}
          >
            Save trade
          </Button>
        </div>
      </div>
    </div>
  );
}
