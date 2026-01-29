import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '../queryKeys'
import { apiClient } from '../../client'

export type AdminAuditLogItem = {
  id: number
  created_at: string
  action: string
  outcome: string
  actor_username: string
  actor_id: number | null
  target_type: string
  target_id: string
  metadata: Record<string, unknown>
  error_message: string
}

const RBAC_STALE_TIME_MS = 5 * 60_000

export function useAdminAuditLog(
  filters?: {
    action?: string
    outcome?: string
    actor?: string
    target_type?: string
    target_id?: string
    search?: string
    since?: string
    until?: string
    limit?: number
    offset?: number
  },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.audit(filters),
    queryFn: async (): Promise<{ items: AdminAuditLogItem[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-admin-audit/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
  })
}
