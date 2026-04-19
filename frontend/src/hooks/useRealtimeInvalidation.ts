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

const INVALIDATION_WINDOW_MS = 1000

export function useRealtimeInvalidation(enabled = true) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!enabled) return

    const pendingInvalidations = new Map<string, ReturnType<typeof setTimeout>>()
    const scheduleInvalidate = (cacheKey: string, queryKey?: readonly unknown[]) => {
      if (pendingInvalidations.has(cacheKey)) {
        return
      }

      const timerId = setTimeout(() => {
        pendingInvalidations.delete(cacheKey)
        if (queryKey) {
          void queryClient.invalidateQueries({ queryKey })
          return
        }
        void queryClient.invalidateQueries()
      }, INVALIDATION_WINDOW_MS)

      pendingInvalidations.set(cacheKey, timerId)
    }

    const clearPendingInvalidations = () => {
      pendingInvalidations.forEach((timerId) => clearTimeout(timerId))
      pendingInvalidations.clear()
    }

    serviceMeshManager.start()
    const unsubscribe = serviceMeshManager.subscribeInvalidation(({ scope }) => {
      switch (scope) {
        case 'operations':
          // Dashboard already polls on its own cadence; invalidating it here turns
          // noisy model updates into request storms on the home route.
          scheduleInvalidate('operations', queryKeys.operations.all)
          break
        case 'databases':
          scheduleInvalidate('databases', queryKeys.databases.all)
          break
        case 'clusters':
          scheduleInvalidate('clusters', queryKeys.clusters.all)
          break
        case 'all':
        default:
          clearPendingInvalidations()
          void queryClient.invalidateQueries()
          break
      }
    })

    return () => {
      clearPendingInvalidations()
      unsubscribe()
      serviceMeshManager.stop()
    }
  }, [enabled, queryClient])
}

export default useRealtimeInvalidation
