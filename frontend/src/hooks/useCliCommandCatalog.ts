/**
 * Hook for fetching designer CLI command catalog.
 */

import { useCallback, useEffect, useState } from 'react'
import { getCliCommandCatalog, type CliCommandCatalogResponse, type CliCommandDescriptor } from '../api/operations'

export interface UseCliCommandCatalogResult {
  catalog: CliCommandCatalogResponse | null
  commands: CliCommandDescriptor[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useCliCommandCatalog(): UseCliCommandCatalogResult {
  const [commands, setCommands] = useState<CliCommandDescriptor[]>([])
  const [catalog, setCatalog] = useState<CliCommandCatalogResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getCliCommandCatalog()
      setCatalog(response)
      setCommands(response.commands ?? [])
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load CLI command catalog'
      setError(message)
      setCatalog(null)
      setCommands([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchCatalog()
  }, [fetchCatalog])

  return {
    catalog,
    commands,
    loading,
    error,
    refetch: fetchCatalog,
  }
}

export default useCliCommandCatalog
