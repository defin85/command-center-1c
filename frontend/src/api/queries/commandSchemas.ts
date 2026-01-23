import { useQuery } from '@tanstack/react-query'

import { listCommandSchemasAudit } from '../commandSchemas'

import { queryKeys } from './queryKeys'

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
    staleTime: 60_000,
    retry: false,
    enabled: options?.enabled ?? true,
  })
}
