import { Button, Checkbox, Col, Divider, Input, Modal, Row, Select, Space, Switch, Tabs, Tag, Typography } from 'antd'
import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import type { TableFilterConfig, TableFilters } from './types'
import type { TableColumnConfig, TableViewPreset } from './hooks/useTablePreferences'

const { Text } = Typography

interface TablePreferencesModalProps {
  open: boolean
  onClose: () => void
  columns: TableColumnConfig[]
  filters: TableFilterConfig[]
  presets: TableViewPreset[]
  activePresetId: string
  onSelectPreset: (presetId: string) => void
  onUpdatePreset: (preset: TableViewPreset) => void
  onCreatePreset: (preset: TableViewPreset) => void
  onDeletePreset: (presetId: string) => void
}

interface ColumnsTabProps {
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
}

const ColumnsTab = memo(({
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
                  value={selectedGroupKey}
                  onChange={(value) => onChangeGroup(selectedColumn.key, value)}
                  options={groupOptions}
                  style={{ width: '100%' }}
                />
              </div>
              <Space>
                <Text type="secondary">Visible</Text>
                <Switch
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

interface FiltersTabProps {
  filterOrder: string[]
  filterVisibility: Record<string, boolean>
  filters: TableFilterConfig[]
  search: string
  onSearchChange: (value: string) => void
  onReorder: (fromKey: string, toKey: string) => void
  onMove: (key: string, direction: -1 | 1) => void
  onToggleVisible: (key: string, checked: boolean) => void
}

const FiltersTab = memo(({
  filterOrder,
  filterVisibility,
  filters,
  search,
  onSearchChange,
  onReorder,
  onMove,
  onToggleVisible,
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
                checked={filterVisibility[key] !== false}
                onChange={(checked) => onToggleVisible(key, checked)}
              />
            </Space>
          </div>
        )
      })}
    </Space>
  )
})

interface DefaultsTabProps {
  filters: TableFilterConfig[]
  values: TableFilters
  onChange: (key: string, value: TableFilters[string]) => void
}

const DefaultsTab = memo(({
  filters,
  values,
  onChange,
}: DefaultsTabProps) => (
  <Space direction="vertical" style={{ width: '100%' }}>
    {filters.map((filter) => {
      if (filter.type === 'select') {
        return (
          <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{filter.label}</Text>
            <Select
              allowClear
              placeholder="Any"
              value={(values[filter.key] as string | null) ?? undefined}
              onChange={(value) => onChange(filter.key, value ?? null)}
              options={filter.options || []}
              style={{ width: 180 }}
            />
          </Space>
        )
      }
      if (filter.type === 'boolean') {
        return (
          <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{filter.label}</Text>
            <Select
              allowClear
              placeholder="Any"
              value={
                typeof values[filter.key] === 'boolean'
                  ? String(values[filter.key])
                  : undefined
              }
              onChange={(value) => {
                if (value === undefined) {
                  onChange(filter.key, null)
                  return
                }
                onChange(filter.key, value === 'true')
              }}
              options={[
                { value: 'true', label: 'Yes' },
                { value: 'false', label: 'No' },
              ]}
              style={{ width: 180 }}
            />
          </Space>
        )
      }
      return (
        <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
          <Text>{filter.label}</Text>
          <Input
            value={(values[filter.key] as string | null) ?? ''}
            onChange={(event) => onChange(filter.key, event.target.value || null)}
            style={{ width: 220 }}
          />
        </Space>
      )
    })}
  </Space>
))

interface SortingTabProps {
  columns: TableColumnConfig[]
  sortableColumns: string[]
  onToggle: (key: string, checked: boolean) => void
}

const SortingTab = memo(({
  columns,
  sortableColumns,
  onToggle,
}: SortingTabProps) => (
  <Space direction="vertical" style={{ width: '100%' }}>
    <Text type="secondary">Allowed sortable columns</Text>
    <Space wrap>
      {columns
        .filter((col) => col.sortable)
        .map((col) => (
          <Space key={col.key}>
            <Switch
              checked={sortableColumns.includes(col.key)}
              onChange={(checked) => onToggle(col.key, checked)}
            />
            <Text>{col.label}</Text>
          </Space>
        ))}
    </Space>
  </Space>
))

export const TablePreferencesModal = ({
  open,
  onClose,
  columns,
  filters,
  presets,
  activePresetId,
  onSelectPreset,
  onUpdatePreset,
  onCreatePreset,
  onDeletePreset,
}: TablePreferencesModalProps) => {
  const activePreset = presets.find((preset) => preset.id === activePresetId) || presets[0]
  const [draft, setDraft] = useState<TableViewPreset>(activePreset)
  const [newPresetName, setNewPresetName] = useState('New view')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [columnSearch, setColumnSearch] = useState('')
  const [filterSearch, setFilterSearch] = useState('')
  const [selectedColumnKey, setSelectedColumnKey] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setDraft(activePreset)
    setSelectedColumnKey((prev) => prev ?? activePreset.columnOrder[0] ?? null)
  }, [activePreset, open])

  const updateDefaultFilter = (key: string, value: TableFilters[string]) => {
    setDraft((prev) => ({
      ...prev,
      defaultFilters: {
        ...prev.defaultFilters,
        [key]: value,
      },
    }))
  }

  const columnsByKey = useMemo(() => {
    const map = new Map<string, TableColumnConfig>()
    columns.forEach((col) => {
      map.set(col.key, col)
    })
    return map
  }, [columns])

  const groupLabelByKey = useMemo(() => {
    const map = new Map<string, string>()
    columns.forEach((col) => {
      const key = col.groupKey || 'general'
      const label = col.groupLabel || col.groupKey || 'General'
      if (!map.has(key)) {
        map.set(key, label)
      }
    })
    Object.values(draft.columnGroups || {}).forEach((key) => {
      if (!map.has(key)) {
        map.set(key, key)
      }
    })
    return map
  }, [columns, draft.columnGroups])

  const groupKeyByColumn = useMemo(() => {
    const map = new Map<string, string>()
    columns.forEach((col) => {
      map.set(col.key, draft.columnGroups?.[col.key] || col.groupKey || 'general')
    })
    return map
  }, [columns, draft.columnGroups])

  const orderedColumns = useMemo(() => {
    return draft.columnOrder
      .map((key) => columnsByKey.get(key))
      .filter(Boolean) as TableColumnConfig[]
  }, [columnsByKey, draft.columnOrder])

  const groupOptions = useMemo(() => {
    return Array.from(groupLabelByKey.entries()).map(([value, label]) => ({
      value,
      label,
    }))
  }, [groupLabelByKey])

  useEffect(() => {
    if (!selectedColumnKey) return
    if (columnsByKey.has(selectedColumnKey)) return
    setSelectedColumnKey(draft.columnOrder[0] ?? null)
  }, [columnsByKey, draft.columnOrder, selectedColumnKey])

  const previewVisibleColumns = useMemo(() => {
    if (!previewOpen) return []
    return orderedColumns.filter((col) => draft.visibleColumns.includes(col.key))
  }, [draft.visibleColumns, orderedColumns, previewOpen])

  const previewFilters = useMemo(() => {
    if (!previewOpen) return []
    return draft.filterOrder
      .filter((key) => draft.filterVisibility[key] !== false)
      .map((key) => filters.find((filter) => filter.key === key))
      .filter(Boolean) as TableFilterConfig[]
  }, [draft.filterOrder, draft.filterVisibility, filters, previewOpen])

  const handleToggleColumn = useCallback((key: string, checked: boolean) => {
    setDraft((prev) => ({
      ...prev,
      visibleColumns: checked
        ? [...prev.visibleColumns, key]
        : prev.visibleColumns.filter((col) => col !== key),
    }))
  }, [])

  const handleReorderColumn = useCallback((fromKey: string, toKey: string) => {
    setDraft((prev) => {
      const order = [...prev.columnOrder]
      const fromIndex = order.indexOf(fromKey)
      const toIndex = order.indexOf(toKey)
      if (fromIndex === -1 || toIndex === -1) return prev
      order.splice(fromIndex, 1)
      order.splice(toIndex, 0, fromKey)
      return { ...prev, columnOrder: order }
    })
  }, [])

  const handleChangeColumnGroup = useCallback((key: string, groupKey: string) => {
    setDraft((prev) => {
      const nextGroups = { ...prev.columnGroups, [key]: groupKey }
      const order = [...prev.columnOrder]
      const index = order.indexOf(key)
      if (index === -1) {
        return { ...prev, columnGroups: nextGroups }
      }
      order.splice(index, 1)
      let insertIndex = order.length
      for (let i = 0; i < order.length; i += 1) {
        const candidate = order[i]
        const candidateGroup = nextGroups[candidate] || columnsByKey.get(candidate)?.groupKey || 'general'
        if (candidateGroup === groupKey) {
          insertIndex = i + 1
        }
      }
      order.splice(insertIndex, 0, key)
      return { ...prev, columnGroups: nextGroups, columnOrder: order }
    })
  }, [columnsByKey])

  const handleMoveColumn = useCallback((key: string, direction: -1 | 1) => {
    setDraft((prev) => {
      const order = [...prev.columnOrder]
      const index = order.indexOf(key)
      if (index === -1) return prev
      const groupKey = prev.columnGroups[key] || columnsByKey.get(key)?.groupKey || 'general'
      let targetIndex = index
      let cursor = index + direction
      while (cursor >= 0 && cursor < order.length) {
        const candidate = order[cursor]
        const candidateGroup = prev.columnGroups[candidate] || columnsByKey.get(candidate)?.groupKey || 'general'
        if (candidateGroup === groupKey) {
          targetIndex = cursor
          break
        }
        cursor += direction
      }
      if (targetIndex === index) return prev
      order.splice(index, 1)
      order.splice(targetIndex, 0, key)
      return { ...prev, columnOrder: order }
    })
  }, [columnsByKey])

  const handleReorderFilter = useCallback((fromKey: string, toKey: string) => {
    setDraft((prev) => ({
      ...prev,
      filterOrder: (() => {
        const order = [...prev.filterOrder]
        const fromIndex = order.indexOf(fromKey)
        const toIndex = order.indexOf(toKey)
        if (fromIndex === -1 || toIndex === -1) return order
        order.splice(fromIndex, 1)
        order.splice(toIndex, 0, fromKey)
        return order
      })(),
    }))
  }, [])

  const handleMoveFilter = useCallback((key: string, direction: -1 | 1) => {
    setDraft((prev) => {
      const order = [...prev.filterOrder]
      const index = order.indexOf(key)
      const targetIndex = index + direction
      if (index === -1 || targetIndex < 0 || targetIndex >= order.length) {
        return prev
      }
      order.splice(index, 1)
      order.splice(targetIndex, 0, key)
      return { ...prev, filterOrder: order }
    })
  }, [])

  const handleToggleFilter = useCallback((key: string, checked: boolean) => {
    setDraft((prev) => ({
      ...prev,
      filterVisibility: {
        ...prev.filterVisibility,
        [key]: checked,
      },
    }))
  }, [])

  const handleToggleSortable = useCallback((key: string, checked: boolean) => {
    setDraft((prev) => ({
      ...prev,
      sortableColumns: checked
        ? [...prev.sortableColumns, key]
        : prev.sortableColumns.filter((item) => item !== key),
    }))
  }, [])

  const handleShowAllColumns = useCallback(() => {
    const visible = columns.map((col) => col.key)
    setDraft((prev) => ({ ...prev, visibleColumns: visible }))
  }, [columns])

  const handleHideAllColumns = useCallback(() => {
    setDraft((prev) => ({ ...prev, visibleColumns: [] }))
  }, [])

  const tabs = useMemo(() => ([
    {
      key: 'columns',
      label: 'Columns',
      children: (
        <ColumnsTab
          columns={orderedColumns}
          visibleColumns={draft.visibleColumns}
          sortableColumns={draft.sortableColumns}
          search={columnSearch}
          selectedKey={selectedColumnKey}
          groupLabelByKey={groupLabelByKey}
          groupOptions={groupOptions}
          onSearchChange={setColumnSearch}
          onShowAll={handleShowAllColumns}
          onHideAll={handleHideAllColumns}
          onSelect={setSelectedColumnKey}
          onMove={handleMoveColumn}
          onChangeGroup={handleChangeColumnGroup}
          onToggleVisible={handleToggleColumn}
          onReorder={handleReorderColumn}
          groupKeyByColumn={groupKeyByColumn}
        />
      ),
    },
    {
      key: 'filters',
      label: 'Filters',
      children: (
        <FiltersTab
          filterOrder={draft.filterOrder}
          filterVisibility={draft.filterVisibility}
          filters={filters}
          search={filterSearch}
          onSearchChange={setFilterSearch}
          onReorder={handleReorderFilter}
          onMove={handleMoveFilter}
          onToggleVisible={handleToggleFilter}
        />
      ),
    },
    {
      key: 'defaults',
      label: 'Defaults',
      children: (
        <DefaultsTab
          filters={filters}
          values={draft.defaultFilters}
          onChange={updateDefaultFilter}
        />
      ),
    },
    {
      key: 'sorting',
      label: 'Sorting',
      children: (
        <SortingTab
          columns={columns}
          sortableColumns={draft.sortableColumns}
          onToggle={handleToggleSortable}
        />
      ),
    },
  ]), [
    columns,
    columnSearch,
    columnsByKey,
    filterSearch,
    draft.defaultFilters,
    draft.filterOrder,
    draft.filterVisibility,
    draft.sortableColumns,
    draft.visibleColumns,
    draft.columnOrder,
    draft.columnGroups,
    filters,
    groupKeyByColumn,
    groupLabelByKey,
    groupOptions,
    handleChangeColumnGroup,
    handleMoveColumn,
    handleReorderFilter,
    handleMoveFilter,
    handleToggleColumn,
    handleToggleFilter,
    handleToggleSortable,
    handleShowAllColumns,
    handleHideAllColumns,
    updateDefaultFilter,
    orderedColumns,
    selectedColumnKey,
  ])

  return (
    <Modal
      title="Table Settings"
      open={open}
      onCancel={onClose}
      width={760}
      footer={[
        <Button key="close" onClick={onClose}>Close</Button>,
        <Button
          key="delete"
          danger
          disabled={presets.length <= 1}
          onClick={() => onDeletePreset(activePresetId)}
        >
          Delete view
        </Button>,
        <Button
          key="create"
          onClick={() => {
            onCreatePreset({
              ...draft,
              name: newPresetName || 'New view',
            })
            setNewPresetName('New view')
          }}
        >
          Save as new
        </Button>,
        <Button
          key="save"
          type="primary"
          onClick={() => onUpdatePreset(draft)}
        >
          Save
        </Button>,
      ]}
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space wrap>
          <Text strong>View:</Text>
          <Select
            value={activePresetId}
            onChange={onSelectPreset}
            options={presets.map((preset) => ({
              value: preset.id,
              label: preset.name,
            }))}
            style={{ minWidth: 220 }}
          />
          <Input
            value={draft.name}
            onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="View name"
            style={{ width: 220 }}
          />
        </Space>

        <Space wrap>
          <Text strong>New view name:</Text>
          <Input
            value={newPresetName}
            onChange={(event) => setNewPresetName(event.target.value)}
            style={{ width: 220 }}
          />
        </Space>

        <Divider style={{ margin: '8px 0' }} />

        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <Text strong>Preview</Text>
            <Button size="small" onClick={() => setPreviewOpen((prev) => !prev)}>
              {previewOpen ? 'Hide' : 'Show'}
            </Button>
          </Space>
          {previewOpen && (
            <>
              <Space wrap>
                <Text type="secondary">Columns:</Text>
                {previewVisibleColumns.length === 0 && <Text type="secondary">none</Text>}
                {previewVisibleColumns.map((col) => (
                  <Tag key={col.key}>{col.label}</Tag>
                ))}
              </Space>
              <Space wrap>
                <Text type="secondary">Filters:</Text>
                {previewFilters.length === 0 && <Text type="secondary">none</Text>}
                {previewFilters.map((filter) => (
                  <Tag key={filter.key}>{filter.label}</Tag>
                ))}
              </Space>
              {draft.defaultSort.key && (
                <Text type="secondary">
                  Default sort: {draft.defaultSort.key} ({draft.defaultSort.order})
                </Text>
              )}
            </>
          )}
        </Space>

        <Tabs destroyInactiveTabPane defaultActiveKey="columns" items={tabs} />
      </Space>
    </Modal>
  )
}
