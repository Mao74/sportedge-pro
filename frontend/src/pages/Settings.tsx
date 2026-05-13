import { useEffect, useState } from 'react';
import {
  Folder,
  Upload,
  RefreshCw,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Wallet,
  Palette,
  Sun,
  Moon,
} from 'lucide-react';
import {
  Button,
  Card,
  EmptyState,
  Input,
  NumberInput,
  Segmented,
  Skeleton,
  Switch,
  useToast,
} from '@/components/primitives';
import {
  useExportAll,
  useObsidianStatus,
  usePatchObsidianConfig,
  useSyncNow,
} from '@/queries/obsidian';
import {
  useAdjustBankroll,
  useBankrollSnapshots,
} from '@/queries/preferences';
import { useAccounts } from '@/queries/accounts';
import { useBankrollCurrent } from '@/queries/dashboard';
import { useTheme, type ThemeName } from '@/lib/theme';
import { ApiError } from '@/lib/api';
import { formatEur, pnlTone } from '@/lib/format';
import { cn } from '@/lib/cn';
import { DataIoPanel } from '@/components/settings/DataIoPanel';
import { AccountsPanel } from '@/components/settings/AccountsPanel';
import { AccountPicker } from '@/components/accounts/AccountPicker';
import { useUiStore } from '@/stores/ui';

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

export default function Settings() {
  return (
    <div className="space-y-6">
      <header>
        <div className="text-2xs uppercase tracking-widest text-text-tertiary">Settings</div>
        <h1 className="text-2xl font-medium text-text-primary">Settings</h1>
        <p className="text-sm text-text-secondary">
          Accounts, bankroll housekeeping, data I/O, Obsidian vault.
        </p>
      </header>
      <AccountsPanel />
      <BankrollPanel />
      <AppearancePanel />
      <DataIoPanel />
      <ObsidianPanel />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bankroll (per-account)
// ---------------------------------------------------------------------------

function BankrollPanel() {
  const accountsQ = useAccounts();
  const accounts = accountsQ.data?.filter((a) => !a.archived_at) ?? [];
  const [accountId, setAccountId] = useState<string | null>(null);

  // Default the selector to the first active account once they load.
  useEffect(() => {
    if (accountId === null && accounts[0]) setAccountId(accounts[0].id);
  }, [accounts, accountId]);

  const current = useBankrollCurrent(accountId);
  const snapshots = useBankrollSnapshots(10, accountId);
  const adjust = useAdjustBankroll();
  const toast = useToast();

  const [kind, setKind] = useState<'deposit' | 'withdrawal'>('deposit');
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('');

  const submit = () => {
    if (!amount || Number(amount) <= 0) {
      toast.push({ tone: 'warn', title: 'Amount required', description: 'Enter a positive amount.' });
      return;
    }
    if (!accountId) {
      toast.push({ tone: 'warn', title: 'Pick an account first.' });
      return;
    }
    adjust.mutate(
      { amount_eur: amount, kind, notes: notes.trim() || undefined, account_id: accountId },
      {
        onSuccess: () => {
          toast.push({
            tone: 'success',
            title: kind === 'deposit' ? 'Deposit recorded.' : 'Withdrawal recorded.',
          });
          setAmount('');
          setNotes('');
        },
        onError: (err) => {
          const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
          toast.push({ tone: 'error', title: 'Adjustment failed.', description: msg });
        },
      },
    );
  };

  return (
    <Card
      header={
        <>
          <span className="flex items-center gap-2 text-text-primary">
            <Wallet size={14} strokeWidth={1.5} />
            Bankroll
          </span>
          <span className="text-xs text-text-tertiary">Deposits, withdrawals, and recent snapshots — per account.</span>
        </>
      }
    >
      <div className="space-y-5">
        {accounts.length > 0 ? (
          <AccountPicker accounts={accounts} value={accountId} onChange={setAccountId} />
        ) : null}

        <div className="flex items-baseline justify-between rounded-lg border border-border-subtle bg-bg-overlay px-4 py-3">
          <div>
            <div className="text-2xs uppercase tracking-widest text-text-tertiary">Current balance</div>
            <div className="mt-0.5 font-mono text-xl tabular-nums text-text-primary">
              {current.data ? formatEur(current.data.balance_eur) : <Skeleton width={120} height={24} />}
            </div>
          </div>
          {current.data ? (
            <div className="text-right">
              <div className="text-2xs uppercase tracking-widest text-text-tertiary">Since inception</div>
              <div
                className={cn(
                  'mt-0.5 font-mono tabular-nums text-sm',
                  pnlTone(current.data.since_inception_pnl_eur) === 'gain'
                    ? 'text-accent-gain'
                    : pnlTone(current.data.since_inception_pnl_eur) === 'loss'
                      ? 'text-accent-loss'
                      : 'text-text-tertiary',
                )}
              >
                {Number(current.data.since_inception_pnl_eur) >= 0 ? '+' : ''}
                {formatEur(current.data.since_inception_pnl_eur)}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-3 rounded-lg border border-border-subtle bg-bg-overlay p-4">
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">New adjustment</div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[180px_1fr_1fr_auto]">
            <Segmented<'deposit' | 'withdrawal'>
              value={kind}
              onChange={setKind}
              options={[
                { value: 'deposit', label: 'Deposit' },
                { value: 'withdrawal', label: 'Withdrawal' },
              ]}
            />
            <NumberInput
              label="Amount (€)"
              step="0.01"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <Input
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="optional"
            />
            <div className="flex items-end">
              <Button
                variant="primary"
                size="lg"
                className="w-full"
                onClick={submit}
                loading={adjust.isPending}
              >
                {kind === 'deposit' ? (
                  <ArrowDownToLine size={14} strokeWidth={1.5} />
                ) : (
                  <ArrowUpFromLine size={14} strokeWidth={1.5} />
                )}
                Record
              </Button>
            </div>
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-2xs uppercase tracking-widest text-text-tertiary">Recent snapshots (10)</span>
            <span className="text-xs text-text-tertiary">
              Full equity curve on the dashboard
            </span>
          </div>
          {snapshots.isLoading ? (
            <Skeleton height={120} />
          ) : !snapshots.data || snapshots.data.length === 0 ? (
            <EmptyState
              size="sm"
              icon={Wallet}
              title="No snapshots yet"
              description="The first deposit or daily auto-snapshot will appear here."
            />
          ) : (
            <ul className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-bg-overlay">
              {snapshots.data.map((s) => {
                const dep = Number(s.deposit_eur);
                const wd = Number(s.withdrawal_eur);
                const tag =
                  dep > 0 ? `+${formatEur(s.deposit_eur)} deposit` :
                  wd > 0 ? `−${formatEur(s.withdrawal_eur)} withdrawal` :
                  'auto-snapshot';
                const tagTone =
                  dep > 0 ? 'text-accent-gain' :
                  wd > 0 ? 'text-accent-loss' :
                  'text-text-tertiary';
                return (
                  <li key={s.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-xs text-text-tertiary">
                        {dateFmt.format(new Date(s.taken_at))}
                      </div>
                      <div className={cn('font-mono text-sm tabular-nums', tagTone)}>{tag}</div>
                      {s.notes ? (
                        <div className="text-xs text-text-secondary truncate">{s.notes}</div>
                      ) : null}
                    </div>
                    <div className="text-right font-mono text-sm tabular-nums text-text-primary">
                      {formatEur(s.balance_eur)}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Appearance (theme only — venue/commission moved to AccountsPanel)
// ---------------------------------------------------------------------------

function AppearancePanel() {
  const [theme, setTheme] = useTheme();

  return (
    <Card
      header={
        <>
          <span className="flex items-center gap-2 text-text-primary">
            <Palette size={14} strokeWidth={1.5} />
            Appearance
          </span>
          <span className="text-xs text-text-tertiary">Theme preference.</span>
        </>
      }
    >
      <div className="space-y-2">
        <span className="text-2xs uppercase tracking-widest text-text-tertiary">Theme</span>
        <Segmented<ThemeName>
          value={theme}
          onChange={setTheme}
          options={[
            { value: 'dark', label: '🌙 Dark' },
            { value: 'light', label: '☀️ Light' },
          ]}
        />
        <p className="text-xs text-text-tertiary">
          {theme === 'dark' ? (
            <span className="inline-flex items-center gap-1">
              <Moon size={11} strokeWidth={1.5} /> Trader-grade default.
            </span>
          ) : (
            <span className="inline-flex items-center gap-1">
              <Sun size={11} strokeWidth={1.5} /> High-contrast daytime palette.
            </span>
          )}
        </p>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Obsidian (unchanged behaviour)
// ---------------------------------------------------------------------------

function ObsidianPanel() {
  const status = useObsidianStatus();
  const patch = usePatchObsidianConfig();
  const exportAll = useExportAll();
  const syncNow = useSyncNow();
  const toast = useToast();

  const [vaultDraft, setVaultDraft] = useState<string>('');

  useEffect(() => {
    if (status.data?.vault_path) setVaultDraft(status.data.vault_path);
  }, [status.data?.vault_path]);

  if (status.isLoading || !status.data) {
    return <Skeleton height={300} />;
  }

  const s = status.data;
  const dirtyVault = vaultDraft !== s.vault_path;

  return (
    <Card
      header={
        <>
          <span className="flex items-center gap-2 text-text-primary">
            <Folder size={14} strokeWidth={1.5} />
            Obsidian
          </span>
          <span className="text-xs text-text-tertiary">
            Filesystem-based vault sync. No plugin required.
          </span>
        </>
      }
    >
      <div className="space-y-5">
        <div className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-overlay px-4 py-3">
          <div>
            <div className="text-sm text-text-primary">Enable integration</div>
            <div className="text-xs text-text-tertiary">
              When on, trade writes queue an asynchronous re-export to the vault.
            </div>
          </div>
          <Switch
            checked={s.enabled}
            onChange={(v) =>
              patch.mutate(
                { enabled: v },
                {
                  onSuccess: () =>
                    toast.push({ tone: v ? 'success' : 'info', title: v ? 'Enabled.' : 'Disabled.' }),
                },
              )
            }
          />
        </div>

        <Input
          label="Vault path (inside the container)"
          value={vaultDraft}
          onChange={(e) => setVaultDraft(e.target.value)}
          hint="Default /vault — bound to OBSIDIAN_VAULT_PATH on the host."
        />
        {dirtyVault ? (
          <div className="flex justify-end">
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                patch.mutate(
                  { vault_path: vaultDraft },
                  { onSuccess: () => toast.push({ tone: 'success', title: 'Vault path saved.' }) },
                )
              }
            >
              Save vault path
            </Button>
          </div>
        ) : null}

        <label className="flex flex-col gap-1.5">
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">Sync mode</span>
          <select
            value={s.sync_mode}
            onChange={(e) =>
              patch.mutate({ sync_mode: e.target.value as 'export_only' | 'two_way' | 'manual_only' })
            }
            className="h-9 rounded-lg border border-border-subtle bg-bg-overlay px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
          >
            <option value="export_only">export_only — app → vault only (safest)</option>
            <option value="two_way">two_way — also imports notes via Sync now</option>
            <option value="manual_only">manual_only — runs only when you click Export now</option>
          </select>
        </label>

        <div className="flex flex-wrap items-center gap-2 border-t border-border-subtle pt-4">
          <Button
            variant="primary"
            size="md"
            disabled={!s.enabled}
            loading={exportAll.isPending}
            onClick={() =>
              exportAll.mutate(undefined, {
                onSuccess: (summary) =>
                  toast.push({
                    tone: 'success',
                    title: 'Vault exported.',
                    description: `${summary.trades_exported} trades, ${summary.daily_exported} daily, ${summary.strategies_exported} strategies in ${summary.took_ms}ms.`,
                  }),
                onError: (err) => {
                  const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
                  toast.push({ tone: 'error', title: 'Export failed.', description: msg });
                },
              })
            }
          >
            <Upload size={14} strokeWidth={1.5} />
            Export now
          </Button>
          <Button
            variant="secondary"
            size="md"
            disabled={!s.enabled || s.sync_mode === 'export_only'}
            loading={syncNow.isPending}
            onClick={() =>
              syncNow.mutate(undefined, {
                onSuccess: (events) => {
                  const updated = events.filter((e) => e.action === 'updated').length;
                  const conflicts = events.filter((e) => e.action === 'conflict').length;
                  toast.push({
                    tone: conflicts > 0 ? 'warn' : 'success',
                    title: 'Sync complete.',
                    description: `${updated} updated, ${conflicts} conflict${conflicts === 1 ? '' : 's'}.`,
                  });
                },
                onError: (err) => {
                  const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
                  toast.push({ tone: 'error', title: 'Sync failed.', description: msg });
                },
              })
            }
          >
            <RefreshCw size={14} strokeWidth={1.5} />
            Sync now
          </Button>
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <dt className="text-text-tertiary">Last sync</dt>
          <dd className="text-text-primary font-mono">
            {s.last_sync_at ? dateFmt.format(new Date(s.last_sync_at)) : '—'}
          </dd>
          <dt className="text-text-tertiary">Conflicts</dt>
          <dd className={s.conflict_count > 0 ? 'text-accent-warn font-mono' : 'text-text-primary font-mono'}>
            {s.conflict_count > 0 ? (
              <button
                type="button"
                onClick={() => useUiStore.getState().setConflictsOpen(true)}
                className="underline hover:text-accent-warn/80"
              >
                {s.conflict_count} pending — resolve
              </button>
            ) : (
              <>0</>
            )}
          </dd>
          {s.last_error ? (
            <>
              <dt className="text-text-tertiary">Last error</dt>
              <dd className="text-accent-loss font-mono break-all">{s.last_error}</dd>
            </>
          ) : null}
        </dl>

        {!s.enabled ? (
          <EmptyState
            size="sm"
            icon={AlertTriangle}
            title="Integration is off"
            description="Toggle on, then click Export now to populate the vault. Files outside Trades/Daily/Strategies/Dashboards/_meta are never touched."
          />
        ) : null}
      </div>
    </Card>
  );
}
