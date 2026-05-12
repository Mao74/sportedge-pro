import { Outlet } from 'react-router-dom';
import { useCallback } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { CommandPalette } from './CommandPalette';
import { OfflineBanner } from './OfflineBanner';
import { ErrorBoundary } from './ErrorBoundary';
import { ConflictsDrawer } from '@/components/obsidian/ConflictsDrawer';
import { useUiStore } from '@/stores/ui';
import { useHotkey } from '@/hooks/useHotkey';

export function AppShell() {
  const setPalette = useUiStore((s) => s.setPaletteOpen);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);

  // Cmd/Ctrl+K → command palette
  useHotkey('k', useCallback(() => setPalette(true), [setPalette]), { meta: true });
  // Cmd/Ctrl+B → toggle sidebar
  useHotkey('b', useCallback(() => toggleSidebar(), [toggleSidebar]), { meta: true });

  return (
    <div className="flex min-h-full bg-bg-base">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-accent-brand focus:px-3 focus:py-1 focus:text-xs focus:text-white"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <OfflineBanner />
        <TopBar />
        <main id="main-content" tabIndex={-1} className="flex-1 px-6 py-6 outline-none">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
      <CommandPalette />
      <ConflictsDrawer />
    </div>
  );
}
