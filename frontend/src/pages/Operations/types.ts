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
  onFilterWorkflow?: (workflowExecutionId: string) => void
  onFilterNode?: (nodeId: string) => void
}

/**
 * Props for OperationDetailsModal component
 */
export interface OperationDetailsModalProps {
  operation: UIBatchOperation | null
  visible: boolean
  onClose: () => void
  onTimeline: (operationId: string) => void
}
