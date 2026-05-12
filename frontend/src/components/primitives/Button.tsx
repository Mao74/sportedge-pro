import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'xl';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-7 px-2.5 text-xs',
  md: 'h-8 px-3 text-sm',
  lg: 'h-9 px-3.5 text-sm',
  xl: 'h-10 px-4 text-base',
};

const VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-accent-brand text-white hover:opacity-90 active:scale-[0.98] disabled:opacity-50',
  secondary:
    'bg-transparent border border-border-subtle text-text-primary hover:bg-bg-hover hover:border-border-strong disabled:opacity-50',
  ghost:
    'bg-transparent text-text-secondary hover:bg-bg-hover hover:text-text-primary disabled:opacity-50',
  destructive:
    'bg-accent-loss text-white hover:opacity-90 active:scale-[0.98] disabled:opacity-50',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'secondary', size = 'md', loading, disabled, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex select-none items-center justify-center gap-2 rounded-lg font-medium',
        'transition-[background-color,opacity,transform,border-color] duration-150 ease-out',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand-bg',
        SIZE[size],
        VARIANT[variant],
        loading && 'cursor-wait',
        className,
      )}
      {...rest}
    >
      {loading ? <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-current opacity-50" /> : null}
      {children}
    </button>
  );
});
