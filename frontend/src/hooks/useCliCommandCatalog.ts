/**
 * Hook for fetching designer CLI command catalog.
 */

import { useCallback, useEffect, useState } from 'react'
import { getCliCommandCatalog, type CliCommandDescriptor } from '../api/operations'

export interface UseCliCommandCatalogResult {
  commands: CliCommandDescriptor[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useCliCommandCatalog(): UseCliCommandCatalogResult {
  const [commands, setCommands] = useState<CliCommandDescriptor[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getCliCommandCatalog()
      setCommands(response.commands ?? [])
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load CLI command catalog'
      setError(message)
      setCommands([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchCatalog()
  }, [fetchCatalog])

  return {
    commands,
    loading,
    error,
    refetch: fetchCatalog,
  }
}

export default useCliCommandCatalog
