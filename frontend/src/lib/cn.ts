import { clsx, type ClassValue } from 'clsx';

/** Tailwind-friendly className merger. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
