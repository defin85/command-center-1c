import { apiClient } from './client'

export type PoolSchemaTemplateFormat = 'xlsx' | 'json'

export type PoolSchemaTemplate = {
  id: string
  tenant_id: string
  code: string
  name: string
  format: PoolSchemaTemplateFormat
  is_public: boolean
  is_active: boolean
  schema: Record<string, unknown>
  metadata: Record<string, unknown>
  workflow_template_id: string | null
  created_at: string
  updated_at: string
}

export type OrganizationPool = {
  id: string
  code: string
  name: string
  is_active: boolean
  metadata: Record<string, unknown>
  updated_at: string
}

export type PoolRun = {
  id: string
  tenant_id: string
  pool_id: string
  schema_template_id: string | null
  mode: string
  direction: string
  status: string
  period_start: string
  period_end: string | null
  source_hash: string
  idempotency_key: string
  seed: number | null
  validation_summary: Record<string, unknown>
  publication_summary: Record<string, unknown>
  diagnostics: unknown[]
  last_error: string
  created_at: string
  updated_at: string
  validated_at: string | null
  publication_confirmed_at: string | null
  publishing_started_at: string | null
  completed_at: string | null
}

export type PoolRunReport = {
  run: PoolRun
  publication_attempts: Array<Record<string, unknown>>
  validation_summary: Record<string, unknown>
  publication_summary: Record<string, unknown>
  diagnostics: unknown[]
  attempts_by_status: Record<string, number>
}

export type PoolGraphNode = {
  node_version_id: string
  organization_id: string
  inn: string
  name: string
  is_root: boolean
}

export type PoolGraphEdge = {
  edge_version_id: string
  parent_node_version_id: string
  child_node_version_id: string
  weight: string
  min_amount: string | null
  max_amount: string | null
}

export type PoolGraph = {
  pool_id: string
  date: string
  nodes: PoolGraphNode[]
  edges: PoolGraphEdge[]
}

export type ListPoolSchemaTemplatesParams = {
  format?: PoolSchemaTemplateFormat
  isPublic?: boolean
  isActive?: boolean
}

export type CreatePoolSchemaTemplatePayload = {
  code: string
  name: string
  format: PoolSchemaTemplateFormat
  is_public?: boolean
  is_active?: boolean
  schema?: Record<string, unknown>
  metadata?: Record<string, unknown>
  workflow_template_id?: string | null
}

export type ListPoolRunsParams = {
  poolId?: string
  status?: string
  limit?: number
}

export type CreatePoolRunPayload = {
  pool_id: string
  direction: 'top_down' | 'bottom_up'
  period_start: string
  period_end?: string | null
  source_hash?: string
  mode?: 'safe' | 'unsafe'
  schema_template_id?: string | null
  seed?: number | null
  validation_summary?: Record<string, unknown>
  diagnostics?: unknown[]
}

export type RetryPoolRunPayload = {
  entity_name: string
  documents_by_database: Record<string, Array<Record<string, unknown>>>
  max_attempts?: number
  retry_interval_seconds?: number
  external_key_field?: string
}

export async function listPoolSchemaTemplates(
  params: ListPoolSchemaTemplatesParams = {}
): Promise<PoolSchemaTemplate[]> {
  const query: Record<string, string> = {}
  if (params.format) {
    query.format = params.format
  }
  if (typeof params.isPublic === 'boolean') {
    query.is_public = params.isPublic ? 'true' : 'false'
  }
  if (typeof params.isActive === 'boolean') {
    query.is_active = params.isActive ? 'true' : 'false'
  }

  const response = await apiClient.get<{ templates: PoolSchemaTemplate[] }>(
    '/api/v2/pools/schema-templates/',
    { params: query, skipGlobalError: true }
  )
  return response.data.templates ?? []
}

export async function createPoolSchemaTemplate(
  payload: CreatePoolSchemaTemplatePayload
): Promise<PoolSchemaTemplate> {
  const response = await apiClient.post<{ template: PoolSchemaTemplate }>(
    '/api/v2/pools/schema-templates/',
    payload,
    { skipGlobalError: true }
  )
  return response.data.template
}

export async function listOrganizationPools(): Promise<OrganizationPool[]> {
  const response = await apiClient.get<{ pools: OrganizationPool[] }>(
    '/api/v2/pools/',
    { skipGlobalError: true }
  )
  return response.data.pools ?? []
}

export async function getPoolGraph(poolId: string, targetDate?: string): Promise<PoolGraph> {
  const response = await apiClient.get<PoolGraph>(`/api/v2/pools/${poolId}/graph/`, {
    params: targetDate ? { date: targetDate } : undefined,
    skipGlobalError: true,
  })
  return response.data
}

export async function listPoolRuns(params: ListPoolRunsParams = {}): Promise<PoolRun[]> {
  const query: Record<string, string | number> = {}
  if (params.poolId) {
    query.pool_id = params.poolId
  }
  if (params.status) {
    query.status = params.status
  }
  if (params.limit) {
    query.limit = params.limit
  }
  const response = await apiClient.get<{ runs: PoolRun[] }>('/api/v2/pools/runs/', {
    params: query,
    skipGlobalError: true,
  })
  return response.data.runs ?? []
}

export async function createPoolRun(payload: CreatePoolRunPayload): Promise<{ run: PoolRun; created: boolean }> {
  const response = await apiClient.post<{ run: PoolRun; created: boolean }>(
    '/api/v2/pools/runs/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function getPoolRunReport(runId: string): Promise<PoolRunReport> {
  const response = await apiClient.get<PoolRunReport>(`/api/v2/pools/runs/${runId}/report/`, {
    skipGlobalError: true,
  })
  return response.data
}

export async function retryPoolRunFailed(runId: string, payload: RetryPoolRunPayload): Promise<{ run: PoolRun; summary: Record<string, number> }> {
  const response = await apiClient.post<{ run: PoolRun; summary: Record<string, number> }>(
    `/api/v2/pools/runs/${runId}/retry/`,
    payload,
    { skipGlobalError: true }
  )
  return response.data
}
