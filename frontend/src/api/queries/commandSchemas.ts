import { useQuery } from '@tanstack/react-query'

import { listCommandSchemasAudit } from '../commandSchemas'

import { queryKeys } from './queryKeys'
import { withQueryPolicy } from '../../lib/queryRuntime'

const RBAC_STALE_TIME_MS = 5 * 60_000

export function useCanManageDriverCatalogs(options?: { enabled?: boolean }) {
  return useQuery(withQueryPolicy('capability', {
    queryKey: queryKeys.commandSchemas.canManage(),
    queryFn: async (): Promise<boolean> => {
      try {
        await listCommandSchemasAudit({ limit: 1, offset: 0 }, { errorPolicy: 'background' })
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
    enabled: options?.enabled ?? true,
  }))
}
