import { useEffect, useRef, useState } from 'react'

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
  const debounceMs = params.debounceMs ?? 300
  const [search, setSearch] = useState<string>('')
  const debouncedSearch = useDebouncedValue(search, debounceMs)
  const [offset, setOffset] = useState<number>(0)
  const [options, setOptions] = useState<SelectOption[]>([])
  const labelById = useRef<Map<string, string>>(new Map())

  const filters = params.buildFilters({
    search: debouncedSearch.trim() ? debouncedSearch : undefined,
    limit: params.pageSize,
    offset,
  })

  const query = params.queryHook(filters, { enabled: params.enabled })

  const total = typeof (query.data as any)?.total === 'number'
    ? Number((query.data as any).total)
    : options.length

  useEffect(() => {
    setOffset(0)
    setOptions([])
  }, [debouncedSearch])

  useEffect(() => {
    const page = params.getItems(query.data)
    if (!page) return
    page.forEach((item) => {
      const id = params.getId(item)
      labelById.current.set(id, params.getLabel(item))
    })
    const nextOptions = page.map((item) => ({ label: params.getLabel(item), value: params.getId(item) }))
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
  }, [query.data, offset, params.getId, params.getItems, params.getLabel])

  const handlePopupScroll = (event: any) => {
    const target = event?.target as HTMLElement | undefined
    if (!target) return
    if (!isScrollNearBottom(target)) return
    if (query.isFetching) return
    if (options.length >= total) return
    setOffset((prev) => prev + params.pageSize)
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
