import { apiClient } from './client'

export type OperationCatalogDefinition = {
  id: string
  tenant_scope: string
  executor_kind: 'ibcmd_cli' | 'designer_cli' | 'workflow' | string
  executor_payload: Record<string, unknown>
  contract_version: number
  fingerprint: string
  status: 'active' | 'archived' | string
  created_at?: string
  updated_at?: string
}

export type OperationCatalogExposure = {
  id: string
  definition_id: string
  surface: 'template' | 'action_catalog' | string
  alias: string
  tenant_id?: string | null
  name: string
  description?: string | null
  is_active: boolean
  capability: string
  contexts?: string[]
  display_order?: number
  capability_config?: Record<string, unknown>
  status: 'draft' | 'published' | 'invalid' | string
  system_managed?: boolean
  domain?: string
  operation_type?: string
  target_entity?: string
  template_data?: Record<string, unknown>
  template_exposure_id?: string
  exposure_revision?: number
  template_exposure_revision?: number
  executor_kind?: string
  executor_command_id?: string | null
  execution_contract?: OperationCatalogExposureExecutionContract
  created_at?: string
  updated_at?: string
}

export type OperationCatalogExposureExecutionCapability = {
  id?: string
  label?: string
  operation_type?: string
  target_entity?: string
  executor_kind?: string
}

export type OperationCatalogExposureExecutionInput = {
  mode?: 'params' | 'input_context' | string
  required_parameters?: string[]
  optional_parameters?: string[]
  parameter_schemas?: Record<string, Record<string, unknown>>
}

export type OperationCatalogExposureExecutionOutput = {
  result_path?: string
  supports_structured_mapping?: boolean
}

export type OperationCatalogExposureExecutionSideEffect = {
  execution_mode?: 'sync' | 'async' | string
  effect_kind?: string
  summary?: string | null
  timeout_seconds?: number | null
  max_retries?: number | null
}

export type OperationCatalogExposureExecutionProvenance = {
  surface?: string
  alias?: string
  exposure_id?: string
  exposure_revision?: number
  definition_id?: string
  executor_command_id?: string | null
}

export type OperationCatalogExposureExecutionContract = {
  contract_version?: string
  capability?: OperationCatalogExposureExecutionCapability
  input_contract?: OperationCatalogExposureExecutionInput
  output_contract?: OperationCatalogExposureExecutionOutput
  side_effect_profile?: OperationCatalogExposureExecutionSideEffect
  binding_provenance?: OperationCatalogExposureExecutionProvenance
}

export type OperationCatalogDefinitionInput = {
  tenant_scope: string
  executor_kind: 'ibcmd_cli' | 'designer_cli' | 'workflow' | string
  executor_payload: Record<string, unknown>
  contract_version?: number
}

export type OperationCatalogExposureInput = {
  surface: 'template' | 'action_catalog' | string
  alias: string
  tenant_id?: string | null
  name: string
  description?: string | null
  is_active?: boolean
  capability: string
  contexts?: string[]
  display_order?: number
  capability_config?: Record<string, unknown>
  status?: 'draft' | 'published' | 'invalid' | string
}

export type OperationCatalogExposureUpsertRequest = {
  exposure_id?: string
  definition_id?: string | null
  definition?: OperationCatalogDefinitionInput
  exposure: OperationCatalogExposureInput
}

export type OperationCatalogExposureValidateRequest = {
  definition?: OperationCatalogDefinitionInput
  exposure: OperationCatalogExposureInput
}

export type OperationCatalogValidationError = {
  path: string
  code: string
  message: string
}

export type OperationCatalogDefinitionListResponse = {
  definitions: OperationCatalogDefinition[]
  count: number
  total: number
}

export type OperationCatalogExposureListResponse = {
  exposures: OperationCatalogExposure[]
  definitions?: OperationCatalogDefinition[]
  count: number
  total: number
}

export type OperationCatalogExposureDetailResponse = {
  exposure: OperationCatalogExposure
  definition: OperationCatalogDefinition
}

export type OperationCatalogExposurePublishResponse = {
  published: boolean
  exposure: OperationCatalogExposure
  validation_errors: OperationCatalogValidationError[]
}

export type OperationCatalogExposureValidateResponse = {
  valid: boolean
  errors: OperationCatalogValidationError[]
}

export type OperationCatalogExposureDeleteResponse = {
  deleted: boolean
  exposure: OperationCatalogExposure
}

export async function listOperationCatalogDefinitions(params?: {
  tenant_scope?: string
  executor_kind?: string
  status?: string
  q?: string
  limit?: number
  offset?: number
}): Promise<OperationCatalogDefinitionListResponse> {
  const response = await apiClient.get<OperationCatalogDefinitionListResponse>(
    '/api/v2/operation-catalog/definitions/',
    { params, skipGlobalError: true }
  )
  return response.data
}

export async function listOperationCatalogExposures(params?: {
  surface?: string
  tenant_id?: string
  capability?: string
  status?: string
  alias?: string
  search?: string
  filters?: string
  sort?: string
  include?: string
  limit?: number
  offset?: number
}): Promise<OperationCatalogExposureListResponse> {
  const response = await apiClient.get<OperationCatalogExposureListResponse>(
    '/api/v2/operation-catalog/exposures/',
    { params, skipGlobalError: true }
  )
  return response.data
}

export async function upsertOperationCatalogExposure(
  payload: OperationCatalogExposureUpsertRequest
): Promise<OperationCatalogExposureDetailResponse> {
  const response = await apiClient.post<OperationCatalogExposureDetailResponse>(
    '/api/v2/operation-catalog/exposures/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function publishOperationCatalogExposure(
  exposureId: string
): Promise<OperationCatalogExposurePublishResponse> {
  const response = await apiClient.post<OperationCatalogExposurePublishResponse>(
    `/api/v2/operation-catalog/exposures/${encodeURIComponent(exposureId)}/publish/`,
    {},
    { skipGlobalError: true }
  )
  return response.data
}

export async function validateOperationCatalogExposure(
  payload: OperationCatalogExposureValidateRequest
): Promise<OperationCatalogExposureValidateResponse> {
  const response = await apiClient.post<OperationCatalogExposureValidateResponse>(
    '/api/v2/operation-catalog/validate/',
    payload,
    { skipGlobalError: true }
  )
  return response.data
}

export async function deleteOperationCatalogExposure(
  exposureId: string
): Promise<OperationCatalogExposureDeleteResponse> {
  const response = await apiClient.delete<OperationCatalogExposureDeleteResponse>(
    `/api/v2/operation-catalog/exposures/${encodeURIComponent(exposureId)}/`,
    { skipGlobalError: true }
  )
  return response.data
}
