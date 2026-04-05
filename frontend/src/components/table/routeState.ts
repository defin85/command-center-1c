import type { TableFilterConfig, TableFilters, TableFilterValue, TableSortState } from './types'

const isRecord = (value: unknown): value is Record<string, unknown> => (
  value !== null && typeof value === 'object' && !Array.isArray(value)
)

const isTableFilterValue = (value: unknown): value is Exclude<TableFilterValue, null> => {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return true
  }

  if (!Array.isArray(value)) {
    return false
  }

  return value.every((item) => typeof item === 'string')
}

const hasFilterValue = (value: TableFilterValue): boolean => {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  return true
}

export const buildDefaultRouteTableFilters = (filterConfigs: TableFilterConfig[]): TableFilters => (
  Object.fromEntries(filterConfigs.map((config) => [config.key, null]))
)

export const parseRouteTableFilters = (
  rawValue: string | null,
  filterConfigs: TableFilterConfig[],
): TableFilters => {
  const next = buildDefaultRouteTableFilters(filterConfigs)
  if (!rawValue) {
    return next
  }

  try {
    const parsed = JSON.parse(rawValue)
    if (!isRecord(parsed)) {
      return next
    }

    filterConfigs.forEach((config) => {
      const value = parsed[config.key]
      if (value === null || value === undefined) {
        return
      }
      if (isTableFilterValue(value)) {
        next[config.key] = value
      }
    })
  } catch {
    return next
  }

  return next
}

export const serializeRouteTableFilters = (filters: TableFilters): string | null => {
  const entries = Object.entries(filters).filter(([, value]) => hasFilterValue(value))
  if (entries.length === 0) {
    return null
  }
  return JSON.stringify(Object.fromEntries(entries))
}

export const areRouteTableFiltersEqual = (left: TableFilters, right: TableFilters): boolean => (
  JSON.stringify(left) === JSON.stringify(right)
)

export const parseRouteTableSort = (
  rawValue: string | null,
  sortableColumns: Set<string>,
): TableSortState => {
  if (!rawValue) {
    return { key: null, order: null }
  }

  try {
    const parsed = JSON.parse(rawValue)
    if (!isRecord(parsed)) {
      return { key: null, order: null }
    }

    const key = typeof parsed.key === 'string' ? parsed.key.trim() : ''
    const order = parsed.order === 'asc' || parsed.order === 'desc'
      ? parsed.order
      : null

    if (!key || !order || !sortableColumns.has(key)) {
      return { key: null, order: null }
    }

    return { key, order }
  } catch {
    return { key: null, order: null }
  }
}

export const serializeRouteTableSort = (sort: TableSortState): string | null => {
  if (!sort.key || !sort.order) {
    return null
  }
  return JSON.stringify({ key: sort.key, order: sort.order })
}

