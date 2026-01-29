/**
 * Hook for real-time React Query cache invalidation via WebSocket.
 *
 * Listens to dashboard_invalidate events from serviceMeshManager and
 * invalidates the corresponding React Query caches (without subscribing
 * to the full ServiceMeshState in React).
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
import { serviceMeshManager } from '../stores/serviceMeshManager'
import { queryKeys } from '../api/queries/queryKeys'

export function useRealtimeInvalidation(enabled = true) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!enabled) return

    serviceMeshManager.start()
    const unsubscribe = serviceMeshManager.subscribeInvalidation(({ scope }) => {
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
    })

    return () => {
      unsubscribe()
      serviceMeshManager.stop()
    }
  }, [enabled, queryClient])
}

export default useRealtimeInvalidation
