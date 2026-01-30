import { Space, Input } from 'antd'
import type { OperationFilters } from '../../../api/queries'

interface OperationsFiltersProps {
  filters: OperationFilters
  onChange: (next: OperationFilters) => void
}

export const OperationsFilters = ({ filters, onChange }: OperationsFiltersProps) => {
  return (
    <Space size="middle" wrap>
      <Input
        placeholder="Operation ID"
        value={filters.operation_id || ''}
        onChange={(event) => onChange({ ...filters, operation_id: event.target.value })}
        style={{ width: 260 }}
        allowClear
        aria-label="Operation ID filter"
      />
      <Input
        placeholder="Workflow execution ID"
        value={filters.workflow_execution_id || ''}
        onChange={(event) => onChange({ ...filters, workflow_execution_id: event.target.value })}
        style={{ width: 260 }}
        allowClear
        aria-label="Workflow execution ID filter"
      />
      <Input
        placeholder="Node ID"
        value={filters.node_id || ''}
        onChange={(event) => onChange({ ...filters, node_id: event.target.value })}
        style={{ width: 200 }}
        allowClear
        aria-label="Node ID filter"
      />
    </Space>
  )
}
