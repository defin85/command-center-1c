import { describe, it, expect } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'

import { usePaginatedRefSelectOptions } from '../usePaginatedRefSelectOptions'

type Item = { id: string; name: string }
type Filters = { search?: string; limit: number; offset: number }
type Data = { items: Item[]; total: number }

function useTestQuery(filters: Filters, options?: { enabled?: boolean }) {
  if (options?.enabled === false) {
    return { data: undefined as Data | undefined, isFetching: false }
  }

  const search = typeof filters.search === 'string' ? filters.search : ''
  const total = search ? 3 : 5

  const all: Item[] = Array.from({ length: total }).map((_, idx) => ({
    id: `${search || 'id'}-${idx + 1}`,
    name: `Item ${idx + 1}`,
  }))
  const page = all.slice(filters.offset, filters.offset + filters.limit)

  return {
    data: { items: page, total },
    isFetching: false,
  }
}

describe('usePaginatedRefSelectOptions', () => {
  it('loads first page and merges next pages on scroll', async () => {
    const { result } = renderHook(() => usePaginatedRefSelectOptions<Item, Filters, Data>({
      enabled: true,
      pageSize: 2,
      debounceMs: 0,
      queryHook: useTestQuery,
      buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
      getItems: (data) => data?.items,
      getId: (item) => item.id,
      getLabel: (item) => item.name,
    }))

    await waitFor(() => expect(result.current.options).toHaveLength(2))
    expect(result.current.labelById.current.get('id-1')).toBe('Item 1')

    act(() => {
      result.current.handlePopupScroll({
        target: { scrollTop: 80, clientHeight: 40, scrollHeight: 100 },
      })
    })
    await waitFor(() => expect(result.current.options).toHaveLength(4))

    act(() => {
      result.current.handlePopupScroll({
        target: { scrollTop: 80, clientHeight: 40, scrollHeight: 100 },
      })
    })
    await waitFor(() => expect(result.current.options).toHaveLength(5))

    act(() => {
      result.current.handlePopupScroll({
        target: { scrollTop: 80, clientHeight: 40, scrollHeight: 100 },
      })
    })
    await waitFor(() => expect(result.current.options).toHaveLength(5))
  })

  it('resets options on debounced search change', async () => {
    const { result } = renderHook(() => usePaginatedRefSelectOptions<Item, Filters, Data>({
      enabled: true,
      pageSize: 2,
      debounceMs: 0,
      queryHook: useTestQuery,
      buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
      getItems: (data) => data?.items,
      getId: (item) => item.id,
      getLabel: (item) => item.name,
    }))

    await waitFor(() => expect(result.current.options).toHaveLength(2))

    act(() => {
      result.current.setSearch('foo')
    })

    await waitFor(() => expect(result.current.debouncedSearch).toBe('foo'))
    await waitFor(() => expect(result.current.options).toHaveLength(2))
    expect(result.current.options[0]?.value).toBe('foo-1')
  })
})

