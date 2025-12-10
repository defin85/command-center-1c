/**
 * Hook for dashboard statistics.
 *
 * Transforms raw API data into dashboard statistics using React Query
 * for data fetching and caching.
 */
import { useCallback, useMemo } from 'react'

import type { BatchOperation } from '../../../api/generated/model/batchOperation'
import type { Database } from '../../../api/generated/model/database'
import type { Cluster } from '../../../api/generated/model/cluster'
import { useDashboardQuery } from '../../../api/queries/dashboard'

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

// =============================================================================
// Helper Functions
// =============================================================================

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

// =============================================================================
// Hook Types
// =============================================================================

/**
 * Hook return type
 */
export interface UseDashboardStatsResult extends DashboardStats {
  /** Manually trigger refresh */
  refresh: () => void
}

// =============================================================================
// Main Hook
// =============================================================================

/**
 * Hook for dashboard statistics with auto-refresh.
 *
 * Uses React Query for data fetching with:
 * - Auto-refetch every 30 seconds (configurable)
 * - Caching and background updates
 * - Automatic AbortController handling
 *
 * @param refreshInterval - Refresh interval in milliseconds (default: 30000)
 */
export function useDashboardStats(refreshInterval = 30000): UseDashboardStatsResult {
  const { data, isLoading, error, dataUpdatedAt, refetch } = useDashboardQuery({
    refetchInterval: refreshInterval,
  })

  // Manual refresh callback
  const refresh = useCallback(() => {
    refetch()
  }, [refetch])

  // Calculate statistics from raw data
  const stats = useMemo((): DashboardStats => {
    // No data yet - return empty stats with loading state
    if (!data) {
      return {
        ...EMPTY_DASHBOARD_STATS,
        loading: isLoading,
        error: error ? (error as Error).message : null,
      }
    }

    const { operations, databases, clusters } = data

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

    return {
      operations: operationsStats,
      databases: databasesStats,
      clusters: clusterStats,
      recentOperations,
      failedOperations,
      // Show loading only on initial load (not on refetch)
      loading: isLoading && !data,
      error: error ? (error as Error).message : null,
      lastUpdated: dataUpdatedAt ? new Date(dataUpdatedAt) : null,
    }
  }, [data, isLoading, error, dataUpdatedAt])

  return {
    ...stats,
    refresh,
  }
}

export default useDashboardStats
