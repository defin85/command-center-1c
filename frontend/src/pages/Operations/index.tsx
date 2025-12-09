/**
 * Operations page exports.
 * Re-exports OperationsPage as Operations for backward compatibility.
 */

export { OperationsPage as Operations } from './OperationsPage'
export { OperationsPage } from './OperationsPage'
export { OperationsTable } from './components/OperationsTable'
export { OperationDetailsModal } from './components/OperationDetailsModal'
export { LiveMonitorTab } from './components/LiveMonitorTab'
export { NewOperationWizard } from './components/NewOperationWizard'
export { getStatusColor, getOperationTypeLabel } from './utils'
export type {
  UIBatchOperation,
  UITask,
  OperationsTableProps,
  OperationDetailsModalProps,
  LiveMonitorTabProps,
  OperationsTabKey,
} from './types'
export type {
  NewOperationWizardProps,
  NewOperationData,
  OperationType,
} from './components/NewOperationWizard'
