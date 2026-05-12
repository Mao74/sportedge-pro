/**
 * Walks a strategy.field_schema.fields[] declaration and renders one form
 * control per field. Hooks into a parent react-hook-form context via
 * ``register`` + ``setValue`` + ``watch`` callbacks so the parent owns the
 * form state.
 *
 * Honours ``depends_on`` (parent must be truthy) and the type-specific
 * widgets: text, number, select, multiselect, boolean, chip-picker, computed
 * (read-only — value derived from the formula).
 */

import { useMemo } from 'react';
import { Input, NumberInput, Switch } from '@/components/primitives';

export interface FieldDef {
  key: string;
  label: string;
  type:
    | 'text'
    | 'number'
    | 'select'
    | 'multiselect'
    | 'boolean'
    | 'chip-picker'
    | 'computed';
  required?: boolean;
  default?: unknown;
  depends_on?: string;
  required_for_status?: string;
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  min_picks?: number;
  max_picks?: number;
  formula?: string;
}

interface DynamicFieldRendererProps {
  fields: FieldDef[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  errors?: Record<string, string>;
  className?: string;
}

export function DynamicFieldRenderer({
  fields,
  values,
  onChange,
  errors,
  className,
}: DynamicFieldRendererProps) {
  const visible = useMemo(() => {
    return fields.filter((f) => {
      if (!f.depends_on) return true;
      return Boolean(values[f.depends_on]);
    });
  }, [fields, values]);

  return (
    <div className={className}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {visible.map((f) => (
          <FieldControl
            key={f.key}
            field={f}
            value={values[f.key]}
            onChange={(v) => onChange(f.key, v)}
            error={errors?.[f.key]}
          />
        ))}
      </div>
    </div>
  );
}

interface FieldControlProps {
  field: FieldDef;
  value: unknown;
  onChange: (v: unknown) => void;
  error?: string;
}

function FieldControl({ field, value, onChange, error }: FieldControlProps) {
  switch (field.type) {
    case 'text':
      return (
        <Input
          label={field.label}
          value={(value as string | undefined) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          errorText={error}
        />
      );

    case 'number':
      return (
        <NumberInput
          label={field.label}
          value={(value as string | number | undefined) ?? ''}
          step={field.step ?? 1}
          min={field.min}
          max={field.max}
          onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
          errorText={error}
        />
      );

    case 'boolean':
      return (
        <div className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-overlay px-3 py-2">
          <span className="text-sm text-text-primary">{field.label}</span>
          <Switch checked={Boolean(value)} onChange={onChange} />
        </div>
      );

    case 'select':
      return (
        <label className="flex flex-col gap-1.5">
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">
            {field.label}
          </span>
          <select
            value={(value as string | undefined) ?? ''}
            onChange={(e) => onChange(e.target.value || null)}
            className="h-9 rounded-lg border border-border-subtle bg-bg-overlay px-3 text-sm text-text-primary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
          >
            <option value="">—</option>
            {(field.options ?? []).map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          {error ? <span className="text-xs text-accent-loss">{error}</span> : null}
        </label>
      );

    case 'multiselect':
      return (
        <ChipPicker
          label={field.label}
          options={field.options ?? []}
          value={(value as string[] | undefined) ?? []}
          onChange={onChange}
          error={error}
        />
      );

    case 'chip-picker':
      return (
        <ChipPicker
          label={field.label}
          options={field.options ?? []}
          value={(value as string[] | undefined) ?? []}
          onChange={onChange}
          error={error}
          minPicks={field.min_picks}
          maxPicks={field.max_picks}
        />
      );

    case 'computed':
      return (
        <div className="flex flex-col gap-1.5">
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">
            {field.label}
          </span>
          <div className="flex h-9 items-center rounded-lg border border-dashed border-border-subtle bg-bg-base px-3 text-sm text-text-tertiary font-mono">
            {field.formula ? `= ${field.formula}` : 'computed'}
          </div>
        </div>
      );
  }
}

interface ChipPickerProps {
  label: string;
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  minPicks?: number;
  maxPicks?: number;
  error?: string;
}

function ChipPicker({ label, options, value, onChange, minPicks, maxPicks, error }: ChipPickerProps) {
  const toggle = (opt: string) => {
    const has = value.includes(opt);
    if (has) {
      onChange(value.filter((v) => v !== opt));
    } else {
      if (maxPicks && value.length >= maxPicks) return;
      onChange([...value, opt]);
    }
  };

  const hint =
    minPicks || maxPicks
      ? `Pick ${[
          minPicks ? `min ${minPicks}` : null,
          maxPicks ? `max ${maxPicks}` : null,
        ]
          .filter(Boolean)
          .join(', ')} · ${value.length} selected`
      : `${value.length} selected`;

  return (
    <div className="sm:col-span-2 flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="text-2xs uppercase tracking-widest text-text-tertiary">{label}</span>
        <span className="text-xs text-text-tertiary">{hint}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = value.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(opt)}
              className={`rounded-full px-3 py-1 text-xs font-mono tabular-nums transition-colors duration-150 ${
                active
                  ? 'bg-accent-brand-bg text-accent-brand'
                  : 'bg-bg-overlay text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              }`}
            >
              {opt}
            </button>
          );
        })}
      </div>
      {error ? <span className="text-xs text-accent-loss">{error}</span> : null}
    </div>
  );
}
