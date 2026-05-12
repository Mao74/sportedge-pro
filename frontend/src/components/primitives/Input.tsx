import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  errorText?: string;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, errorText, leadingIcon, trailingIcon, className, id, ...rest },
  ref,
) {
  const inputId = id ?? rest.name;
  return (
    <label htmlFor={inputId} className="flex flex-col gap-1.5">
      {label ? (
        <span className="text-2xs uppercase tracking-widest text-text-tertiary">{label}</span>
      ) : null}
      <span
        className={cn(
          'flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-overlay px-3',
          'transition-[border-color,box-shadow] duration-150 ease-out',
          'focus-within:border-border-focus focus-within:ring-2 focus-within:ring-accent-brand-bg',
          errorText && 'border-accent-loss focus-within:border-accent-loss focus-within:ring-accent-loss-bg',
        )}
      >
        {leadingIcon ? <span className="text-text-tertiary">{leadingIcon}</span> : null}
        <input
          id={inputId}
          ref={ref}
          className={cn(
            'h-9 flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary',
            'outline-none disabled:cursor-not-allowed disabled:opacity-50',
            'tabular-nums',
            className,
          )}
          {...rest}
        />
        {trailingIcon ? <span className="text-text-tertiary">{trailingIcon}</span> : null}
      </span>
      {errorText ? (
        <span className="text-xs text-accent-loss">{errorText}</span>
      ) : hint ? (
        <span className="text-xs text-text-tertiary">{hint}</span>
      ) : null}
    </label>
  );
});
