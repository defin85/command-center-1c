import { Space, Switch, Typography } from 'antd'
import { memo } from 'react'

import type { TableColumnConfig } from '../hooks/useTablePreferences'

const { Text } = Typography

export interface SortingTabProps {
  columns: TableColumnConfig[]
  sortableColumns: string[]
  onToggle: (key: string, checked: boolean) => void
  idPrefix: string
}

export const SortingTab = memo(({
  columns,
  sortableColumns,
  onToggle,
  idPrefix,
}: SortingTabProps) => (
  <Space direction="vertical" style={{ width: '100%' }}>
    <Text type="secondary">Allowed sortable columns</Text>
    <Space wrap>
      {columns
        .filter((col) => col.sortable)
        .map((col) => (
          <Space key={col.key}>
            <Switch
              id={`${idPrefix}-sortable-${col.key}`}
              checked={sortableColumns.includes(col.key)}
              onChange={(checked) => onToggle(col.key, checked)}
            />
            <Text>{col.label}</Text>
          </Space>
        ))}
    </Space>
  </Space>
))

