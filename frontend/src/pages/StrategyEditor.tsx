import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Save, Lock } from 'lucide-react';
import { Button, Card, Chip, Input, Skeleton, useToast } from '@/components/primitives';
import {
  DynamicFieldRenderer,
  type FieldDef,
} from '@/components/strategies/DynamicFieldRenderer';
import { FieldSchemaBuilder } from '@/components/strategies/FieldSchemaBuilder';
import { useStrategy, useUpdateStrategy } from '@/queries/strategies';
import { ApiError } from '@/lib/api';

export default function StrategyEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: strategy, isLoading } = useStrategy(id ?? null);
  const update = useUpdateStrategy(id ?? null);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [colorHex, setColorHex] = useState('');
  const [fields, setFields] = useState<FieldDef[]>([]);
  const [previewData, setPreviewData] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState(false);

  const isBuiltin = strategy?.kind === 'builtin';

  // Hydrate state when the strategy arrives (or reset on mount).
  useEffect(() => {
    if (!strategy) return;
    setName(strategy.name);
    setDescription(strategy.description ?? '');
    setColorHex(strategy.color_hex ?? '');
    const incoming = (strategy.field_schema?.fields ?? []) as FieldDef[];
    setFields(incoming);
    setDirty(false);
  }, [strategy]);

  // Track dirty state on any local edit.
  const markDirty = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setDirty(true);
  };

  const removedKeys = useMemo(() => {
    if (!strategy) return [] as string[];
    const before = new Set(((strategy.field_schema?.fields ?? []) as FieldDef[]).map((f) => f.key));
    const after = new Set(fields.map((f) => f.key));
    return [...before].filter((k) => !after.has(k));
  }, [strategy, fields]);

  const onSave = (force = false) => {
    if (!id) return;
    const payload: Record<string, unknown> = {
      name: name.trim(),
      description: description.trim() || null,
      color_hex: colorHex || null,
    };
    if (!isBuiltin) {
      payload.field_schema = { fields };
    }
    update.mutate(
      payload as Parameters<typeof update.mutate>[0],
      {
        onSuccess: () => {
          toast.push({ tone: 'success', title: 'Strategy saved.' });
          setDirty(false);
        },
        onError: (err) => {
          if (err instanceof ApiError && err.status === 422 && !force) {
            const detail = err.problem.detail ?? '';
            const affected = (err.problem as { affected_trade_ids?: string[] }).affected_trade_ids ?? [];
            toast.push({
              tone: 'warn',
              title: 'Field removal blocked',
              description: `${detail} (${affected.length} trades affected)`,
              ttl: 8000,
            });
            return;
          }
          const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
          toast.push({ tone: 'error', title: 'Save failed.', description: msg });
        },
      },
    );
  };

  if (isLoading || !strategy) {
    return (
      <div className="space-y-4">
        <Skeleton height={32} />
        <Skeleton height={120} />
        <Skeleton height={120} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="md" onClick={() => navigate('/strategies')}>
            <ArrowLeft size={14} strokeWidth={1.5} />
            Back
          </Button>
          <div>
            <div className="text-2xs uppercase tracking-widest text-text-tertiary">Strategy</div>
            <h1 className="text-2xl font-medium text-text-primary">{strategy.name}</h1>
            <div className="mt-1 flex items-center gap-2 text-xs">
              <Chip tone={isBuiltin ? 'info' : 'brand'}>{strategy.kind}</Chip>
              <span className="font-mono text-text-tertiary">{strategy.slug}</span>
              {strategy.template_key ? (
                <span className="font-mono text-text-tertiary">· {strategy.template_key}</span>
              ) : null}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {removedKeys.length > 0 && !isBuiltin ? (
            <span className="text-xs text-accent-warn">
              Removing {removedKeys.length} field(s): {removedKeys.join(', ')}
            </span>
          ) : null}
          <Button variant="primary" size="lg" disabled={!dirty} loading={update.isPending} onClick={() => onSave()}>
            <Save size={14} strokeWidth={1.5} />
            Save
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Left column: editor */}
        <div className="space-y-4">
          <Card header={<span>Metadata</span>}>
            <div className="space-y-3">
              <Input
                label="Name"
                value={name}
                onChange={(e) => markDirty(setName)(e.target.value)}
              />
              <label className="flex items-center gap-3">
                <span className="text-2xs uppercase tracking-widest text-text-tertiary">Color</span>
                <input
                  type="color"
                  value={colorHex || '#8B7FFF'}
                  onChange={(e) => markDirty(setColorHex)(e.target.value)}
                  className="h-8 w-12 cursor-pointer rounded border border-border-subtle bg-transparent"
                />
                <span className="font-mono text-xs text-text-tertiary">{colorHex || '—'}</span>
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-2xs uppercase tracking-widest text-text-tertiary">Description</span>
                <textarea
                  value={description}
                  onChange={(e) => markDirty(setDescription)(e.target.value)}
                  rows={3}
                  className="rounded-lg border border-border-subtle bg-bg-overlay p-3 text-sm leading-relaxed text-text-primary placeholder:text-text-tertiary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
                  placeholder="Short description shown on the trade form."
                />
              </label>
            </div>
          </Card>

          <Card header={isBuiltin ? <span className="flex items-center gap-2"><Lock size={12} strokeWidth={1.5} /> Schema (locked)</span> : <span>Field schema</span>}>
            <FieldSchemaBuilder
              fields={fields}
              onChange={(f) => {
                setFields(f);
                setDirty(true);
              }}
              locked={isBuiltin}
            />
          </Card>
        </div>

        {/* Right column: live preview */}
        <div className="space-y-4 xl:sticky xl:top-20 xl:self-start">
          <Card header={<span>Live preview — trade form fields</span>}>
            {fields.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border-subtle p-6 text-center text-sm text-text-tertiary">
                Add a field to see how the form will look.
              </div>
            ) : (
              <DynamicFieldRenderer
                fields={fields}
                values={previewData}
                onChange={(k, v) => setPreviewData({ ...previewData, [k]: v })}
              />
            )}
          </Card>

          {!isBuiltin ? (
            <Card>
              <p className="text-xs text-text-tertiary">
                Removing a field that has data on existing trades is blocked
                with a 422 — re-add the field, migrate the data, or contact
                yourself in 6 months when you remember why you wrote that.
              </p>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
