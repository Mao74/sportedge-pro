import { useEffect } from 'react';

/**
 * Bind a keyboard shortcut. ``key`` is matched against ``KeyboardEvent.key``
 * (case-insensitive). Use the modifier flags as needed.
 */
export function useHotkey(
  key: string,
  handler: (e: KeyboardEvent) => void,
  opts: { meta?: boolean; ctrl?: boolean; alt?: boolean; shift?: boolean; preventDefault?: boolean } = {},
): void {
  const { meta, ctrl, alt, shift, preventDefault = true } = opts;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== key.toLowerCase()) return;
      // Treat Cmd (mac) and Ctrl (others) as the same "meta" shortcut.
      if (meta || ctrl) {
        const cmdOrCtrl = e.metaKey || e.ctrlKey;
        if (!cmdOrCtrl) return;
      }
      if (alt && !e.altKey) return;
      if (shift && !e.shiftKey) return;
      if (preventDefault) e.preventDefault();
      handler(e);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [key, handler, meta, ctrl, alt, shift, preventDefault]);
}
