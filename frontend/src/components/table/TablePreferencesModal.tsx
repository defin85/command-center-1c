import { Button, Divider, Input, Modal, Select, Space, Tabs, Tag, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { TableFilterConfig, TableFilters } from './types'
import type { TableColumnConfig, TableViewPreset } from './hooks/useTablePreferences'

import { ColumnsTab } from './tablePreferencesModal/ColumnsTab'
import { DefaultsTab } from './tablePreferencesModal/DefaultsTab'
import { FiltersTab } from './tablePreferencesModal/FiltersTab'
import { SortingTab } from './tablePreferencesModal/SortingTab'

const { Text } = Typography

export interface TablePreferencesModalProps {
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
  canToggleFilter?: (key: string) => boolean
  onToggleFilter?: (key: string, visible: boolean) => void
  idPrefix?: string
}

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
  canToggleFilter,
  onToggleFilter,
  idPrefix,
}: TablePreferencesModalProps) => {
  const baseId = idPrefix || 'table-preferences'
  const activePreset = presets.find((preset) => preset.id === activePresetId) || presets[0]
  const [draft, setDraft] = useState<TableViewPreset>(activePreset)
  const [newPresetName, setNewPresetName] = useState('New view')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [columnSearch, setColumnSearch] = useState('')
  const [filterSearch, setFilterSearch] = useState('')
  const [selectedColumnKey, setSelectedColumnKey] = useState<string | null>(null)
  const lastPresetIdRef = useRef<string | null>(null)
  const lastOpenRef = useRef(false)

  useEffect(() => {
    if (!open) {
      lastOpenRef.current = false
      return
    }
    const presetId = activePreset?.id ?? null
    const shouldReset = !lastOpenRef.current || lastPresetIdRef.current !== presetId
    if (!shouldReset) return
    lastOpenRef.current = true
    lastPresetIdRef.current = presetId
    setDraft(activePreset)
    setSelectedColumnKey((prev) => prev ?? activePreset.columnOrder[0] ?? null)
  }, [activePreset, open])

  const updateDefaultFilter = useCallback((key: string, value: TableFilters[string]) => {
    setDraft((prev) => ({
      ...prev,
      defaultFilters: {
        ...prev.defaultFilters,
        [key]: value,
      },
    }))
  }, [])

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
    if (canToggleFilter && !canToggleFilter(key)) {
      return
    }
    if (onToggleFilter) {
      onToggleFilter(key, checked)
      return
    }
    setDraft((prev) => ({
      ...prev,
      filterVisibility: {
        ...prev.filterVisibility,
        [key]: checked,
      },
    }))
  }, [canToggleFilter, onToggleFilter])

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
          idPrefix={baseId}
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
          canToggleVisible={canToggleFilter}
          idPrefix={baseId}
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
          idPrefix={baseId}
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
          idPrefix={baseId}
        />
      ),
    },
  ]), [
    columns,
    columnSearch,
    filterSearch,
    draft.defaultFilters,
    draft.filterOrder,
    draft.filterVisibility,
    draft.sortableColumns,
    draft.visibleColumns,
    filters,
    groupKeyByColumn,
    groupLabelByKey,
    groupOptions,
    handleChangeColumnGroup,
    handleMoveColumn,
    handleReorderColumn,
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
    baseId,
    canToggleFilter,
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
            id={`${baseId}-view-select`}
            value={activePresetId}
            onChange={onSelectPreset}
            options={presets.map((preset) => ({
              value: preset.id,
              label: preset.name,
            }))}
            style={{ minWidth: 220 }}
          />
          <Input
            id={`${baseId}-view-name`}
            value={draft.name}
            onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="View name"
            style={{ width: 220 }}
          />
        </Space>

        <Space wrap>
          <Text strong>New view name:</Text>
          <Input
            id={`${baseId}-new-view-name`}
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

        <Tabs destroyOnHidden defaultActiveKey="columns" items={tabs} />
      </Space>
    </Modal>
  )
}
