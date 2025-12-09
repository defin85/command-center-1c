/**
 * Local types for Operations page components.
 * Re-exports UI types from operationTransforms for convenience.
 */

import type { UIBatchOperation, UITask } from '../../utils/operationTransforms'

// Re-export for convenience
export type { UIBatchOperation, UITask }

/**
 * Props for OperationsTable component
 */
export interface OperationsTableProps {
  operations: UIBatchOperation[]
  loading: boolean
  onRefresh: () => void
  onViewDetails: (operation: UIBatchOperation) => void
  onCancel: (operationId: string) => void
}

/**
 * Props for OperationDetailsModal component
 */
export interface OperationDetailsModalProps {
  operation: UIBatchOperation | null
  visible: boolean
  onClose: () => void
  onMonitor: (operationId: string) => void
}

/**
 * Props for LiveMonitorTab component (placeholder)
 */
export interface LiveMonitorTabProps {
  operationId?: string
}

/**
 * Tab keys for OperationsPage
 */
export type OperationsTabKey = 'list' | 'monitor'
