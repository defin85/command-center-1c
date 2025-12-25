import { useCallback, useEffect, useMemo, useState } from 'react'
import type { TableFilters, TableFilterConfig, TableSortState } from '../types'

export interface TableColumnConfig {
  key: string
  label: string
  sortable?: boolean
  defaultVisible?: boolean
  groupKey?: string
  groupLabel?: string
}

export interface TableViewPreset {
  id: string
  name: string
  columnOrder: string[]
  columnGroups: Record<string, string>
  visibleColumns: string[]
  filterOrder: string[]
  filterVisibility: Record<string, boolean>
  defaultFilters: TableFilters
  sortableColumns: string[]
  defaultSort: TableSortState
}

export interface TablePreferences {
  activePresetId: string
  presets: TableViewPreset[]
}

const createId = () =>
  (globalThis.crypto && 'randomUUID' in globalThis.crypto)
    ? globalThis.crypto.randomUUID()
    : `preset-${Math.random().toString(36).slice(2)}`

const buildDefaultPreset = (
  columns: TableColumnConfig[],
  filters: TableFilterConfig[],
): TableViewPreset => {
  const columnOrder = columns.map((col) => col.key)
  const columnGroups: Record<string, string> = {}
  columns.forEach((col) => {
    columnGroups[col.key] = col.groupKey || 'general'
  })
  const visibleColumns = columns
    .filter((col) => col.defaultVisible !== false)
    .map((col) => col.key)
  const filterOrder = filters.map((filter) => filter.key)
  const filterVisibility: Record<string, boolean> = {}
  filters.forEach((filter) => {
    filterVisibility[filter.key] = true
  })
  const sortableColumns = columns
    .filter((col) => col.sortable)
    .map((col) => col.key)

  return {
    id: createId(),
    name: 'Default',
    columnOrder,
    columnGroups,
    visibleColumns,
    filterOrder,
    filterVisibility,
    defaultFilters: {},
    sortableColumns,
    defaultSort: { key: null, order: null },
  }
}

const normalizePreset = (
  preset: TableViewPreset,
  columns: TableColumnConfig[],
  filters: TableFilterConfig[],
): TableViewPreset => {
  const columnKeys = new Set(columns.map((col) => col.key))
  const filterKeys = new Set(filters.map((filter) => filter.key))

  const columnGroups = { ...(preset.columnGroups || {}) }
  columns.forEach((column) => {
    if (!(column.key in columnGroups)) {
      columnGroups[column.key] = column.groupKey || 'general'
    }
  })

  const columnOrder = (preset.columnOrder || []).filter((key) => columnKeys.has(key))
  columns.forEach((column) => {
    if (!columnOrder.includes(column.key)) {
      columnOrder.push(column.key)
    }
  })

  const visibleColumns = preset.visibleColumns.filter((key) => columnKeys.has(key))
  const sortableColumns = preset.sortableColumns.filter((key) => columnKeys.has(key))
  const filterOrder = preset.filterOrder.filter((key) => filterKeys.has(key))
  const filterVisibility = { ...preset.filterVisibility }
  filters.forEach((filter) => {
    if (!(filter.key in filterVisibility)) {
      filterVisibility[filter.key] = true
    }
    if (!filterOrder.includes(filter.key)) {
      filterOrder.push(filter.key)
    }
  })

  return {
    ...preset,
    columnOrder: columnOrder.length > 0 ? columnOrder : columns.map((col) => col.key),
    columnGroups,
    visibleColumns: visibleColumns.length > 0 ? visibleColumns : columns.map((col) => col.key),
    sortableColumns,
    filterOrder,
    filterVisibility,
    defaultFilters: preset.defaultFilters || {},
    defaultSort: preset.defaultSort || { key: null, order: null },
  }
}

export const useTablePreferences = (
  tableId: string,
  columns: TableColumnConfig[],
  filters: TableFilterConfig[],
) => {
  const storageKey = `cc1c.tablePreferences.${tableId}`
  const defaultPreset = useMemo(() => buildDefaultPreset(columns, filters), [columns, filters])
  const [preferences, setPreferences] = useState<TablePreferences>(() => ({
    activePresetId: defaultPreset.id,
    presets: [defaultPreset],
  }))

  useEffect(() => {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw) as TablePreferences
      if (!parsed?.presets?.length) return
      const normalizedPresets = parsed.presets.map((preset) =>
        normalizePreset(preset, columns, filters)
      )
      const activePresetId = normalizedPresets.some((p) => p.id === parsed.activePresetId)
        ? parsed.activePresetId
        : normalizedPresets[0].id
      setPreferences({
        activePresetId,
        presets: normalizedPresets,
      })
    } catch {
      // ignore
    }
  }, [columns, filters, storageKey])

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(preferences))
  }, [preferences, storageKey])

  const activePreset = useMemo(() => {
    return preferences.presets.find((preset) => preset.id === preferences.activePresetId)
      || preferences.presets[0]
  }, [preferences])

  const setActivePreset = useCallback((presetId: string) => {
    setPreferences((prev) => ({
      ...prev,
      activePresetId: presetId,
    }))
  }, [])

  const updatePreset = useCallback((updated: TableViewPreset) => {
    setPreferences((prev) => ({
      ...prev,
      presets: prev.presets.map((preset) =>
        preset.id === updated.id ? updated : preset
      ),
    }))
  }, [])

  const createPreset = useCallback((preset: TableViewPreset) => {
    const next = { ...preset, id: createId() }
    setPreferences((prev) => ({
      activePresetId: next.id,
      presets: [...prev.presets, next],
    }))
  }, [])

  const deletePreset = useCallback((presetId: string) => {
    setPreferences((prev) => {
      if (prev.presets.length <= 1) return prev
      const remaining = prev.presets.filter((preset) => preset.id !== presetId)
      const activePresetId = prev.activePresetId === presetId
        ? remaining[0].id
        : prev.activePresetId
      return {
        activePresetId,
        presets: remaining,
      }
    })
  }, [])

  const resetToDefault = useCallback(() => {
    setPreferences({
      activePresetId: defaultPreset.id,
      presets: [defaultPreset],
    })
  }, [defaultPreset])

  return {
    preferences,
    activePreset,
    setActivePreset,
    updatePreset,
    createPreset,
    deletePreset,
    resetToDefault,
  }
}
