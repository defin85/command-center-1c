/**
 * Hook for fetching and managing dashboard statistics.
 *
 * Features:
 * - Auto-refresh every 30 seconds (configurable)
 * - Parallel API requests via Promise.all
 * - AbortController for cleanup on unmount
 * - Error handling without crashing
 * - Loading state management
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { apiClient } from '../../../api/client'
import type { BatchOperation } from '../../../api/generated/model/batchOperation'
import type { Database } from '../../../api/generated/model/database'
import type { Cluster } from '../../../api/generated/model/cluster'

import {
  OPERATION_RUNNING_STATUSES,
  OPERATION_COMPLETED_STATUS,
  OPERATION_FAILED_STATUS,
  DATABASE_LOCKED_STATUS,
  DATABASE_MAINTENANCE_STATUS,
  DATABASE_UNHEALTHY_STATUSES,
  CLUSTER_CRITICAL_STATUSES,
} from '../constants'

import type {
  DashboardStats,
  OperationsStats,
  DatabasesStats,
  ClusterStats,
  DashboardOperation,
} from '../types'
import {
  EMPTY_DASHBOARD_STATS,
  EMPTY_OPERATIONS_STATS,
  EMPTY_DATABASES_STATS,
} from '../types'

// API response types for v2 action-based API
interface OperationsResponse {
  operations?: BatchOperation[]
  count?: number
  total?: number
}

interface DatabasesResponse {
  databases?: Database[]
  count?: number
  total?: number
}

interface ClustersResponse {
  clusters?: Cluster[]
  count?: number
}

/**
 * Hook return type
 */
export interface UseDashboardStatsResult extends DashboardStats {
  /** Manually trigger refresh */
  refresh: () => void
}

/**
 * Get start of today in ISO format
 */
function getTodayStart(): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return today.toISOString()
}

/**
 * Calculate operations statistics from API response
 */
function calculateOperationsStats(operations: BatchOperation[]): OperationsStats {
  if (operations.length === 0) {
    return EMPTY_OPERATIONS_STATS
  }

  const todayStart = getTodayStart()
  let running = 0
  let completed = 0
  let failed = 0
  let todayCount = 0

  for (const op of operations) {
    const status = op.status

    if ((OPERATION_RUNNING_STATUSES as readonly string[]).includes(status)) {
      running++
    } else if (status === OPERATION_COMPLETED_STATUS) {
      completed++
    } else if (status === OPERATION_FAILED_STATUS) {
      failed++
    }

    if (op.created_at >= todayStart) {
      todayCount++
    }
  }

  const total = operations.length
  const finishedCount = completed + failed
  const successRate = finishedCount > 0 ? Math.round((completed / finishedCount) * 100) : 0

  return { total, running, completed, failed, successRate, todayCount }
}

/**
 * Calculate database statistics from API response
 */
function calculateDatabasesStats(databases: Database[]): DatabasesStats {
  if (databases.length === 0) {
    return EMPTY_DATABASES_STATS
  }

  let active = 0
  let locked = 0
  let maintenance = 0

  for (const db of databases) {
    // Cast to string for comparison since API may return statuses not in StatusD4eEnum
    const status = db.status as string | undefined

    if (status === DATABASE_LOCKED_STATUS) {
      locked++
    } else if (status === DATABASE_MAINTENANCE_STATUS) {
      maintenance++
    } else {
      active++
    }
  }

  return { total: databases.length, active, locked, maintenance }
}

/**
 * Calculate cluster statistics from databases and clusters
 */
function calculateClusterStats(
  clusters: Cluster[],
  databases: Database[]
): ClusterStats[] {
  if (clusters.length === 0) {
    return []
  }

  // Group databases by cluster_id
  const dbsByCluster = new Map<string, { total: number; healthy: number }>()

  for (const db of databases) {
    const clusterId = db.cluster_id
    if (!clusterId) continue

    const current = dbsByCluster.get(clusterId) || { total: 0, healthy: 0 }
    current.total++

    const isUnhealthy = (DATABASE_UNHEALTHY_STATUSES as readonly string[]).includes(
      db.status ?? ''
    )
    if (!isUnhealthy) {
      current.healthy++
    }

    dbsByCluster.set(clusterId, current)
  }

  return clusters.map((cluster) => {
    const stats = dbsByCluster.get(cluster.id) || { total: 0, healthy: 0 }

    let status: ClusterStats['status'] = 'healthy'
    if (stats.total > 0) {
      const healthyRatio = stats.healthy / stats.total
      if (healthyRatio < 0.5) {
        status = 'critical'
      } else if (healthyRatio < 0.9) {
        status = 'degraded'
      }
    }

    const isCritical = (CLUSTER_CRITICAL_STATUSES as readonly string[]).includes(
      cluster.status ?? ''
    )
    if (isCritical) {
      status = 'critical'
    }

    return {
      id: cluster.id,
      name: cluster.name || 'Unknown Cluster',
      totalDatabases: stats.total,
      healthyDatabases: stats.healthy,
      status,
    }
  })
}

/**
 * Transform BatchOperation to lightweight DashboardOperation
 */
function toDashboardOperation(op: BatchOperation): DashboardOperation {
  return {
    id: op.id,
    name: op.name,
    operation_type: op.operation_type,
    status: op.status,
    progress: op.progress,
    created_at: op.created_at,
    updated_at: op.updated_at,
    completed_at: op.completed_at ?? null,
  }
}

/**
 * Hook for dashboard statistics with auto-refresh
 *
 * @param refreshInterval - Refresh interval in milliseconds (default: 30000)
 */
export function useDashboardStats(refreshInterval = 30000): UseDashboardStatsResult {
  const [stats, setStats] = useState<DashboardStats>(EMPTY_DASHBOARD_STATS)

  // Track if this is the first load
  const isFirstLoadRef = useRef(true)
  const abortControllerRef = useRef<AbortController | null>(null)
  const isMountedRef = useRef(false)

  const fetchData = useCallback(async () => {
    // Create new AbortController first to avoid race condition
    const abortController = new AbortController()

    // Cancel previous request atomically
    const previousController = abortControllerRef.current
    abortControllerRef.current = abortController
    previousController?.abort()

    // Set loading only on first load
    if (isFirstLoadRef.current) {
      setStats((prev) => ({ ...prev, loading: true, error: null }))
    }

    try {
      // Parallel API requests (v2 action-based API)
      const [operationsRes, databasesRes, clustersRes] = await Promise.all([
        apiClient.get<OperationsResponse>('/api/v2/operations/list-operations/', {
          signal: abortController.signal,
          params: { limit: 100 },
        }),
        apiClient.get<DatabasesResponse>('/api/v2/databases/list-databases/', {
          signal: abortController.signal,
        }),
        apiClient.get<ClustersResponse>('/api/v2/clusters/list-clusters/', {
          signal: abortController.signal,
        }),
      ])

      // Check if still mounted
      if (!isMountedRef.current) return

      const operations = operationsRes.data.operations || []
      const databases = databasesRes.data.databases || []
      const clusters = clustersRes.data.clusters || []

      // Calculate statistics
      const operationsStats = calculateOperationsStats(operations)
      const databasesStats = calculateDatabasesStats(databases)
      const clusterStats = calculateClusterStats(clusters, databases)

      // Transform operations for UI
      const recentOperations = operations.slice(0, 10).map(toDashboardOperation)

      const failedOperations = operations
        .filter((op) => op.status === OPERATION_FAILED_STATUS)
        .slice(0, 10)
        .map(toDashboardOperation)

      setStats({
        operations: operationsStats,
        databases: databasesStats,
        clusters: clusterStats,
        recentOperations,
        failedOperations,
        loading: false,
        error: null,
        lastUpdated: new Date(),
      })

      isFirstLoadRef.current = false
    } catch (error) {
      // Ignore abort/cancel errors (both native AbortError and axios CanceledError)
      if (
        error instanceof Error &&
        (error.name === 'AbortError' || error.name === 'CanceledError')
      ) {
        return
      }

      // Check if still mounted
      if (!isMountedRef.current) return

      console.error('Dashboard fetch error:', error)

      setStats((prev) => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load dashboard data',
      }))

      isFirstLoadRef.current = false
    }
  }, [])

  // Manual refresh
  const refresh = useCallback(() => {
    fetchData()
  }, [fetchData])

  // Setup polling and cleanup
  useEffect(() => {
    isMountedRef.current = true

    // Initial fetch
    fetchData()

    // Setup polling
    const intervalId = setInterval(fetchData, refreshInterval)

    // Cleanup
    return () => {
      isMountedRef.current = false

      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }

      clearInterval(intervalId)
    }
  }, [fetchData, refreshInterval])

  return {
    ...stats,
    refresh,
  }
}

export default useDashboardStats
