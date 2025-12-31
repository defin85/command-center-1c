/**
 * Utility functions for Operations components.
 * Separated for react-refresh compatibility.
 */

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
export const getOperationTypeLabel = (type: string): string => {
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
