import { useQuery } from '@tanstack/react-query'
import { getV2 } from '../generated'

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
