/** CSV import/export queries. */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/auth';
import { ApiError } from '@/lib/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export interface CsvRowError {
  row_index: number;
  column: string | null;
  detail: string;
}

export interface CsvImportResult {
  parsed_rows: number;
  valid_rows: number;
  errors: CsvRowError[];
  inserted: number;
  dry_run: boolean;
}

export async function exportTradesCsv(): Promise<void> {
  const token = useAuthStore.getState().accessToken;
  const resp = await fetch(`${API_BASE}/trades/export.csv`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) {
    if (resp.status === 401) useAuthStore.getState().clear();
    throw new ApiError({
      type: 'about:blank',
      title: resp.statusText,
      status: resp.status,
    });
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  // Match the backend's filename hint if present.
  const cd = resp.headers.get('content-disposition') || '';
  const filenameMatch = cd.match(/filename="([^"]+)"/);
  a.download = filenameMatch?.[1] ?? `sportedge-trades-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function useImportTradesCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { file: File; dryRun: boolean }) => {
      const fd = new FormData();
      fd.append('file', args.file);
      fd.append('dry_run', args.dryRun ? 'true' : 'false');
      const token = useAuthStore.getState().accessToken;
      const resp = await fetch(`${API_BASE}/trades/import`, {
        method: 'POST',
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await resp.json();
      if (!resp.ok) {
        if (resp.status === 401) useAuthStore.getState().clear();
        throw new ApiError(data);
      }
      return data as CsvImportResult;
    },
    onSuccess: (result) => {
      if (!result.dry_run && result.inserted > 0) {
        qc.invalidateQueries({ queryKey: ['trades'] });
        qc.invalidateQueries({ queryKey: ['analytics'] });
        qc.invalidateQueries({ queryKey: ['bankroll'] });
      }
    },
  });
}
