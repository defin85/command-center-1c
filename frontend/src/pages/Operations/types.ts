/**
 * Local types for Operations page components.
 * Re-exports UI types from operationTransforms for convenience.
 */

import type { UIBatchOperation, UITask } from '../../utils/operationTransforms'
import type { TimelineStreamEvent } from '../../hooks/useOperationTimelineStream'
import type { TableToolkitState } from '../../components/table/hooks/useTableToolkit'

// Re-export for convenience
export type { UIBatchOperation, UITask }

/**
 * Props for OperationsTable component
 */
export interface OperationsTableProps {
  table: TableToolkitState<UIBatchOperation>
  operations: UIBatchOperation[]
  total: number
  loading: boolean
  toolbarActions?: React.ReactNode
  columns: import('antd/es/table').ColumnsType<UIBatchOperation>
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
  liveEvent?: TimelineStreamEvent | null
}
