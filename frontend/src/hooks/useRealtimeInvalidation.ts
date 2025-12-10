/**
 * Hook for real-time React Query cache invalidation via WebSocket.
 *
 * Listens to dashboard_invalidate events from useServiceMesh and
 * invalidates the corresponding React Query caches.
 *
 * Usage:
 * ```tsx
 * // In App.tsx or a top-level component
 * function App() {
 *   useRealtimeInvalidation()
 *   return <Router>...</Router>
 * }
 * ```
 */
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useServiceMesh } from './useServiceMesh'
import { queryKeys } from '../api/queries'

export function useRealtimeInvalidation() {
  const queryClient = useQueryClient()
  const { lastInvalidation } = useServiceMesh()

  useEffect(() => {
    if (!lastInvalidation) return

    const { scope } = lastInvalidation

    switch (scope) {
      case 'operations':
        queryClient.invalidateQueries({ queryKey: queryKeys.operations.all })
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.stats })
        break
      case 'databases':
        queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.stats })
        break
      case 'clusters':
        queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.stats })
        break
      case 'all':
      default:
        queryClient.invalidateQueries()
        break
    }
  }, [lastInvalidation, queryClient])
}

export default useRealtimeInvalidation
