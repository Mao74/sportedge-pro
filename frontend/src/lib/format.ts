/**
 * Display formatters. Money is always EUR formatted via Intl with the
 * Italian locale; percentages are 1 dp; odds are 2 dp; the U+2212 minus
 * character is used for negative signs.
 */

const MINUS = '−';

const eurFormatter = new Intl.NumberFormat('it-IT', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const percentFormatter = new Intl.NumberFormat('it-IT', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const oddsFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const integerFormatter = new Intl.NumberFormat('it-IT');

/** Format an EUR amount. Negatives use the proper minus sign and a leading sign is preserved. */
export function formatEur(value: number | string, opts?: { signed?: boolean }): string {
  const n = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  const formatted = eurFormatter.format(abs);
  const sign = n < 0 ? MINUS : opts?.signed ? '+' : '';
  return `${sign}${formatted}`;
}

export function formatPercent(value: number | string, opts?: { signed?: boolean }): string {
  const n = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  const formatted = percentFormatter.format(abs);
  const sign = n < 0 ? MINUS : opts?.signed ? '+' : '';
  return `${sign}${formatted}%`;
}

export function formatOdds(value: number | string): string {
  const n = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(n)) return '—';
  return oddsFormatter.format(n);
}

export function formatInteger(value: number): string {
  return integerFormatter.format(value);
}

/** Returns 'gain', 'loss' or 'zero' for color-coding. */
export function pnlTone(value: number | string): 'gain' | 'loss' | 'zero' {
  const n = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(n) || n === 0) return 'zero';
  return n > 0 ? 'gain' : 'loss';
}
