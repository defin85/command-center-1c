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
import type {
  DashboardStats,
  OperationsStats,
  DatabasesStats,
  ClusterStats,
  UIBatchOperation,
} from '../types'
import {
  EMPTY_DASHBOARD_STATS,
  EMPTY_OPERATIONS_STATS,
  EMPTY_DATABASES_STATS,
} from '../types'

// API response types (from generated API)
interface OperationListResponse {
  operations?: Array<{
    id?: string
    operation_type?: string
    status?: string
    progress?: number
    created_at?: string
    updated_at?: string
    completed_at?: string | null
  }>
  total?: number
}

interface DatabaseListResponse {
  databases?: Array<{
    id?: string
    name?: string
    cluster_id?: string
    status?: string
  }>
  total?: number
}

interface ClusterListResponse {
  clusters?: Array<{
    id?: string
    name?: string
    status?: string
  }>
  total?: number
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
function calculateOperationsStats(
  operations: OperationListResponse['operations']
): OperationsStats {
  if (!operations || operations.length === 0) {
    return EMPTY_OPERATIONS_STATS
  }

  const todayStart = getTodayStart()
  let running = 0
  let completed = 0
  let failed = 0
  let todayCount = 0

  for (const op of operations) {
    const status = op.status?.toLowerCase()

    if (status === 'running' || status === 'pending' || status === 'processing') {
      running++
    } else if (status === 'completed') {
      completed++
    } else if (status === 'failed') {
      failed++
    }

    // Count today's operations
    if (op.created_at && op.created_at >= todayStart) {
      todayCount++
    }
  }

  const total = operations.length
  const finishedCount = completed + failed
  const successRate = finishedCount > 0 ? Math.round((completed / finishedCount) * 100) : 0

  return {
    total,
    running,
    completed,
    failed,
    successRate,
    todayCount,
  }
}

/**
 * Calculate database statistics from API response
 */
function calculateDatabasesStats(
  databases: DatabaseListResponse['databases']
): DatabasesStats {
  if (!databases || databases.length === 0) {
    return EMPTY_DATABASES_STATS
  }

  let active = 0
  let locked = 0
  let maintenance = 0

  for (const db of databases) {
    const status = db.status?.toLowerCase()

    if (status === 'locked') {
      locked++
    } else if (status === 'maintenance') {
      maintenance++
    } else {
      // active or any other status
      active++
    }
  }

  return {
    total: databases.length,
    active,
    locked,
    maintenance,
  }
}

/**
 * Calculate cluster statistics from databases and clusters
 */
function calculateClusterStats(
  clusters: ClusterListResponse['clusters'],
  databases: DatabaseListResponse['databases']
): ClusterStats[] {
  if (!clusters || clusters.length === 0) {
    return []
  }

  // Group databases by cluster_id
  const dbsByCluster = new Map<string, { total: number; healthy: number }>()

  if (databases) {
    for (const db of databases) {
      const clusterId = db.cluster_id
      if (!clusterId) continue

      const current = dbsByCluster.get(clusterId) || { total: 0, healthy: 0 }
      current.total++

      // Consider non-locked, non-maintenance databases as healthy
      const status = db.status?.toLowerCase()
      if (status !== 'locked' && status !== 'maintenance') {
        current.healthy++
      }

      dbsByCluster.set(clusterId, current)
    }
  }

  return clusters.map((cluster) => {
    const id = cluster.id || ''
    const stats = dbsByCluster.get(id) || { total: 0, healthy: 0 }

    // Determine cluster health status
    let status: ClusterStats['status'] = 'healthy'
    if (stats.total > 0) {
      const healthyRatio = stats.healthy / stats.total
      if (healthyRatio < 0.5) {
        status = 'critical'
      } else if (healthyRatio < 0.9) {
        status = 'degraded'
      }
    }

    // Check cluster API status
    const clusterStatus = cluster.status?.toLowerCase()
    if (clusterStatus === 'error' || clusterStatus === 'inactive') {
      status = 'critical'
    }

    return {
      id,
      name: cluster.name || 'Unknown Cluster',
      totalDatabases: stats.total,
      healthyDatabases: stats.healthy,
      status,
    }
  })
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
      // Parallel API requests
      const [operationsRes, databasesRes, clustersRes] = await Promise.all([
        apiClient.get<OperationListResponse>('/api/v1/operations/', {
          signal: abortController.signal,
          params: { limit: 100 },
        }),
        apiClient.get<DatabaseListResponse>('/api/v1/databases/', {
          signal: abortController.signal,
        }),
        apiClient.get<ClusterListResponse>('/api/v1/databases/clusters/', {
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

      // Transform operations for UI (create UIBatchOperation directly)
      const recentOperations: UIBatchOperation[] = operations
        .slice(0, 10)
        .map((op) => ({
          id: op.id || '',
          name: op.operation_type || '',
          description: '',
          operation_type: (op.operation_type || 'query') as UIBatchOperation['operation_type'],
          target_entity: '',
          status: (op.status || 'pending') as UIBatchOperation['status'],
          progress: op.progress || 0,
          total_tasks: 0,
          completed_tasks: 0,
          failed_tasks: 0,
          payload: null,
          config: null,
          task_id: null,
          started_at: null,
          completed_at: op.completed_at || null,
          duration_seconds: null,
          success_rate: null,
          created_by: '',
          metadata: null,
          created_at: op.created_at || '',
          updated_at: op.updated_at || '',
          database_names: [],
          tasks: [],
        }))

      const failedOperations: UIBatchOperation[] = operations
        .filter((op) => op.status?.toLowerCase() === 'failed')
        .slice(0, 10)
        .map((op) => ({
          id: op.id || '',
          name: op.operation_type || '',
          description: '',
          operation_type: (op.operation_type || 'query') as UIBatchOperation['operation_type'],
          target_entity: '',
          status: 'failed' as const,
          progress: op.progress || 0,
          total_tasks: 0,
          completed_tasks: 0,
          failed_tasks: 0,
          payload: null,
          config: null,
          task_id: null,
          started_at: null,
          completed_at: op.completed_at || null,
          duration_seconds: null,
          success_rate: null,
          created_by: '',
          metadata: null,
          created_at: op.created_at || '',
          updated_at: op.updated_at || '',
          database_names: [],
          tasks: [],
        }))

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
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
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
