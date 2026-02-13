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

export type OrganizationStatus = 'active' | 'inactive' | 'archived'

export type Organization = {
  id: string
  tenant_id: string
  database_id: string | null
  name: string
  full_name: string
  inn: string
  kpp: string
  status: OrganizationStatus
  external_ref: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type OrganizationPoolBinding = {
  pool_id: string
  pool_code: string
  pool_name: string
  is_root: boolean
  effective_from: string
  effective_to: string | null
}

export type PoolRunMode = 'safe' | 'unsafe'
export type PoolRunStatus = 'draft' | 'validated' | 'publishing' | 'published' | 'partial_success' | 'failed'
export type PoolRunStatusReason = 'preparing' | 'awaiting_approval' | 'queued' | null
export type PoolRunApprovalState = 'not_required' | 'preparing' | 'awaiting_approval' | 'approved' | null
export type PoolRunPublicationStepState = 'not_enqueued' | 'queued' | 'started' | 'completed' | null

export type PoolRunRetryChainAttempt = {
  workflow_run_id: string
  parent_workflow_run_id: string | null
  attempt_number: number
  attempt_kind: 'initial' | 'retry' | string
  status: string
}

export type PoolRunProvenance = {
  workflow_run_id: string | null
  workflow_status: string | null
  execution_backend: 'workflow_core' | 'legacy_pool_runtime' | string
  retry_chain: PoolRunRetryChainAttempt[]
  legacy_reference?: string | null
}

export type PoolPublicationAttemptHttpError = {
  status: number
  code?: string
  message?: string
} | null

export type PoolPublicationAttemptTransportError = {
  code?: string
  message?: string
} | null

export type PoolPublicationAttemptDiagnostics = {
  id: string
  run_id: string
  target_database_id: string
  attempt_number: number
  attempt_timestamp?: string | null
  status: string
  entity_name: string
  documents_count: number
  payload_summary?: Record<string, unknown>
  http_error?: PoolPublicationAttemptHttpError
  transport_error?: PoolPublicationAttemptTransportError
  domain_error_message?: string
  external_document_identity?: string
  identity_strategy?: string
  publication_identity_strategy?: string
  posted: boolean
  http_status?: number | null
  error_code?: string
  domain_error_code?: string
  error_message?: string
  request_summary?: Record<string, unknown>
  response_summary?: Record<string, unknown>
  started_at?: string
  finished_at?: string | null
  created_at?: string
}

export type PoolRun = {
  id: string
  tenant_id: string
  pool_id: string
  schema_template_id: string | null
  mode: PoolRunMode
  direction: string
  status: PoolRunStatus
  status_reason: PoolRunStatusReason
  period_start: string
  period_end: string | null
  source_hash: string
  idempotency_key: string
  workflow_execution_id: string | null
  workflow_status: string | null
  approval_state: PoolRunApprovalState
  publication_step_state: PoolRunPublicationStepState
  terminal_reason: string | null
  execution_backend: string | null
  provenance: PoolRunProvenance
  workflow_template_name: string | null
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
  publication_attempts: PoolPublicationAttemptDiagnostics[]
  validation_summary: Record<string, unknown>
  publication_summary: Record<string, unknown>
  diagnostics: unknown[]
  attempts_by_status: Record<string, number>
}

export type PoolRunSafeCommandType = 'confirm-publication' | 'abort-publication'

export type PoolRunSafeCommandResponse = {
  run: PoolRun
  command_type: string
  result: 'accepted' | 'noop'
  replayed: boolean
}

export type PoolRunSafeCommandConflict = {
  success: boolean
  error_code: string
  error_message: string
  conflict_reason: string
  retryable: boolean
  run_id: string
}

export type PoolRunRetryTargetSummary = {
  requested_targets: number
  requested_documents: number
  failed_targets: number
  enqueued_targets: number
  skipped_successful_targets: number
}

export type PoolRunRetryAcceptedResponse = {
  accepted: boolean
  workflow_execution_id: string
  operation_id: string | null
  retry_target_summary: PoolRunRetryTargetSummary
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

export type ListOrganizationsParams = {
  status?: OrganizationStatus
  query?: string
  databaseLinked?: boolean
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

export type UpsertOrganizationPayload = {
  organization_id?: string
  inn: string
  name: string
  full_name?: string
  kpp?: string
  status?: OrganizationStatus
  database_id?: string | null
  external_ref?: string
  metadata?: Record<string, unknown>
}

export type SyncOrganizationsPayload = {
  rows: Array<Record<string, unknown>>
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

export async function listOrganizations(
  params: ListOrganizationsParams = {}
): Promise<Organization[]> {
  const query: Record<string, string | number> = {}
  if (params.status) {
    query.status = params.status
  }
  if (params.query) {
    query.query = params.query
  }
  if (typeof params.databaseLinked === 'boolean') {
    query.database_linked = params.databaseLinked ? 'true' : 'false'
  }
  if (params.limit) {
    query.limit = params.limit
  }
  const response = await apiClient.get<{ organizations: Organization[] }>(
    '/api/v2/pools/organizations/',
    { params: query, skipGlobalError: true }
  )
  return response.data.organizations ?? []
}

export async function getOrganization(
  organizationId: string
): Promise<{ organization: Organization; pool_bindings: OrganizationPoolBinding[] }> {
  const response = await apiClient.get<{ organization: Organization; pool_bindings: OrganizationPoolBinding[] }>(
    `/api/v2/pools/organizations/${organizationId}/`,
    { skipGlobalError: true }
  )
  return response.data
}

export async function upsertOrganization(
  payload: UpsertOrganizationPayload
): Promise<{ organization: Organization; created: boolean }> {
  const response = await apiClient.post<{ organization: Organization; created: boolean }>(
    '/api/v2/pools/organizations/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function syncOrganizationsCatalog(
  payload: SyncOrganizationsPayload
): Promise<{ stats: { created: number; updated: number; skipped: number }; total_rows: number }> {
  const response = await apiClient.post<{ stats: { created: number; updated: number; skipped: number }; total_rows: number }>(
    '/api/v2/pools/organizations/sync/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
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

export async function retryPoolRunFailed(
  runId: string,
  payload: RetryPoolRunPayload,
  idempotencyKey?: string
): Promise<PoolRunRetryAcceptedResponse> {
  const response = await apiClient.post<PoolRunRetryAcceptedResponse>(
    `/api/v2/pools/runs/${runId}/retry/`,
    payload,
    {
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      skipGlobalError: true,
    }
  )
  return response.data
}

async function executePoolRunSafeCommand(
  runId: string,
  commandType: PoolRunSafeCommandType,
  idempotencyKey: string
): Promise<PoolRunSafeCommandResponse> {
  const route =
    commandType === 'confirm-publication'
      ? `/api/v2/pools/runs/${runId}/confirm-publication/`
      : `/api/v2/pools/runs/${runId}/abort-publication/`
  const response = await apiClient.post<PoolRunSafeCommandResponse>(
    route,
    {},
    {
      headers: { 'Idempotency-Key': idempotencyKey },
      skipGlobalError: true,
    }
  )
  return response.data
}

export async function confirmPoolRunPublication(
  runId: string,
  idempotencyKey: string
): Promise<PoolRunSafeCommandResponse> {
  return executePoolRunSafeCommand(runId, 'confirm-publication', idempotencyKey)
}

export async function abortPoolRunPublication(
  runId: string,
  idempotencyKey: string
): Promise<PoolRunSafeCommandResponse> {
  return executePoolRunSafeCommand(runId, 'abort-publication', idempotencyKey)
}
