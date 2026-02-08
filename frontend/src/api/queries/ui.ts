import { useQuery } from '@tanstack/react-query'
import { getV2 } from '../generated'
import { apiClient } from '../client'

const api = getV2()

export function useTableMetadata(tableId: string) {
  return useQuery({
    queryKey: ['ui', 'table-metadata', tableId],
    queryFn: () => api.getUiTableMetadata({ table: tableId }),
    enabled: Boolean(tableId),
  })
}

export function useActionCatalog() {
  return useQuery({
    queryKey: ['ui', 'action-catalog'],
    queryFn: () => api.getUiActionCatalog(),
  })
}

export function useOperationExposureEditorHints(enabled = true) {
  return useQuery({
    queryKey: ['ui', 'operation-exposures', 'editor-hints'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v2/ui/operation-exposures/editor-hints/', { skipGlobalError: true })
      return response.data as Record<string, unknown>
    },
    staleTime: 60 * 60 * 1000,
    enabled,
  })
}
