import { Button, Checkbox, Col, Divider, Input, Row, Select, Space, Switch, Typography } from 'antd'
import { memo, useMemo, useState } from 'react'

import type { TableColumnConfig } from '../hooks/useTablePreferences'

const { Text } = Typography

export interface ColumnsTabProps {
  columns: TableColumnConfig[]
  visibleColumns: string[]
  sortableColumns: string[]
  search: string
  selectedKey: string | null
  groupLabelByKey: Map<string, string>
  groupOptions: Array<{ value: string; label: string }>
  onSearchChange: (value: string) => void
  onShowAll: () => void
  onHideAll: () => void
  onSelect: (key: string) => void
  onMove: (key: string, direction: -1 | 1) => void
  onChangeGroup: (key: string, groupKey: string) => void
  onToggleVisible: (key: string, checked: boolean) => void
  onReorder: (fromKey: string, toKey: string) => void
  groupKeyByColumn: Map<string, string>
  idPrefix: string
}

export const ColumnsTab = memo(({
  columns,
  visibleColumns,
  sortableColumns,
  search,
  selectedKey,
  groupLabelByKey,
  groupOptions,
  onSearchChange,
  onShowAll,
  onHideAll,
  onSelect,
  onMove,
  onChangeGroup,
  onToggleVisible,
  onReorder,
  groupKeyByColumn,
  idPrefix,
}: ColumnsTabProps) => {
  const [draggingKey, setDraggingKey] = useState<string | null>(null)
  const selectedColumn = selectedKey
    ? columns.find((col) => col.key === selectedKey) || null
    : null
  const selectedGroupKey = selectedColumn
    ? (groupKeyByColumn.get(selectedColumn.key) || 'general')
    : 'general'

  const filteredColumns = columns.filter((col) => {
    if (!search.trim()) return true
    const query = search.trim().toLowerCase()
    return col.label.toLowerCase().includes(query) || col.key.toLowerCase().includes(query)
  })

  const moveAvailability = useMemo(() => {
    const result = new Map<string, { up: boolean; down: boolean }>()
    const orderKeys = columns.map((col) => col.key)
    orderKeys.forEach((key, index) => {
      const groupKey = groupKeyByColumn.get(key) || 'general'
      let up = false
      let down = false
      for (let i = index - 1; i >= 0; i -= 1) {
        if ((groupKeyByColumn.get(orderKeys[i]) || 'general') === groupKey) {
          up = true
          break
        }
      }
      for (let i = index + 1; i < orderKeys.length; i += 1) {
        if ((groupKeyByColumn.get(orderKeys[i]) || 'general') === groupKey) {
          down = true
          break
        }
      }
      result.set(key, { up, down })
    })
    return result
  }, [columns, groupKeyByColumn])

  const groupedColumns = useMemo(() => {
    const groups: Array<{ key: string; label: string; items: TableColumnConfig[] }> = []
    const seen = new Map<string, number>()
    filteredColumns.forEach((col) => {
      const key = groupKeyByColumn.get(col.key) || 'general'
      const label = groupLabelByKey.get(key) || key
      if (!seen.has(key)) {
        seen.set(key, groups.length)
        groups.push({ key, label, items: [col] })
        return
      }
      const index = seen.get(key) as number
      groups[index].items.push(col)
    })
    return groups
  }, [filteredColumns, groupKeyByColumn, groupLabelByKey])

  return (
    <Row gutter={16}>
      <Col span={14}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <Input
              id={`${idPrefix}-columns-search`}
              placeholder="Search columns"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              style={{ width: 220 }}
              allowClear
            />
            <Button onClick={onShowAll}>Show all</Button>
            <Button onClick={onHideAll}>Hide all</Button>
          </Space>
          {groupedColumns.map((group) => (
            <div key={group.key}>
              <Text strong>{group.label}</Text>
              <Divider style={{ margin: '8px 0' }} />
              {group.items.map((col) => (
                <div
                  key={col.key}
                  draggable
                  onClick={() => onSelect(col.key)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      onSelect(col.key)
                    }
                  }}
                  onDragStart={() => setDraggingKey(col.key)}
                  onDragEnd={() => setDraggingKey(null)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => {
                    if (!draggingKey || draggingKey === col.key) return
                    if (groupKeyByColumn.get(draggingKey) !== groupKeyByColumn.get(col.key)) {
                      setDraggingKey(null)
                      return
                    }
                    onReorder(draggingKey, col.key)
                    setDraggingKey(null)
                  }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Select column ${col.label}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                    padding: '4px 6px',
                    cursor: 'move',
                    borderRadius: 6,
                    backgroundColor: selectedKey === col.key ? '#f0f5ff' : undefined,
                  }}
                >
                  <Space>
                    <Button
                      size="small"
                      disabled={!moveAvailability.get(col.key)?.up}
                      onClick={() => onMove(col.key, -1)}
                    >
                      ↑
                    </Button>
                    <Button
                      size="small"
                      disabled={!moveAvailability.get(col.key)?.down}
                      onClick={() => onMove(col.key, 1)}
                    >
                      ↓
                    </Button>
                    <Checkbox
                      id={`${idPrefix}-column-visible-${col.key}`}
                      checked={visibleColumns.includes(col.key)}
                      onChange={(event) => onToggleVisible(col.key, event.target.checked)}
                    >
                      {col.label}
                    </Checkbox>
                  </Space>
                  {col.sortable && (
                    <Text type="secondary">
                      {sortableColumns.includes(col.key) ? 'Sortable' : 'Not sortable'}
                    </Text>
                  )}
                </div>
              ))}
            </div>
          ))}
        </Space>
      </Col>
      <Col span={10}>
        <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, padding: 12 }}>
          <Text strong>Column settings</Text>
          <Divider style={{ margin: '8px 0 12px' }} />
          {!selectedColumn && (
            <Text type="secondary">Select a column to edit its settings.</Text>
          )}
          {selectedColumn && (
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">Name</Text>
                <div>{selectedColumn.label}</div>
              </div>
              <div>
                <Text type="secondary">Group</Text>
                <Select
                  id={`${idPrefix}-column-group-select`}
                  value={selectedGroupKey}
                  onChange={(value) => onChangeGroup(selectedColumn.key, value)}
                  options={groupOptions}
                  style={{ width: '100%' }}
                />
              </div>
              <Space>
                <Text type="secondary">Visible</Text>
                <Switch
                  id={`${idPrefix}-column-visible-toggle`}
                  checked={visibleColumns.includes(selectedColumn.key)}
                  onChange={(checked) => onToggleVisible(selectedColumn.key, checked)}
                />
              </Space>
              <div>
                <Text type="secondary">Sortable</Text>
                <div>
                  {selectedColumn.sortable
                    ? (sortableColumns.includes(selectedColumn.key) ? 'Allowed' : 'Not allowed')
                    : 'Not supported'}
                </div>
              </div>
              <Space>
                <Text type="secondary">Order</Text>
                <Button size="small" onClick={() => onMove(selectedColumn.key, -1)}>Up</Button>
                <Button size="small" onClick={() => onMove(selectedColumn.key, 1)}>Down</Button>
              </Space>
            </Space>
          )}
        </div>
      </Col>
    </Row>
  )
})

