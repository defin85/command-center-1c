/**
 * Constants for dashboard statistics calculations.
 */
import { BatchOperationStatus } from '../../api/generated/model/batchOperationStatus'
import { ClusterStatus } from '../../api/generated/model/clusterStatus'
import { DatabaseStatus } from '../../api/generated/model/databaseStatus'

// ============================================================================
// Operation Status Groups (for statistics calculation)
// ============================================================================

/** Statuses considered as "running" for dashboard stats */
export const OPERATION_RUNNING_STATUSES = [
  BatchOperationStatus.pending,
  BatchOperationStatus.queued,
  BatchOperationStatus.processing,
] as const

/** Status for completed operations */
export const OPERATION_COMPLETED_STATUS = BatchOperationStatus.completed

/** Status for failed operations */
export const OPERATION_FAILED_STATUS = BatchOperationStatus.failed

// ============================================================================
// Database Status Groups
// ============================================================================

/**
 * Database status indicating locked state.
 * Note: 'locked' is a business status not present in StatusC5cEnum,
 * but may be returned by API or used in Dashboard logic.
 */
export const DATABASE_LOCKED_STATUS = 'locked' as const

/** Database status indicating maintenance */
export const DATABASE_MAINTENANCE_STATUS = DatabaseStatus.maintenance

/** Database statuses considered unhealthy */
export const DATABASE_UNHEALTHY_STATUSES = [
  DATABASE_LOCKED_STATUS,
  DATABASE_MAINTENANCE_STATUS,
] as const

// ============================================================================
// Cluster Status Groups
// ============================================================================

/** Cluster statuses indicating critical state */
export const CLUSTER_CRITICAL_STATUSES = [
  ClusterStatus.error,
  ClusterStatus.inactive,
] as const
