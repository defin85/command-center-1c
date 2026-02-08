import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '../client'

import { queryKeys } from './queryKeys'

export interface OperationTemplate {
  id: string
  name: string
  description?: string | null
  operation_type: string
  target_entity: string
  template_data: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface OperationTemplateListResponse {
  templates: OperationTemplate[]
  count: number
  total: number
}

export interface OperationTemplateDetailResponse {
  template: OperationTemplate
}

export interface OperationTemplateWrite {
  id?: string
  name: string
  description?: string
  operation_type: string
  target_entity: string
  template_data: Record<string, unknown>
  is_active?: boolean
}

export interface OperationTemplateSyncRequest {
  dry_run?: boolean
}

export interface OperationTemplateSyncResponse {
  created: number
  updated: number
  unchanged: number
  message: string
}

export interface OperationTemplateId {
  template_id: string
}

export interface OperationTemplateFilters {
  operation_type?: string
  target_entity?: string
  is_active?: boolean
  search?: string
  limit?: number
  offset?: number
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

  const response = await apiClient.get<OperationTemplateListResponse>(
    '/api/v2/templates/list-templates/',
    {
      params: {
        ...params,
        filters: filtersParam,
        sort: sortParam,
      },
      skipGlobalError: true,
    }
  )
  return response.data
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
    mutationFn: async (request: OperationTemplateSyncRequest): Promise<OperationTemplateSyncResponse> => {
      const response = await apiClient.post<OperationTemplateSyncResponse>(
        '/api/v2/templates/sync-from-registry/',
        request,
        { skipGlobalError: true }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}

export function useCreateTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (request: OperationTemplateWrite): Promise<OperationTemplateDetailResponse> => {
      const response = await apiClient.post<OperationTemplateDetailResponse>(
        '/api/v2/templates/create-template/',
        request,
        { skipGlobalError: true }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}

export function useUpdateTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (request: OperationTemplateWrite): Promise<OperationTemplateDetailResponse> => {
      const response = await apiClient.post<OperationTemplateDetailResponse>(
        '/api/v2/templates/update-template/',
        request,
        { skipGlobalError: true }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (request: OperationTemplateId): Promise<OperationTemplateDetailResponse> => {
      const response = await apiClient.post<OperationTemplateDetailResponse>(
        '/api/v2/templates/delete-template/',
        request,
        { skipGlobalError: true }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}
