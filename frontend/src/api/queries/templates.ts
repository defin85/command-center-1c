import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { GetTemplatesListTemplatesParams } from '../generated/model/getTemplatesListTemplatesParams'
import type { OperationTemplateListResponse } from '../generated/model/operationTemplateListResponse'
import type { OperationTemplateWrite } from '../generated/model/operationTemplateWrite'
import type { OperationTemplateSyncRequest } from '../generated/model/operationTemplateSyncRequest'
import type { OperationTemplateSyncResponse } from '../generated/model/operationTemplateSyncResponse'
import type { OperationTemplateId } from '../generated/model/operationTemplateId'
import type { OperationTemplateDetailResponse } from '../generated/model/operationTemplateDetailResponse'

import { queryKeys } from './queryKeys'

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

export function useCreateTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: OperationTemplateWrite): Promise<OperationTemplateDetailResponse> =>
      api.postTemplatesCreateTemplate(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}

export function useUpdateTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: OperationTemplateWrite): Promise<OperationTemplateDetailResponse> =>
      api.postTemplatesUpdateTemplate(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: OperationTemplateId): Promise<OperationTemplateDetailResponse> =>
      api.postTemplatesDeleteTemplate(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}
