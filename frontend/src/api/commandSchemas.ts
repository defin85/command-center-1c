import { apiClient } from './client'
import type { DriverCatalogV2, DriverCommandParamV2, DriverCommandV2 } from './driverCommands'

export type CommandSchemaDriver = 'cli' | 'ibcmd'

export type CommandSchemaPermissionSpec = {
  allowed_roles?: string[]
  denied_roles?: string[]
  allowed_envs?: string[]
  denied_envs?: string[]
  min_db_level?: 'operate' | 'manage' | 'admin'
}

export type CommandSchemaParamPatch = Partial<DriverCommandParamV2>

export type CommandSchemaCommandPatch = Partial<Omit<DriverCommandV2, 'params_by_name' | 'permissions'>> & {
  params_by_name?: Record<string, CommandSchemaParamPatch>
  permissions?: CommandSchemaPermissionSpec
}

export type CommandSchemasOverridesCatalogV2 = {
  catalog_version: 2
  driver: CommandSchemaDriver
  overrides: {
    commands_by_id: Record<string, CommandSchemaCommandPatch>
  }
}

export type CommandSchemasEffectivePayload = {
  base_version: string | null
  base_version_id: string | null
  base_alias: string | null
  overrides_version: string | null
  overrides_version_id: string | null
  catalog: DriverCatalogV2
  source: string
}

export type CommandSchemasEditorView = {
  driver: CommandSchemaDriver
  etag: string
  base: {
    approved_version: string | null
    approved_version_id: string | null
    latest_version: string | null
    latest_version_id: string | null
  }
  overrides: {
    active_version: string | null
    active_version_id: string | null
  }
  catalogs: {
    base: DriverCatalogV2
    overrides: CommandSchemasOverridesCatalogV2
    effective: CommandSchemasEffectivePayload
  }
}

export async function getCommandSchemasEditorView(driver: CommandSchemaDriver): Promise<CommandSchemasEditorView> {
  const response = await apiClient.get<CommandSchemasEditorView>(
    '/api/v2/settings/command-schemas/editor/',
    { params: { driver } }
  )
  return response.data
}

export type CommandSchemaArtifactType = 'base' | 'overrides'

export type CommandSchemaVersionListItem = {
  id: string
  version: string
  created_at: string | null
  created_by: string
  metadata: Record<string, unknown>
}

export type CommandSchemaVersionsListResponse = {
  driver: CommandSchemaDriver
  artifact: CommandSchemaArtifactType
  versions: CommandSchemaVersionListItem[]
  count: number
}

export async function listCommandSchemaVersions(
  driver: CommandSchemaDriver,
  artifact: CommandSchemaArtifactType,
  filters?: { limit?: number; offset?: number }
): Promise<CommandSchemaVersionsListResponse> {
  const response = await apiClient.get<CommandSchemaVersionsListResponse>(
    '/api/v2/settings/command-schemas/versions/',
    { params: { driver, artifact, ...filters } }
  )
  return response.data
}

export type CommandSchemaOverridesUpdateRequest = {
  driver: CommandSchemaDriver
  catalog: Record<string, unknown>
  reason: string
  expected_etag?: string
}

export type CommandSchemaOverridesUpdateResponse = {
  driver: CommandSchemaDriver
  overrides_version: string
  etag: string
}

export async function updateCommandSchemaOverrides(
  payload: CommandSchemaOverridesUpdateRequest
): Promise<CommandSchemaOverridesUpdateResponse> {
  const response = await apiClient.post<CommandSchemaOverridesUpdateResponse>(
    '/api/v2/settings/command-schemas/overrides/update/',
    payload
  )
  return response.data
}

export type CommandSchemaOverridesRollbackRequest = {
  driver: CommandSchemaDriver
  version?: string
  version_id?: string
  reason: string
  expected_etag?: string
}

export type CommandSchemaOverridesRollbackResponse = {
  driver: CommandSchemaDriver
  overrides_version: string
  etag: string
}

export async function rollbackCommandSchemaOverrides(
  payload: CommandSchemaOverridesRollbackRequest
): Promise<CommandSchemaOverridesRollbackResponse> {
  const response = await apiClient.post<CommandSchemaOverridesRollbackResponse>(
    '/api/v2/settings/command-schemas/overrides/rollback/',
    payload
  )
  return response.data
}

export type CommandSchemaIssue = {
  severity: 'error' | 'warning'
  code: string
  message: string
  command_id?: string | null
  path?: string | null
}

export type CommandSchemasValidateRequest = {
  driver: CommandSchemaDriver
  catalog?: CommandSchemasOverridesCatalogV2
}

export type CommandSchemasValidateResponse = {
  driver: CommandSchemaDriver
  ok: boolean
  base_version: string | null
  base_version_id: string | null
  overrides_version: string | null
  overrides_version_id: string | null
  issues: CommandSchemaIssue[]
  errors_count: number
  warnings_count: number
}

export async function validateCommandSchemas(
  payload: CommandSchemasValidateRequest
): Promise<CommandSchemasValidateResponse> {
  const response = await apiClient.post<CommandSchemasValidateResponse>(
    '/api/v2/settings/command-schemas/validate/',
    payload
  )
  return response.data
}

export type CommandSchemasPreviewMode = 'guided' | 'manual'

export type CommandSchemasPreviewRequest = {
  driver: CommandSchemaDriver
  command_id: string
  mode?: CommandSchemasPreviewMode
  params?: Record<string, unknown>
  additional_args?: string[]
  catalog?: CommandSchemasOverridesCatalogV2
}

export type CommandSchemasPreviewResponse = {
  driver: CommandSchemaDriver
  command_id: string
  argv: string[]
  argv_masked: string[]
  risk_level?: string | null
  scope?: string | null
  disabled?: boolean | null
}

export async function previewCommandSchemas(
  payload: CommandSchemasPreviewRequest
): Promise<CommandSchemasPreviewResponse> {
  const response = await apiClient.post<CommandSchemasPreviewResponse>(
    '/api/v2/settings/command-schemas/preview/',
    payload
  )
  return response.data
}

export type CommandSchemasDiffRequest = {
  driver: CommandSchemaDriver
  command_id: string
  catalog?: CommandSchemasOverridesCatalogV2
}

export type CommandSchemasDiffItem = {
  path: string
  base_present: boolean
  base?: unknown
  effective_present: boolean
  effective?: unknown
}

export type CommandSchemasDiffResponse = {
  driver: CommandSchemaDriver
  command_id: string
  has_overrides: boolean
  changes: CommandSchemasDiffItem[]
  count: number
}

export async function diffCommandSchemas(
  payload: CommandSchemasDiffRequest
): Promise<CommandSchemasDiffResponse> {
  const response = await apiClient.post<CommandSchemasDiffResponse>(
    '/api/v2/settings/command-schemas/diff/',
    payload
  )
  return response.data
}

export type CommandSchemasAuditLogItem = {
  id: number
  created_at: string
  action: string
  outcome: string
  actor_username: string
  target_type: string
  target_id: string
  metadata: Record<string, unknown>
  error_message: string
}

export type CommandSchemasAuditListResponse = {
  items: CommandSchemasAuditLogItem[]
  count: number
  total: number
}

export async function listCommandSchemasAudit(
  filters?: { driver?: CommandSchemaDriver; limit?: number; offset?: number }
): Promise<CommandSchemasAuditListResponse> {
  const response = await apiClient.get<CommandSchemasAuditListResponse>(
    '/api/v2/settings/command-schemas/audit/',
    { params: filters }
  )
  return response.data
}
