import { Button, Input, Space } from 'antd'
import type { ReactNode } from 'react'

interface TableToolbarProps {
  searchValue?: string
  searchPlaceholder?: string
  onSearchChange?: (value: string) => void
  filters?: ReactNode
  onReset?: () => void
  actions?: ReactNode
  idPrefix?: string
}

export const TableToolbar = ({
  searchValue,
  searchPlaceholder = 'Search',
  onSearchChange,
  filters,
  onReset,
  actions,
  idPrefix,
}: TableToolbarProps) => {
  const normalizedPlaceholder = searchPlaceholder
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  const baseId = idPrefix || 'table-toolbar'
  const searchId = `${baseId}-search-${normalizedPlaceholder || 'search'}`
  return (
    <Space wrap style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
      <Space wrap>
        {onSearchChange && (
          <Input
            id={searchId}
            allowClear
            value={searchValue}
            placeholder={searchPlaceholder}
            onChange={(event) => onSearchChange(event.target.value)}
            style={{ width: 260 }}
          />
        )}
        {filters}
      </Space>
      <Space>
        {actions}
        {onReset && (
          <Button onClick={onReset}>Reset</Button>
        )}
      </Space>
    </Space>
  )
}
