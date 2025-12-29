import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { GetDlqListParams } from '../generated/model/getDlqListParams'
import type { DLQListResponse } from '../generated/model/dLQListResponse'
import type { DLQRetryRequest } from '../generated/model/dLQRetryRequest'
import type { DLQRetryResponse } from '../generated/model/dLQRetryResponse'

import { queryKeys } from './index'

const api = getV2()

export interface DlqListFilters extends Omit<GetDlqListParams, 'filters' | 'sort'> {
  filters?: Record<string, { op?: string; value?: unknown } | unknown> | string
  sort?: { key: string; order: 'asc' | 'desc' } | string
}

async function fetchDlqMessages(params?: DlqListFilters, signal?: AbortSignal): Promise<DLQListResponse> {
  const filtersParam = params?.filters
    ? (typeof params.filters === 'string' ? params.filters : JSON.stringify(params.filters))
    : undefined
  const sortParam = params?.sort
    ? (typeof params.sort === 'string' ? params.sort : JSON.stringify(params.sort))
    : undefined
  return api.getDlqList(
    {
      ...params,
      filters: filtersParam,
      sort: sortParam,
    },
    { signal }
  )
}

export function useDlqMessages(params?: DlqListFilters, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.dlq.list(params),
    queryFn: ({ signal }) => fetchDlqMessages(params, signal),
    enabled: options?.enabled ?? true,
  })
}

export function useRetryDlqMessage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: DLQRetryRequest): Promise<DLQRetryResponse> =>
      api.postDlqRetry(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dlq.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.operations.all })
    },
  })
}
