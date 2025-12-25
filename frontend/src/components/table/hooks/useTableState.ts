import { useCallback, useEffect, useMemo, useState } from 'react'
import type { TableFilters, TablePaginationState, TableFilterValue, TableSortState, TableSortOrder } from '../types'

export interface UseTableStateOptions<TFilters extends TableFilters> {
  initialFilters?: TFilters
  initialSearch?: string
  initialPage?: number
  initialPageSize?: number
  initialSort?: TableSortState
  autoResetPageOnFilterChange?: boolean
}

export interface UseTableStateResult<TFilters extends TableFilters> {
  search: string
  setSearch: (value: string) => void
  filters: TFilters
  setFilter: (key: keyof TFilters, value: TableFilterValue) => void
  setFilters: (next: TFilters) => void
  resetFilters: () => void
  sort: TableSortState
  setSort: (key: string | null, order: TableSortOrder | null) => void
  pagination: TablePaginationState
  setPage: (page: number) => void
  setPageSize: (pageSize: number) => void
}

export function useTableState<TFilters extends TableFilters>(
  options: UseTableStateOptions<TFilters> = {}
): UseTableStateResult<TFilters> {
  const {
    initialFilters = {} as TFilters,
    initialSearch = '',
    initialPage = 1,
    initialPageSize = 50,
    initialSort = { key: null, order: null },
    autoResetPageOnFilterChange = true,
  } = options

  const [search, setSearch] = useState(initialSearch)
  const [filters, setFiltersState] = useState<TFilters>(initialFilters)
  const [sort, setSortState] = useState<TableSortState>(initialSort)
  const [pagination, setPagination] = useState<TablePaginationState>({
    page: initialPage,
    pageSize: initialPageSize,
  })

  const setFilter = useCallback(
    (key: keyof TFilters, value: TableFilterValue) => {
      setFiltersState((prev) => ({
        ...prev,
        [key]: value,
      }))
    },
    []
  )

  const setFilters = useCallback((next: TFilters) => {
    setFiltersState(next)
  }, [])

  const resetFilters = useCallback(() => {
    setFiltersState(initialFilters)
    setSearch(initialSearch)
  }, [initialFilters, initialSearch])

  const setSort = useCallback((key: string | null, order: TableSortOrder | null) => {
    setSortState({ key, order })
  }, [])

  const setPage = useCallback((page: number) => {
    setPagination((prev) => ({ ...prev, page }))
  }, [])

  const setPageSize = useCallback((pageSize: number) => {
    setPagination((prev) => ({ ...prev, pageSize, page: 1 }))
  }, [])

  const filtersSnapshot = useMemo(() => ({ search, filters }), [filters, search])

  useEffect(() => {
    if (!autoResetPageOnFilterChange) return
    setPagination((prev) => ({ ...prev, page: 1 }))
  }, [filtersSnapshot, autoResetPageOnFilterChange])

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
  }
}
