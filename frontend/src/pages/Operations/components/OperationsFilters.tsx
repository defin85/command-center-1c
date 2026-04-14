import { Space, Input } from 'antd'
import type { OperationFilters } from '../../../api/queries'
import { useOperationsTranslation } from '../../../i18n'

interface OperationsFiltersProps {
  filters: OperationFilters
  onChange: (next: OperationFilters) => void
}

export const OperationsFilters = ({ filters, onChange }: OperationsFiltersProps) => {
  const { t } = useOperationsTranslation()
  return (
    <Space size="middle" wrap>
      <Input
        placeholder={t(($) => $.table.operationId)}
        value={filters.operation_id || ''}
        onChange={(event) => onChange({ ...filters, operation_id: event.target.value })}
        style={{ width: 260 }}
        allowClear
        aria-label={t(($) => $.table.operationId)}
      />
      <Input
        placeholder={t(($) => $.table.workflow)}
        value={filters.workflow_execution_id || ''}
        onChange={(event) => onChange({ ...filters, workflow_execution_id: event.target.value })}
        style={{ width: 260 }}
        allowClear
        aria-label={t(($) => $.table.workflow)}
      />
      <Input
        placeholder={t(($) => $.inspect.node)}
        value={filters.node_id || ''}
        onChange={(event) => onChange({ ...filters, node_id: event.target.value })}
        style={{ width: 200 }}
        allowClear
        aria-label={t(($) => $.inspect.node)}
      />
    </Space>
  )
}
