import { useEffect, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  width?: number;
  children: ReactNode;
  footer?: ReactNode;
}

export function Drawer({ open, onClose, title, width = 480, children, footer }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
            onClick={onClose}
            aria-hidden
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            initial={{ x: width }}
            animate={{ x: 0 }}
            exit={{ x: width }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            style={{ width }}
            className={cn(
              'fixed right-0 top-0 z-50 flex h-full flex-col border-l border-border-subtle bg-bg-overlay',
            )}
          >
            <header className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
              <h2 className="text-base font-medium text-text-primary">{title}</h2>
              <button
                type="button"
                aria-label="Close"
                onClick={onClose}
                className="rounded p-1 text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
              >
                <X size={16} strokeWidth={1.5} />
              </button>
            </header>
            <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
            {footer ? (
              <footer className="border-t border-border-subtle px-5 py-3">{footer}</footer>
            ) : null}
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
