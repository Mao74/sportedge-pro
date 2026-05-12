import { cn } from '@/lib/cn';

interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (v: T) => void;
  size?: 'sm' | 'md';
  className?: string;
}

const SIZE = {
  sm: 'h-7 text-xs',
  md: 'h-8 text-sm',
} as const;

/** A segmented control. The single Switch variant lives below. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  size = 'md',
  className,
}: SegmentedProps<T>) {
  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex rounded-lg border border-border-subtle bg-bg-overlay p-0.5',
        SIZE[size],
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'flex-1 rounded-md px-3 transition-colors duration-150 ease-out',
              active
                ? 'bg-bg-hover text-text-primary'
                : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, disabled }: SwitchProps) {
  return (
    <label className={cn('flex cursor-pointer items-center gap-2 select-none', disabled && 'opacity-50 cursor-not-allowed')}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-5 w-9 rounded-full transition-colors duration-200 ease-out',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand-bg',
          checked ? 'bg-accent-brand' : 'bg-border-strong',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform duration-200 ease-out',
            checked ? 'translate-x-4' : 'translate-x-0.5',
          )}
        />
      </button>
      {label ? <span className="text-sm text-text-primary">{label}</span> : null}
    </label>
  );
}
