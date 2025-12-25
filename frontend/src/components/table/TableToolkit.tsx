import { Button, Table } from 'antd'
import type { ColumnsType, TableProps } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { EyeInvisibleOutlined, EyeOutlined } from '@ant-design/icons'
import { TableFiltersRow } from './TableFiltersRow'
import { TablePagination } from './TablePagination'
import { TablePreferencesModal } from './TablePreferencesModal'
import { TableToolbar } from './TableToolbar'
import type { TableToolkitState } from './hooks/useTableToolkit'
import type { TableFilterConfig } from './types'

interface TableToolkitProps<T> {
  table: TableToolkitState<T>
  data: T[]
  total: number
  loading?: boolean
  columns: ColumnsType<T>
  rowKey: string | ((record: T) => string)
  rowSelection?: TableProps<T>['rowSelection']
  toolbarActions?: React.ReactNode
  searchPlaceholder?: string
  tableLayout?: 'auto' | 'fixed'
  scroll?: { x?: number | string; y?: number | string }
  onRow?: (record: T) => React.HTMLAttributes<HTMLElement>
  size?: 'small' | 'middle' | 'large'
}

const renderFilterTitle = (
  key: string,
  label: string,
  filterConfigByKey: Map<string, TableFilterConfig>,
  isVisible: boolean,
  disableHide: boolean,
  onToggle: (visible: boolean) => void
) => {
  if (!filterConfigByKey.has(key)) {
    return label
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span>{label}</span>
      <Button
        type="text"
        size="small"
        icon={isVisible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
        disabled={disableHide}
        onClick={(event) => {
          event.stopPropagation()
          onToggle(!isVisible)
        }}
      />
    </span>
  )
}

export const TableToolkit = <T,>({
  table,
  data,
  total,
  loading = false,
  columns,
  rowKey,
  rowSelection,
  toolbarActions,
  searchPlaceholder,
  tableLayout = 'fixed',
  scroll,
  onRow,
  size,
}: TableToolkitProps<T>) => {
  const [preferencesOpen, setPreferencesOpen] = useState(false)
  const filterConfigByKey = useMemo(
    () => new Map(table.filterConfigs.map((config) => [config.key, config])),
    [table.filterConfigs]
  )

  const decoratedColumns = useMemo<ColumnsType<T>>(() => {
    return columns.map((col) => {
      if (!col || typeof col !== 'object') {
        return col
      }
      const key = col.key ? String(col.key) : null
      if (!key) return col
      const config = table.columnConfigs.find((item) => item.key === key)
      const label = config?.label || (typeof col.title === 'string' ? col.title : key)
      const isVisible = table.filterVisibility[key] !== false
      const disableHide = !table.canHideFilter(key)
      const title = renderFilterTitle(
        key,
        label,
        filterConfigByKey,
        isVisible,
        disableHide,
        (visible) => table.toggleFilterVisibility(key, visible)
      )
      const sortable = table.sortableColumns.has(key)
      const sortOrder = table.sort.key === key
        ? (table.sort.order === 'asc' ? 'ascend' : 'descend')
        : undefined
      return {
        ...col,
        title,
        sorter: sortable ? (col.sorter ?? true) : col.sorter,
        sortOrder,
      }
    })
  }, [
    columns,
    filterConfigByKey,
    table.canHideFilter,
    table.columnConfigs,
    table.filterVisibility,
    table.sort.key,
    table.sort.order,
    table.sortableColumns,
    table.toggleFilterVisibility,
  ])

  const tableColumns = useMemo<ColumnsType<T>>(() => {
    if (table.groupedColumns.length === 0) {
      return decoratedColumns
    }
    return table.groupedColumns.map((group) => {
      if (!group || typeof group !== 'object' || !('children' in group)) {
        return group
      }
      const children = (group.children || []).map((col: ColumnsType<T>[number]) => {
        if (!col || typeof col !== 'object') return col
        const key = col.key ? String(col.key) : null
        if (!key) return col
        const match = decoratedColumns.find((item) => {
          if (!item || typeof item !== 'object') return false
          return String(item.key) === key
        })
        return match || col
      })
      return {
        ...group,
        children,
      }
    })
  }, [decoratedColumns, table.groupedColumns])

  return (
    <div>
      <TableToolbar
        searchValue={table.search}
        searchPlaceholder={searchPlaceholder}
        onSearchChange={table.setSearch}
        onReset={table.resetToDefaults}
        actions={
          <>
            {toolbarActions}
            <Button onClick={() => setPreferencesOpen(true)}>Table settings</Button>
          </>
        }
      />

      <TableFiltersRow
        columns={table.filterColumns}
        configs={table.orderedFilters}
        values={table.filters}
        visibility={table.filterVisibility}
        onChange={table.setFilter}
      />

      <Table
        rowSelection={rowSelection}
        columns={tableColumns}
        dataSource={data}
        loading={loading}
        rowKey={rowKey}
        pagination={false}
        tableLayout={tableLayout}
        scroll={scroll}
        size={size}
        onRow={onRow}
        onChange={(_, __, sorter) => {
          if (Array.isArray(sorter)) {
            table.setSort(null, null)
            return
          }
          const key = sorter?.field ? String(sorter.field) : null
          if (key && !table.sortableColumns.has(key)) {
            table.setSort(null, null)
            return
          }
          const order = sorter?.order === 'ascend'
            ? 'asc'
            : sorter?.order === 'descend'
              ? 'desc'
              : null
          table.setSort(key, order)
        }}
      />

      <TablePagination
        total={total}
        page={table.pagination.page}
        pageSize={table.pagination.pageSize}
        onChange={(page, pageSize) => {
          if (pageSize !== table.pagination.pageSize) {
            table.setPageSize(pageSize)
            return
          }
          table.setPage(page)
        }}
      />

      <TablePreferencesModal
        open={preferencesOpen}
        onClose={() => setPreferencesOpen(false)}
        columns={table.columnConfigs}
        filters={table.filterConfigs}
        presets={table.presets}
        activePresetId={table.preferencesId}
        onSelectPreset={table.setActivePreset}
        onUpdatePreset={table.updatePreset}
        onCreatePreset={table.createPreset}
        onDeletePreset={table.deletePreset}
        canToggleFilter={(key) => table.canHideFilter(key)}
        onToggleFilter={(key, visible) => table.toggleFilterVisibility(key, visible)}
      />
    </div>
  )
}
