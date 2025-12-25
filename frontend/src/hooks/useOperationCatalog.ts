/**
 * Hook for fetching operation catalog for Operations Wizard.
 */

import { useCallback, useEffect, useState } from 'react'
import { getOperationCatalog, type OperationCatalogItem } from '../api/operations'

export interface UseOperationCatalogResult {
  items: OperationCatalogItem[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useOperationCatalog(): UseOperationCatalogResult {
  const [items, setItems] = useState<OperationCatalogItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getOperationCatalog()
      setItems(response.items ?? [])
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load operation catalog'
      setError(message)
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchCatalog()
  }, [fetchCatalog])

  return {
    items,
    loading,
    error,
    refetch: fetchCatalog,
  }
}

export default useOperationCatalog
