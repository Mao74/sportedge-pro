import { useLocation, useNavigate } from 'react-router-dom';
import { Search, Plus } from 'lucide-react';
import { Button } from '@/components/primitives';
import { useUiStore } from '@/stores/ui';
import { ObsidianStatusBadge } from './ObsidianStatusBadge';

const PATH_LABELS: Record<string, string> = {
  '': 'Dashboard',
  trades: 'Trades',
  strategies: 'Strategies',
  analytics: 'Analytics',
  whatif: 'What-if',
  settings: 'Settings',
  new: 'New',
  _dev: '_dev',
  primitives: 'Primitives',
};

function breadcrumbs(pathname: string): string[] {
  const parts = pathname.replace(/^\/+|\/+$/g, '').split('/');
  return parts.map((p) => PATH_LABELS[p] ?? p).filter(Boolean);
}

export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const setPaletteOpen = useUiStore((s) => s.setPaletteOpen);
  const crumbs = breadcrumbs(location.pathname);

  const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);
  const cmd = isMac ? '⌘' : 'Ctrl';

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-border-subtle bg-bg-base/80 px-6 backdrop-blur">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-text-secondary">
        {crumbs.length === 0 ? (
          <span className="text-text-primary">Dashboard</span>
        ) : (
          crumbs.map((c, i) => (
            <span key={`${c}-${i}`} className="flex items-center gap-1.5">
              {i > 0 ? <span className="text-text-tertiary">/</span> : null}
              <span className={i === crumbs.length - 1 ? 'text-text-primary' : ''}>{c}</span>
            </span>
          ))
        )}
      </nav>

      <div className="flex items-center gap-2">
        <ObsidianStatusBadge />
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="flex items-center gap-3 rounded-lg border border-border-subtle bg-bg-overlay px-3 py-1.5 text-xs text-text-tertiary hover:border-border-strong hover:text-text-secondary"
        >
          <Search size={14} strokeWidth={1.5} />
          <span>Search…</span>
          <kbd className="ml-2 hidden rounded border border-border-subtle bg-bg-base px-1.5 py-0.5 font-mono text-2xs text-text-secondary md:inline">
            {cmd}+K
          </kbd>
        </button>
        <Button variant="primary" size="md" onClick={() => navigate('/trades/new')}>
          <Plus size={14} strokeWidth={2} />
          <span>New trade</span>
        </Button>
      </div>
    </header>
  );
}
