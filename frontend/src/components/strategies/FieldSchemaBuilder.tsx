/**
 * Visual editor for a strategy's field_schema. Drag-and-drop reorder via
 * dnd-kit. Each field row has an editable label + key, type picker, and
 * type-specific options (options list, min/max, min_picks/max_picks,
 * formula, depends_on). Locked when the parent strategy is built-in.
 */

import { useState } from 'react';
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Plus, Trash2, ChevronDown, ChevronUp, Lock } from 'lucide-react';
import { Button, Chip, Input } from '@/components/primitives';
import type { FieldDef } from '@/components/strategies/DynamicFieldRenderer';

const TYPES: FieldDef['type'][] = [
  'text',
  'number',
  'select',
  'multiselect',
  'boolean',
  'chip-picker',
  'computed',
];

interface FieldSchemaBuilderProps {
  fields: FieldDef[];
  onChange: (fields: FieldDef[]) => void;
  locked?: boolean;
}

export function FieldSchemaBuilder({ fields, onChange, locked }: FieldSchemaBuilderProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const from = fields.findIndex((f) => f.key === active.id);
    const to = fields.findIndex((f) => f.key === over.id);
    if (from < 0 || to < 0) return;
    onChange(arrayMove(fields, from, to));
  };

  const updateField = (idx: number, patch: Partial<FieldDef>) => {
    const next = [...fields];
    next[idx] = { ...next[idx], ...patch } as FieldDef;
    onChange(next);
  };

  const removeField = (idx: number) => {
    if (locked) return;
    const next = fields.filter((_, i) => i !== idx);
    onChange(next);
    if (expandedIdx === idx) setExpandedIdx(null);
  };

  const addField = () => {
    if (locked) return;
    const baseKey = `field_${fields.length + 1}`;
    let key = baseKey;
    let n = 1;
    while (fields.some((f) => f.key === key)) {
      n += 1;
      key = `${baseKey}_${n}`;
    }
    onChange([
      ...fields,
      { key, label: `Field ${fields.length + 1}`, type: 'text' } as FieldDef,
    ]);
    setExpandedIdx(fields.length);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-2xs uppercase tracking-widest text-text-tertiary">
          Fields ({fields.length})
        </span>
        {locked ? (
          <Chip tone="info">
            <Lock size={11} strokeWidth={1.5} />
            <span>Built-in schema is locked</span>
          </Chip>
        ) : null}
      </div>

      {fields.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-subtle bg-bg-overlay p-6 text-center text-sm text-text-tertiary">
          No fields yet. {locked ? '' : 'Add the first one below.'}
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={fields.map((f) => f.key)} strategy={verticalListSortingStrategy}>
            <ul className="space-y-2">
              {fields.map((f, i) => (
                <SortableFieldRow
                  key={f.key}
                  field={f}
                  expanded={expandedIdx === i}
                  onToggle={() => setExpandedIdx(expandedIdx === i ? null : i)}
                  onChange={(patch) => updateField(i, patch)}
                  onRemove={() => removeField(i)}
                  locked={locked}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
      )}

      {!locked ? (
        <Button variant="secondary" size="md" onClick={addField}>
          <Plus size={14} strokeWidth={1.5} />
          Add field
        </Button>
      ) : null}
    </div>
  );
}

interface RowProps {
  field: FieldDef;
  expanded: boolean;
  onToggle: () => void;
  onChange: (patch: Partial<FieldDef>) => void;
  onRemove: () => void;
  locked?: boolean;
}

function SortableFieldRow({ field, expanded, onToggle, onChange, onRemove, locked }: RowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: field.key,
    disabled: locked,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="rounded-lg border border-border-subtle bg-bg-overlay"
    >
      <div className="flex items-center gap-2 px-2 py-2">
        <button
          type="button"
          {...attributes}
          {...listeners}
          aria-label="Drag to reorder"
          className={`rounded p-1.5 text-text-tertiary hover:bg-bg-hover ${locked ? 'cursor-not-allowed opacity-50' : 'cursor-grab active:cursor-grabbing'}`}
          disabled={locked}
        >
          <GripVertical size={14} strokeWidth={1.5} />
        </button>
        <div className="flex flex-1 items-baseline gap-3 min-w-0">
          <span className="font-mono text-xs text-text-tertiary truncate">{field.key}</span>
          <span className="text-sm text-text-primary truncate">{field.label}</span>
          <Chip tone="neutral">{field.type}</Chip>
          {field.required ? <Chip tone="warn">required</Chip> : null}
          {field.depends_on ? <Chip tone="info">depends_on {field.depends_on}</Chip> : null}
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="rounded p-1.5 text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUp size={14} strokeWidth={1.5} /> : <ChevronDown size={14} strokeWidth={1.5} />}
        </button>
        {!locked ? (
          <button
            type="button"
            onClick={onRemove}
            className="rounded p-1.5 text-text-tertiary hover:bg-accent-loss-bg hover:text-accent-loss"
            aria-label="Remove field"
          >
            <Trash2 size={14} strokeWidth={1.5} />
          </button>
        ) : null}
      </div>

      {expanded ? (
        <div className="border-t border-border-subtle p-3">
          <FieldEditor field={field} onChange={onChange} locked={locked} />
        </div>
      ) : null}
    </li>
  );
}

interface FieldEditorProps {
  field: FieldDef;
  onChange: (patch: Partial<FieldDef>) => void;
  locked?: boolean;
}

function FieldEditor({ field, onChange, locked }: FieldEditorProps) {
  const optionsText = (field.options ?? []).join(', ');
  const dis = locked;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <Input
        label="Key"
        value={field.key}
        onChange={(e) =>
          onChange({ key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })
        }
        disabled={dis}
        hint="snake_case"
      />
      <Input
        label="Label"
        value={field.label}
        onChange={(e) => onChange({ label: e.target.value })}
        disabled={dis}
      />
      <label className="flex flex-col gap-1.5">
        <span className="text-2xs uppercase tracking-widest text-text-tertiary">Type</span>
        <select
          value={field.type}
          onChange={(e) => onChange({ type: e.target.value as FieldDef['type'] })}
          disabled={dis}
          className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg disabled:opacity-50"
        >
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <Input
        label="Depends on (key)"
        value={field.depends_on ?? ''}
        onChange={(e) => onChange({ depends_on: e.target.value || undefined })}
        disabled={dis}
        hint="parent must be truthy to show this field"
      />
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={Boolean(field.required)}
          onChange={(e) => onChange({ required: e.target.checked })}
          disabled={dis}
          className="h-4 w-4"
        />
        <span className="text-sm text-text-primary">Required</span>
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-2xs uppercase tracking-widest text-text-tertiary">
          Required for status
        </span>
        <select
          value={field.required_for_status ?? ''}
          onChange={(e) => onChange({ required_for_status: e.target.value || undefined })}
          disabled={dis}
          className="h-9 rounded-lg border border-border-subtle bg-bg-base px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg disabled:opacity-50"
        >
          <option value="">— never —</option>
          <option value="CLOSED">CLOSED</option>
        </select>
      </label>

      {(field.type === 'select' || field.type === 'multiselect' || field.type === 'chip-picker') ? (
        <Input
          label="Options (comma-separated)"
          value={optionsText}
          onChange={(e) =>
            onChange({
              options: e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
          disabled={dis}
          className="sm:col-span-2"
        />
      ) : null}

      {field.type === 'number' ? (
        <>
          <Input
            label="Min"
            type="number"
            value={field.min ?? ''}
            onChange={(e) => onChange({ min: e.target.value === '' ? undefined : Number(e.target.value) })}
            disabled={dis}
          />
          <Input
            label="Max"
            type="number"
            value={field.max ?? ''}
            onChange={(e) => onChange({ max: e.target.value === '' ? undefined : Number(e.target.value) })}
            disabled={dis}
          />
          <Input
            label="Step"
            type="number"
            value={field.step ?? ''}
            onChange={(e) => onChange({ step: e.target.value === '' ? undefined : Number(e.target.value) })}
            disabled={dis}
          />
        </>
      ) : null}

      {field.type === 'chip-picker' ? (
        <>
          <Input
            label="Min picks"
            type="number"
            value={field.min_picks ?? ''}
            onChange={(e) => onChange({ min_picks: e.target.value === '' ? undefined : Number(e.target.value) })}
            disabled={dis}
          />
          <Input
            label="Max picks"
            type="number"
            value={field.max_picks ?? ''}
            onChange={(e) => onChange({ max_picks: e.target.value === '' ? undefined : Number(e.target.value) })}
            disabled={dis}
          />
        </>
      ) : null}

      {field.type === 'computed' ? (
        <Input
          label="Formula"
          value={field.formula ?? ''}
          onChange={(e) => onChange({ formula: e.target.value })}
          disabled={dis}
          className="sm:col-span-2"
          hint="e.g. (model_prob * odds - 1) * 100"
        />
      ) : null}
    </div>
  );
}
