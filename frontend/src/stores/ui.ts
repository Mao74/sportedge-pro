/** Ephemeral UI state — sidebar open, command palette open, etc. */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebar: (collapsed: boolean) => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  conflictsOpen: boolean;
  setConflictsOpen: (v: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
      setSidebar: (sidebarCollapsed) => set({ sidebarCollapsed }),
      paletteOpen: false,
      setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
      conflictsOpen: false,
      setConflictsOpen: (conflictsOpen) => set({ conflictsOpen }),
    }),
    { name: 'sportedge:ui', partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed }) },
  ),
);
