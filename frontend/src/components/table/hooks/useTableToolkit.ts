import { useCallback, useEffect, useMemo, useRef } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { useTableMetadata } from '../../../api/queries'
import type { TableFilterConfig, TableFilterValue, TableFilters, TableSortOrder } from '../types'
import { useTableState } from './useTableState'
import { useTablePreferences, type TableColumnConfig } from './useTablePreferences'

export interface TableToolkitState<T> {
  search: string
  setSearch: (value: string) => void
  filters: TableFilters
  setFilter: (key: keyof TableFilters, value: TableFilterValue) => void
  setFilters: (next: TableFilters) => void
  resetFilters: () => void
  sort: { key: string | null; order: TableSortOrder | null }
  setSort: (key: string | null, order: TableSortOrder | null) => void
  pagination: { page: number; pageSize: number }
  setPage: (page: number) => void
  setPageSize: (pageSize: number) => void
  columnConfigs: TableColumnConfig[]
  filterConfigs: TableFilterConfig[]
  orderedFilters: TableFilterConfig[]
  filterVisibility: Record<string, boolean>
  activePreset: ReturnType<typeof useTablePreferences>['activePreset']
  presets: ReturnType<typeof useTablePreferences>['preferences']['presets']
  preferencesId: string
  setActivePreset: (presetId: string) => void
  updatePreset: ReturnType<typeof useTablePreferences>['updatePreset']
  createPreset: ReturnType<typeof useTablePreferences>['createPreset']
  deletePreset: ReturnType<typeof useTablePreferences>['deletePreset']
  visibleColumns: Set<string>
  sortableColumns: Set<string>
  groupedColumns: ColumnsType<T>
  filterColumns: Array<{ key: string; width?: number }>
  totalColumnsWidth: number
  filtersPayload: Record<string, { op: string; value: TableFilterValue }> | undefined
  sortPayload: { key: string; order: TableSortOrder } | undefined
  resetToDefaults: () => void
  canHideFilter: (key: string) => boolean
  toggleFilterVisibility: (key: string, visible: boolean) => void
}

export interface UseTableToolkitOptions<T> {
  tableId: string
  columns: ColumnsType<T>
  fallbackColumns: TableColumnConfig[]
  initialPageSize?: number
  disableServerMetadata?: boolean
}

const defaultFilterConfigs = (columns: TableColumnConfig[]): TableFilterConfig[] =>
  columns
    .filter((col) => col.key !== 'actions')
    .map((col) => ({
      key: col.key,
      label: col.label,
      type: 'text',
      placeholder: col.label,
    }))

const isFilterValueEqual = (left: TableFilterValue, right: TableFilterValue) => {
  if (left === right) return true
  if (Array.isArray(left) && Array.isArray(right)) {
    if (left.length !== right.length) return false
    return left.every((value, index) => value === right[index])
  }
  return false
}

const areFiltersEqual = (left: TableFilters, right: TableFilters) => {
  const leftKeys = Object.keys(left)
  const rightKeys = Object.keys(right)
  if (leftKeys.length !== rightKeys.length) return false
  return leftKeys.every((key) => isFilterValueEqual(left[key], right[key]))
}

export const useTableToolkit = <T,>({
  tableId,
  columns,
  fallbackColumns,
  initialPageSize = 50,
  disableServerMetadata = false,
}: UseTableToolkitOptions<T>): TableToolkitState<T> => {
  const metadataTableId = disableServerMetadata ? '' : tableId
  const { data: tableMetadata } = useTableMetadata(metadataTableId)
  type MetadataColumn = NonNullable<typeof tableMetadata>['columns'][number]
  const emptyMetadataColumns = useMemo<MetadataColumn[]>(() => [], [])
  const metadataColumns = tableMetadata?.columns ?? emptyMetadataColumns

  const columnConfigs = useMemo<TableColumnConfig[]>(() => {
    if (metadataColumns.length === 0) {
      return fallbackColumns
    }
    return metadataColumns.map((col) => ({
      key: col.key,
      label: col.label,
      sortable: col.sortable ?? false,
      groupKey: col.group_key ?? undefined,
      groupLabel: col.group_label ?? undefined,
    }))
  }, [fallbackColumns, metadataColumns])

  const filterConfigs = useMemo<TableFilterConfig[]>(() => {
    if (metadataColumns.length === 0) {
      return defaultFilterConfigs(columnConfigs)
    }
    return metadataColumns
      .filter((col) => col.filter)
      .map((col) => ({
        key: col.key,
        label: col.label,
        type: (col.filter?.type as TableFilterConfig['type']) || 'text',
        options: col.filter?.options,
        placeholder: col.filter?.placeholder ?? col.label,
      }))
  }, [columnConfigs, metadataColumns])

  const filterOperatorsByKey = useMemo<Record<string, string>>(() => {
    if (metadataColumns.length === 0) {
      return {}
    }
    const map: Record<string, string> = {}
    metadataColumns.forEach((col) => {
      if (!col.filter) return
      if (col.filter.operators?.includes('contains')) {
        map[col.key] = 'contains'
        return
      }
      map[col.key] = col.filter.operators?.[0] || 'eq'
    })
    return map
  }, [metadataColumns])

  const serverFieldByKey = useMemo(() => {
    const map = new Map<string, string>()
    metadataColumns.forEach((col) => {
      if (col.server_field) {
        map.set(col.key, col.server_field)
      }
    })
    return map
  }, [metadataColumns])

  const defaultFilterState = useMemo<TableFilters>(() => {
    const state: Record<string, TableFilterValue> = {}
    filterConfigs.forEach((config) => {
      state[config.key] = null
    })
    return state
  }, [filterConfigs])

  const {
    search,
    setSearch,
    filters,
    setFilter,
    setFilters,
    resetFilters,
    sort,
    setSort,
    pagination,
    setPage,
    setPageSize,
  } = useTableState<TableFilters>({
    initialFilters: defaultFilterState,
    initialPageSize,
  })
  const filtersRef = useRef(filters)
  const sortRef = useRef(sort)
  const pageRef = useRef(pagination.page)

  useEffect(() => {
    filtersRef.current = filters
    sortRef.current = sort
    pageRef.current = pagination.page
  }, [filters, pagination.page, sort])

  const {
    preferences,
    activePreset,
    setActivePreset,
    updatePreset,
    createPreset,
    deletePreset,
  } = useTablePreferences(tableId, columnConfigs, filterConfigs)

  const visibleColumns = useMemo(() => new Set(activePreset.visibleColumns), [activePreset.visibleColumns])
  const sortableColumns = useMemo(() => new Set(activePreset.sortableColumns), [activePreset.sortableColumns])

  const orderedFilters = useMemo(() => {
    const configs = filterConfigs.filter((filter) => activePreset.filterVisibility[filter.key] !== false)
    const order = activePreset.filterOrder
    return configs.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
  }, [activePreset.filterOrder, activePreset.filterVisibility, filterConfigs])

  useEffect(() => {
    const defaults = activePreset.defaultFilters || {}
    const nextFilters: TableFilters = { ...defaultFilterState }
    Object.entries(defaults).forEach(([key, value]) => {
      if (key in nextFilters) {
        nextFilters[key] = value
      }
    })
    if (!areFiltersEqual(filtersRef.current, nextFilters)) {
      setFilters(nextFilters)
    }
    const nextSortKey = activePreset.defaultSort?.key ?? null
    const nextSortOrder = activePreset.defaultSort?.order ?? null
    if (sortRef.current.key !== nextSortKey || sortRef.current.order !== nextSortOrder) {
      setSort(nextSortKey, nextSortOrder)
    }
    if (pageRef.current !== 1) {
      setPage(1)
    }
  }, [
    activePreset.defaultFilters,
    activePreset.defaultSort,
    defaultFilterState,
    setFilters,
    setPage,
    setSort,
  ])

  const hasFilterValue = useCallback((value: TableFilterValue) => {
    if (value === null || value === undefined) return false
    if (typeof value === 'string') return value.trim().length > 0
    if (Array.isArray(value)) return value.length > 0
    return true
  }, [])

  const canHideFilter = useCallback(
    (key: string) => {
      const isVisible = activePreset.filterVisibility[key] !== false
      return !(isVisible && hasFilterValue(filters[key]))
    },
    [activePreset.filterVisibility, filters, hasFilterValue]
  )

  const toggleFilterVisibility = useCallback(
    (key: string, visible: boolean) => {
      if (!visible && hasFilterValue(filters[key])) {
        return
      }
      updatePreset({
        ...activePreset,
        filterVisibility: {
          ...activePreset.filterVisibility,
          [key]: visible,
        },
      })
    },
    [activePreset, filters, hasFilterValue, updatePreset]
  )

  const columnsByKey = useMemo(() => {
    const map = new Map<string, ColumnsType<T>[number]>()
    columns.forEach((col) => {
      if (col && typeof col === 'object' && 'key' in col) {
        map.set(String(col.key), col)
      }
    })
    return map
  }, [columns])

  const groupedColumns = useMemo(() => {
    const groups: Array<{ key: string; title: string; children: ColumnsType<T>[number][] }> = []
    const seen = new Map<string, number>()

    activePreset.columnOrder.forEach((key) => {
      if (!visibleColumns.has(key)) return
      const column = columnsByKey.get(key)
      if (!column) return
      const config = columnConfigs.find((item) => item.key === key)
      const groupKey = config?.groupKey || 'general'
      const groupLabel = config?.groupLabel || config?.groupKey || 'General'
      if (!seen.has(groupKey)) {
        seen.set(groupKey, groups.length)
        groups.push({ key: groupKey, title: groupLabel, children: [column] })
        return
      }
      const index = seen.get(groupKey) as number
      groups[index].children.push(column)
    })

    return groups.map((group) => ({
      title: group.title,
      key: group.key,
      children: group.children,
    }))
  }, [activePreset.columnOrder, columnConfigs, columnsByKey, visibleColumns])

  const filterColumns = useMemo(() => {
    return activePreset.columnOrder
      .filter((key) => visibleColumns.has(key))
      .map((key) => ({ key, width: (columnsByKey.get(key) as { width?: number } | undefined)?.width }))
  }, [activePreset.columnOrder, columnsByKey, visibleColumns])

  const totalColumnsWidth = useMemo(() => {
    return filterColumns.reduce((sum, col) => sum + (col.width ?? 160), 0)
  }, [filterColumns])

  const filtersPayload = useMemo(() => {
    const payload: Record<string, { op: string; value: TableFilterValue }> = {}
    filterConfigs.forEach((config) => {
      const value = filters[config.key]
      if (value === null || value === undefined || value === '') {
        return
      }
      const operator = filterOperatorsByKey[config.key]
        || (config.type === 'text' ? 'contains' : 'eq')
      const serverField = serverFieldByKey.get(config.key) || config.key
      payload[serverField] = {
        op: operator,
        value,
      }
    })
    return Object.keys(payload).length > 0 ? payload : undefined
  }, [filterConfigs, filterOperatorsByKey, filters, serverFieldByKey])

  const sortPayload = useMemo(() => {
    if (!sort.key || !sort.order) return undefined
    return { key: sort.key, order: sort.order }
  }, [sort.key, sort.order])

  const resetToDefaults = useCallback(() => {
    setSearch('')
    const defaults = activePreset.defaultFilters || {}
    const nextFilters: TableFilters = { ...defaultFilterState }
    Object.entries(defaults).forEach(([key, value]) => {
      if (key in nextFilters) {
        nextFilters[key] = value
      }
    })
    setFilters(nextFilters)
    if (activePreset.defaultSort?.key && activePreset.defaultSort.order) {
      setSort(activePreset.defaultSort.key, activePreset.defaultSort.order)
    } else {
      setSort(null, null)
    }
  }, [activePreset.defaultFilters, activePreset.defaultSort, defaultFilterState, setFilters, setSearch, setSort])

  return {
    search,
    setSearch,
    filters,
    setFilter,
    setFilters,
    resetFilters,
    sort,
    setSort,
    pagination,
    setPage,
    setPageSize,
    columnConfigs,
    filterConfigs,
    orderedFilters,
    filterVisibility: activePreset.filterVisibility,
    activePreset,
    presets: preferences.presets,
    preferencesId: preferences.activePresetId,
    setActivePreset,
    updatePreset,
    createPreset,
    deletePreset,
    visibleColumns,
    sortableColumns,
    groupedColumns,
    filterColumns,
    totalColumnsWidth,
    filtersPayload,
    sortPayload,
    resetToDefaults,
    canHideFilter,
    toggleFilterVisibility,
  }
}
