import { useEffect, useRef, useState, type UIEvent } from 'react'

import { useDebouncedValue } from '../../../hooks/useDebouncedValue'

type SelectOption = { label: string; value: string }

type QueryResult<TData> = {
  data?: TData
  isFetching: boolean
}

function mergeSelectOptions(prev: SelectOption[], next: SelectOption[]): SelectOption[] {
  if (prev.length === 0) return next
  const existing = new Set(prev.map((opt) => opt.value))
  let hasNew = false
  const out: SelectOption[] = [...prev]
  next.forEach((opt) => {
    if (existing.has(opt.value)) return
    existing.add(opt.value)
    out.push(opt)
    hasNew = true
  })
  return hasNew ? out : prev
}

function isScrollNearBottom(target: HTMLElement): boolean {
  return target.scrollTop + target.clientHeight >= target.scrollHeight - 24
}

export function usePaginatedRefSelectOptions<TItem, TFilters, TData>(params: {
  enabled: boolean
  pageSize: number
  debounceMs?: number
  queryHook: (filters: TFilters, options?: { enabled?: boolean }) => QueryResult<TData>
  buildFilters: (args: { search?: string; limit: number; offset: number }) => TFilters
  getItems: (data: TData | undefined) => TItem[] | undefined
  getId: (item: TItem) => string
  getLabel: (item: TItem) => string
}) {
  const {
    enabled,
    pageSize,
    debounceMs: debounceMsParam,
    queryHook,
    buildFilters,
    getItems,
    getId,
    getLabel,
  } = params

  const debounceMs = debounceMsParam ?? 300
  const [search, setSearch] = useState<string>('')
  const debouncedSearch = useDebouncedValue(search, debounceMs)
  const [offset, setOffset] = useState<number>(0)
  const [options, setOptions] = useState<SelectOption[]>([])
  const labelById = useRef<Map<string, string>>(new Map())

  const filters = buildFilters({
    search: debouncedSearch.trim() ? debouncedSearch : undefined,
    limit: pageSize,
    offset,
  })

  const query = queryHook(filters, { enabled })

  const total = (() => {
    const data = query.data as unknown
    if (!data || typeof data !== 'object') return options.length
    const maybeTotal = (data as Record<string, unknown>)['total']
    return typeof maybeTotal === 'number' ? maybeTotal : options.length
  })()

  useEffect(() => {
    setOffset(0)
    setOptions([])
  }, [debouncedSearch])

  useEffect(() => {
    const page = getItems(query.data)
    if (!page) return
    page.forEach((item) => {
      const id = getId(item)
      labelById.current.set(id, getLabel(item))
    })
    const nextOptions = page.map((item) => ({ label: getLabel(item), value: getId(item) }))
    setOptions((prev) => {
      if (offset === 0) {
        if (prev.length === nextOptions.length) {
          const same = prev.every((opt, idx) => (
            opt.value === nextOptions[idx]?.value && opt.label === nextOptions[idx]?.label
          ))
          if (same) return prev
        }
        return nextOptions
      }
      return mergeSelectOptions(prev, nextOptions)
    })
  }, [getId, getItems, getLabel, offset, query.data])

  const handlePopupScroll = (event: UIEvent<HTMLElement>) => {
    const target = event.currentTarget
    if (!isScrollNearBottom(target)) return
    if (query.isFetching) return
    if (options.length >= total) return
    setOffset((prev) => prev + pageSize)
  }

  return {
    search,
    setSearch,
    debouncedSearch,
    options,
    labelById,
    query,
    total,
    handlePopupScroll,
  }
}
