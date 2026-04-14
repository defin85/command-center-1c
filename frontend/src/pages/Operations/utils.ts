/**
 * Utility functions for Operations components.
 * Separated for react-refresh compatibility.
 */

import type { useOperationsTranslation } from '../../i18n'

type OperationsT = ReturnType<typeof useOperationsTranslation>['t']

const getTypeKey = (type: string) => {
  const keys: Record<string, string> = {
    create: 'create',
    update: 'update',
    delete: 'delete',
    query: 'query',
    designer_cli: 'designerCli',
    lock_scheduled_jobs: 'lockScheduledJobs',
    unlock_scheduled_jobs: 'unlockScheduledJobs',
    terminate_sessions: 'terminateSessions',
    block_sessions: 'blockSessions',
    unblock_sessions: 'unblockSessions',
    sync_cluster: 'syncCluster',
    discover_clusters: 'discoverClusters',
    health_check: 'healthCheck',
    ibcmd_cli: 'ibcmdCli',
  }
  return keys[type] ?? null
}

const getStatusKey = (status: string) => {
  const keys: Record<string, string> = {
    pending: 'pending',
    queued: 'queued',
    processing: 'processing',
    completed: 'completed',
    failed: 'failed',
    cancelled: 'cancelled',
  }
  return keys[status] ?? null
}

/**
 * Get Ant Design tag color for operation status
 */
export const getStatusColor = (status: string): string => {
  const colors: Record<string, string> = {
    pending: 'default',
    queued: 'blue',
    processing: 'processing',
    completed: 'success',
    failed: 'error',
    cancelled: 'default',
  }
  return colors[status] || 'default'
}

/**
 * Get human-readable label for operation type
 */
export const getOperationTypeLabel = (type: string, t?: OperationsT): string => {
  const key = getTypeKey(type)
  if (key && t) {
    return t(($) => $.operationTypes[key as keyof typeof $.operationTypes])
  }
  const labels: Record<string, string> = {
    create: 'Create',
    update: 'Update',
    delete: 'Delete',
    query: 'Query',
    designer_cli: 'Designer CLI',
    // RAS operations
    lock_scheduled_jobs: 'Lock Scheduled Jobs',
    unlock_scheduled_jobs: 'Unlock Scheduled Jobs',
    terminate_sessions: 'Terminate Sessions',
    block_sessions: 'Block Sessions',
    unblock_sessions: 'Unblock Sessions',
    // Cluster operations
    sync_cluster: 'Sync Cluster',
    discover_clusters: 'Discover Clusters',
  }
  return labels[type] || type
}

export const getOperationTypeDescription = (type: string, t?: OperationsT): string | null => {
  const key = getTypeKey(type)
  if (key && t) {
    return t(($) => $.operationDescriptions[key as keyof typeof $.operationDescriptions])
  }
  const descriptions: Record<string, string> = {
    lock_scheduled_jobs: 'Prevent scheduled jobs from running',
    unlock_scheduled_jobs: 'Allow scheduled jobs to run',
    block_sessions: 'Block new user connections',
    unblock_sessions: 'Allow new user connections',
    terminate_sessions: 'Disconnect active user sessions',
    designer_cli: 'Execute 1C DESIGNER batch command',
    ibcmd_cli: 'Execute schema-driven IBCMD command (driver catalog)',
    query: 'Run OData query on databases',
    sync_cluster: 'Synchronize cluster data with RAS',
    health_check: 'Check database connectivity',
  }
  return descriptions[type] ?? null
}

export const getOperationStatusLabel = (status: string, t?: OperationsT): string => {
  const key = getStatusKey(status)
  if (key && t) {
    return t(($) => $.statuses[key as keyof typeof $.statuses])
  }
  return status
}

export const getOperationDriverLabel = (driver: string, t?: OperationsT): string => {
  if (t && ['ras', 'odata', 'cli', 'ibcmd', 'workflow'].includes(driver)) {
    return t(($) => $.drivers[driver as keyof typeof $.drivers])
  }
  return driver
}
