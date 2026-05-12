import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/cn';

interface MarkdownEditorProps {
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  placeholder?: string;
  label?: string;
}

type Tab = 'edit' | 'preview';

export function MarkdownEditor({
  value,
  onChange,
  rows = 8,
  placeholder = 'Write notes — markdown supported.',
  label,
}: MarkdownEditorProps) {
  const [tab, setTab] = useState<Tab>('edit');

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        {label ? (
          <span className="text-2xs uppercase tracking-widest text-text-tertiary">{label}</span>
        ) : <span />}
        <div className="flex rounded-lg border border-border-subtle bg-bg-overlay p-0.5 text-xs">
          {(['edit', 'preview'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                'rounded-md px-2.5 py-1 transition-colors',
                tab === t
                  ? 'bg-bg-hover text-text-primary'
                  : 'text-text-secondary hover:text-text-primary',
              )}
            >
              {t === 'edit' ? 'Edit' : 'Preview'}
            </button>
          ))}
        </div>
      </div>
      {tab === 'edit' ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={rows}
          placeholder={placeholder}
          className="w-full resize-y rounded-lg border border-border-subtle bg-bg-overlay p-3 text-sm leading-relaxed text-text-primary placeholder:text-text-tertiary outline-none focus:border-border-focus focus:ring-2 focus:ring-accent-brand-bg"
        />
      ) : (
        <div className="prose-trade rounded-lg border border-border-subtle bg-bg-overlay p-4 text-sm text-text-primary">
          {value.trim() === '' ? (
            <span className="text-text-tertiary">Nothing to preview.</span>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
          )}
        </div>
      )}
    </div>
  );
}
