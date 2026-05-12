import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import { AnimatePresence, motion } from 'framer-motion';
import {
  LayoutDashboard,
  ListOrdered,
  Layers3,
  BarChart3,
  Calculator,
  Plus,
  Settings as SettingsIcon,
  Sun,
  Moon,
  PanelLeftClose,
} from 'lucide-react';
import { useEffect } from 'react';
import { useUiStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';
import { useTheme } from '@/lib/theme';

export function CommandPalette() {
  const open = useUiStore((s) => s.paletteOpen);
  const setOpen = useUiStore((s) => s.setPaletteOpen);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const navigate = useNavigate();
  const [theme, setTheme] = useTheme();
  const clearAuth = useAuthStore((s) => s.clear);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    if (open) window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, setOpen]);

  const go = (path: string) => () => {
    navigate(path);
    setOpen(false);
  };

  const run = (fn: () => void) => () => {
    fn();
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-32 backdrop-blur-[2px]"
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ y: -8, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -8, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="w-full max-w-xl overflow-hidden rounded-xl border border-border-subtle bg-bg-overlay shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Command label="Command palette" className="flex flex-col">
              <Command.Input
                autoFocus
                placeholder="Search actions, trades, strategies…"
                className="h-12 w-full bg-transparent border-b border-border-subtle px-4 text-sm text-text-primary placeholder:text-text-tertiary outline-none"
              />
              <Command.List className="max-h-[60vh] overflow-y-auto px-2 py-2 text-sm">
                <Command.Empty className="px-3 py-6 text-center text-text-tertiary">
                  No results.
                </Command.Empty>

                <Command.Group heading="Navigate" className="text-2xs uppercase tracking-widest text-text-tertiary [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2">
                  <PaletteItem icon={LayoutDashboard} label="Dashboard" onSelect={go('/')} shortcut="g d" />
                  <PaletteItem icon={ListOrdered} label="Trades" onSelect={go('/trades')} shortcut="g t" />
                  <PaletteItem icon={Layers3} label="Strategies" onSelect={go('/strategies')} shortcut="g s" />
                  <PaletteItem icon={BarChart3} label="Analytics" onSelect={go('/analytics')} shortcut="g a" />
                  <PaletteItem icon={Calculator} label="What-if cash-out" onSelect={go('/whatif')} />
                  <PaletteItem icon={SettingsIcon} label="Settings" onSelect={go('/settings')} />
                </Command.Group>

                <Command.Group heading="Actions">
                  <PaletteItem icon={Plus} label="New trade" onSelect={go('/trades/new')} shortcut="n" />
                  <PaletteItem
                    icon={theme === 'dark' ? Sun : Moon}
                    label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
                    onSelect={run(() => setTheme(theme === 'dark' ? 'light' : 'dark'))}
                  />
                  <PaletteItem icon={PanelLeftClose} label="Toggle sidebar" onSelect={run(toggleSidebar)} shortcut="⌘ B" />
                </Command.Group>

                <Command.Group heading="Account">
                  <PaletteItem icon={SettingsIcon} label="Sign out" onSelect={run(clearAuth)} />
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function PaletteItem({
  icon: Icon,
  label,
  onSelect,
  shortcut,
}: {
  icon: typeof LayoutDashboard;
  label: string;
  onSelect: () => void;
  shortcut?: string;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex h-9 cursor-pointer items-center gap-3 rounded-lg px-3 text-text-secondary aria-selected:bg-bg-hover aria-selected:text-text-primary"
    >
      <Icon size={14} strokeWidth={1.5} />
      <span className="flex-1">{label}</span>
      {shortcut ? (
        <kbd className="rounded border border-border-subtle bg-bg-base px-1.5 py-0.5 font-mono text-2xs text-text-tertiary">
          {shortcut}
        </kbd>
      ) : null}
    </Command.Item>
  );
}
