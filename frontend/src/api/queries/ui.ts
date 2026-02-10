import { useQuery } from '@tanstack/react-query'
import { getV2 } from '../generated'
import type { ActionCatalogEditorHintsResponse } from '../generated/model/actionCatalogEditorHintsResponse'

const api = getV2()

export function useTableMetadata(tableId: string) {
  return useQuery({
    queryKey: ['ui', 'table-metadata', tableId],
    queryFn: () => api.getUiTableMetadata({ table: tableId }),
    enabled: Boolean(tableId),
  })
}

export function useOperationExposureEditorHints(enabled = true) {
  return useQuery<ActionCatalogEditorHintsResponse>({
    queryKey: ['ui', 'operation-exposures', 'editor-hints'],
    queryFn: () => api.getUiOperationExposuresEditorHints(),
    staleTime: 60 * 60 * 1000,
    enabled,
  })
}
