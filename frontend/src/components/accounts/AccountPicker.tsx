/**
 * Chip-style account selector. Lists every non-archived account; the
 * currently-selected one shows brand styling. The optional ``includeAll``
 * mode adds an "All" pseudo-chip that selects ``null`` — used on screens
 * (Dashboard, TradeLog) that can show an aggregated view across all
 * accounts.
 */

import type { Account } from '@/queries/accounts';

export interface AccountPickerProps {
  accounts: Account[];
  value: string | null;
  onChange: (accountId: string | null) => void;
  includeAll?: boolean;
  size?: 'sm' | 'md';
}

export function AccountPicker({
  accounts,
  value,
  onChange,
  includeAll = false,
  size = 'md',
}: AccountPickerProps) {
  const padding = size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-xs';

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {includeAll ? (
        <button
          type="button"
          onClick={() => onChange(null)}
          className={`inline-flex items-center gap-1.5 rounded-full border font-medium transition-colors ${padding} ${
            value === null
              ? 'border-accent-brand bg-accent-brand-bg text-accent-brand'
              : 'border-border-subtle text-text-secondary hover:border-border-strong hover:text-text-primary'
          }`}
          aria-pressed={value === null}
        >
          All accounts
        </button>
      ) : null}
      {accounts.map((acc) => {
        const isActive = acc.id === value;
        return (
          <button
            key={acc.id}
            type="button"
            onClick={() => onChange(acc.id)}
            className={`inline-flex items-center gap-1.5 rounded-full border font-medium transition-colors ${padding} ${
              isActive
                ? 'border-accent-brand bg-accent-brand-bg text-accent-brand'
                : 'border-border-subtle text-text-secondary hover:border-border-strong hover:text-text-primary'
            }`}
            aria-pressed={isActive}
            title={`${acc.venue} · ${acc.market_type} · ${acc.commission_pct}%`}
          >
            <span className="font-medium">{acc.name}</span>
            <span className="text-text-tertiary">· {acc.market_type}</span>
          </button>
        );
      })}
    </div>
  );
}
