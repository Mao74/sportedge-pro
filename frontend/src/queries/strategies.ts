/** Strategy CRUD queries + types. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export type StrategyKind = 'builtin' | 'custom';

export interface StrategyFull {
  id: string;
  name: string;
  slug: string;
  kind: StrategyKind;
  template_key: string | null;
  sport: string;
  description: string | null;
  color_hex: string | null;
  is_active: boolean;
  field_schema: { fields: unknown[] };
  created_at: string;
  updated_at: string;
}

export function useStrategiesList(includeInactive = false) {
  return useQuery({
    queryKey: ['strategies', 'list', includeInactive],
    queryFn: () =>
      api.get<StrategyFull[]>('/strategies', includeInactive ? { include_inactive: true } : undefined),
  });
}

export function useStrategy(id: string | null) {
  return useQuery({
    queryKey: ['strategies', 'detail', id],
    queryFn: () => api.get<StrategyFull>(`/strategies/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name: string;
      description?: string | null;
      color_hex?: string | null;
      field_schema: { fields: unknown[] };
    }) => api.post<StrategyFull>('/strategies', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  });
}

export function useUpdateStrategy(id: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name?: string;
      description?: string | null;
      color_hex?: string | null;
      is_active?: boolean;
      field_schema?: { fields: unknown[] };
    }) => api.patch<StrategyFull>(`/strategies/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  });
}

export function useDeleteStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<{ status: string; n_trades?: number }>(`/strategies/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  });
}
