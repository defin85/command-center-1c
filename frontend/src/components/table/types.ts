export type TableFilterValue = string | number | boolean | string[] | null

export type TableFilters = Record<string, TableFilterValue>

export interface TablePaginationState {
  page: number
  pageSize: number
}

export type TableFilterType = 'select' | 'text' | 'boolean'

export interface TableFilterOption {
  value: string
  label: string
}

export interface TableFilterConfig {
  key: string
  label: string
  type: TableFilterType
  options?: TableFilterOption[]
  placeholder?: string
}

export type TableSortOrder = 'asc' | 'desc'

export interface TableSortState {
  key: string | null
  order: TableSortOrder | null
}
