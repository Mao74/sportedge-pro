/**
 * Dark/light theme bootstrap + hook. Default is dark.
 */

import { useEffect, useState } from 'react';

export type ThemeName = 'dark' | 'light';

const STORAGE_KEY = 'sportedge:theme';

export function initTheme(): void {
  const root = document.documentElement;
  const stored = localStorage.getItem(STORAGE_KEY) as ThemeName | null;
  const theme: ThemeName = stored ?? 'dark';
  root.setAttribute('data-theme', theme);
}

export function setTheme(theme: ThemeName): void {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEY, theme);
  window.dispatchEvent(new CustomEvent('themechange', { detail: theme }));
}

export function getTheme(): ThemeName {
  const attr = document.documentElement.getAttribute('data-theme');
  return attr === 'light' ? 'light' : 'dark';
}

export function useTheme(): [ThemeName, (t: ThemeName) => void] {
  const [theme, setLocal] = useState<ThemeName>(getTheme());
  useEffect(() => {
    const handler = (e: Event) => setLocal((e as CustomEvent<ThemeName>).detail);
    window.addEventListener('themechange', handler);
    return () => window.removeEventListener('themechange', handler);
  }, []);
  return [theme, setTheme];
}
