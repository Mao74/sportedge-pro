/**
 * Settings → Accounts panel. Lists every trading account (with archived
 * filter) and lets the user create / rename / archive / unarchive / delete
 * each one. The "default account" picker drives which account is
 * pre-selected on the new-trade form.
 */

import { useState } from 'react';
import {
  Archive,
  ArchiveRestore,
  Briefcase,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react';
import {
  Button,
  Card,
  Chip,
  EmptyState,
  Input,
  Modal,
  NumberInput,
  Segmented,
  Skeleton,
  Switch,
  useToast,
} from '@/components/primitives';
import {
  useAccounts,
  useArchiveAccount,
  useCreateAccount,
  useDeleteAccount,
  useUnarchiveAccount,
  useUpdateAccount,
  KNOWN_VENUES,
  type Account,
  type AccountUpdate,
  type MarketType,
} from '@/queries/accounts';
import { usePatchPreferences, usePreferences } from '@/queries/preferences';
import { ApiError } from '@/lib/api';
import { formatEur } from '@/lib/format';
import { cn } from '@/lib/cn';

const DEFAULT_DRAFT = {
  name: '',
  venue: 'betfair',
  market_type: 'exchange' as MarketType,
  commission_pct: '5.00',
  opening_balance: '1000.00',
};

type Draft = typeof DEFAULT_DRAFT;

export function AccountsPanel() {
  const [includeArchived, setIncludeArchived] = useState(false);
  const accountsQ = useAccounts({ includeArchived });
  const prefsQ = usePreferences();
  const patchPrefs = usePatchPreferences();
  const create = useCreateAccount();
  const update = useUpdateAccount();
  const archive = useArchiveAccount();
  const unarchive = useUnarchiveAccount();
  const remove = useDeleteAccount();
  const toast = useToast();

  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);

  if (accountsQ.isLoading || prefsQ.isLoading) {
    return <Card><Skeleton height={220} /></Card>;
  }
  const accounts = accountsQ.data ?? [];
  const activeAccounts = accounts.filter((a) => !a.archived_at);

  const handleCreate = (draft: Draft, openingBalance: string) => {
    create.mutate(
      {
        name: draft.name.trim(),
        venue: draft.venue,
        market_type: draft.market_type,
        commission_pct: draft.commission_pct,
        opening_balance: openingBalance,
      },
      {
        onSuccess: () => {
          toast.push({ tone: 'success', title: 'Account created.' });
          setShowCreate(false);
        },
        onError: (err) => {
          const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
          toast.push({ tone: 'error', title: 'Could not create account.', description: msg });
        },
      },
    );
  };

  const handlePatch = (id: string, patch: AccountUpdate, onDone?: () => void) => {
    update.mutate(
      { id, patch },
      {
        onSuccess: () => {
          toast.push({ tone: 'success', title: 'Account updated.' });
          onDone?.();
        },
        onError: (err) => {
          const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
          toast.push({ tone: 'error', title: 'Save failed.', description: msg });
        },
      },
    );
  };

  const handleDelete = (acc: Account) => {
    if (!window.confirm(`Delete account "${acc.name}"? This cannot be undone.`)) return;
    remove.mutate(acc.id, {
      onSuccess: () => toast.push({ tone: 'success', title: 'Account deleted.' }),
      onError: (err) => {
        const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
        toast.push({ tone: 'error', title: 'Delete blocked.', description: msg });
      },
    });
  };

  const handleArchiveToggle = (acc: Account) => {
    if (acc.archived_at) {
      unarchive.mutate(acc.id, {
        onSuccess: () => toast.push({ tone: 'success', title: 'Account restored.' }),
      });
    } else {
      archive.mutate(acc.id, {
        onSuccess: () => toast.push({ tone: 'info', title: 'Account archived.' }),
      });
    }
  };

  const onDefaultChange = (id: string) => {
    patchPrefs.mutate(
      { default_account_id: id },
      { onSuccess: () => toast.push({ tone: 'success', title: 'Default account updated.' }) },
    );
  };

  return (
    <>
      <Card
        header={
          <>
            <span className="flex items-center gap-2 text-text-primary">
              <Briefcase size={14} strokeWidth={1.5} />
              Accounts
            </span>
            <span className="text-xs text-text-tertiary">
              Track multiple bankrolls — one per venue.
            </span>
          </>
        }
      >
        <div className="space-y-5">
          {accounts.length === 0 ? (
            <EmptyState
              size="sm"
              icon={Briefcase}
              title="No accounts yet"
              description="Create your first account to start booking trades."
              action={
                <Button variant="primary" onClick={() => setShowCreate(true)}>
                  <Plus size={14} strokeWidth={1.5} /> New account
                </Button>
              }
            />
          ) : (
            <>
              {/* Default account */}
              <div className="space-y-2">
                <span className="text-2xs uppercase tracking-widest text-text-tertiary">
                  Default account (pre-selected on new trade)
                </span>
                <select
                  value={prefsQ.data?.default_account_id ?? ''}
                  onChange={(e) => onDefaultChange(e.target.value)}
                  className="h-9 rounded-lg border border-border-subtle bg-bg-overlay px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
                >
                  <option value="" disabled>
                    Select an account…
                  </option>
                  {activeAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} · {a.market_type} · {a.commission_pct}%
                    </option>
                  ))}
                </select>
              </div>

              {/* Table-like list */}
              <ul className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-bg-overlay">
                {accounts.map((acc) => {
                  const isDefault = prefsQ.data?.default_account_id === acc.id;
                  return (
                    <li
                      key={acc.id}
                      className={cn(
                        'flex items-center justify-between gap-3 px-4 py-3',
                        acc.archived_at && 'opacity-60',
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-text-primary">{acc.name}</span>
                          <Chip tone={acc.market_type === 'exchange' ? 'brand' : 'info'}>
                            {acc.market_type}
                          </Chip>
                          {isDefault ? <Chip tone="gain">default</Chip> : null}
                          {acc.archived_at ? <Chip tone="neutral">archived</Chip> : null}
                        </div>
                        <div className="mt-0.5 text-xs text-text-tertiary tabular-nums">
                          {acc.venue} · {acc.commission_pct}% · opening{' '}
                          {formatEur(acc.opening_balance)} · since{' '}
                          {new Date(acc.opened_at).toLocaleDateString('it-IT')}
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditing(acc)}
                          aria-label="Edit account"
                        >
                          <Pencil size={14} strokeWidth={1.5} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleArchiveToggle(acc)}
                          aria-label={acc.archived_at ? 'Restore' : 'Archive'}
                        >
                          {acc.archived_at ? (
                            <ArchiveRestore size={14} strokeWidth={1.5} />
                          ) : (
                            <Archive size={14} strokeWidth={1.5} />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(acc)}
                          aria-label="Delete"
                        >
                          <Trash2 size={14} strokeWidth={1.5} />
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-xs text-text-tertiary">
                  <Switch checked={includeArchived} onChange={setIncludeArchived} />
                  Show archived
                </label>
                <Button variant="secondary" size="sm" onClick={() => setShowCreate(true)}>
                  <Plus size={14} strokeWidth={1.5} /> New account
                </Button>
              </div>
            </>
          )}
        </div>
      </Card>

      {showCreate ? (
        <AccountFormModal
          title="New account"
          onClose={() => setShowCreate(false)}
          submitLabel="Create"
          submitting={create.isPending}
          onSubmit={({ draft, openingBalance }) => handleCreate(draft, openingBalance)}
        />
      ) : null}
      {editing ? (
        <AccountFormModal
          title={`Edit "${editing.name}"`}
          onClose={() => setEditing(null)}
          submitLabel="Save"
          submitting={update.isPending}
          initial={{
            name: editing.name,
            venue: editing.venue,
            market_type: editing.market_type,
            commission_pct: editing.commission_pct,
            opening_balance: editing.opening_balance,
          }}
          onSubmit={({ draft, openingBalance }) =>
            handlePatch(
              editing.id,
              {
                name: draft.name.trim(),
                venue: draft.venue,
                market_type: draft.market_type,
                commission_pct: draft.commission_pct,
                opening_balance:
                  openingBalance !== editing.opening_balance ? openingBalance : undefined,
              },
              () => setEditing(null),
            )
          }
        />
      ) : null}
    </>
  );
}


interface AccountFormModalProps {
  title: string;
  submitLabel: string;
  submitting: boolean;
  initial?: Draft;
  onClose: () => void;
  onSubmit: (payload: { draft: Draft; openingBalance: string }) => void;
}

function AccountFormModal({
  title,
  submitLabel,
  submitting,
  initial,
  onClose,
  onSubmit,
}: AccountFormModalProps) {
  const [draft, setDraft] = useState<Draft>(initial ?? DEFAULT_DRAFT);
  const [openingBalance, setOpeningBalance] = useState(initial?.opening_balance ?? '1000.00');

  const upd = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const onVenue = (next: string) => {
    upd('venue', next);
    const known = KNOWN_VENUES.find((k) => k.value === next);
    if (!known) return;
    upd('market_type', known.market_type);
    upd('commission_pct', known.default_commission);
  };

  const onMarketType = (next: MarketType) => {
    upd('market_type', next);
    if (next === 'classic') upd('commission_pct', '0.00');
  };

  const valid = draft.name.trim().length > 0;

  return (
    <Modal open onClose={onClose} title={title}>
      <div className="space-y-4">
        <Input
          label="Name"
          value={draft.name}
          onChange={(e) => upd('name', e.target.value)}
          placeholder="e.g. Betfair main"
        />
        <label className="flex flex-col gap-1.5">
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">Venue</span>
          <select
            value={KNOWN_VENUES.some((k) => k.value === draft.venue) ? draft.venue : 'other'}
            onChange={(e) => onVenue(e.target.value)}
            className="h-9 rounded-lg border border-border-subtle bg-bg-overlay px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
          >
            <optgroup label="Betting exchanges">
              {KNOWN_VENUES.filter((k) => k.market_type === 'exchange' && k.value !== 'other').map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </optgroup>
            <optgroup label="Classic bookmakers">
              {KNOWN_VENUES.filter((k) => k.market_type === 'classic').map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </optgroup>
            <option value="other">Other</option>
          </select>
        </label>
        <div className="space-y-2">
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">Market type</span>
          <Segmented<MarketType>
            value={draft.market_type}
            onChange={onMarketType}
            options={[
              { value: 'exchange', label: 'Exchange (commission)' },
              { value: 'classic',  label: 'Classic (no commission)' },
            ]}
          />
        </div>
        <NumberInput
          label="Commission (%)"
          step="0.01" min="0" max="100"
          value={draft.commission_pct}
          onChange={(e) => upd('commission_pct', e.target.value)}
          suffix="%"
          disabled={draft.market_type === 'classic'}
          hint={
            draft.market_type === 'classic'
              ? 'Disabled — Classic markets have no commission.'
              : undefined
          }
        />
        <NumberInput
          label="Opening balance (€)"
          step="0.01" min="0"
          value={openingBalance}
          onChange={(e) => setOpeningBalance(e.target.value)}
          hint="The bankroll baseline for this account. Edit any time during setup; for ongoing money movements after trades, prefer Bankroll → Deposit/Withdrawal."
        />
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button
          variant="primary"
          loading={submitting}
          disabled={!valid}
          onClick={() => onSubmit({ draft, openingBalance })}
        >
          {submitLabel}
        </Button>
      </div>
    </Modal>
  );
}


