import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteOperationCatalogExposure,
  listOperationCatalogExposures,
  upsertOperationCatalogExposure,
  type OperationCatalogExposureUpsertRequest,
  type OperationCatalogExposure,
} from '../operationCatalog'
import { apiClient } from '../client'

import { queryKeys } from './queryKeys'

export interface OperationTemplate {
  id: string
  name: string
  description?: string | null
  operation_type: string
  target_entity: string
  capability?: string
  capability_config?: Record<string, unknown>
  template_data: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
  exposure_id?: string
  template_exposure_id?: string
  template_exposure_revision?: number
  definition_id?: string
  executor_kind?: string
  executor_command_id?: string | null
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
  capability?: string
  capability_config?: Record<string, unknown>
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

const isPlainObject = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const deepClone = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

const parseFiltersParam = (raw: OperationTemplateFilters['filters']): Record<string, unknown> => {
  if (!raw) return {}
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown
      return isPlainObject(parsed) ? parsed : {}
    } catch (_err) {
      return {}
    }
  }
  return isPlainObject(raw) ? raw : {}
}

const parseSortParam = (raw: OperationTemplateFilters['sort']): { key: string; order: 'asc' | 'desc' } | null => {
  if (!raw) return null
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown
      if (!isPlainObject(parsed)) return null
      const key = typeof parsed.key === 'string' ? parsed.key : ''
      const order = parsed.order === 'desc' ? 'desc' : parsed.order === 'asc' ? 'asc' : null
      if (!key || !order) return null
      return { key, order }
    } catch (_err) {
      return null
    }
  }
  if (!isPlainObject(raw)) return null
  const key = typeof raw.key === 'string' ? raw.key : ''
  const order = raw.order === 'desc' ? 'desc' : raw.order === 'asc' ? 'asc' : null
  if (!key || !order) return null
  return { key, order }
}

const canonicalDriverForOperationType = (operationType: string): string | null => {
  if (operationType === 'designer_cli') return 'cli'
  if (operationType === 'ibcmd_cli') return 'ibcmd'
  return null
}

const toOperationTemplate = (exposure: OperationCatalogExposure): OperationTemplate => {
  const templateData = isPlainObject(exposure.template_data) ? deepClone(exposure.template_data) : {}
  const operationType = String(exposure.operation_type || '').trim() || 'designer_cli'
  const executorKind = String(exposure.executor_kind || operationType).trim() || operationType
  const templateExposureId = String(exposure.template_exposure_id || exposure.id || '').trim() || undefined
  const rawTemplateExposureRevision = (
    typeof exposure.template_exposure_revision === 'number'
      ? exposure.template_exposure_revision
      : typeof exposure.exposure_revision === 'number'
        ? exposure.exposure_revision
        : undefined
  )
  const templateExposureRevision = (
    typeof rawTemplateExposureRevision === 'number'
      && Number.isFinite(rawTemplateExposureRevision)
      && rawTemplateExposureRevision >= 1
      ? Math.trunc(rawTemplateExposureRevision)
      : undefined
  )
  let executorCommandId = (
    typeof exposure.executor_command_id === 'string'
      ? exposure.executor_command_id.trim()
      : ''
  )
  if (!executorCommandId) {
    executorCommandId = typeof templateData.command_id === 'string' ? templateData.command_id.trim() : ''
  }
  const targetEntity = String(exposure.target_entity || '').trim() || 'infobase'
  return {
    id: exposure.alias,
    name: exposure.name,
    description: exposure.description ?? '',
    operation_type: operationType,
    target_entity: targetEntity,
    capability: String(exposure.capability || '').trim() || undefined,
    capability_config: isPlainObject(exposure.capability_config)
      ? deepClone(exposure.capability_config)
      : {},
    template_data: templateData,
    is_active: exposure.is_active !== false,
    created_at: String(exposure.created_at || ''),
    updated_at: String(exposure.updated_at || ''),
    exposure_id: exposure.id,
    template_exposure_id: templateExposureId,
    template_exposure_revision: templateExposureRevision,
    definition_id: exposure.definition_id,
    executor_kind: executorKind,
    executor_command_id: executorCommandId || undefined,
  }
}

const applyOperationTypeFilter = (rows: OperationTemplate[], value: unknown): OperationTemplate[] => {
  const next = String(value ?? '').trim()
  if (!next) return rows
  return rows.filter((row) => row.operation_type === next)
}

const applyTargetEntityFilter = (rows: OperationTemplate[], value: unknown): OperationTemplate[] => {
  const next = String(value ?? '').trim()
  if (!next) return rows
  return rows.filter((row) => row.target_entity === next)
}

const applyIsActiveFilter = (rows: OperationTemplate[], value: unknown): OperationTemplate[] => {
  if (typeof value === 'boolean') return rows.filter((row) => row.is_active === value)
  const text = String(value ?? '').trim().toLowerCase()
  if (text === 'true' || text === '1' || text === 'yes') return rows.filter((row) => row.is_active)
  if (text === 'false' || text === '0' || text === 'no') return rows.filter((row) => !row.is_active)
  return rows
}

const applySearch = (rows: OperationTemplate[], search: string | undefined): OperationTemplate[] => {
  const q = String(search || '').trim().toLowerCase()
  if (!q) return rows
  return rows.filter((row) => (
    row.id.toLowerCase().includes(q)
    || row.name.toLowerCase().includes(q)
    || String(row.description || '').toLowerCase().includes(q)
    || String(row.executor_kind || '').toLowerCase().includes(q)
    || String(row.executor_command_id || '').toLowerCase().includes(q)
    || String(row.template_exposure_id || '').toLowerCase().includes(q)
  ))
}

const applySort = (rows: OperationTemplate[], sort: { key: string; order: 'asc' | 'desc' } | null): OperationTemplate[] => {
  if (!sort) return rows
  const next = rows.slice()
  const toComparable = (row: OperationTemplate, key: string): string | number => {
    if (key === 'is_active') return row.is_active ? 1 : 0
    if (key === 'created_at') return row.created_at
    if (key === 'updated_at') return row.updated_at
    if (key === 'operation_type') return row.operation_type
    if (key === 'executor_kind') return row.executor_kind || ''
    if (key === 'executor_command_id') return row.executor_command_id || ''
    if (key === 'target_entity') return row.target_entity
    if (key === 'template_exposure_id') return row.template_exposure_id || ''
    if (key === 'template_exposure_revision') return row.template_exposure_revision || 0
    if (key === 'name') return row.name
    if (key === 'id') return row.id
    return ''
  }
  next.sort((a, b) => {
    const av = toComparable(a, sort.key)
    const bv = toComparable(b, sort.key)
    const result = typeof av === 'number' && typeof bv === 'number'
      ? av - bv
      : String(av).localeCompare(String(bv))
    return sort.order === 'desc' ? -result : result
  })
  return next
}

async function fetchOperationTemplates(params?: OperationTemplateFilters): Promise<OperationTemplateListResponse> {
  const exposuresResponse = await listOperationCatalogExposures({
    surface: 'template',
    limit: 1000,
    offset: 0,
  })

  let rows = (exposuresResponse.exposures ?? [])
    .filter((item) => item.surface === 'template')
    .map((item) => toOperationTemplate(item))

  if (params?.operation_type) rows = applyOperationTypeFilter(rows, params.operation_type)
  if (params?.target_entity) rows = applyTargetEntityFilter(rows, params.target_entity)
  if (params?.is_active !== undefined) rows = applyIsActiveFilter(rows, params.is_active)
  rows = applySearch(rows, params?.search)

  const filters = parseFiltersParam(params?.filters)
  if (isPlainObject(filters.operation_type) && 'value' in filters.operation_type) {
    rows = applyOperationTypeFilter(rows, (filters.operation_type as { value?: unknown }).value)
  }
  if (isPlainObject(filters.target_entity) && 'value' in filters.target_entity) {
    rows = applyTargetEntityFilter(rows, (filters.target_entity as { value?: unknown }).value)
  }
  if (isPlainObject(filters.is_active) && 'value' in filters.is_active) {
    rows = applyIsActiveFilter(rows, (filters.is_active as { value?: unknown }).value)
  }

  rows = applySort(rows, parseSortParam(params?.sort))

  const total = rows.length
  const offset = Math.max(0, Number(params?.offset ?? 0))
  const limit = Math.max(1, Math.min(1000, Number(params?.limit ?? 50)))
  const paged = rows.slice(offset, offset + limit)

  return { templates: paged, count: paged.length, total }
}

export const buildTemplateOperationCatalogUpsertPayload = (
  request: OperationTemplateWrite
): OperationCatalogExposureUpsertRequest => {
  const operationType = String(request.operation_type || '').trim() || 'designer_cli'
  const targetEntity = String(request.target_entity || '').trim() || 'infobase'
  const templateData = isPlainObject(request.template_data) ? deepClone(request.template_data) : {}
  const capability = String(request.capability || '').trim()
  const capabilityConfig = isPlainObject(request.capability_config)
    ? deepClone(request.capability_config)
    : {}

  const executorPayload: Record<string, unknown> = {
    operation_type: operationType,
    target_entity: targetEntity,
    template_data: templateData,
    kind: operationType,
  }
  const canonicalDriver = canonicalDriverForOperationType(operationType)
  if (canonicalDriver) {
    executorPayload.driver = canonicalDriver
  }

  const commandId = typeof templateData.command_id === 'string' ? templateData.command_id.trim() : ''
  if (commandId) {
    executorPayload.command_id = commandId
  }
  const workflowId = typeof templateData.workflow_id === 'string' ? templateData.workflow_id.trim() : ''
  if (workflowId) {
    executorPayload.workflow_id = workflowId
  }
  if (templateData.mode === 'manual' || templateData.mode === 'guided') {
    executorPayload.mode = templateData.mode
  }
  if (isPlainObject(templateData.params)) {
    executorPayload.params = deepClone(templateData.params)
  }
  if (Array.isArray(templateData.additional_args)) {
    executorPayload.additional_args = templateData.additional_args
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean)
  }
  if (typeof templateData.stdin === 'string') {
    executorPayload.stdin = templateData.stdin
  }
  if (isPlainObject(templateData.fixed)) {
    executorPayload.fixed = deepClone(templateData.fixed)
  }

  return {
    definition: {
      tenant_scope: 'global',
      executor_kind: operationType,
      executor_payload: executorPayload,
      contract_version: 1,
    },
    exposure: {
      surface: 'template' as const,
      alias: String(request.id || '').trim(),
      tenant_id: null,
      name: String(request.name || '').trim(),
      description: String(request.description || ''),
      is_active: request.is_active !== false,
      capability: capability || `templates.${operationType || 'legacy'}`,
      contexts: [],
      display_order: 0,
      capability_config: capabilityConfig,
      status: request.is_active === false ? 'draft' as const : 'published' as const,
    },
  }
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
      const payload = buildTemplateOperationCatalogUpsertPayload(request)
      const response = await upsertOperationCatalogExposure(payload)
      return { template: toOperationTemplate(response.exposure) }
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
      const payload = buildTemplateOperationCatalogUpsertPayload(request)
      const response = await upsertOperationCatalogExposure(payload)
      return { template: toOperationTemplate(response.exposure) }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (request: OperationTemplateId): Promise<void> => {
      const alias = String(request.template_id || '').trim()
      if (!alias) throw new Error('template_id is required')
      const response = await listOperationCatalogExposures({
        surface: 'template',
        alias,
        limit: 1,
        offset: 0,
      })
      const exposure = (response.exposures ?? []).find((item) => item.surface === 'template' && item.alias === alias)
      if (!exposure || typeof exposure.id !== 'string') {
        throw new Error('Template not found')
      }
      await deleteOperationCatalogExposure(exposure.id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}
