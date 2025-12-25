import { Button, Input, Space } from 'antd'
import type { ReactNode } from 'react'

interface TableToolbarProps {
  searchValue?: string
  searchPlaceholder?: string
  onSearchChange?: (value: string) => void
  filters?: ReactNode
  onReset?: () => void
  actions?: ReactNode
}

export const TableToolbar = ({
  searchValue,
  searchPlaceholder = 'Search',
  onSearchChange,
  filters,
  onReset,
  actions,
}: TableToolbarProps) => {
  return (
    <Space wrap style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
      <Space wrap>
        {onSearchChange && (
          <Input
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
