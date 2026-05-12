import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Lock, Settings as SettingsIcon, Eye, EyeOff, Trash2 } from 'lucide-react';
import { Button, Card, Chip, Input, Modal, Skeleton, Switch, useToast } from '@/components/primitives';
import {
  useCreateStrategy,
  useDeleteStrategy,
  useStrategiesList,
  useUpdateStrategy,
  type StrategyFull,
} from '@/queries/strategies';
import { ApiError } from '@/lib/api';

const dateFmt = new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: 'short', year: 'numeric' });

export default function StrategiesPage() {
  const [showInactive, setShowInactive] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();
  const { data, isLoading } = useStrategiesList(showInactive);

  const create = useCreateStrategy();
  const del = useDeleteStrategy();
  const upd = useUpdateStrategy(null);

  const builtins = (data ?? []).filter((s) => s.kind === 'builtin');
  const customs = (data ?? []).filter((s) => s.kind === 'custom');

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <div className="text-2xs uppercase tracking-widest text-text-tertiary">Strategies</div>
          <h1 className="text-2xl font-medium text-text-primary">Strategies</h1>
          <p className="text-sm text-text-secondary">
            Built-in templates ship with the app. Create custom strategies for
            your own playbooks — they get a visual field-schema editor with
            live preview.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Switch checked={showInactive} onChange={setShowInactive} label="Show inactive" />
          <Button variant="primary" size="lg" onClick={() => setCreateOpen(true)}>
            <Plus size={14} strokeWidth={2} />
            New strategy
          </Button>
        </div>
      </header>

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton height={64} />
          <Skeleton height={64} />
        </div>
      ) : (
        <>
          <Section title="Built-in" hint="Locked schemas — only display fields editable.">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {builtins.map((s) => (
                <StrategyCard
                  key={s.id}
                  strategy={s}
                  onToggleActive={(v) => {
                    const m = upd as ReturnType<typeof useUpdateStrategy>;
                    m.mutate({ is_active: v }, {
                      onSuccess: () => toast.push({ tone: 'success', title: 'Updated.' }),
                    });
                  }}
                />
              ))}
            </div>
          </Section>

          <Section
            title="Custom"
            hint={customs.length === 0 ? 'No custom strategies yet — start with "New strategy".' : undefined}
          >
            {customs.length === 0 ? null : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {customs.map((s) => (
                  <StrategyCard
                    key={s.id}
                    strategy={s}
                    onDelete={() => {
                      if (!confirm(`Delete "${s.name}"? Trades referencing it will keep working but the strategy will be soft-deactivated.`)) return;
                      del.mutate(s.id, {
                        onSuccess: (res) => {
                          if (res.status === 'soft_deactivated') {
                            toast.push({
                              tone: 'warn',
                              title: 'Soft-deactivated.',
                              description: `${res.n_trades} trades reference it — kept for history.`,
                            });
                          } else {
                            toast.push({ tone: 'success', title: 'Deleted.' });
                          }
                        },
                        onError: (err) => {
                          const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
                          toast.push({ tone: 'error', title: 'Delete failed.', description: msg });
                        },
                      });
                    }}
                    onToggleActive={(v) => {
                      const m = upd as ReturnType<typeof useUpdateStrategy>;
                      m.mutate({ is_active: v }, {
                        onSuccess: () => toast.push({ tone: 'success', title: 'Updated.' }),
                      });
                    }}
                  />
                ))}
              </div>
            )}
          </Section>
        </>
      )}

      <CreateStrategyModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        submitting={create.isPending}
        onSubmit={(name, color_hex) =>
          create.mutate(
            { name, color_hex, field_schema: { fields: [] } },
            {
              onSuccess: (s) => {
                toast.push({ tone: 'success', title: 'Strategy created.' });
                setCreateOpen(false);
                navigate(`/strategies/${s.id}`);
              },
              onError: (err) => {
                const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
                toast.push({ tone: 'error', title: 'Creation failed.', description: msg });
              },
            },
          )
        }
      />
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xs uppercase tracking-widest text-text-tertiary">{title}</h2>
        {hint ? <span className="text-xs text-text-tertiary">{hint}</span> : null}
      </div>
      {children}
    </section>
  );
}

interface StrategyCardProps {
  strategy: StrategyFull;
  onDelete?: () => void;
  onToggleActive?: (v: boolean) => void;
}

function StrategyCard({ strategy, onDelete, onToggleActive }: StrategyCardProps) {
  const fieldsCount = strategy.field_schema?.fields?.length ?? 0;
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <Link
          to={`/strategies/${strategy.id}`}
          className="flex flex-1 items-start gap-3 min-w-0 group"
        >
          <span
            className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: strategy.color_hex ?? 'var(--accent-brand)' }}
            aria-hidden
          />
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-sm font-medium text-text-primary group-hover:underline">
                {strategy.name}
              </span>
              <Chip tone={strategy.kind === 'builtin' ? 'info' : 'brand'}>
                {strategy.kind}
              </Chip>
              {!strategy.is_active ? <Chip>inactive</Chip> : null}
            </div>
            <div className="mt-1 truncate text-xs text-text-tertiary font-mono">
              {strategy.slug} · {fieldsCount} field{fieldsCount === 1 ? '' : 's'}
              {strategy.template_key ? ` · ${strategy.template_key}` : ''}
            </div>
            {strategy.description ? (
              <p className="mt-2 text-sm text-text-secondary line-clamp-2">{strategy.description}</p>
            ) : null}
          </div>
        </Link>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label={strategy.is_active ? 'Deactivate' : 'Activate'}
            onClick={() => onToggleActive?.(!strategy.is_active)}
            className="rounded p-1.5 text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
            title={strategy.is_active ? 'Deactivate' : 'Activate'}
          >
            {strategy.is_active ? <Eye size={14} strokeWidth={1.5} /> : <EyeOff size={14} strokeWidth={1.5} />}
          </button>
          <Link
            to={`/strategies/${strategy.id}`}
            className="rounded p-1.5 text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
            title={strategy.kind === 'builtin' ? 'View (locked schema)' : 'Edit'}
            aria-label="Edit"
          >
            {strategy.kind === 'builtin' ? <Lock size={14} strokeWidth={1.5} /> : <SettingsIcon size={14} strokeWidth={1.5} />}
          </Link>
          {strategy.kind === 'custom' && onDelete ? (
            <button
              type="button"
              aria-label="Delete"
              onClick={onDelete}
              className="rounded p-1.5 text-text-tertiary hover:bg-accent-loss-bg hover:text-accent-loss"
              title="Delete"
            >
              <Trash2 size={14} strokeWidth={1.5} />
            </button>
          ) : null}
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between text-2xs text-text-tertiary font-mono">
        <span>updated {dateFmt.format(new Date(strategy.updated_at))}</span>
        {strategy.color_hex ? <span>{strategy.color_hex}</span> : null}
      </div>
    </Card>
  );
}

interface CreateModalProps {
  open: boolean;
  onClose: () => void;
  submitting: boolean;
  onSubmit: (name: string, color: string | null) => void;
}

function CreateStrategyModal({ open, onClose, submitting, onSubmit }: CreateModalProps) {
  const [name, setName] = useState('');
  const [color, setColor] = useState('#FFB547');
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New custom strategy"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={submitting}
            onClick={() => onSubmit(name.trim(), color || null)}
            disabled={!name.trim()}
          >
            Create
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          placeholder="Value 1X2"
        />
        <label className="flex items-center gap-3">
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">Accent color</span>
          <input
            type="color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
            className="h-8 w-12 cursor-pointer rounded border border-border-subtle bg-transparent"
          />
          <span className="font-mono text-xs text-text-tertiary">{color}</span>
        </label>
        <p className="text-xs text-text-tertiary">
          You'll add fields next in the field-schema editor.
        </p>
      </div>
    </Modal>
  );
}
