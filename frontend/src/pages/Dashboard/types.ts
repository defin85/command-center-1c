/**
 * Dashboard page types.
 *
 * Types for statistics, cluster health, and dashboard state management.
 */

import type { BatchOperationStatus } from '../../api/generated/model/batchOperationStatus'
import type { BatchOperationOperationType } from '../../api/generated/model/batchOperationOperationType'

/**
 * Statistics for operations
 */
export interface OperationsStats {
  /** Total number of operations */
  total: number
  /** Currently running operations */
  running: number
  /** Successfully completed operations */
  completed: number
  /** Failed operations */
  failed: number
  /** Success rate percentage (0-100) */
  successRate: number
  /** Operations created today */
  todayCount: number
}

/**
 * Statistics for databases
 */
export interface DatabasesStats {
  /** Total number of databases */
  total: number
  /** Active (not locked or in maintenance) databases */
  active: number
  /** Locked databases */
  locked: number
  /** Databases in maintenance mode */
  maintenance: number
}

/**
 * Cluster health status
 */
export interface ClusterStats {
  /** Cluster ID */
  id: string
  /** Cluster display name */
  name: string
  /** Total databases in cluster */
  totalDatabases: number
  /** Healthy databases count */
  healthyDatabases: number
  /** Overall cluster status */
  status: 'healthy' | 'degraded' | 'critical'
}

/**
 * Lightweight operation type for Dashboard display.
 * Contains only fields needed for RecentOperations and FailedOperations widgets.
 */
export interface DashboardOperation {
  id: string
  name: string
  operation_type: BatchOperationOperationType
  status: BatchOperationStatus
  progress: number
  created_at: string
  updated_at: string
  completed_at: string | null
}

/**
 * Complete dashboard state
 */
export interface DashboardStats {
  /** Operations statistics */
  operations: OperationsStats
  /** Database statistics */
  databases: DatabasesStats
  /** Per-cluster statistics */
  clusters: ClusterStats[]
  /** Recent operations (last 10) */
  recentOperations: DashboardOperation[]
  /** Failed operations requiring attention */
  failedOperations: DashboardOperation[]
  /** Loading state */
  loading: boolean
  /** Error message if any */
  error: string | null
  /** Last successful data update */
  lastUpdated: Date | null
}

/**
 * Default empty stats for initial state
 */
export const EMPTY_OPERATIONS_STATS: OperationsStats = {
  total: 0,
  running: 0,
  completed: 0,
  failed: 0,
  successRate: 0,
  todayCount: 0,
}

/**
 * Default empty database stats
 */
export const EMPTY_DATABASES_STATS: DatabasesStats = {
  total: 0,
  active: 0,
  locked: 0,
  maintenance: 0,
}

/**
 * Default empty dashboard state
 */
export const EMPTY_DASHBOARD_STATS: DashboardStats = {
  operations: EMPTY_OPERATIONS_STATS,
  databases: EMPTY_DATABASES_STATS,
  clusters: [],
  recentOperations: [],
  failedOperations: [],
  loading: true,
  error: null,
  lastUpdated: null,
}
