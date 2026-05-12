import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

interface NumberInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  hint?: string;
  errorText?: string;
  suffix?: string;
}

export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(function NumberInput(
  { label, hint, errorText, suffix, className, id, ...rest },
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
        <input
          id={inputId}
          ref={ref}
          type="number"
          inputMode="decimal"
          className={cn(
            'h-9 flex-1 bg-transparent font-mono text-sm tabular-nums text-text-primary placeholder:text-text-tertiary',
            'outline-none disabled:cursor-not-allowed disabled:opacity-50',
            // Hide the spinner — distracting in number-heavy forms.
            '[&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none',
            '[appearance:textfield]',
            className,
          )}
          {...rest}
        />
        {suffix ? (
          <span className="text-xs text-text-tertiary">{suffix}</span>
        ) : null}
      </span>
      {errorText ? (
        <span className="text-xs text-accent-loss">{errorText}</span>
      ) : hint ? (
        <span className="text-xs text-text-tertiary">{hint}</span>
      ) : null}
    </label>
  );
});
