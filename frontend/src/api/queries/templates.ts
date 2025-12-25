import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { GetTemplatesListTemplatesParams } from '../generated/model/getTemplatesListTemplatesParams'
import type { OperationTemplateListResponse } from '../generated/model/operationTemplateListResponse'
import type { OperationTemplateSyncRequest } from '../generated/model/operationTemplateSyncRequest'
import type { OperationTemplateSyncResponse } from '../generated/model/operationTemplateSyncResponse'

import { queryKeys } from './index'

const api = getV2()

export interface OperationTemplateFilters extends Omit<GetTemplatesListTemplatesParams, 'filters' | 'sort'> {
  filters?: Record<string, { op?: string; value?: unknown } | unknown> | string
  sort?: { key: string; order: 'asc' | 'desc' } | string
}

async function fetchOperationTemplates(params?: OperationTemplateFilters): Promise<OperationTemplateListResponse> {
  const filtersParam = params?.filters
    ? (typeof params.filters === 'string' ? params.filters : JSON.stringify(params.filters))
    : undefined
  const sortParam = params?.sort
    ? (typeof params.sort === 'string' ? params.sort : JSON.stringify(params.sort))
    : undefined
  return api.getTemplatesListTemplates({
    ...params,
    filters: filtersParam,
    sort: sortParam,
  })
}

export function useOperationTemplates(params?: OperationTemplateFilters) {
  return useQuery({
    queryKey: queryKeys.templates.list(params),
    queryFn: () => fetchOperationTemplates(params),
  })
}

export function useSyncTemplatesFromRegistry() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: OperationTemplateSyncRequest): Promise<OperationTemplateSyncResponse> =>
      api.postTemplatesSyncFromRegistry(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}
