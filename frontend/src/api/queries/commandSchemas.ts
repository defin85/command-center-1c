import { useQuery } from '@tanstack/react-query'

import { listCommandSchemasAudit } from '../commandSchemas'

import { queryKeys } from './queryKeys'

const RBAC_STALE_TIME_MS = 5 * 60_000

export function useCanManageDriverCatalogs(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.commandSchemas.canManage(),
    queryFn: async (): Promise<boolean> => {
      try {
        await listCommandSchemasAudit({ limit: 1, offset: 0 })
        return true
      } catch (error) {
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status === 401 || status === 403) {
          return false
        }
        throw error
      }
    },
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
    retry: false,
    enabled: options?.enabled ?? true,
  })
}
