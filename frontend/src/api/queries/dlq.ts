import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { GetDlqListParams } from '../generated/model/getDlqListParams'
import type { DLQListResponse } from '../generated/model/dLQListResponse'
import type { DLQRetryRequest } from '../generated/model/dLQRetryRequest'
import type { DLQRetryResponse } from '../generated/model/dLQRetryResponse'

import { queryKeys } from './index'

const api = getV2()

async function fetchDlqMessages(params?: GetDlqListParams, signal?: AbortSignal): Promise<DLQListResponse> {
  return api.getDlqList(params, { signal })
}

export function useDlqMessages(params?: GetDlqListParams) {
  return useQuery({
    queryKey: queryKeys.dlq.list(params),
    queryFn: ({ signal }) => fetchDlqMessages(params, signal),
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
