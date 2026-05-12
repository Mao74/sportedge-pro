import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, AlertTriangle, AlertOctagon, Info, X } from 'lucide-react';
import { cn } from '@/lib/cn';

export type ToastTone = 'success' | 'error' | 'warn' | 'info';

interface Toast {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
  ttl: number;
}

interface ToastContextValue {
  push: (t: Omit<Toast, 'id' | 'ttl'> & { ttl?: number }) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TONE_ICON = {
  success: CheckCircle2,
  error: AlertOctagon,
  warn: AlertTriangle,
  info: Info,
} as const;

const TONE_COLOR = {
  success: 'text-accent-gain',
  error: 'text-accent-loss',
  warn: 'text-accent-warn',
  info: 'text-accent-info',
} as const;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((curr) => curr.filter((t) => t.id !== id));
  }, []);

  const push: ToastContextValue['push'] = useCallback(
    (t) => {
      const id = ++seq.current;
      const ttl = t.ttl ?? 4000;
      setToasts((curr) => [...curr.slice(-2), { ...t, id, ttl }]);
      if (ttl > 0) {
        setTimeout(() => dismiss(id), ttl);
      }
    },
    [dismiss],
  );

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="region"
        aria-label="Notifications"
        aria-live="polite"
        className="pointer-events-none fixed bottom-6 right-6 z-50 flex w-80 flex-col gap-2"
      >
        <AnimatePresence initial={false}>
          {toasts.map((t) => {
            const Icon = TONE_ICON[t.tone];
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="pointer-events-auto rounded-xl border border-border-subtle bg-bg-overlay p-3 shadow-2xl backdrop-blur-md"
              >
                <div className="flex items-start gap-3">
                  <Icon className={cn('mt-0.5 shrink-0', TONE_COLOR[t.tone])} size={16} />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-text-primary">{t.title}</div>
                    {t.description ? (
                      <div className="mt-0.5 text-xs text-text-secondary">{t.description}</div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    aria-label="Dismiss"
                    onClick={() => dismiss(t.id)}
                    className="rounded p-0.5 text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
                  >
                    <X size={14} />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}
