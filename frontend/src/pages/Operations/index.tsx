/**
 * Operations page exports.
 * Re-exports OperationsPage as Operations for backward compatibility.
 */

/* eslint-disable react-refresh/only-export-components */

export { OperationsPage as Operations } from './OperationsPage'
export { OperationsPage } from './OperationsPage'
export { OperationsTable } from './components/OperationsTable'
export { OperationDetailsModal } from './components/OperationDetailsModal'
export { OperationsFilters } from './components/OperationsFilters'
export { NewOperationWizard } from './components/NewOperationWizard'
export { getStatusColor, getOperationTypeLabel } from './utils'
export type {
  UIBatchOperation,
  UITask,
  OperationsTableProps,
  OperationDetailsModalProps,
} from './types'
export type {
  NewOperationWizardProps,
  NewOperationData,
  OperationType,
} from './components/NewOperationWizard'
