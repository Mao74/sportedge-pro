import { useMemo, useRef, useState } from 'react';
import { X, Plus } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { cn } from '@/lib/cn';

interface TagPickerProps {
  value: string[];
  onChange: (v: string[]) => void;
  label?: string;
  placeholder?: string;
}

interface ExistingTag {
  id: string;
  name: string;
  n_trades: number;
  color_hex: string | null;
}

export function TagPicker({
  value,
  onChange,
  label = 'Tags',
  placeholder = 'Add tag…',
}: TagPickerProps) {
  const [draft, setDraft] = useState('');
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: existing = [] } = useQuery({
    queryKey: ['tags'],
    queryFn: () => api.get<ExistingTag[]>('/tags'),
    staleTime: 30_000,
  });

  const suggestions = useMemo(() => {
    const q = draft.trim().toLowerCase();
    return existing
      .filter((t) => !value.includes(t.name))
      .filter((t) => (q ? t.name.toLowerCase().includes(q) : true))
      .slice(0, 8);
  }, [existing, draft, value]);

  const addTag = (name: string) => {
    const clean = name.trim();
    if (!clean || value.includes(clean)) return;
    onChange([...value, clean]);
    setDraft('');
    inputRef.current?.focus();
  };

  const removeTag = (name: string) => {
    onChange(value.filter((v) => v !== name));
  };

  return (
    <div className="space-y-2">
      <span className="text-2xs uppercase tracking-widest text-text-tertiary">{label}</span>
      <div
        className={cn(
          'flex min-h-[36px] flex-wrap items-center gap-1.5 rounded-lg border border-border-subtle bg-bg-overlay px-2 py-1.5',
          'focus-within:border-border-focus focus-within:ring-2 focus-within:ring-accent-brand-bg',
        )}
      >
        {value.map((t) => (
          <span
            key={t}
            className="inline-flex h-6 items-center gap-1.5 rounded-full bg-accent-brand-bg px-2 text-xs font-medium text-accent-brand"
          >
            {t}
            <button
              type="button"
              aria-label={`Remove ${t}`}
              onClick={() => removeTag(t)}
              className="-mr-0.5 rounded p-0.5 hover:bg-bg-hover"
            >
              <X size={10} strokeWidth={1.5} />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && draft.trim()) {
              e.preventDefault();
              addTag(draft);
            }
            if (e.key === 'Backspace' && draft === '' && value.length > 0) {
              onChange(value.slice(0, -1));
            }
          }}
          placeholder={value.length === 0 ? placeholder : ''}
          className="min-w-[120px] flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary outline-none"
        />
      </div>
      {open && (suggestions.length > 0 || draft.trim().length > 0) ? (
        <div className="rounded-lg border border-border-subtle bg-bg-overlay py-1 text-sm shadow-xl">
          {suggestions.map((s) => (
            <button
              key={s.id}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                addTag(s.name);
              }}
              className="flex w-full items-center justify-between px-3 py-1.5 text-text-secondary hover:bg-bg-hover hover:text-text-primary"
            >
              <span>{s.name}</span>
              <span className="text-xs text-text-tertiary">{s.n_trades} use{s.n_trades === 1 ? '' : 's'}</span>
            </button>
          ))}
          {draft.trim() && !existing.some((e) => e.name.toLowerCase() === draft.trim().toLowerCase()) ? (
            <button
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                addTag(draft);
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-accent-brand hover:bg-bg-hover"
            >
              <Plus size={12} strokeWidth={1.5} />
              <span>
                Create <span className="font-medium">{draft.trim()}</span>
              </span>
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
