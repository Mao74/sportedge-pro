/** Obsidian queries + mutations. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export interface ObsidianStatus {
  enabled: boolean;
  vault_path: string;
  sync_mode: 'export_only' | 'two_way' | 'manual_only';
  template_set: 'complete' | 'minimal' | 'tactical';
  last_sync_at: string | null;
  last_error: string | null;
  conflict_count: number;
}

export interface ObsidianConflict {
  id: string;
  path: string;
  trade_id: string | null;
  detected_at: string;
  db_updated_at: string | null;
  file_updated_at: string | null;
  db_text: string | null;
  file_text: string | null;
}

export interface ExportSummary {
  trades_exported: number;
  daily_exported: number;
  strategies_exported: number;
  dashboards_exported: number;
  took_ms: number;
}

export interface ChangeEvent {
  path: string;
  trade_id: string | null;
  action: 'updated' | 'conflict' | 'unknown';
  detail: string | null;
}

export function useObsidianStatus(opts?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: ['obsidian', 'status'],
    queryFn: () => api.get<ObsidianStatus>('/obsidian/status'),
    refetchInterval: opts?.refetchInterval,
  });
}

export function usePatchObsidianConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Pick<ObsidianStatus, 'enabled' | 'vault_path' | 'sync_mode' | 'template_set'>>) =>
      api.patch<ObsidianStatus>('/obsidian/config', body),
    onSuccess: (data) => {
      qc.setQueryData(['obsidian', 'status'], data);
    },
  });
}

export function useExportAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ExportSummary>('/obsidian/export-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['obsidian'] }),
  });
}

export function useSyncNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ChangeEvent[]>('/obsidian/sync-now'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['obsidian'] });
      qc.invalidateQueries({ queryKey: ['trades'] });
    },
  });
}

export function useConflicts() {
  return useQuery({
    queryKey: ['obsidian', 'conflicts'],
    queryFn: () => api.get<ObsidianConflict[]>('/obsidian/conflicts'),
  });
}

export function useResolveConflict() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { id: string; resolution: 'keep_db' | 'keep_file' | 'merged'; merged_text?: string }) =>
      api.post(`/obsidian/conflicts/${args.id}/resolve`, {
        resolution: args.resolution,
        merged_text: args.merged_text,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['obsidian'] }),
  });
}
