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

export type PoolTopologyTemplateNode = {
  slot_key: string
  label?: string | null
  is_root: boolean
  metadata: Record<string, unknown>
}

export type PoolTopologyTemplateEdge = {
  parent_slot_key: string
  child_slot_key: string
  weight: string
  min_amount?: string | null
  max_amount?: string | null
  document_policy_key?: string | null
  metadata: Record<string, unknown>
}

export type PoolTopologyTemplateRevision = {
  topology_template_revision_id: string
  topology_template_id: string
  revision_number: number
  nodes: PoolTopologyTemplateNode[]
  edges: PoolTopologyTemplateEdge[]
  metadata: Record<string, unknown>
  created_at: string
}

export type PoolTopologyTemplate = {
  topology_template_id: string
  code: string
  name: string
  description: string
  status: 'active' | 'deactivated'
  metadata: Record<string, unknown>
  latest_revision_number: number
  latest_revision: PoolTopologyTemplateRevision
  revisions: PoolTopologyTemplateRevision[]
  created_at: string
  updated_at: string
}

export type OrganizationPool = {
  id: string
  code: string
  name: string
  description: string
  is_active: boolean
  metadata: Record<string, unknown>
  workflow_bindings?: PoolWorkflowBinding[]
  updated_at: string
}

export type WorkflowDefinitionRef = {
  contract_version?: string
  workflow_definition_key: string
  workflow_revision_id: string
  workflow_revision: number
  workflow_name: string
}

export type DecisionTableRef = {
  decision_table_id: string
  decision_key: string
  decision_revision: number
}

export type PoolWorkflowBindingDecisionRef = {
  decision_table_id: string
  decision_key: string
  slot_key?: string | null
  decision_revision: number
}

export type PoolWorkflowBindingSelector = {
  direction?: string | null
  mode?: string | null
  tags?: string[]
}

export type PoolWorkflowBindingStatus = 'draft' | 'active' | 'inactive'

type PoolWorkflowBindingBase = {
  contract_version?: string
  selector?: PoolWorkflowBindingSelector
  effective_from: string
  effective_to?: string | null
  workflow?: WorkflowDefinitionRef
  decisions?: PoolWorkflowBindingDecisionRef[]
  parameters?: Record<string, unknown>
  role_mapping?: Record<string, string>
}

export type PoolWorkflowBindingProfileLifecycleWarning = {
  code: string
  title: string
  detail: string
}

export type PoolWorkflowBindingResolvedProfile = {
  binding_profile_id: string
  code: string
  name: string
  status: string
  binding_profile_revision_id: string
  binding_profile_revision_number: number
  workflow: WorkflowDefinitionRef
  decisions?: PoolWorkflowBindingDecisionRef[]
  parameters?: Record<string, unknown>
  role_mapping?: Record<string, string>
}

export type PoolWorkflowBinding = PoolWorkflowBindingBase & {
  binding_id: string
  pool_id: string
  revision: number
  status: PoolWorkflowBindingStatus
  binding_profile_id: string
  binding_profile_revision_id: string
  binding_profile_revision_number: number
  resolved_profile: PoolWorkflowBindingResolvedProfile
  profile_lifecycle_warning?: PoolWorkflowBindingProfileLifecycleWarning | null
}

export type PoolWorkflowBindingInput = {
  contract_version?: string
  binding_id?: string
  pool_id?: string
  revision?: number
  binding_profile_revision_id: string
  selector?: PoolWorkflowBindingSelector
  effective_from: string
  effective_to?: string | null
  status?: PoolWorkflowBindingStatus
}

export type PoolWorkflowBindingBlockingRemediation = {
  code: string
  title: string
  detail: string
}

export type PoolWorkflowBindingCollection = {
  pool_id: string
  workflow_bindings: PoolWorkflowBinding[]
  collection_etag: string
  blocking_remediation?: PoolWorkflowBindingBlockingRemediation | null
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
export type PoolRunInputContractVersion = 'run_input_v1' | 'legacy_pre_run_input'

export type PoolRunMasterDataGate = {
  status: 'completed' | 'failed' | 'skipped'
  mode: 'resolve_upsert'
  targets_count: number
  bindings_count: number
  error_code: string | null
  detail: string | null
  diagnostic: Record<string, unknown> | null
} | null

export type PoolRunReadinessBlocker = {
  code?: string | null
  detail?: string | null
  kind?: string | null
  entity_name?: string | null
  field_or_table_path?: string | null
  database_id?: string | null
  organization_id?: string | null
  diagnostic?: Record<string, unknown> | null
}

export type PoolRunReadinessCheckCode =
  | 'master_data_coverage'
  | 'organization_party_bindings'
  | 'policy_completeness'
  | 'odata_verify_readiness'

export type PoolRunReadinessCheckStatus = 'ready' | 'not_ready'

export type PoolRunReadinessCheck = {
  code: PoolRunReadinessCheckCode
  status: PoolRunReadinessCheckStatus
  blocker_codes: string[]
  blockers: PoolRunReadinessBlocker[]
}

export type PoolRunReadinessChecklist = {
  status: PoolRunReadinessCheckStatus
  checks: PoolRunReadinessCheck[]
}

export type PoolRunVerificationStatus = 'not_verified' | 'passed' | 'failed'

export type PoolRunVerificationMismatch = {
  database_id?: string | null
  entity_name?: string | null
  document_idempotency_key?: string | null
  field_or_table_path?: string | null
  kind?: string | null
}

export type PoolRunVerificationSummary = {
  checked_targets: number
  verified_documents: number
  mismatches_count: number
  mismatches: PoolRunVerificationMismatch[]
} | null

export type PoolRunRetryChainAttempt = {
  workflow_run_id: string
  parent_workflow_run_id: string | null
  attempt_number: number
  attempt_kind: 'initial' | 'retry'
  status: string
}

export type PoolRunProvenance = {
  workflow_run_id: string | null
  workflow_status: string | null
  execution_backend: 'workflow_core' | 'legacy_pool_runtime' | string
  root_operation_id?: string | null
  execution_consumer?: string | null
  lane?: string | null
  retry_chain: PoolRunRetryChainAttempt[]
  legacy_reference?: string | null
}

export type PoolRunRuntimeProjectionWorkflowDefinition = {
  plan_key: string
  template_version: string
  workflow_template_name: string
  workflow_type: string
}

export type PoolRunRuntimeProjectionWorkflowBinding = {
  binding_mode: string
  binding_id?: string
  binding_profile_id?: string
  pool_id?: string
  binding_profile_revision_id?: string
  binding_profile_revision_number?: number
  attachment_revision?: number
  workflow_definition_key?: string
  workflow_revision_id?: string
  workflow_revision?: number
  workflow_name?: string
  decision_refs?: PoolWorkflowBindingDecisionRef[]
  selector?: PoolWorkflowBindingSelector
  status?: string
}

export type PoolRunRuntimeProjectionDocumentPolicyRef = {
  slot_key: string | null
  edge_ref: {
    parent_node_id: string
    child_node_id: string
  }
  policy_version: string
  source: string
}

export type PoolRunRuntimeProjectionDocumentPolicyProjection = {
  source_mode: string
  policy_refs: PoolRunRuntimeProjectionDocumentPolicyRef[]
  compiled_document_policy_slots: Record<string, Record<string, unknown>>
  slot_coverage_summary: PoolWorkflowBindingPreviewSlotCoverageSummary
  policy_refs_count: number
  targets_count: number
}

export type PoolRunRuntimeProjectionArtifacts = {
  document_plan_artifact_version: string | null
  topology_version_ref: string | null
  distribution_artifact_ref: Record<string, unknown> | null
}

export type PoolRunRuntimeProjectionCompileSummary = {
  steps_count: number
  atomic_publication_steps_count: number
  compiled_targets_count: number
}

export type PoolRunRuntimeProjection = {
  version: string
  run_id: string
  pool_id: string
  direction: string
  mode: string
  workflow_definition: PoolRunRuntimeProjectionWorkflowDefinition
  workflow_binding: PoolRunRuntimeProjectionWorkflowBinding
  document_policy_projection: PoolRunRuntimeProjectionDocumentPolicyProjection
  artifacts: PoolRunRuntimeProjectionArtifacts
  compile_summary: PoolRunRuntimeProjectionCompileSummary
}

export type PoolWorkflowBindingPreviewSlotCoverage = {
  code: string | null
  status: 'resolved' | 'missing_selector' | 'missing_slot' | 'ambiguous_slot' | 'ambiguous_context' | 'unavailable_context'
  label: string
  detail: string
}

export type PoolWorkflowBindingPreviewSlotCoverageItem = {
  edge_id: string
  edge_label: string
  slot_key: string
  coverage: PoolWorkflowBindingPreviewSlotCoverage
}

export type PoolWorkflowBindingPreviewSlotCoverageSummary = {
  total_edges: number
  counts: {
    resolved: number
    missing_selector: number
    missing_slot: number
    ambiguous_slot: number
    ambiguous_context: number
    unavailable_context: number
  }
  items: PoolWorkflowBindingPreviewSlotCoverageItem[]
}

export type PoolWorkflowBindingPreview = {
  workflow_binding: PoolWorkflowBinding
  compiled_document_policy_slots: Record<string, Record<string, unknown>>
  compiled_document_policy?: Record<string, unknown>
  slot_coverage_summary: PoolWorkflowBindingPreviewSlotCoverageSummary
  runtime_projection: PoolRunRuntimeProjection
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
  publication_identity_strategy?: string
  posted: boolean
  domain_error_code?: string
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
  run_input: Record<string, unknown> | null
  input_contract_version?: PoolRunInputContractVersion
  idempotency_key: string
  workflow_execution_id: string | null
  workflow_status: string | null
  root_operation_id?: string | null
  execution_consumer?: string | null
  lane?: string | null
  approval_state: PoolRunApprovalState
  publication_step_state: PoolRunPublicationStepState
  master_data_gate?: PoolRunMasterDataGate
  readiness_blockers?: PoolRunReadinessBlocker[]
  readiness_checklist?: PoolRunReadinessChecklist
  verification_status?: PoolRunVerificationStatus | null
  verification_summary?: PoolRunVerificationSummary
  terminal_reason: string | null
  execution_backend: string | null
  provenance: PoolRunProvenance
  workflow_binding?: PoolWorkflowBinding
  runtime_projection?: PoolRunRuntimeProjection | null
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
  metadata: Record<string, unknown>
}

export type PoolTopologyEdgeMetadata = Record<string, unknown> & {
  document_policy_key?: string
}

export type PoolGraphEdge = {
  edge_version_id: string
  parent_node_version_id: string
  child_node_version_id: string
  weight: string
  min_amount: string | null
  max_amount: string | null
  metadata: PoolTopologyEdgeMetadata
}

export type PoolGraph = {
  pool_id: string
  date: string
  version: string
  nodes: PoolGraphNode[]
  edges: PoolGraphEdge[]
}

export type PoolTopologySnapshotPeriod = {
  effective_from: string
  effective_to: string | null
  nodes_count: number
  edges_count: number
}

export type PoolTopologySnapshotList = {
  pool_id: string
  count: number
  snapshots: PoolTopologySnapshotPeriod[]
}

export type PoolDocumentPolicyMigrationDecisionRef = {
  decision_id: string
  decision_table_id: string
  decision_revision: number
}

export type PoolDocumentPolicyMigrationBindingDecisionRef = PoolWorkflowBindingDecisionRef

export type PoolDocumentPolicyMigrationAffectedBinding = {
  binding_id: string
  revision: number
  updated: boolean
  decision_ref: PoolDocumentPolicyMigrationBindingDecisionRef
}

export type PoolDocumentPolicyMigrationSource = {
  kind?: string
  source_path: string
  pool_id: string
  pool_code?: string
  edge_version_id: string
  parent_node_version_id?: string
  child_node_version_id?: string
  parent_organization_id?: string
  child_organization_id?: string
  parent_organization_name?: string
  child_organization_name?: string
  child_database_id?: string
  effective_from?: string
  effective_to?: string | null
  legacy_policy_hash?: string
}

export type PoolDocumentPolicyMigrationReport = {
  created: boolean
  reused_existing_revision: boolean
  binding_update_required: boolean
  slot_key: string
  legacy_payload_removed: boolean
  source: PoolDocumentPolicyMigrationSource
  decision_ref: PoolDocumentPolicyMigrationDecisionRef
  affected_bindings: PoolDocumentPolicyMigrationAffectedBinding[]
}

export type PoolDocumentPolicyMigrationDecision = {
  id: string
  decision_table_id: string
  decision_key: string
  decision_revision: number
  name: string
  description?: string
  inputs?: unknown[]
  outputs?: unknown[]
  rules?: unknown[]
  hit_policy?: string
  validation_mode?: string
  is_active?: boolean
  parent_version?: string | null
  metadata_context?: Record<string, unknown> | null
  created_at?: string
  updated_at?: string
}

export type PoolDocumentPolicyMigrationPayload = {
  edge_version_id: string
  decision_table_id?: string
  name?: string
  description?: string
}

export type PoolDocumentPolicyMigrationResponse = {
  decision: PoolDocumentPolicyMigrationDecision
  metadata_context: Record<string, unknown>
  migration: PoolDocumentPolicyMigrationReport
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

export type UpdatePoolSchemaTemplatePayload = CreatePoolSchemaTemplatePayload

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
  pool_workflow_binding_id: string
  direction: 'top_down' | 'bottom_up'
  period_start: string
  period_end?: string | null
  run_input: Record<string, unknown>
  mode?: 'safe' | 'unsafe'
  schema_template_id?: string | null
  seed?: number | null
  validation_summary?: Record<string, unknown>
  diagnostics?: unknown[]
}

export type UpsertOrganizationPoolPayload = {
  pool_id?: string
  code: string
  name: string
  description?: string
  is_active?: boolean
  metadata?: Record<string, unknown>
}

export type PoolTopologySnapshotNodeInput = {
  organization_id: string
  is_root?: boolean
  metadata?: Record<string, unknown>
}

export type PoolTopologySnapshotEdgeInput = {
  parent_organization_id: string
  child_organization_id: string
  weight?: string
  min_amount?: string | null
  max_amount?: string | null
  metadata?: PoolTopologyEdgeMetadata
}

export type PoolTopologyTemplateSlotAssignmentInput = {
  slot_key: string
  organization_id: string
}

export type PoolTopologyTemplateEdgeSelectorOverrideInput = {
  parent_slot_key: string
  child_slot_key: string
  document_policy_key: string
}

export type UpsertPoolTopologySnapshotPayload = {
  version: string
  effective_from: string
  effective_to?: string | null
  topology_template_revision_id?: string
  slot_assignments?: PoolTopologyTemplateSlotAssignmentInput[]
  edge_selector_overrides?: PoolTopologyTemplateEdgeSelectorOverrideInput[]
  nodes?: PoolTopologySnapshotNodeInput[]
  edges?: PoolTopologySnapshotEdgeInput[]
}

export type RetryPoolRunPayload = {
  entity_name?: string
  documents_by_database?: Record<string, Array<Record<string, unknown>>>
  target_database_ids?: string[]
  max_attempts?: number
  retry_interval_seconds?: number
  external_key_field?: string
  use_retry_subset_payload?: boolean
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

export async function updatePoolSchemaTemplate(
  templateId: string,
  payload: UpdatePoolSchemaTemplatePayload
): Promise<PoolSchemaTemplate> {
  const response = await apiClient.put<{ template: PoolSchemaTemplate }>(
    `/api/v2/pools/schema-templates/${templateId}/`,
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

export async function listPoolTopologyTemplates(): Promise<PoolTopologyTemplate[]> {
  const response = await apiClient.get<{ topology_templates: PoolTopologyTemplate[] }>(
    '/api/v2/pools/topology-templates/',
    { skipGlobalError: true }
  )
  return response.data.topology_templates ?? []
}

export async function upsertOrganizationPool(
  payload: UpsertOrganizationPoolPayload
): Promise<{ pool: OrganizationPool; created: boolean }> {
  const response = await apiClient.post<{ pool: OrganizationPool; created: boolean }>(
    '/api/v2/pools/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function listPoolWorkflowBindings(
  poolId: string
): Promise<PoolWorkflowBindingCollection> {
  const response = await apiClient.get<PoolWorkflowBindingCollection>(
    '/api/v2/pools/workflow-bindings/',
    {
      params: { pool_id: poolId },
      skipGlobalError: true,
    }
  )
  return {
    pool_id: response.data.pool_id,
    workflow_bindings: response.data.workflow_bindings ?? [],
    collection_etag: response.data.collection_etag,
    blocking_remediation: response.data.blocking_remediation ?? null,
  }
}

export async function replacePoolWorkflowBindingsCollection(
  payload: {
    pool_id: string
    expected_collection_etag: string
    workflow_bindings: PoolWorkflowBindingInput[]
  }
): Promise<PoolWorkflowBindingCollection> {
  const response = await apiClient.put<PoolWorkflowBindingCollection>(
    '/api/v2/pools/workflow-bindings/',
    payload,
    { skipGlobalError: true }
  )
  return {
    pool_id: response.data.pool_id,
    workflow_bindings: response.data.workflow_bindings ?? [],
    collection_etag: response.data.collection_etag,
    blocking_remediation: response.data.blocking_remediation ?? null,
  }
}

export async function getPoolWorkflowBinding(
  poolId: string,
  bindingId: string
): Promise<PoolWorkflowBinding> {
  const response = await apiClient.get<{ pool_id: string; workflow_binding: PoolWorkflowBinding }>(
    `/api/v2/pools/workflow-bindings/${encodeURIComponent(bindingId)}/`,
    {
      params: { pool_id: poolId },
      skipGlobalError: true,
    }
  )
  return response.data.workflow_binding
}

export async function upsertPoolWorkflowBinding(
  payload: {
    pool_id: string
    workflow_binding: PoolWorkflowBindingInput
  }
): Promise<{ pool_id: string; workflow_binding: PoolWorkflowBinding; created: boolean }> {
  const response = await apiClient.post<{
    pool_id: string
    workflow_binding: PoolWorkflowBinding
    created: boolean
  }>(
    '/api/v2/pools/workflow-bindings/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function deletePoolWorkflowBinding(
  poolId: string,
  bindingId: string,
  revision: number
): Promise<{ pool_id: string; workflow_binding: PoolWorkflowBinding; deleted: boolean }> {
  const response = await apiClient.delete<{
    pool_id: string
    workflow_binding: PoolWorkflowBinding
    deleted: boolean
  }>(
    `/api/v2/pools/workflow-bindings/${encodeURIComponent(bindingId)}/`,
    {
      params: { pool_id: poolId, revision },
      skipGlobalError: true,
    }
  )
  return response.data
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

export async function listPoolTopologySnapshots(poolId: string): Promise<PoolTopologySnapshotList> {
  const response = await apiClient.get<PoolTopologySnapshotList>(
    `/api/v2/pools/${poolId}/topology-snapshots/`,
    { skipGlobalError: true }
  )
  return response.data
}

export async function upsertPoolTopologySnapshot(
  poolId: string,
  payload: UpsertPoolTopologySnapshotPayload
): Promise<{
  pool_id: string
  version: string
  effective_from: string
  effective_to: string | null
  nodes_count: number
  edges_count: number
}> {
  const response = await apiClient.post<{
    pool_id: string
    version: string
    effective_from: string
    effective_to: string | null
    nodes_count: number
    edges_count: number
  }>(
    `/api/v2/pools/${poolId}/topology-snapshot/upsert/`,
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function migratePoolEdgeDocumentPolicy(
  poolId: string,
  payload: PoolDocumentPolicyMigrationPayload
): Promise<PoolDocumentPolicyMigrationResponse> {
  const response = await apiClient.post<PoolDocumentPolicyMigrationResponse>(
    `/api/v2/pools/${poolId}/document-policy-migrations/`,
    payload,
    { skipGlobalError: true }
  )
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

export async function previewPoolWorkflowBinding(
  payload: CreatePoolRunPayload
): Promise<PoolWorkflowBindingPreview> {
  const response = await apiClient.post<PoolWorkflowBindingPreview>(
    '/api/v2/pools/workflow-bindings/preview/',
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

export type PoolMasterDataEntityType = 'party' | 'item' | 'contract' | 'tax_profile'
export type PoolMasterBindingCatalogKind = 'organization' | 'counterparty' | ''
export type PoolMasterBindingSyncStatus = 'resolved' | 'upserted' | 'conflict'

export type PoolMasterParty = {
  id: string
  tenant_id: string
  canonical_id: string
  name: string
  full_name: string
  inn: string
  kpp: string
  is_our_organization: boolean
  is_counterparty: boolean
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type PoolMasterItem = {
  id: string
  tenant_id: string
  canonical_id: string
  name: string
  sku: string
  unit: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type PoolMasterContract = {
  id: string
  tenant_id: string
  canonical_id: string
  name: string
  owner_counterparty_id: string
  owner_counterparty_canonical_id: string
  number: string
  date: string | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type PoolMasterTaxProfile = {
  id: string
  tenant_id: string
  canonical_id: string
  vat_rate: number
  vat_included: boolean
  vat_code: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type PoolMasterDataBinding = {
  id: string
  tenant_id: string
  entity_type: PoolMasterDataEntityType
  canonical_id: string
  database_id: string
  ib_ref_key: string
  ib_catalog_kind: PoolMasterBindingCatalogKind
  owner_counterparty_canonical_id: string
  sync_status: PoolMasterBindingSyncStatus
  fingerprint: string
  metadata: Record<string, unknown>
  last_synced_at: string
  created_at: string
  updated_at: string
}

export type PoolMasterDataSyncPriority = 'p0' | 'p1' | 'p2' | 'p3'

export type PoolMasterDataSyncRole = 'inbound' | 'outbound' | 'reconcile' | 'manual_remediation'

export type PoolMasterDataSyncDeadlineState = 'none' | 'pending' | 'met' | 'missed'

export type PoolMasterDataSyncQueueStates = {
  queued: number
  processing: number
  retrying: number
  failed: number
  completed: number
}

export type PoolMasterDataSyncStatus = {
  tenant_id: string
  database_id: string
  entity_type: PoolMasterDataEntityType
  checkpoint_token: string
  pending_checkpoint_token: string
  checkpoint_status: string
  pending_count: number
  retry_count: number
  conflict_pending_count: number
  conflict_retrying_count: number
  lag_seconds: number
  last_success_at: string | null
  last_applied_at: string | null
  last_error_code: string
  last_error_reason: string
  priority: PoolMasterDataSyncPriority | ''
  role: PoolMasterDataSyncRole | ''
  server_affinity: string
  deadline_at: string
  deadline_state: PoolMasterDataSyncDeadlineState
  queue_states: PoolMasterDataSyncQueueStates
}

export type PoolMasterDataSyncConflict = {
  id: string
  tenant_id: string
  database_id: string
  entity_type: PoolMasterDataEntityType
  status: 'pending' | 'retrying' | 'resolved'
  conflict_code: string
  canonical_id: string
  origin_system: string
  origin_event_id: string
  diagnostics: Record<string, unknown>
  metadata: Record<string, unknown>
  resolved_at: string | null
  resolved_by_id: string | null
  created_at: string
  updated_at: string
}

export type PoolMasterDataBootstrapImportEntityType = PoolMasterDataEntityType | 'binding'

export type PoolMasterDataBootstrapImportJobStatus =
  | 'preflight_pending'
  | 'preflight_failed'
  | 'dry_run_pending'
  | 'dry_run_failed'
  | 'execute_pending'
  | 'running'
  | 'finalized'
  | 'failed'
  | 'canceled'

export type PoolMasterDataBootstrapImportChunkStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'deferred'
  | 'canceled'

export type PoolMasterDataBootstrapImportPreflightError = {
  code?: string
  detail?: string
  path?: string
  [key: string]: unknown
}

export type PoolMasterDataBootstrapImportPreflightResult = {
  ok: boolean
  source_kind: string
  coverage: Record<string, boolean>
  credential_strategy: string
  errors: PoolMasterDataBootstrapImportPreflightError[]
  diagnostics: Record<string, unknown>
}

export type PoolMasterDataBootstrapImportChunk = {
  id: string
  job_id: string
  entity_type: PoolMasterDataBootstrapImportEntityType
  chunk_index: number
  status: PoolMasterDataBootstrapImportChunkStatus
  attempt_count: number
  idempotency_key: string
  records_total: number
  records_created: number
  records_updated: number
  records_skipped: number
  records_failed: number
  last_error_code: string
  last_error: string
  diagnostics: Record<string, unknown>
  metadata: Record<string, unknown>
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export type PoolMasterDataBootstrapImportReport = {
  created_count: number
  updated_count: number
  skipped_count: number
  failed_count: number
  deferred_count: number
  diagnostics: Record<string, unknown>
}

export type PoolMasterDataBootstrapImportProgress = {
  total_chunks: number
  processed_chunks: number
  pending_chunks: number
  running_chunks: number
  succeeded_chunks: number
  failed_chunks: number
  deferred_chunks: number
  canceled_chunks: number
  completion_ratio: number
}

export type PoolMasterDataBootstrapImportJob = {
  id: string
  tenant_id: string
  database_id: string
  entity_scope: PoolMasterDataBootstrapImportEntityType[]
  status: PoolMasterDataBootstrapImportJobStatus
  started_at: string | null
  finished_at: string | null
  last_error_code: string
  last_error: string
  preflight_result: Record<string, unknown>
  dry_run_summary: Record<string, unknown>
  progress: PoolMasterDataBootstrapImportProgress
  audit_trail: Array<Record<string, unknown>>
  report: PoolMasterDataBootstrapImportReport
  chunks?: PoolMasterDataBootstrapImportChunk[]
  created_at: string
  updated_at: string
}

export type PoolMasterDataBootstrapImportScopePayload = {
  database_id: string
  entity_scope: PoolMasterDataBootstrapImportEntityType[]
}

export type CreatePoolMasterDataBootstrapImportJobPayload = PoolMasterDataBootstrapImportScopePayload & {
  mode: 'dry_run' | 'execute'
  chunk_size?: number
}

export type ListPoolMasterDataBootstrapImportJobsParams = {
  database_id?: string
  limit?: number
  offset?: number
}

export type ListMasterDataPartiesParams = {
  query?: string
  canonical_id?: string
  role?: Exclude<PoolMasterBindingCatalogKind, ''>
  limit?: number
  offset?: number
}

export type UpsertMasterDataPartyPayload = {
  party_id?: string
  canonical_id: string
  name: string
  full_name?: string
  inn?: string
  kpp?: string
  is_our_organization?: boolean
  is_counterparty?: boolean
  metadata?: Record<string, unknown>
}

export type ListMasterDataItemsParams = {
  query?: string
  canonical_id?: string
  sku?: string
  limit?: number
  offset?: number
}

export type UpsertMasterDataItemPayload = {
  item_id?: string
  canonical_id: string
  name: string
  sku?: string
  unit?: string
  metadata?: Record<string, unknown>
}

export type ListMasterDataContractsParams = {
  query?: string
  canonical_id?: string
  owner_counterparty_canonical_id?: string
  limit?: number
  offset?: number
}

export type UpsertMasterDataContractPayload = {
  contract_id?: string
  canonical_id: string
  name: string
  owner_counterparty_id: string
  number?: string
  date?: string | null
  metadata?: Record<string, unknown>
}

export type ListMasterDataTaxProfilesParams = {
  query?: string
  canonical_id?: string
  vat_code?: string
  limit?: number
  offset?: number
}

export type UpsertMasterDataTaxProfilePayload = {
  tax_profile_id?: string
  canonical_id: string
  vat_rate: number | string
  vat_included: boolean
  vat_code: string
  metadata?: Record<string, unknown>
}

export type ListMasterDataBindingsParams = {
  entity_type?: PoolMasterDataEntityType
  canonical_id?: string
  database_id?: string
  ib_catalog_kind?: Exclude<PoolMasterBindingCatalogKind, ''>
  owner_counterparty_canonical_id?: string
  sync_status?: PoolMasterBindingSyncStatus
  limit?: number
  offset?: number
}

export type UpsertMasterDataBindingPayload = {
  binding_id?: string
  entity_type: PoolMasterDataEntityType
  canonical_id: string
  database_id: string
  ib_ref_key: string
  ib_catalog_kind?: PoolMasterBindingCatalogKind
  owner_counterparty_canonical_id?: string
  sync_status?: PoolMasterBindingSyncStatus
  fingerprint?: string
  metadata?: Record<string, unknown>
}

export type ListMasterDataSyncStatusParams = {
  database_id?: string
  entity_type?: PoolMasterDataEntityType
  priority?: PoolMasterDataSyncPriority
  role?: PoolMasterDataSyncRole
  server_affinity?: string
  deadline_state?: PoolMasterDataSyncDeadlineState
}

export type ListMasterDataSyncConflictsParams = {
  database_id?: string
  entity_type?: PoolMasterDataEntityType
  status?: 'pending' | 'retrying' | 'resolved'
  limit?: number
}

export type RetryMasterDataSyncConflictPayload = {
  note?: string
  metadata?: Record<string, unknown>
}

export type ReconcileMasterDataSyncConflictPayload = {
  note?: string
  reconcile_payload?: Record<string, unknown>
}

export type ResolveMasterDataSyncConflictPayload = {
  resolution_code: string
  note?: string
  metadata?: Record<string, unknown>
}

export type MasterDataListMeta = {
  count: number
  limit: number
  offset: number
}

export type SimpleDatabaseRef = {
  id: string
  name: string
}

export async function listMasterDataParties(
  params: ListMasterDataPartiesParams = {}
): Promise<{ parties: PoolMasterParty[]; meta: MasterDataListMeta }> {
  const response = await apiClient.get<{
    parties: PoolMasterParty[]
    count: number
    limit: number
    offset: number
  }>('/api/v2/pools/master-data/parties/', {
    params,
    skipGlobalError: true,
  })
  return {
    parties: response.data.parties ?? [],
    meta: {
      count: response.data.count ?? 0,
      limit: response.data.limit ?? (params.limit ?? 50),
      offset: response.data.offset ?? (params.offset ?? 0),
    },
  }
}

export async function upsertMasterDataParty(
  payload: UpsertMasterDataPartyPayload
): Promise<{ party: PoolMasterParty; created: boolean }> {
  const response = await apiClient.post<{ party: PoolMasterParty; created: boolean }>(
    '/api/v2/pools/master-data/parties/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function listMasterDataItems(
  params: ListMasterDataItemsParams = {}
): Promise<{ items: PoolMasterItem[]; meta: MasterDataListMeta }> {
  const response = await apiClient.get<{
    items: PoolMasterItem[]
    count: number
    limit: number
    offset: number
  }>('/api/v2/pools/master-data/items/', {
    params,
    skipGlobalError: true,
  })
  return {
    items: response.data.items ?? [],
    meta: {
      count: response.data.count ?? 0,
      limit: response.data.limit ?? (params.limit ?? 50),
      offset: response.data.offset ?? (params.offset ?? 0),
    },
  }
}

export async function upsertMasterDataItem(
  payload: UpsertMasterDataItemPayload
): Promise<{ item: PoolMasterItem; created: boolean }> {
  const response = await apiClient.post<{ item: PoolMasterItem; created: boolean }>(
    '/api/v2/pools/master-data/items/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function listMasterDataContracts(
  params: ListMasterDataContractsParams = {}
): Promise<{ contracts: PoolMasterContract[]; meta: MasterDataListMeta }> {
  const response = await apiClient.get<{
    contracts: PoolMasterContract[]
    count: number
    limit: number
    offset: number
  }>('/api/v2/pools/master-data/contracts/', {
    params,
    skipGlobalError: true,
  })
  return {
    contracts: response.data.contracts ?? [],
    meta: {
      count: response.data.count ?? 0,
      limit: response.data.limit ?? (params.limit ?? 50),
      offset: response.data.offset ?? (params.offset ?? 0),
    },
  }
}

export async function upsertMasterDataContract(
  payload: UpsertMasterDataContractPayload
): Promise<{ contract: PoolMasterContract; created: boolean }> {
  const response = await apiClient.post<{ contract: PoolMasterContract; created: boolean }>(
    '/api/v2/pools/master-data/contracts/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function listMasterDataTaxProfiles(
  params: ListMasterDataTaxProfilesParams = {}
): Promise<{ tax_profiles: PoolMasterTaxProfile[]; meta: MasterDataListMeta }> {
  const response = await apiClient.get<{
    tax_profiles: PoolMasterTaxProfile[]
    count: number
    limit: number
    offset: number
  }>('/api/v2/pools/master-data/tax-profiles/', {
    params,
    skipGlobalError: true,
  })
  return {
    tax_profiles: response.data.tax_profiles ?? [],
    meta: {
      count: response.data.count ?? 0,
      limit: response.data.limit ?? (params.limit ?? 50),
      offset: response.data.offset ?? (params.offset ?? 0),
    },
  }
}

export async function upsertMasterDataTaxProfile(
  payload: UpsertMasterDataTaxProfilePayload
): Promise<{ tax_profile: PoolMasterTaxProfile; created: boolean }> {
  const response = await apiClient.post<{ tax_profile: PoolMasterTaxProfile; created: boolean }>(
    '/api/v2/pools/master-data/tax-profiles/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function listMasterDataBindings(
  params: ListMasterDataBindingsParams = {}
): Promise<{ bindings: PoolMasterDataBinding[]; meta: MasterDataListMeta }> {
  const response = await apiClient.get<{
    bindings: PoolMasterDataBinding[]
    count: number
    limit: number
    offset: number
  }>('/api/v2/pools/master-data/bindings/', {
    params,
    skipGlobalError: true,
  })
  return {
    bindings: response.data.bindings ?? [],
    meta: {
      count: response.data.count ?? 0,
      limit: response.data.limit ?? (params.limit ?? 50),
      offset: response.data.offset ?? (params.offset ?? 0),
    },
  }
}

export async function upsertMasterDataBinding(
  payload: UpsertMasterDataBindingPayload
): Promise<{ binding: PoolMasterDataBinding; created: boolean }> {
  const response = await apiClient.post<{ binding: PoolMasterDataBinding; created: boolean }>(
    '/api/v2/pools/master-data/bindings/upsert/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function listPoolTargetDatabases(): Promise<SimpleDatabaseRef[]> {
  const response = await apiClient.get<{ databases: SimpleDatabaseRef[] }>(
    '/api/v2/databases/list-databases/',
    { skipGlobalError: true }
  )
  return response.data.databases ?? []
}

export async function listMasterDataSyncStatus(
  params: ListMasterDataSyncStatusParams = {}
): Promise<{ statuses: PoolMasterDataSyncStatus[]; count: number }> {
  const response = await apiClient.get<{
    statuses: PoolMasterDataSyncStatus[]
    count: number
  }>('/api/v2/pools/master-data/sync-status/', {
    params,
    skipGlobalError: true,
  })
  return {
    statuses: response.data.statuses ?? [],
    count: response.data.count ?? 0,
  }
}

export async function listMasterDataSyncConflicts(
  params: ListMasterDataSyncConflictsParams = {}
): Promise<{ conflicts: PoolMasterDataSyncConflict[]; count: number }> {
  const response = await apiClient.get<{
    conflicts: PoolMasterDataSyncConflict[]
    count: number
  }>('/api/v2/pools/master-data/sync-conflicts/', {
    params,
    skipGlobalError: true,
  })
  return {
    conflicts: response.data.conflicts ?? [],
    count: response.data.count ?? 0,
  }
}

export async function retryMasterDataSyncConflict(
  conflictId: string,
  payload: RetryMasterDataSyncConflictPayload = {}
): Promise<{ conflict: PoolMasterDataSyncConflict }> {
  const response = await apiClient.post<{ conflict: PoolMasterDataSyncConflict }>(
    `/api/v2/pools/master-data/sync-conflicts/${conflictId}/retry/`,
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function reconcileMasterDataSyncConflict(
  conflictId: string,
  payload: ReconcileMasterDataSyncConflictPayload
): Promise<{ conflict: PoolMasterDataSyncConflict }> {
  const response = await apiClient.post<{ conflict: PoolMasterDataSyncConflict }>(
    `/api/v2/pools/master-data/sync-conflicts/${conflictId}/reconcile/`,
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function resolveMasterDataSyncConflict(
  conflictId: string,
  payload: ResolveMasterDataSyncConflictPayload
): Promise<{ conflict: PoolMasterDataSyncConflict }> {
  const response = await apiClient.post<{ conflict: PoolMasterDataSyncConflict }>(
    `/api/v2/pools/master-data/sync-conflicts/${conflictId}/resolve/`,
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function runPoolMasterDataBootstrapImportPreflight(
  payload: PoolMasterDataBootstrapImportScopePayload
): Promise<{ preflight: PoolMasterDataBootstrapImportPreflightResult }> {
  const response = await apiClient.post<{ preflight: PoolMasterDataBootstrapImportPreflightResult }>(
    '/api/v2/pools/master-data/bootstrap-import/preflight/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function createPoolMasterDataBootstrapImportJob(
  payload: CreatePoolMasterDataBootstrapImportJobPayload
): Promise<{ job: PoolMasterDataBootstrapImportJob }> {
  const response = await apiClient.post<{ job: PoolMasterDataBootstrapImportJob }>(
    '/api/v2/pools/master-data/bootstrap-import/jobs/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function listPoolMasterDataBootstrapImportJobs(
  params: ListPoolMasterDataBootstrapImportJobsParams = {}
): Promise<{
  count: number
  limit: number
  offset: number
  jobs: PoolMasterDataBootstrapImportJob[]
}> {
  const response = await apiClient.get<{
    count: number
    limit: number
    offset: number
    jobs: PoolMasterDataBootstrapImportJob[]
  }>('/api/v2/pools/master-data/bootstrap-import/jobs/', {
    params,
    skipGlobalError: true,
  })
  return {
    count: response.data.count ?? 0,
    limit: response.data.limit ?? (params.limit ?? 50),
    offset: response.data.offset ?? (params.offset ?? 0),
    jobs: response.data.jobs ?? [],
  }
}

export async function getPoolMasterDataBootstrapImportJob(
  jobId: string
): Promise<{ job: PoolMasterDataBootstrapImportJob }> {
  const response = await apiClient.get<{ job: PoolMasterDataBootstrapImportJob }>(
    `/api/v2/pools/master-data/bootstrap-import/jobs/${jobId}/`,
    { skipGlobalError: true }
  )
  return response.data
}

export async function cancelPoolMasterDataBootstrapImportJob(
  jobId: string
): Promise<{ job: PoolMasterDataBootstrapImportJob }> {
  const response = await apiClient.post<{ job: PoolMasterDataBootstrapImportJob }>(
    `/api/v2/pools/master-data/bootstrap-import/jobs/${jobId}/cancel/`,
    {},
    { skipGlobalError: true }
  )
  return response.data
}

export async function retryFailedPoolMasterDataBootstrapImportChunks(
  jobId: string
): Promise<{ job: PoolMasterDataBootstrapImportJob }> {
  const response = await apiClient.post<{ job: PoolMasterDataBootstrapImportJob }>(
    `/api/v2/pools/master-data/bootstrap-import/jobs/${jobId}/retry-failed-chunks/`,
    {},
    { skipGlobalError: true }
  )
  return response.data
}
