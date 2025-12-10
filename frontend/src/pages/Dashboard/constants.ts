/**
 * Constants for dashboard statistics calculations.
 */
import { BatchOperationStatusEnum } from '../../api/generated/model/batchOperationStatusEnum'
import { StatusD4eEnum } from '../../api/generated/model/statusD4eEnum'

// ============================================================================
// Operation Status Groups (for statistics calculation)
// ============================================================================

/** Statuses considered as "running" for dashboard stats */
export const OPERATION_RUNNING_STATUSES = [
  BatchOperationStatusEnum.pending,
  BatchOperationStatusEnum.queued,
  BatchOperationStatusEnum.processing,
] as const

/** Status for completed operations */
export const OPERATION_COMPLETED_STATUS = BatchOperationStatusEnum.completed

/** Status for failed operations */
export const OPERATION_FAILED_STATUS = BatchOperationStatusEnum.failed

// ============================================================================
// Database Status Groups
// ============================================================================

/**
 * Database status indicating locked state.
 * Note: 'locked' is a business status not present in StatusD4eEnum,
 * but may be returned by API or used in Dashboard logic.
 */
export const DATABASE_LOCKED_STATUS = 'locked' as const

/** Database status indicating maintenance */
export const DATABASE_MAINTENANCE_STATUS = StatusD4eEnum.maintenance

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
  StatusD4eEnum.error,
  StatusD4eEnum.inactive,
] as const
