import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ListOrdered,
  Layers3,
  BarChart3,
  Calculator,
  Settings as SettingsIcon,
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  TrendingUp,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { useUiStore } from '@/stores/ui';
import { useTheme } from '@/lib/theme';

const NAV: { to: string; label: string; icon: typeof LayoutDashboard }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/trades', label: 'Trades', icon: ListOrdered },
  { to: '/strategies', label: 'Strategies', icon: Layers3 },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/whatif', label: 'What-if', icon: Calculator },
];

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUiStore();
  const [theme, setTheme] = useTheme();

  return (
    <aside
      className={cn(
        'sticky top-0 flex h-screen flex-col border-r border-border-subtle bg-bg-elevated',
        'transition-[width] duration-200 ease-out',
        sidebarCollapsed ? 'w-14' : 'w-60',
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-border-subtle px-3">
        <div className={cn('flex items-center gap-2', sidebarCollapsed && 'mx-auto')}>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-brand-bg text-accent-brand">
            <TrendingUp size={16} strokeWidth={2} />
          </div>
          {!sidebarCollapsed ? (
            <span className="text-sm font-medium text-text-primary">SportEdge</span>
          ) : null}
        </div>
        {!sidebarCollapsed ? (
          <button
            type="button"
            onClick={toggleSidebar}
            aria-label="Collapse sidebar"
            className="rounded p-1 text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
          >
            <PanelLeftClose size={16} strokeWidth={1.5} />
          </button>
        ) : null}
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="flex flex-col gap-0.5">
          {NAV.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex h-9 items-center gap-3 rounded-lg px-2 text-sm transition-colors duration-150',
                    sidebarCollapsed && 'justify-center px-0',
                    isActive
                      ? 'bg-bg-hover text-text-primary'
                      : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
                  )
                }
                title={sidebarCollapsed ? label : undefined}
              >
                <Icon size={16} strokeWidth={1.5} className="shrink-0" />
                {!sidebarCollapsed ? <span>{label}</span> : null}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-border-subtle p-2">
        {sidebarCollapsed ? (
          <button
            type="button"
            onClick={toggleSidebar}
            aria-label="Expand sidebar"
            className="flex h-9 w-full items-center justify-center rounded-lg text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
          >
            <PanelLeftOpen size={16} strokeWidth={1.5} />
          </button>
        ) : (
          <div className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5">
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                cn(
                  'flex flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                  isActive
                    ? 'bg-bg-hover text-text-primary'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
                )
              }
            >
              <SettingsIcon size={16} strokeWidth={1.5} />
              <span>Settings</span>
            </NavLink>
            <button
              type="button"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              aria-label="Toggle theme"
              className="rounded p-1.5 text-text-tertiary hover:bg-bg-hover hover:text-text-primary"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {theme === 'dark' ? <Sun size={16} strokeWidth={1.5} /> : <Moon size={16} strokeWidth={1.5} />}
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
