import { Button, Input, Space, Switch, Typography } from 'antd'
import { memo, useState } from 'react'

import type { TableFilterConfig } from '../types'

const { Text } = Typography

export interface FiltersTabProps {
  filterOrder: string[]
  filterVisibility: Record<string, boolean>
  filters: TableFilterConfig[]
  search: string
  onSearchChange: (value: string) => void
  onReorder: (fromKey: string, toKey: string) => void
  onMove: (key: string, direction: -1 | 1) => void
  onToggleVisible: (key: string, checked: boolean) => void
  canToggleVisible?: (key: string) => boolean
  idPrefix: string
}

export const FiltersTab = memo(({
  filterOrder,
  filterVisibility,
  filters,
  search,
  onSearchChange,
  onReorder,
  onMove,
  onToggleVisible,
  canToggleVisible,
  idPrefix,
}: FiltersTabProps) => {
  const [draggingKey, setDraggingKey] = useState<string | null>(null)
  const query = search.trim().toLowerCase()
  const filteredOrder = filterOrder.filter((key) => {
    if (!query) return true
    const filter = filters.find((item) => item.key === key)
    if (!filter) return false
    return filter.label.toLowerCase().includes(query) || filter.key.toLowerCase().includes(query)
  })

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Input
        id={`${idPrefix}-filters-search`}
        placeholder="Search filters"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        style={{ width: 220 }}
        allowClear
      />
      {filteredOrder.map((key) => {
        const filter = filters.find((item) => item.key === key)
        if (!filter) return null
        const index = filterOrder.indexOf(key)
        return (
          <div
            key={key}
            draggable
            onDragStart={() => setDraggingKey(key)}
            onDragEnd={() => setDraggingKey(null)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => {
              if (!draggingKey || draggingKey === key) return
              onReorder(draggingKey, key)
              setDraggingKey(null)
            }}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 12,
              padding: '4px 0',
              cursor: 'move',
            }}
          >
            <Space>
              <Button size="small" disabled={index === 0} onClick={() => onMove(key, -1)}>↑</Button>
              <Button
                size="small"
                disabled={index === filterOrder.length - 1}
                onClick={() => onMove(key, 1)}
              >
                ↓
              </Button>
              <Text>{filter.label}</Text>
            </Space>
            <Space>
              <Text type="secondary">Visible</Text>
              <Switch
                id={`${idPrefix}-filter-visible-${key}`}
                checked={filterVisibility[key] !== false}
                disabled={canToggleVisible ? !canToggleVisible(key) : false}
                onChange={(checked) => onToggleVisible(key, checked)}
              />
            </Space>
          </div>
        )
      })}
    </Space>
  )
})

