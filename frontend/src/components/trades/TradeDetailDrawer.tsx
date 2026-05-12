/**
 * TradeDetailDrawer: 480px right-side drawer with tabs Overview / Notes /
 * History. Inline-edit on overview fields (double-click to enter edit mode,
 * Enter to save, Esc to cancel). Notes via the same MarkdownEditor.
 */

import { useState } from 'react';
import { Trash2, Pencil } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button, Chip, Drawer, NumberInput, Input, Skeleton } from '@/components/primitives';
import { MarkdownEditor } from '@/components/notes/MarkdownEditor';
import { formatEur, formatOdds, pnlTone } from '@/lib/format';
import { cn } from '@/lib/cn';
import { ApiError } from '@/lib/api';
import { useToast } from '@/components/primitives';
import { useDeleteTrade, usePatchTrade, useTradeDetail } from '@/queries/trade_detail';

type Tab = 'overview' | 'notes' | 'history';

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

interface DrawerProps {
  tradeId: string | null;
  open: boolean;
  onClose: () => void;
}

export function TradeDetailDrawer({ tradeId, open, onClose }: DrawerProps) {
  const [tab, setTab] = useState<Tab>('overview');
  const [editing, setEditing] = useState(false);
  const toast = useToast();
  const { data: trade, isLoading } = useTradeDetail(tradeId);
  const patch = usePatchTrade(tradeId);
  const del = useDeleteTrade();

  return (
    <Drawer
      open={open}
      onClose={() => {
        setEditing(false);
        onClose();
      }}
      title={trade ? `${trade.home_team} vs ${trade.away_team}` : 'Trade'}
      footer={
        trade ? (
          <div className="flex items-center justify-between gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (!confirm('Delete this trade? This cannot be undone.')) return;
                del.mutate(trade.id, {
                  onSuccess: () => {
                    toast.push({ tone: 'success', title: 'Trade deleted.' });
                    onClose();
                  },
                  onError: (err) => {
                    const msg =
                      err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
                    toast.push({ tone: 'error', title: 'Delete failed.', description: msg });
                  },
                });
              }}
            >
              <Trash2 size={14} strokeWidth={1.5} />
              Delete
            </Button>
            {trade.status === 'OPEN' ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() =>
                  patch.mutate(
                    { status: 'CLOSED' },
                    {
                      onSuccess: () =>
                        toast.push({ tone: 'success', title: 'Trade closed.' }),
                    },
                  )
                }
              >
                Close trade
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  patch.mutate(
                    { status: 'OPEN' },
                    {
                      onSuccess: () =>
                        toast.push({ tone: 'info', title: 'Re-opened.' }),
                    },
                  )
                }
              >
                Re-open
              </Button>
            )}
          </div>
        ) : null
      }
    >
      {isLoading || !trade ? (
        <div className="space-y-3">
          <Skeleton height={24} />
          <Skeleton height={16} />
          <Skeleton height={16} />
        </div>
      ) : (
        <div className="space-y-4">
          {/* Result strip */}
          <div className="rounded-lg border border-border-subtle bg-bg-base p-3">
            <div className="flex items-baseline justify-between">
              <div>
                <div className="text-xs text-text-tertiary">{trade.league}</div>
                <div className="text-xs text-text-tertiary font-mono">
                  {dateFmt.format(new Date(trade.kickoff_at))}
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xs uppercase tracking-widest text-text-tertiary">P/L</div>
                <div
                  className={cn(
                    'font-mono text-xl tabular-nums',
                    pnlTone(trade.computed_pnl_eur) === 'gain'
                      ? 'text-accent-gain'
                      : pnlTone(trade.computed_pnl_eur) === 'loss'
                        ? 'text-accent-loss'
                        : 'text-text-tertiary',
                  )}
                >
                  {Number(trade.computed_pnl_eur) >= 0 ? '+' : ''}
                  {formatEur(trade.computed_pnl_eur)}
                </div>
              </div>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Chip tone="brand" dot={trade.strategy.color_hex ?? true}>
                {trade.strategy.name}
              </Chip>
              <Chip>{trade.pnl_mode}</Chip>
              {trade.outcome_label ? <Chip tone="info">{trade.outcome_label}</Chip> : null}
              <Chip tone={trade.status === 'OPEN' ? 'info' : 'neutral'}>{trade.status}</Chip>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-border-subtle">
            {(['overview', 'notes', 'history'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={cn(
                  'relative px-3 py-2 text-sm transition-colors',
                  tab === t ? 'text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                )}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
                {tab === t ? (
                  <span className="absolute inset-x-2 -bottom-px h-px bg-accent-brand" />
                ) : null}
              </button>
            ))}
            <div className="ml-auto flex items-center pb-1">
              {tab === 'overview' ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditing((v) => !v)}
                >
                  <Pencil size={12} strokeWidth={1.5} />
                  {editing ? 'Done' : 'Edit'}
                </Button>
              ) : null}
            </div>
          </div>

          {tab === 'overview' ? (
            <OverviewTab trade={trade} editing={editing} onPatch={(p) => patch.mutate(p)} />
          ) : null}
          {tab === 'notes' ? (
            <NotesTab
              trade={trade}
              onPatch={(p) =>
                patch.mutate(p, {
                  onSuccess: () => toast.push({ tone: 'success', title: 'Notes saved.' }),
                })
              }
            />
          ) : null}
          {tab === 'history' ? <HistoryTab trade={trade} /> : null}
        </div>
      )}
    </Drawer>
  );
}

// --- Tabs ------------------------------------------------------------------

type TradeFull = NonNullable<ReturnType<typeof useTradeDetail>['data']>;

interface OverviewProps {
  trade: TradeFull;
  editing: boolean;
  onPatch: (p: Record<string, unknown>) => void;
}

function OverviewTab({ trade, editing, onPatch }: OverviewProps) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
      <Row label="Stake">
        {editing ? (
          <NumberInput
            value={trade.stake_total}
            step="0.01"
            onBlur={(e) => {
              const v = e.currentTarget.value;
              if (v !== trade.stake_total) onPatch({ stake_total: v });
            }}
            defaultValue={trade.stake_total}
          />
        ) : (
          <span className="font-mono tabular-nums">{formatEur(trade.stake_total)}</span>
        )}
      </Row>
      <Row label="Avg odds">
        {editing ? (
          <NumberInput
            defaultValue={trade.avg_odds}
            step="0.01"
            min="1.01"
            onBlur={(e) => {
              const v = e.currentTarget.value;
              if (v !== trade.avg_odds) onPatch({ avg_odds: v });
            }}
          />
        ) : (
          <span className="font-mono tabular-nums">{formatOdds(trade.avg_odds)}</span>
        )}
      </Row>
      <Row label="Commission">
        <span className="font-mono tabular-nums text-text-secondary">{trade.commission_pct}%</span>
      </Row>
      <Row label="Position side">
        <span className="font-mono text-text-secondary">{trade.position_side ?? '—'}</span>
      </Row>
      {trade.cashout_odds ? (
        <Row label="Cashout odds">
          <span className="font-mono tabular-nums">{formatOdds(trade.cashout_odds)}</span>
        </Row>
      ) : null}
      {trade.manual_pnl_eur ? (
        <Row label="Manual P/L">
          <span className="font-mono tabular-nums">{formatEur(trade.manual_pnl_eur)}</span>
        </Row>
      ) : null}
      <Row label="HT score">
        {editing ? (
          <Input
            defaultValue={
              trade.ht_score_home !== null && trade.ht_score_away !== null
                ? `${trade.ht_score_home}-${trade.ht_score_away}`
                : ''
            }
            placeholder="0-0"
            onBlur={(e) => {
              const m = e.currentTarget.value.match(/^(\d+)-(\d+)$/);
              if (m) onPatch({ ht_score_home: Number(m[1]), ht_score_away: Number(m[2]) });
            }}
          />
        ) : (
          <span className="font-mono tabular-nums">
            {trade.ht_score_home !== null && trade.ht_score_away !== null
              ? `${trade.ht_score_home} - ${trade.ht_score_away}`
              : '—'}
          </span>
        )}
      </Row>
      <Row label="FT score">
        {editing ? (
          <Input
            defaultValue={
              trade.ft_score_home !== null && trade.ft_score_away !== null
                ? `${trade.ft_score_home}-${trade.ft_score_away}`
                : ''
            }
            placeholder="0-0"
            onBlur={(e) => {
              const m = e.currentTarget.value.match(/^(\d+)-(\d+)$/);
              if (m) onPatch({ ft_score_home: Number(m[1]), ft_score_away: Number(m[2]) });
            }}
          />
        ) : (
          <span className="font-mono tabular-nums">
            {trade.ft_score_home !== null && trade.ft_score_away !== null
              ? `${trade.ft_score_home} - ${trade.ft_score_away}`
              : '—'}
          </span>
        )}
      </Row>
      {Object.keys(trade.strategy_data ?? {}).length > 0 ? (
        <div className="col-span-2 mt-2 rounded-lg border border-border-subtle bg-bg-base p-3 text-xs">
          <div className="mb-2 text-2xs uppercase tracking-widest text-text-tertiary">
            Strategy data
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-text-secondary">
            {JSON.stringify(trade.strategy_data, null, 2)}
          </pre>
        </div>
      ) : null}
    </dl>
  );
}

function NotesTab({
  trade,
  onPatch,
}: {
  trade: TradeFull;
  onPatch: (p: Record<string, unknown>) => void;
}) {
  const [draft, setDraft] = useState(trade.notes_md ?? '');
  return (
    <div className="space-y-3">
      <MarkdownEditor value={draft} onChange={setDraft} />
      <div className="flex justify-end">
        <Button
          variant="secondary"
          size="sm"
          disabled={draft === (trade.notes_md ?? '')}
          onClick={() => onPatch({ notes_md: draft || null })}
        >
          Save notes
        </Button>
      </div>
    </div>
  );
}

function HistoryTab({ trade }: { trade: TradeFull }) {
  const events: { ts: string; label: string }[] = [
    { ts: trade.created_at, label: 'Created' },
    { ts: trade.updated_at, label: 'Last edited' },
  ];
  if (trade.closed_at) events.push({ ts: trade.closed_at, label: 'Closed' });
  events.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  return (
    <ol className="space-y-3 text-sm">
      {events.map((e, i) => (
        <li key={`${e.label}-${i}`} className="flex items-start gap-3">
          <span className="mt-1 h-2 w-2 rounded-full bg-accent-brand" aria-hidden />
          <div>
            <div className="text-text-primary">{e.label}</div>
            <div className="text-xs text-text-tertiary font-mono">
              {dateFmt.format(new Date(e.ts))}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-2xs uppercase tracking-widest text-text-tertiary">{label}</dt>
      <dd className="text-text-primary">{children}</dd>
    </>
  );
}

// Optional preview helper, currently unused — kept here so the file stays the
// canonical home for trade-detail rendering helpers.
export function _NotesPreview({ value }: { value: string }) {
  return (
    <div className="prose-trade text-sm text-text-primary">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
    </div>
  );
}
