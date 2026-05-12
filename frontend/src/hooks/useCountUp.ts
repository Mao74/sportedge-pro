/**
 * Animate a number from 0 to ``target`` once on mount. Uses requestAnimationFrame
 * with easeOutQuart and clamps duration to 600ms. After mount, target changes
 * are written through directly (no re-animation) so live re-renders stay snappy.
 */

import { useEffect, useRef, useState } from 'react';

const DURATION_MS = 600;

function easeOutQuart(t: number): number {
  return 1 - Math.pow(1 - t, 4);
}

export function useCountUp(target: number, opts: { duration?: number } = {}): number {
  const { duration = DURATION_MS } = opts;
  const [value, setValue] = useState(0);
  const startedRef = useRef(false);

  useEffect(() => {
    if (Number.isNaN(target)) return;
    // After the first animation, future target changes apply instantly.
    if (startedRef.current) {
      setValue(target);
      return;
    }
    startedRef.current = true;
    let raf = 0;
    const start = performance.now();
    const initial = 0;
    const delta = target - initial;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setValue(initial + delta * easeOutQuart(t));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}
