import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Collapse,
  Col,
  Descriptions,
  Form,
  Grid,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { UploadOutlined } from '@ant-design/icons'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'
import { useSearchParams } from 'react-router-dom'

import {
  abortPoolRunPublication,
  confirmPoolRunPublication,
  createPoolRun,
  getPoolGraph,
  getPoolRunReport,
  listOrganizationPools,
  listPoolBatches,
  listPoolRuns,
  listPoolSchemaTemplates,
  previewPoolWorkflowBinding,
  retryPoolRunFailed,
  type CreatePoolRunPayload,
  type OrganizationPool,
  type PoolBatch,
  type PoolGraph,
  type PoolPublicationAttemptDiagnostics,
  type PoolRun,
  type PoolRunReadinessCheck,
  type PoolRunReadinessChecklist,
  type PoolRunReadinessBlocker,
  type PoolRunMasterDataGate,
  type PoolRunReport,
  type PoolRunRetryChainAttempt,
  type PoolRunRuntimeProjection,
  type PoolRunSafeCommandConflict,
  type PoolRunSafeCommandType,
  type PoolRunVerificationMismatch,
  type PoolSchemaTemplate,
  type PoolWorkflowBinding,
  type PoolWorkflowBindingPreview,
  type PoolWorkflowBindingPreviewSlotCoverageSummary,
} from '../../api/intercompanyPools'
import { queryKeys } from '../../api/queries/queryKeys'
import { queryClient } from '../../lib/queryClient'
import { withQueryPolicy } from '../../lib/queryRuntime'
import {
  buildTopologyCoverageContext,
  describePoolWorkflowBindingCoverage,
  summarizeTopologySlotCoverage,
  type TopologyCoverageSummary,
  type TopologyEdgeSelector,
} from './topologySlotCoverage'
import {
  resolvePoolWorkflowBindingAttachmentRevision,
  resolvePoolWorkflowBindingDecisionRefs,
  resolvePoolWorkflowBindingLifecycleWarning,
  resolvePoolWorkflowBindingProfileId,
  resolvePoolWorkflowBindingProfileLabel,
  resolvePoolWorkflowBindingProfileRevisionId,
  resolvePoolWorkflowBindingProfileRevisionNumber,
  resolvePoolWorkflowBindingProfileStatus,
  resolvePoolWorkflowBindingWorkflow,
} from './poolWorkflowBindingPresentation'
import {
  EntityTable,
  MasterDetailShell,
  PageHeader,
  RouteButton,
  WorkspacePage,
} from '../../components/platform'
import { createLocaleFormatters, getCurrentAppLocale, translateNamespace, usePoolsTranslation } from '../../i18n'
import { PoolBatchIntakeDrawer } from './PoolBatchIntakeDrawer'
import { buildPoolFactualRoute, POOL_RUNS_ROUTE } from './routes'

const { Text } = Typography
const { TextArea } = Input
const { useBreakpoint } = Grid

type CreateRunFormValues = {
  period_start: string
  period_end?: string
  direction: 'top_down' | 'bottom_up'
  mode: 'safe' | 'unsafe'
  pool_workflow_binding_id?: string
  top_down_input_mode?: 'manual' | 'batch_backed'
  starting_amount?: number
  batch_id?: string
  start_organization_id?: string
  schema_template_id?: string
  source_payload_json?: string
  source_artifact_id?: string
}

type RetryFormValues = {
  entity_name: string
  max_attempts: number
  retry_interval_seconds: number
  documents_json: string
}

type PoolRunsStage = 'create' | 'inspect' | 'safe' | 'retry'

type InFlightLoad<T> = {
  key: string
  promise: Promise<T>
}

type MasterDataRemediationTarget = {
  label: string
  href: string
}

type RouteSyncState = {
  selectedPoolId: string | null | undefined
  selectedRunId: string | null
  activeStage: PoolRunsStage
  graphDate: string
  detailOpen: boolean
}

const DEFAULT_RETRY_DOCUMENTS_JSON = JSON.stringify(
  {
    "<database_id>": [{ Amount: '100.00' }],
  },
  null,
  2
)

const DEFAULT_BOTTOM_UP_SOURCE_PAYLOAD_JSON = JSON.stringify(
  [{ inn: '730000000001', amount: '100.00' }],
  null,
  2
)

const CREATE_RUN_FORM_INITIAL_VALUES: CreateRunFormValues = {
  period_start: new Date().toISOString().slice(0, 10),
  period_end: '',
  direction: 'top_down',
  mode: 'safe',
  pool_workflow_binding_id: undefined,
  top_down_input_mode: 'manual',
  starting_amount: 100,
  batch_id: '',
  start_organization_id: undefined,
  schema_template_id: undefined,
  source_payload_json: DEFAULT_BOTTOM_UP_SOURCE_PAYLOAD_JSON,
  source_artifact_id: '',
}

const RETRY_FORM_INITIAL_VALUES: RetryFormValues = {
  entity_name: 'Document_РеализацияТоваровУслуг',
  max_attempts: 5,
  retry_interval_seconds: 0,
  documents_json: DEFAULT_RETRY_DOCUMENTS_JSON,
}

const tPools = (key: string, options?: Record<string, unknown>): string => (
  translateNamespace('pools', key, options)
)

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  validated: 'processing',
  publishing: 'processing',
  published: 'success',
  partial_success: 'warning',
  failed: 'error',
}

const STATUS_REASON_COLORS: Record<string, string> = {
  preparing: 'gold',
  awaiting_approval: 'orange',
  queued: 'blue',
}

const APPROVAL_STATE_COLORS: Record<string, string> = {
  preparing: 'gold',
  awaiting_approval: 'orange',
  approved: 'green',
  not_required: 'cyan',
}

const PUBLICATION_STEP_COLORS: Record<string, string> = {
  not_enqueued: 'default',
  queued: 'blue',
  started: 'processing',
  completed: 'success',
}

const INPUT_CONTRACT_COLORS: Record<string, string> = {
  run_input_v1: 'green',
  legacy_pre_run_input: 'orange',
}

const PUBLICATION_MAPPING_ERROR_CODES = new Set([
  'ODATA_MAPPING_NOT_CONFIGURED',
  'ODATA_MAPPING_AMBIGUOUS',
  'ODATA_PUBLICATION_AUTH_CONTEXT_INVALID',
])

const MASTER_DATA_GATE_STATUS_COLORS: Record<string, string> = {
  completed: 'success',
  failed: 'error',
  skipped: 'default',
}

const VERIFICATION_STATUS_COLORS: Record<string, string> = {
  not_verified: 'default',
  passed: 'success',
  failed: 'error',
}

const READINESS_STATUS_COLORS: Record<string, string> = {
  ready: 'success',
  not_ready: 'error',
}

const READINESS_CHECK_ORDER: PoolRunReadinessCheck['code'][] = [
  'master_data_coverage',
  'organization_party_bindings',
  'policy_completeness',
  'odata_verify_readiness',
]

const DEFAULT_STAGE: PoolRunsStage = 'create'

const getDefaultGraphDate = () => new Date().toISOString().slice(0, 10)

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const parseGraphDate = (value: string | null, fallback: string): string => (
  value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : fallback
)

const parsePoolRunsStage = (value: string | null): PoolRunsStage => (
  value === 'inspect' || value === 'safe' || value === 'retry'
    ? value
    : DEFAULT_STAGE
)

const formatDate = (value: string | null | undefined) => {
  if (!value) return '-'
  return createLocaleFormatters(getCurrentAppLocale()).dateTime(value, { fallback: '-' })
}

const formatShortId = (value: string | null | undefined) => {
  if (!value) return '-'
  return value.slice(0, 8)
}

const isPlainObject = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const resolvePoolWorkflowBindingsReadError = (
  pool: OrganizationPool | null,
): { code: string; detail: string } | null => {
  if (!isPlainObject(pool?.metadata)) {
    return null
  }
  const rawError = pool.metadata.workflow_bindings_read_error
  if (!isPlainObject(rawError)) {
    return null
  }
  const code = String(rawError.code ?? '').trim()
  const detail = String(rawError.detail ?? '').trim()
  if (!code || !detail) {
    return null
  }
  return { code, detail }
}

const getStatusColor = (status: string) => STATUS_COLORS[status] ?? 'default'
const getStatusReasonColor = (statusReason: string) => STATUS_REASON_COLORS[statusReason] ?? 'default'
const getApprovalStateColor = (approvalState: string) => APPROVAL_STATE_COLORS[approvalState] ?? 'default'
const getPublicationStepColor = (stepState: string) => PUBLICATION_STEP_COLORS[stepState] ?? 'default'
const getInputContractColor = (contractVersion: string) => INPUT_CONTRACT_COLORS[contractVersion] ?? 'default'
const getWorkflowAttemptKindColor = (attemptKind: string) => (
  attemptKind === 'initial' ? 'blue' : attemptKind === 'retry' ? 'cyan' : 'default'
)
const getWorkflowExecutionStatusColor = (status: string) => (
  status === 'completed'
    ? 'success'
    : status === 'failed' || status === 'cancelled'
      ? 'error'
      : 'processing'
)

const parseDocumentsPayload = (raw: string): Record<string, Array<Record<string, unknown>>> => {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error(tPools('runs.retry.validation.invalidJson'))
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(tPools('runs.retry.validation.objectExpected'))
  }

  const asObject = parsed as Record<string, unknown>
  const result: Record<string, Array<Record<string, unknown>>> = {}
  for (const [databaseId, rows] of Object.entries(asObject)) {
    if (!Array.isArray(rows)) {
      throw new Error(tPools('runs.retry.validation.arrayExpected', { databaseId }))
    }
    result[databaseId] = rows.map((item) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        throw new Error(tPools('runs.retry.validation.objectRowsExpected', { databaseId }))
      }
      return item as Record<string, unknown>
    })
  }
  return result
}

const parseBottomUpSourcePayload = (raw: string): Record<string, unknown> | Array<Record<string, unknown>> => {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error(translateNamespace('pools', 'runs.create.messages.invalidSourcePayloadJson'))
  }
  if (!parsed || (typeof parsed !== 'object' && !Array.isArray(parsed))) {
    throw new Error(translateNamespace('pools', 'runs.create.messages.sourcePayloadObjectOrArrayExpected'))
  }
  if (!Array.isArray(parsed)) {
    return parsed as Record<string, unknown>
  }
  return parsed.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new Error(translateNamespace('pools', 'runs.create.messages.sourcePayloadArrayItemsMustBeObjects'))
    }
    return item as Record<string, unknown>
  })
}

const buildCreateRunPayload = ({
  poolId,
  values,
}: {
  poolId: string
  values: CreateRunFormValues
}): CreatePoolRunPayload => {
  const workflowBindingId = values.pool_workflow_binding_id?.trim() || ''

  if (!workflowBindingId) {
    throw new Error(tPools('runs.create.messages.selectWorkflowBindingToStart'))
  }

  if (values.direction === 'top_down') {
    if (values.top_down_input_mode === 'batch_backed') {
      const batchId = values.batch_id?.trim() || ''
      const startOrganizationId = values.start_organization_id?.trim() || ''
      if (!batchId) {
        throw new Error(tPools('runs.create.messages.topDownBatchRequired'))
      }
      if (!startOrganizationId) {
        throw new Error(tPools('runs.create.messages.topDownStartOrganizationRequired'))
      }
      return {
        pool_id: poolId,
        pool_workflow_binding_id: workflowBindingId,
        direction: values.direction,
        period_start: values.period_start,
        period_end: values.period_end?.trim() || null,
        run_input: {
          batch_id: batchId,
          start_organization_id: startOrganizationId,
        },
        mode: values.mode,
      }
    }

    const startingAmount = Number(values.starting_amount)
    if (!Number.isFinite(startingAmount) || startingAmount <= 0) {
      throw new Error(tPools('runs.create.messages.topDownStartingAmountPositive'))
    }
    return {
      pool_id: poolId,
      pool_workflow_binding_id: workflowBindingId,
      direction: values.direction,
      period_start: values.period_start,
      period_end: values.period_end?.trim() || null,
      run_input: {
        starting_amount: startingAmount.toFixed(2),
      },
      mode: values.mode,
    }
  }

  const runInput: Extract<CreatePoolRunPayload, { direction: 'bottom_up' }>['run_input'] = {}
  const artifactId = values.source_artifact_id?.trim()
  const sourcePayloadRaw = values.source_payload_json?.trim() || ''
  if (sourcePayloadRaw.length > 0) {
    runInput.source_payload = parseBottomUpSourcePayload(sourcePayloadRaw)
  }
  if (artifactId) {
    runInput.source_artifact_id = artifactId
  }
  if (!Object.prototype.hasOwnProperty.call(runInput, 'source_payload') && !artifactId) {
    throw new Error(tPools('runs.create.messages.bottomUpPayloadOrArtifactRequired'))
  }

  return {
    pool_id: poolId,
    pool_workflow_binding_id: workflowBindingId,
    direction: values.direction,
    period_start: values.period_start,
    period_end: values.period_end?.trim() || null,
    run_input: runInput,
    mode: values.mode,
    schema_template_id: values.schema_template_id?.trim() || null,
  }
}

const resolveCreateRunFieldErrors = ({
  direction,
  detail,
}: {
  direction: CreateRunFormValues['direction']
  detail: string
}): Array<{ name: keyof CreateRunFormValues; errors: string[] }> => {
  const normalizedDetail = detail.toLowerCase()
  const fieldErrors: Array<{ name: keyof CreateRunFormValues; errors: string[] }> = []

  if (direction === 'top_down') {
    if (normalizedDetail.includes('starting_amount')) {
      fieldErrors.push({ name: 'starting_amount', errors: [detail] })
    }
    if (normalizedDetail.includes('batch_id')) {
      fieldErrors.push({ name: 'batch_id', errors: [detail] })
    }
    if (normalizedDetail.includes('start_organization_id')) {
      fieldErrors.push({ name: 'start_organization_id', errors: [detail] })
    }
  }
  if (
    direction === 'bottom_up'
    && (
      normalizedDetail.includes('source_payload')
      || normalizedDetail.includes('source_artifact_id')
      || normalizedDetail.includes('bottom_up run_input')
    )
  ) {
    fieldErrors.push({ name: 'source_payload_json', errors: [detail] })
    fieldErrors.push({ name: 'source_artifact_id', errors: [detail] })
  }
  if (normalizedDetail.includes('schema_template')) {
    fieldErrors.push({ name: 'schema_template_id', errors: [detail] })
  }
  if (normalizedDetail.includes('pool_workflow_binding')) {
    fieldErrors.push({ name: 'pool_workflow_binding_id', errors: [detail] })
  }
  return fieldErrors
}

type ProblemDetailsPayload = {
  code: string | null
  detail: string | null
  title: string | null
  status: number | null
  errors: unknown
}

const parseProblemDetails = (error: unknown): ProblemDetailsPayload | null => {
  if (!error || typeof error !== 'object') return null
  const response = (error as { response?: { data?: unknown } }).response
  const payload = response?.data
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null
  }
  const candidate = payload as {
    code?: unknown
    detail?: unknown
    title?: unknown
    status?: unknown
    errors?: unknown
  }
  const hasKnownShape = (
    typeof candidate.code === 'string'
    || typeof candidate.detail === 'string'
    || typeof candidate.title === 'string'
    || typeof candidate.status === 'number'
  )
  if (!hasKnownShape) {
    return null
  }
  return {
    code: typeof candidate.code === 'string' ? candidate.code.trim() : null,
    detail: typeof candidate.detail === 'string' ? candidate.detail.trim() : null,
    title: typeof candidate.title === 'string' ? candidate.title.trim() : null,
    status: typeof candidate.status === 'number' ? candidate.status : null,
    errors: candidate.errors,
  }
}

type PublicationMappingDiagnostic = {
  actorUsername: string | null
  targetDatabaseIds: string[]
}

const parsePublicationMappingDiagnostic = (detail: string | null): PublicationMappingDiagnostic => {
  const normalizedDetail = String(detail || '').trim()
  if (!normalizedDetail) {
    return { actorUsername: null, targetDatabaseIds: [] }
  }

  const actorUsernameMatch = normalizedDetail.match(/actor_username=([^;]+)(?:;|$)/i)
  const targetDatabaseIdsMatch = normalizedDetail.match(/target_database_ids=([A-Za-z0-9,-]+)/i)

  const actorUsername = actorUsernameMatch?.[1]?.trim() || null
  const targetDatabaseIds = (targetDatabaseIdsMatch?.[1] || '')
    .split(',')
    .map((value) => value.trim())
    .filter((value) => value.length > 0)

  return { actorUsername, targetDatabaseIds }
}

const formatTargetDatabaseLabel = (targetDatabaseIds: string[]): string | null => {
  if (targetDatabaseIds.length === 0) {
    return null
  }
  if (targetDatabaseIds.length === 1) {
    return tPools('runs.create.problemMessages.targetDatabaseSingle', { databaseId: targetDatabaseIds[0] })
  }
  return tPools('runs.create.problemMessages.targetDatabaseMany', { databaseIds: targetDatabaseIds.join(', ') })
}

const resolveCreateRunProblemCodeMessage = (code: string | null): string | null => {
  if (!code) {
    return null
  }
  switch (code) {
    case 'VALIDATION_ERROR':
      return tPools('runs.create.problemMessages.validationError')
    case 'TENANT_CONTEXT_REQUIRED':
      return tPools('runs.create.problemMessages.tenantContextRequired')
    case 'POOL_NOT_FOUND':
      return tPools('runs.create.problemMessages.poolNotFound')
    case 'POOL_WORKFLOW_BINDING_REQUIRED':
      return tPools('runs.create.problemMessages.workflowBindingRequired')
    case 'POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID':
      return tPools('runs.create.problemMessages.topologyAliasInvalid')
    case 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING':
      return tPools('runs.create.problemMessages.organizationPartyBindingMissing')
    case 'MASTER_DATA_PARTY_ROLE_MISSING':
      return tPools('runs.create.problemMessages.partyRoleMissing')
    case 'POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING':
      return tPools('runs.create.problemMessages.bindingProfileRefsMissing')
    case 'POOL_WORKFLOW_BINDING_NOT_FOUND':
      return tPools('runs.create.problemMessages.bindingNotFound')
    case 'POOL_WORKFLOW_BINDING_NOT_RESOLVED':
      return tPools('runs.create.problemMessages.bindingNotResolved')
    case 'POOL_WORKFLOW_BINDING_AMBIGUOUS':
      return tPools('runs.create.problemMessages.bindingAmbiguous')
    case 'POOL_WORKFLOW_BINDING_INVALID':
      return tPools('runs.create.problemMessages.bindingInvalid')
    case 'SCHEMA_TEMPLATE_NOT_FOUND':
      return tPools('runs.create.problemMessages.schemaTemplateNotFound')
    case 'ODATA_MAPPING_NOT_CONFIGURED':
      return tPools('runs.create.problemMessages.odataMappingNotConfigured')
    case 'ODATA_MAPPING_AMBIGUOUS':
      return tPools('runs.create.problemMessages.odataMappingAmbiguous')
    case 'ODATA_PUBLICATION_AUTH_CONTEXT_INVALID':
      return tPools('runs.create.problemMessages.odataPublicationAuthContextInvalid')
    default:
      return null
  }
}

const resolvePublicationMappingProblemMessage = (
  problem: ProblemDetailsPayload
): string | null => {
  if (!problem.code || !PUBLICATION_MAPPING_ERROR_CODES.has(problem.code)) {
    return null
  }

  const { actorUsername, targetDatabaseIds } = parsePublicationMappingDiagnostic(problem.detail)
  const targetLabel = formatTargetDatabaseLabel(targetDatabaseIds)

  if (problem.code === 'ODATA_MAPPING_NOT_CONFIGURED') {
    if (actorUsername && targetLabel) {
      return tPools('runs.create.problemMessages.odataActorMappingNotConfigured', {
        actorUsername,
        targetLabel,
      })
    }
    if (targetLabel) {
      return tPools('runs.create.problemMessages.odataTargetMappingNotConfigured', {
        targetLabel,
      })
    }
  }

  const codeMessage = resolveCreateRunProblemCodeMessage(problem.code)
  return codeMessage ?? null
}

const resolveCreateRunProblemMessage = (
  problem: ProblemDetailsPayload,
  fallbackMessage: string
): string => {
  const publicationMappingMessage = resolvePublicationMappingProblemMessage(problem)
  if (publicationMappingMessage) {
    return publicationMappingMessage
  }
  const codeMessage = resolveCreateRunProblemCodeMessage(problem.code)
  if (codeMessage) {
    return codeMessage
  }
  if (problem.detail && problem.detail.length > 0) {
    return problem.detail
  }
  if (problem.title && problem.title.length > 0) {
    return problem.title
  }
  return fallbackMessage
}

const resolveCreateRunPageLevelMessage = ({
  problem,
  fallbackMessage,
  hasFieldErrors,
}: {
  problem: ProblemDetailsPayload
  fallbackMessage: string
  hasFieldErrors: boolean
}): string => {
  if (problem.code === 'VALIDATION_ERROR' && problem.detail && !hasFieldErrors) {
    return problem.detail
  }
  return resolveCreateRunProblemMessage(problem, fallbackMessage)
}

const parseReadinessProblemBlockers = (problem: ProblemDetailsPayload | null): PoolRunReadinessBlocker[] => {
  if (!problem || !Array.isArray(problem.errors)) {
    return []
  }

  const blockers: PoolRunReadinessBlocker[] = []
  for (const candidate of problem.errors) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
      continue
    }
    const raw = candidate as Record<string, unknown>
    const rawEdgeRef = raw.edge_ref && typeof raw.edge_ref === 'object' && !Array.isArray(raw.edge_ref)
      ? raw.edge_ref as Record<string, unknown>
      : null
    const parentNodeId = typeof rawEdgeRef?.parent_node_id === 'string' ? rawEdgeRef.parent_node_id : null
    const childNodeId = typeof rawEdgeRef?.child_node_id === 'string' ? rawEdgeRef.child_node_id : null
    blockers.push({
      code: typeof raw.code === 'string' ? raw.code : null,
      detail: typeof raw.detail === 'string' ? raw.detail : null,
      kind: typeof raw.kind === 'string' ? raw.kind : null,
      entity_name: typeof raw.entity_name === 'string' ? raw.entity_name : null,
      field_or_table_path: typeof raw.field_or_table_path === 'string' ? raw.field_or_table_path : null,
      database_id: typeof raw.database_id === 'string' ? raw.database_id : null,
      organization_id: typeof raw.organization_id === 'string' ? raw.organization_id : null,
      edge_ref: parentNodeId && childNodeId
        ? {
          parent_node_id: parentNodeId,
          child_node_id: childNodeId,
        }
        : undefined,
      participant_side: typeof raw.participant_side === 'string' ? raw.participant_side : null,
      required_role: typeof raw.required_role === 'string' ? raw.required_role : null,
      diagnostic: raw.diagnostic && typeof raw.diagnostic === 'object' && !Array.isArray(raw.diagnostic)
        ? raw.diagnostic as Record<string, unknown>
        : null,
    })
  }
  return blockers
}

const resolveSafeCommandProblemMessage = (
  problem: ProblemDetailsPayload,
  fallbackMessage: string
): string => {
  if (problem.code === 'POOL_RUN_READINESS_BLOCKED') {
    const blockers = parseReadinessProblemBlockers(problem)
    const primary = blockers[0]
    if (primary?.detail && primary?.code) {
      return `${primary.detail} (${primary.code})`
    }
  }
  if (problem.detail && problem.detail.length > 0) {
    return problem.detail
  }
  if (problem.title && problem.title.length > 0) {
    return problem.title
  }
  return fallbackMessage
}

const matchesReadinessCheck = (
  checkCode: PoolRunReadinessCheck['code'],
  blocker: PoolRunReadinessBlocker
): boolean => {
  const code = typeof blocker.code === 'string' ? blocker.code.toUpperCase() : ''
  if (!code) {
    return false
  }
  if (checkCode === 'organization_party_bindings') {
    return code === 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING'
      || code === 'MASTER_DATA_PARTY_ROLE_MISSING'
  }
  if (checkCode === 'policy_completeness') {
    return code === 'POOL_DOCUMENT_POLICY_MAPPING_INVALID'
      || code === 'POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID'
  }
  if (checkCode === 'odata_verify_readiness') {
    return code === 'ODATA_MAPPING_NOT_CONFIGURED'
      || code === 'ODATA_MAPPING_AMBIGUOUS'
      || code === 'ODATA_PUBLICATION_AUTH_CONTEXT_INVALID'
      || code.startsWith('ODATA_')
  }
  if (checkCode === 'master_data_coverage') {
    return code.startsWith('MASTER_DATA_')
      && code !== 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING'
      && code !== 'MASTER_DATA_PARTY_ROLE_MISSING'
  }
  return false
}

const buildLegacyReadinessChecklist = (
  blockers: PoolRunReadinessBlocker[]
): PoolRunReadinessChecklist => {
  const status = blockers.length === 0 ? 'ready' : 'not_ready'
  return {
    status,
    checks: READINESS_CHECK_ORDER.map((checkCode) => {
      const scopedBlockers = blockers.filter((blocker) => matchesReadinessCheck(checkCode, blocker))
      const blockerCodes = Array.from(new Set(
        scopedBlockers
          .map((item) => (typeof item.code === 'string' ? item.code : null))
          .filter((item): item is string => Boolean(item))
      ))
      return {
        code: checkCode,
        status: scopedBlockers.length === 0 && status === 'ready' ? 'ready' : 'not_ready',
        blocker_codes: blockerCodes,
        blockers: scopedBlockers,
      }
    }),
  }
}

const resolveReadinessCheckLabel = (checkCode: PoolRunReadinessCheck['code']): string => {
  switch (checkCode) {
    case 'master_data_coverage':
      return tPools('runs.inspect.readiness.checkLabels.masterDataCoverage')
    case 'organization_party_bindings':
      return tPools('runs.inspect.readiness.checkLabels.organizationPartyBindings')
    case 'policy_completeness':
      return tPools('runs.inspect.readiness.checkLabels.policyCompleteness')
    case 'odata_verify_readiness':
      return tPools('runs.inspect.readiness.checkLabels.odataVerifyReadiness')
    default:
      return checkCode
  }
}

const resolveInputContractVersion = (run: PoolRun): string => {
  if (run.input_contract_version) {
    return run.input_contract_version
  }
  return run.run_input ? 'run_input_v1' : 'legacy_pre_run_input'
}

const summarizeRunInput = (run: PoolRun): string => {
  if (!run.run_input || typeof run.run_input !== 'object') {
    return 'null'
  }
  const keys = Object.keys(run.run_input)
  if (keys.length === 0) {
    return '{}'
  }
  const preview = keys.slice(0, 2).join(', ')
  return keys.length > 2 ? `${preview}, +${keys.length - 2}` : preview
}

const resolveMasterDataGateHint = (errorCode: string | null): string | null => {
  if (!errorCode) {
    return null
  }
  switch (errorCode) {
    case 'MASTER_DATA_GATE_CONFIG_INVALID':
      return tPools('runs.inspect.masterDataGate.hints.configInvalid')
    case 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING':
      return tPools('runs.inspect.masterDataGate.hints.organizationPartyBindingMissing')
    case 'MASTER_DATA_PARTY_ROLE_MISSING':
      return tPools('runs.inspect.masterDataGate.hints.partyRoleMissing')
    case 'MASTER_DATA_ENTITY_NOT_FOUND':
      return tPools('runs.inspect.masterDataGate.hints.entityNotFound')
    case 'MASTER_DATA_BINDING_AMBIGUOUS':
      return tPools('runs.inspect.masterDataGate.hints.bindingAmbiguous')
    case 'MASTER_DATA_BINDING_CONFLICT':
      return tPools('runs.inspect.masterDataGate.hints.bindingConflict')
    case 'MASTER_DATA_DEDUPE_REVIEW_REQUIRED':
      return tPools('runs.inspect.masterDataGate.hints.dedupeReviewRequired')
    case 'POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID':
      return tPools('runs.inspect.masterDataGate.hints.topologyAliasInvalid')
    case 'POOL_DOCUMENT_POLICY_MAPPING_INVALID':
      return tPools('runs.inspect.masterDataGate.hints.policyMappingInvalid')
    default:
      return null
  }
}

const resolveMasterDataWorkspaceTabLabel = (tab: string): string => {
  switch (tab) {
    case 'party':
      return tPools('runs.inspect.masterDataGate.workspaceTabs.party')
    case 'item':
      return tPools('runs.inspect.masterDataGate.workspaceTabs.item')
    case 'contract':
      return tPools('runs.inspect.masterDataGate.workspaceTabs.contract')
    case 'tax-profile':
      return tPools('runs.inspect.masterDataGate.workspaceTabs.taxProfile')
    case 'bindings':
      return tPools('runs.inspect.masterDataGate.workspaceTabs.bindings')
    case 'dedupe-review':
      return tPools('runs.inspect.masterDataGate.workspaceTabs.dedupeReview')
    default:
      return tPools('runs.inspect.masterDataGate.workspaceTabs.masterData')
  }
}

const buildMasterDataWorkspaceHref = ({
  tab,
  entityType,
  canonicalId,
  databaseId,
  role,
  clusterId,
  reviewItemId,
}: {
  tab: string
  entityType?: string
  canonicalId?: string
  databaseId?: string
  role?: string
  clusterId?: string
  reviewItemId?: string
}): string => {
  const params = new URLSearchParams()
  params.set('tab', tab)
  if (entityType) {
    params.set('entityType', entityType)
  }
  if (canonicalId) {
    params.set('canonicalId', canonicalId)
  }
  if (databaseId) {
    params.set('databaseId', databaseId)
  }
  if (role) {
    params.set('role', role)
  }
  if (clusterId) {
    params.set('clusterId', clusterId)
  }
  if (reviewItemId) {
    params.set('reviewItemId', reviewItemId)
  }
  return `/pools/master-data?${params.toString()}`
}

const resolveMasterDataEntityWorkspaceTab = (entityType: string): string | null => {
  switch (entityType) {
    case 'organization':
    case 'party':
      return 'party'
    case 'item':
      return 'item'
    case 'contract':
      return 'contract'
    case 'tax_profile':
      return 'tax-profile'
    default:
      return null
  }
}

const normalizeMasterDataBindingEntityType = (entityType: string): string => {
  if (entityType === 'organization') {
    return 'party'
  }
  return entityType
}

const resolveMasterDataRemediationTarget = ({
  code,
  diagnostic,
  requiredRole,
}: {
  code: string | null
  diagnostic: unknown
  requiredRole?: string | null
}): MasterDataRemediationTarget | null => {
  if (!code || !diagnostic || typeof diagnostic !== 'object' || Array.isArray(diagnostic)) {
    return null
  }
  const payload = diagnostic as Record<string, unknown>
  const entityType = typeof payload.entity_type === 'string' ? payload.entity_type.trim() : ''
  const canonicalId = typeof payload.canonical_id === 'string' ? payload.canonical_id.trim() : ''
  const databaseId = typeof payload.target_database_id === 'string' ? payload.target_database_id.trim() : ''
  const clusterId = typeof payload.dedupe_cluster_id === 'string' ? payload.dedupe_cluster_id.trim() : ''
  const reviewItemId = typeof payload.dedupe_review_item_id === 'string' ? payload.dedupe_review_item_id.trim() : ''

  if (code === 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING' || code === 'MASTER_DATA_PARTY_ROLE_MISSING') {
    return {
      label: tPools('runs.inspect.masterDataGate.remediation.openBindingsWorkspace'),
      href: buildMasterDataWorkspaceHref({
        tab: 'bindings',
        entityType: normalizeMasterDataBindingEntityType(entityType || 'party'),
        canonicalId,
        databaseId,
        role: requiredRole || (code === 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING' ? 'organization' : undefined),
      }),
    }
  }

  if (code === 'MASTER_DATA_BINDING_AMBIGUOUS' || code === 'MASTER_DATA_BINDING_CONFLICT') {
    return {
      label: tPools('runs.inspect.masterDataGate.remediation.openBindingsWorkspace'),
      href: buildMasterDataWorkspaceHref({
        tab: 'bindings',
        entityType: normalizeMasterDataBindingEntityType(entityType),
        canonicalId,
        databaseId,
      }),
    }
  }

  if (code === 'MASTER_DATA_DEDUPE_REVIEW_REQUIRED') {
    return {
      label: tPools('runs.inspect.masterDataGate.remediation.openDedupeReview'),
      href: buildMasterDataWorkspaceHref({
        tab: 'dedupe-review',
        entityType,
        canonicalId,
        databaseId,
        clusterId,
        reviewItemId,
      }),
    }
  }

  if (code === 'MASTER_DATA_ENTITY_NOT_FOUND') {
    const tab = resolveMasterDataEntityWorkspaceTab(entityType)
    if (!tab) {
      return {
        label: tPools('runs.inspect.masterDataGate.remediation.openMasterDataWorkspace'),
        href: '/pools/master-data',
      }
    }
    return {
      label: tPools('runs.inspect.masterDataGate.remediation.openWorkspace', {
        workspace: resolveMasterDataWorkspaceTabLabel(tab),
      }),
      href: buildMasterDataWorkspaceHref({
        tab,
        entityType,
        canonicalId,
        databaseId,
        role: entityType === 'organization' ? 'organization' : undefined,
      }),
    }
  }

  return null
}

const buildMasterDataGateContextLines = (
  masterDataGate: Exclude<PoolRunMasterDataGate, null | undefined>
): string[] => {
  if (!masterDataGate.diagnostic || typeof masterDataGate.diagnostic !== 'object' || Array.isArray(masterDataGate.diagnostic)) {
    return []
  }
  const diagnostic = masterDataGate.diagnostic as Record<string, unknown>
  const lines: string[] = []

  const entityType = typeof diagnostic.entity_type === 'string' ? diagnostic.entity_type : ''
  const canonicalId = typeof diagnostic.canonical_id === 'string' ? diagnostic.canonical_id : ''
  const targetDatabaseId = typeof diagnostic.target_database_id === 'string' ? diagnostic.target_database_id : ''
  if (entityType || canonicalId || targetDatabaseId) {
    lines.push(
      `entity_type=${entityType || '-'} canonical_id=${canonicalId || '-'} target_database_id=${targetDatabaseId || '-'}`
    )
  }

  const runtimeKey = typeof diagnostic.runtime_key === 'string' ? diagnostic.runtime_key : ''
  const source = typeof diagnostic.source === 'string' ? diagnostic.source : ''
  const rawValue = typeof diagnostic.raw_value === 'string' ? diagnostic.raw_value : ''
  if (runtimeKey || source || rawValue) {
    lines.push(`runtime_key=${runtimeKey || '-'} source=${source || '-'} raw_value=${rawValue || '-'}`)
  }

  const missingBindings = Array.isArray(diagnostic.missing_organization_bindings)
    ? diagnostic.missing_organization_bindings
    : []
  if (missingBindings.length > 0) {
    lines.push(`missing_organization_bindings=${missingBindings.length}`)
    missingBindings.slice(0, 3).forEach((item, index) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        return
      }
      const row = item as Record<string, unknown>
      const organizationId = typeof row.organization_id === 'string' ? row.organization_id : '-'
      const name = typeof row.name === 'string' ? row.name : '-'
      const databaseId = typeof row.database_id === 'string' ? row.database_id : '-'
      lines.push(`#${index + 1}: org=${organizationId} name=${name} database_id=${databaseId}`)
    })
    if (missingBindings.length > 3) {
      lines.push(`... +${missingBindings.length - 3} more`)
    }
  }

  return lines
}

const resolveReadinessBlockerHint = (blocker: PoolRunReadinessBlocker): string | null => {
  const code = typeof blocker.code === 'string' ? blocker.code : null
  if (!code) {
    return null
  }
  return resolveMasterDataGateHint(code)
}

const buildReadinessBlockerContextLines = (blocker: PoolRunReadinessBlocker): string[] => {
  const lines: string[] = []

  if (blocker.edge_ref && typeof blocker.edge_ref === 'object' && !Array.isArray(blocker.edge_ref)) {
    const parentNodeId = typeof blocker.edge_ref.parent_node_id === 'string' ? blocker.edge_ref.parent_node_id : '-'
    const childNodeId = typeof blocker.edge_ref.child_node_id === 'string' ? blocker.edge_ref.child_node_id : '-'
    if (parentNodeId !== '-' || childNodeId !== '-') {
      lines.push(`edge_ref=parent_node_id=${parentNodeId} child_node_id=${childNodeId}`)
    }
  }
  if (blocker.participant_side) {
    lines.push(`participant_side=${blocker.participant_side}`)
  }
  if (blocker.required_role) {
    lines.push(`required_role=${blocker.required_role}`)
  }
  if (blocker.entity_name || blocker.field_or_table_path) {
    lines.push(`entity=${blocker.entity_name || '-'} path=${blocker.field_or_table_path || '-'}`)
  }
  if (blocker.database_id || blocker.organization_id) {
    lines.push(`database_id=${blocker.database_id || '-'} organization_id=${blocker.organization_id || '-'}`)
  }

  const diagnostic = blocker.diagnostic
  if (diagnostic && typeof diagnostic === 'object' && !Array.isArray(diagnostic)) {
    for (const [key, value] of Object.entries(diagnostic).slice(0, 3)) {
      lines.push(`${key}=${String(value)}`)
    }
  }

  return lines
}

const buildFlowLayout = (graph: PoolGraph | null): { nodes: Node[]; edges: Edge[] } => {
  if (!graph) {
    return { nodes: [], edges: [] }
  }
  const depthByNodeId = new Map<string, number>()
  for (const node of graph.nodes) {
    if (node.is_root) {
      depthByNodeId.set(node.node_version_id, 0)
    }
  }
  for (let i = 0; i < graph.nodes.length; i += 1) {
    let changed = false
    for (const edge of graph.edges) {
      const parentDepth = depthByNodeId.get(edge.parent_node_version_id)
      if (parentDepth === undefined) continue
      const nextDepth = parentDepth + 1
      const currentDepth = depthByNodeId.get(edge.child_node_version_id)
      if (currentDepth === undefined || nextDepth > currentDepth) {
        depthByNodeId.set(edge.child_node_version_id, nextDepth)
        changed = true
      }
    }
    if (!changed) break
  }

  const groupedByDepth = new Map<number, typeof graph.nodes>()
  for (const node of graph.nodes) {
    const depth = depthByNodeId.get(node.node_version_id) ?? 0
    const current = groupedByDepth.get(depth) ?? []
    current.push(node)
    groupedByDepth.set(depth, current)
  }

  const flowNodes: Node[] = []
  for (const [depth, nodesInDepth] of groupedByDepth.entries()) {
    nodesInDepth.forEach((node, index) => {
      flowNodes.push({
        id: node.node_version_id,
        position: { x: depth * 260, y: index * 110 },
        data: { label: `${node.name}\n${node.inn}` },
        style: {
          border: node.is_root ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 8,
          padding: 8,
          width: 220,
          background: '#fff',
          fontSize: 12,
          whiteSpace: 'pre-line',
        },
      })
    })
  }

  const flowEdges: Edge[] = graph.edges.map((edge) => ({
    id: edge.edge_version_id,
    source: edge.parent_node_version_id,
    target: edge.child_node_version_id,
    label: `w=${edge.weight}`,
    animated: false,
  }))

  return { nodes: flowNodes, edges: flowEdges }
}

const generateIdempotencyKey = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `pool-safe-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const parseSafeCommandConflict = (error: unknown): PoolRunSafeCommandConflict | null => {
  if (!error || typeof error !== 'object') return null
  const response = (error as { response?: { data?: unknown } }).response
  const payload = response?.data
  if (!payload || typeof payload !== 'object') return null

  const candidate = payload as Partial<PoolRunSafeCommandConflict>
  if (
    typeof candidate.error_code === 'string'
    && typeof candidate.error_message === 'string'
    && typeof candidate.conflict_reason === 'string'
  ) {
    return {
      success: Boolean(candidate.success),
      error_code: candidate.error_code,
      error_message: candidate.error_message,
      conflict_reason: candidate.conflict_reason,
      retryable: Boolean(candidate.retryable),
      run_id: String(candidate.run_id ?? ''),
    }
  }
  return null
}

const matchesWorkflowBindingForCreateRun = ({
  binding,
  direction,
  mode,
  periodStart,
}: {
  binding: NonNullable<OrganizationPool['workflow_bindings']>[number]
  direction: CreateRunFormValues['direction']
  mode: CreateRunFormValues['mode']
  periodStart: string
}): boolean => {
  if ((binding.status ?? 'draft') !== 'active') {
    return false
  }
  const selector = binding.selector ?? {}
  if (selector.direction && selector.direction !== direction) {
    return false
  }
  if (selector.mode && selector.mode !== mode) {
    return false
  }
  const effectiveFrom = binding.effective_from?.trim() || ''
  if (effectiveFrom && periodStart && periodStart < effectiveFrom) {
    return false
  }
  const effectiveTo = binding.effective_to?.trim() || ''
  if (effectiveTo && periodStart && periodStart > effectiveTo) {
    return false
  }
  return Boolean(binding.binding_id)
}

const formatWorkflowBindingOptionLabel = (
  binding: NonNullable<OrganizationPool['workflow_bindings']>[number]
): string => {
  const workflow = resolvePoolWorkflowBindingWorkflow(binding)
  const workflowName = workflow?.workflow_name || workflow?.workflow_definition_key || tPools('runs.common.workflowFallback')
  const bindingId = binding.binding_id || tPools('runs.common.bindingFallback')
  const profileRevision = binding.binding_profile_revision_number != null
    ? tPools('runs.common.profileRevision', { revision: binding.binding_profile_revision_number })
    : ''
  const attachmentRevision = binding.revision != null
    ? tPools('runs.common.attachmentRevision', { revision: binding.revision })
    : ''
  return [workflowName, profileRevision, attachmentRevision, bindingId.slice(0, 8)]
    .filter((part) => part && part.trim().length > 0)
    .join(' · ')
}

const formatWorkflowBindingScope = (binding: PoolWorkflowBinding | null | undefined): string => {
  const selector = binding?.selector ?? {}
  const parts: string[] = []
  if (selector.direction) {
    parts.push(tPools('runs.common.bindingScopeDirection', { value: selector.direction }))
  }
  if (selector.mode) {
    parts.push(tPools('runs.common.bindingScopeMode', { value: selector.mode }))
  }
  if (selector.tags && selector.tags.length > 0) {
    parts.push(tPools('runs.common.bindingScopeTags', { value: selector.tags.join(', ') }))
  }
  return parts.length > 0 ? parts.join(' · ') : tPools('runs.common.unscoped')
}

const formatWorkflowBindingEffectivePeriod = (binding: PoolWorkflowBinding | null | undefined): string => {
  if (!binding?.effective_from) {
    return '-'
  }
  return binding.effective_to
    ? `${binding.effective_from}..${binding.effective_to}`
    : `${binding.effective_from}..open`
}

const resolveWorkflowLineageName = ({
  binding,
  runtimeProjection,
  workflowTemplateName,
}: {
  binding: PoolWorkflowBinding | null | undefined
  runtimeProjection: PoolRunRuntimeProjection | null | undefined
  workflowTemplateName: string | null | undefined
}): string => (
  resolvePoolWorkflowBindingWorkflow(binding)?.workflow_name
  || runtimeProjection?.workflow_binding.workflow_name
  || workflowTemplateName
  || '-'
)

const buildTopologyEdgeSelectors = (graph: PoolGraph | null): TopologyEdgeSelector[] => {
  if (!graph) {
    return []
  }
  const nodeByVersionId = new Map(
    graph.nodes.map((node) => [node.node_version_id, node])
  )
  return graph.edges.map((edge, index) => {
    const rawMetadata = edge.metadata
    const metadata = rawMetadata && typeof rawMetadata === 'object' && !Array.isArray(rawMetadata)
      ? rawMetadata as Record<string, unknown>
      : {}
    const slotKey = typeof metadata.document_policy_key === 'string'
      ? metadata.document_policy_key.trim()
      : ''
    const parentNode = nodeByVersionId.get(edge.parent_node_version_id)
    const childNode = nodeByVersionId.get(edge.child_node_version_id)
    const parentLabel = String(parentNode?.name || parentNode?.organization_id || edge.parent_node_version_id).trim()
    const childLabel = String(childNode?.name || childNode?.organization_id || edge.child_node_version_id).trim()
    return {
      edgeId: String(edge.edge_version_id || `${edge.parent_node_version_id}:${edge.child_node_version_id}:${index}`),
      edgeLabel: `${parentLabel} -> ${childLabel}`,
      slotKey,
    }
  })
}

const buildSlotCoverageRefs = (
  decisions: Array<{
    decision_key?: string | null
    slot_key?: string | null
    decision_table_id?: string | null
    decision_revision?: string | number | null
  }> | null | undefined
) => (
  (decisions ?? [])
    .map((decision) => {
      const slotKey = String(decision.slot_key || decision.decision_key || '').trim()
      const decisionTableId = String(decision.decision_table_id || '').trim()
      const decisionKey = String(decision.decision_key || '').trim()
      const decisionRevision = String(decision.decision_revision ?? '').trim()
      if (!slotKey || !decisionTableId || !decisionRevision) {
        return null
      }
      return {
        slotKey,
        refLabel: `${decisionTableId} (${decisionKey || 'decision'}) r${decisionRevision}`,
      }
    })
    .filter((slotRef): slotRef is { slotKey: string; refLabel: string } => Boolean(slotRef))
)

const buildTopologyCoverageSummary = ({
  bindingLabel,
  decisions,
  detail,
  selectors,
  source,
}: {
  bindingLabel: string
  decisions: Array<{
    decision_key?: string | null
    slot_key?: string | null
    decision_table_id?: string | null
    decision_revision?: string | number | null
  }> | null | undefined
  detail: string
  selectors: TopologyEdgeSelector[]
  source: 'selected' | 'auto'
}): TopologyCoverageSummary => summarizeTopologySlotCoverage(
  selectors,
  buildTopologyCoverageContext({
    bindingLabel,
    detail,
    slotRefs: buildSlotCoverageRefs(decisions),
    source,
  })
)

function TopologySlotCoveragePanel({
  emptyMessage,
  itemTestIdPrefix,
  resolvedMessage,
  summary,
  summaryTestId,
}: {
  emptyMessage: string
  itemTestIdPrefix?: string
  resolvedMessage: string
  summary: TopologyCoverageSummary | null
  summaryTestId?: string
}) {
  if (!summary || summary.totalEdges === 0) {
    return <Text type="secondary">{emptyMessage}</Text>
  }
  const unresolvedItems = summary.items.filter((item) => item.coverage.status !== 'resolved')
  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <Space size={[4, 4]} wrap data-testid={summaryTestId}>
        <Tag>{tPools('common.topologyCoverage.totalEdges', { count: summary.totalEdges })}</Tag>
        <Tag color="success">{tPools('common.topologyCoverage.resolvedCount', { count: summary.counts.resolved })}</Tag>
        {summary.counts.missing_slot > 0 ? (
          <Tag color="error">{tPools('common.topologyCoverage.missingSlotCount', { count: summary.counts.missing_slot })}</Tag>
        ) : null}
        {summary.counts.missing_selector > 0 ? (
          <Tag color="default">{tPools('common.topologyCoverage.missingSelectorCount', { count: summary.counts.missing_selector })}</Tag>
        ) : null}
        {summary.counts.ambiguous_slot > 0 ? (
          <Tag color="warning">{tPools('common.topologyCoverage.ambiguousSlotCount', { count: summary.counts.ambiguous_slot })}</Tag>
        ) : null}
        {summary.counts.ambiguous_context > 0 ? (
          <Tag color="warning">{tPools('common.topologyCoverage.ambiguousContextCount', { count: summary.counts.ambiguous_context })}</Tag>
        ) : null}
        {summary.counts.unavailable_context > 0 ? (
          <Tag color="default">{tPools('common.topologyCoverage.unavailableContextCount', { count: summary.counts.unavailable_context })}</Tag>
        ) : null}
      </Space>
      {unresolvedItems.length === 0 ? (
        <Text type="secondary">{resolvedMessage}</Text>
      ) : (
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          {unresolvedItems.map((item) => (
            <Text
              key={`${item.edgeId}:${item.coverage.status}`}
              type="secondary"
              data-testid={itemTestIdPrefix ? `${itemTestIdPrefix}-${item.edgeId}` : undefined}
            >
              {`${item.edgeLabel} · ${item.slotKey || tPools('common.topologyCoverage.slotNotSet')} · ${item.coverage.label}`}
            </Text>
          ))}
        </Space>
      )}
    </Space>
  )
}

const normalizePreviewSlotCoverageSummary = (
  summary: PoolWorkflowBindingPreviewSlotCoverageSummary | null | undefined
): TopologyCoverageSummary | null => {
  if (!summary) {
    return null
  }
  return {
    totalEdges: Number(summary.total_edges || 0),
    counts: {
      resolved: Number(summary.counts?.resolved || 0),
      missing_selector: Number(summary.counts?.missing_selector || 0),
      missing_slot: Number(summary.counts?.missing_slot || 0),
      ambiguous_slot: Number(summary.counts?.ambiguous_slot || 0),
      ambiguous_context: Number(summary.counts?.ambiguous_context || 0),
      unavailable_context: Number(summary.counts?.unavailable_context || 0),
    },
    items: Array.isArray(summary.items)
      ? summary.items.map((item) => ({
        edgeId: String(item.edge_id || ''),
        edgeLabel: String(item.edge_label || '').trim(),
        slotKey: String(item.slot_key || '').trim(),
        coverage: {
          code: item.coverage.code ?? null,
          status: item.coverage.status,
          label: String(item.coverage.label || '').trim(),
          detail: String(item.coverage.detail || '').trim(),
        },
      }))
      : [],
  }
}

export function PoolRunsPage() {
  const { message } = AntApp.useApp()
  const { t, ready } = usePoolsTranslation()
  const stageLabels: Record<PoolRunsStage, string> = {
    create: t('runs.page.stages.create'),
    inspect: t('runs.page.stages.inspect'),
    safe: t('runs.page.stages.safe'),
    retry: t('runs.page.stages.retry'),
  }
  const stageDetailTitles: Record<PoolRunsStage, string> = {
    create: t('runs.page.detailTitles.create'),
    inspect: t('runs.page.detailTitles.inspect'),
    safe: t('runs.page.detailTitles.safe'),
    retry: t('runs.page.detailTitles.retry'),
  }
  const stageMessages: Record<PoolRunsStage, string> = {
    create: t('runs.page.stageMessages.create'),
    inspect: t('runs.page.stageMessages.inspect'),
    safe: t('runs.page.stageMessages.safe'),
    retry: t('runs.page.stageMessages.retry'),
  }
  const screens = useBreakpoint()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const pendingRouteSyncRef = useRef<RouteSyncState | null>(null)
  const previousStageRef = useRef<PoolRunsStage>(DEFAULT_STAGE)
  const previousSelectedPoolIdRef = useRef<string | null | undefined>(undefined)
  const previousSelectedRunIdRef = useRef<string | null>(null)
  const defaultGraphDateRef = useRef(getDefaultGraphDate())
  const poolFromUrl = normalizeRouteParam(searchParams.get('pool'))
  const runFromUrl = normalizeRouteParam(searchParams.get('run'))
  const stageFromUrl = parsePoolRunsStage(searchParams.get('stage'))
  const graphDateFromUrl = parseGraphDate(searchParams.get('date'), defaultGraphDateRef.current)
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [receiptBatches, setReceiptBatches] = useState<PoolBatch[]>([])
  const [schemaTemplates, setSchemaTemplates] = useState<PoolSchemaTemplate[]>([])
  const [hasResolvedPoolsLoad, setHasResolvedPoolsLoad] = useState(false)
  const [selectedPoolId, setSelectedPoolId] = useState<string | null | undefined>(
    () => poolFromUrl ?? undefined
  )
  const [graphDate, setGraphDate] = useState<string>(graphDateFromUrl)
  const [graph, setGraph] = useState<PoolGraph | null>(null)
  const [runs, setRuns] = useState<PoolRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(() => runFromUrl)
  const [report, setReport] = useState<PoolRunReport | null>(null)
  const [loadingPools, setLoadingPools] = useState(false)
  const [loadingReceiptBatches, setLoadingReceiptBatches] = useState(false)
  const [loadingSchemaTemplates, setLoadingSchemaTemplates] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [loadingReport, setLoadingReport] = useState(false)
  const [creatingRun, setCreatingRun] = useState(false)
  const [previewingBinding, setPreviewingBinding] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [safeActionLoading, setSafeActionLoading] = useState<PoolRunSafeCommandType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [bindingPreview, setBindingPreview] = useState<PoolWorkflowBindingPreview | null>(null)
  const [activeStageTab, setActiveStageTab] = useState<PoolRunsStage>(stageFromUrl)
  const [isRunDetailOpen, setIsRunDetailOpen] = useState(detailOpenFromUrl)
  const [isBatchIntakeDrawerOpen, setIsBatchIntakeDrawerOpen] = useState(false)
  const [createForm] = Form.useForm<CreateRunFormValues>()
  const [retryForm] = Form.useForm<RetryFormValues>()
  const selectedPoolIdRef = useRef<string | null | undefined>(selectedPoolId)
  const selectedRunIdRef = useRef<string | null>(selectedRunId)
  const loadRunsRequestRef = useRef(0)
  const loadReportRequestRef = useRef(0)
  const loadGraphInFlightRef = useRef<InFlightLoad<PoolGraph> | null>(null)
  const loadRunsInFlightRef = useRef<InFlightLoad<PoolRun[]> | null>(null)
  const loadReportInFlightRef = useRef<InFlightLoad<PoolRunReport> | null>(null)

  selectedPoolIdRef.current = selectedPoolId
  selectedRunIdRef.current = selectedRunId
  if (previousSelectedPoolIdRef.current === undefined) {
    previousSelectedPoolIdRef.current = selectedPoolId
  }

  const selectedRun = useMemo(
    () => runs.find((item) => item.id === selectedRunId) ?? null,
    [runs, selectedRunId]
  )

  const runDetails = useMemo(() => {
    if (report?.run && report.run.id === selectedRunId) {
      return report.run
    }
    return selectedRun
  }, [report, selectedRun, selectedRunId])

  const flow = useMemo(() => buildFlowLayout(graph), [graph])
  const topologyEdgeSelectors = useMemo(
    () => buildTopologyEdgeSelectors(graph),
    [graph]
  )
  const createDirection = Form.useWatch('direction', createForm) ?? 'top_down'
  const createMode = Form.useWatch('mode', createForm) ?? 'safe'
  const createPeriodStart = Form.useWatch('period_start', createForm) ?? new Date().toISOString().slice(0, 10)
  const createPeriodEnd = Form.useWatch('period_end', createForm) ?? ''
  const createBindingId = Form.useWatch('pool_workflow_binding_id', createForm)
  const createTopDownInputMode = Form.useWatch('top_down_input_mode', createForm) ?? 'manual'
  const createStartingAmount = Form.useWatch('starting_amount', createForm)
  const createBatchId = Form.useWatch('batch_id', createForm)
  const createStartOrganizationId = Form.useWatch('start_organization_id', createForm)
  const createSchemaTemplateId = Form.useWatch('schema_template_id', createForm)
  const createSourcePayloadJson = Form.useWatch('source_payload_json', createForm)
  const createSourceArtifactId = Form.useWatch('source_artifact_id', createForm)
  const selectedPool = useMemo(
    () => pools.find((item) => item.id === selectedPoolId) ?? null,
    [pools, selectedPoolId]
  )
  const selectedPoolWorkflowBindingsReadError = useMemo(
    () => resolvePoolWorkflowBindingsReadError(selectedPool),
    [selectedPool]
  )
  const matchingWorkflowBindings = useMemo(
    () => (selectedPool?.workflow_bindings ?? []).filter((binding) => matchesWorkflowBindingForCreateRun({
      binding,
      direction: createDirection,
      mode: createMode,
      periodStart: createPeriodStart,
    })),
    [createDirection, createMode, createPeriodStart, selectedPool]
  )
  const receiptBatchWorkflowBindings = useMemo(
    () => (selectedPool?.workflow_bindings ?? []).filter((binding) => matchesWorkflowBindingForCreateRun({
      binding,
      direction: 'top_down',
      mode: 'safe',
      periodStart: createPeriodStart,
    })),
    [createPeriodStart, selectedPool]
  )
  const receiptBatchOptions = useMemo(
    () => receiptBatches.map((batch) => ({
      value: batch.id,
      label: `${batch.source_reference || formatShortId(batch.id)} · ${batch.period_start}`,
    })),
    [receiptBatches]
  )
  const receiptBatchWorkflowBindingOptions = useMemo(
    () => receiptBatchWorkflowBindings.map((binding) => ({
      value: binding.binding_id,
      label: formatWorkflowBindingOptionLabel(binding),
    })),
    [receiptBatchWorkflowBindings]
  )
  const selectedCreateBinding = useMemo(() => {
    const normalizedBindingId = String(createBindingId || '').trim()
    if (!normalizedBindingId) {
      return null
    }
    return matchingWorkflowBindings.find((binding) => binding.binding_id === normalizedBindingId) ?? null
  }, [createBindingId, matchingWorkflowBindings])
  const selectedCreateBindingWorkflow = useMemo(
    () => resolvePoolWorkflowBindingWorkflow(selectedCreateBinding),
    [selectedCreateBinding]
  )
  const activeTopologyOrganizations = useMemo(() => {
    const deduped = new Map<string, { value: string; label: string }>()
    for (const node of graph?.nodes ?? []) {
      if (!deduped.has(node.organization_id)) {
        deduped.set(node.organization_id, {
          value: node.organization_id,
          label: node.name,
        })
      }
    }
    return Array.from(deduped.values())
  }, [graph])
  const selectedCreateBindingLifecycleWarning = useMemo(
    () => resolvePoolWorkflowBindingLifecycleWarning(selectedCreateBinding),
    [selectedCreateBinding]
  )
  const createBindingCoverageSummary = useMemo(() => {
    if (!selectedCreateBinding) {
      return null
    }
    const bindingLabel = describePoolWorkflowBindingCoverage(selectedCreateBinding)
    return buildTopologyCoverageSummary({
      bindingLabel,
      decisions: resolvePoolWorkflowBindingDecisionRefs(selectedCreateBinding),
      detail: t('runs.create.preview.coverageDetail', { bindingLabel }),
      selectors: topologyEdgeSelectors,
      source: 'selected',
    })
  }, [selectedCreateBinding, t, topologyEdgeSelectors])
  const isCreateBindingContextAmbiguous = matchingWorkflowBindings.length > 1 && !String(createBindingId || '').trim()

  const loadPools = useCallback(async () => {
    setLoadingPools(true)
    setError(null)
    try {
      const data = await queryClient.fetchQuery(withQueryPolicy('interactive', {
        queryKey: queryKeys.poolCatalog.pools(),
        queryFn: () => listOrganizationPools(),
      }))
      setPools(data)
    } catch {
      setError(t('runs.page.messages.failedToLoadPools'))
    } finally {
      setHasResolvedPoolsLoad(true)
      setLoadingPools(false)
    }
  }, [t])

  const loadSchemaTemplates = useCallback(async () => {
    setLoadingSchemaTemplates(true)
    try {
      const data = await listPoolSchemaTemplates({ isPublic: true, isActive: true })
      setSchemaTemplates(data)
    } catch {
      setError(t('runs.page.messages.failedToLoadSchemaTemplates'))
    } finally {
      setLoadingSchemaTemplates(false)
    }
  }, [t])

  const loadReceiptBatches = useCallback(async () => {
    if (!selectedPoolId) {
      setReceiptBatches([])
      return
    }
    setLoadingReceiptBatches(true)
    try {
      const data = await listPoolBatches({
        poolId: selectedPoolId,
        batchKind: 'receipt',
        limit: 100,
      })
      setReceiptBatches(data)
    } catch {
      setError(t('runs.page.messages.failedToLoadReceiptBatches'))
    } finally {
      setLoadingReceiptBatches(false)
    }
  }, [selectedPoolId, t])

  const loadGraph = useCallback(async (options?: { force?: boolean }) => {
    if (!selectedPoolId) {
      setGraph(null)
      return
    }
    const requestKey = `${selectedPoolId}:${graphDate || ''}`
    const currentGraphLoad = loadGraphInFlightRef.current
    const shouldReuseInFlight = !options?.force && currentGraphLoad?.key === requestKey
    const graphPromise = shouldReuseInFlight
      ? currentGraphLoad.promise
      : getPoolGraph(selectedPoolId, graphDate || undefined)

    if (!shouldReuseInFlight) {
      loadGraphInFlightRef.current = {
        key: requestKey,
        promise: graphPromise,
      }
    }

    setLoadingGraph(true)
    try {
      const data = await graphPromise
      setGraph(data)
    } catch {
      setError(t('runs.page.messages.failedToLoadGraph'))
    } finally {
      if (
        loadGraphInFlightRef.current?.key === requestKey
        && loadGraphInFlightRef.current.promise === graphPromise
      ) {
        loadGraphInFlightRef.current = null
      }
      setLoadingGraph(false)
    }
  }, [graphDate, selectedPoolId, t])

  const loadRuns = useCallback(async (options?: { preferredRunId?: string | null, force?: boolean }) => {
    const poolId = selectedPoolId
    if (!poolId) {
      setRuns([])
      setSelectedRunId(null)
      return
    }
    const requestId = loadRunsRequestRef.current + 1
    loadRunsRequestRef.current = requestId
    const requestKey = poolId
    const currentRunsLoad = loadRunsInFlightRef.current
    const shouldReuseInFlight = (
      !options?.force
      && !options?.preferredRunId
      && currentRunsLoad?.key === requestKey
    )
    const runsPromise = shouldReuseInFlight
      ? currentRunsLoad.promise
      : listPoolRuns({ poolId, limit: 100 })

    if (!shouldReuseInFlight) {
      loadRunsInFlightRef.current = {
        key: requestKey,
        promise: runsPromise,
      }
    }

    setLoadingRuns(true)
    try {
      const data = await runsPromise
      if (loadRunsRequestRef.current !== requestId || selectedPoolIdRef.current !== poolId) {
        return
      }
      const normalizedData = Array.isArray(data) ? data : []
      setRuns(normalizedData)
      setSelectedRunId((currentSelectedRunId) => {
        const preferredRunId = options?.preferredRunId?.trim() || null
        if (preferredRunId && normalizedData.some((item) => item.id === preferredRunId)) {
          return preferredRunId
        }
        if (currentSelectedRunId && normalizedData.some((item) => item.id === currentSelectedRunId)) {
          return currentSelectedRunId
        }
        return normalizedData[0]?.id ?? null
      })
    } catch {
      if (loadRunsRequestRef.current === requestId) {
        setError(t('runs.page.messages.failedToLoadRuns'))
      }
    } finally {
      if (
        loadRunsInFlightRef.current?.key === requestKey
        && loadRunsInFlightRef.current.promise === runsPromise
      ) {
        loadRunsInFlightRef.current = null
      }
      if (loadRunsRequestRef.current === requestId) {
        setLoadingRuns(false)
      }
    }
  }, [selectedPoolId, t])

  const loadReport = useCallback(async (options?: { force?: boolean }) => {
    const runId = selectedRunId
    if (!runId) {
      setReport(null)
      return
    }
    const requestId = loadReportRequestRef.current + 1
    loadReportRequestRef.current = requestId
    const requestKey = runId
    const currentReportLoad = loadReportInFlightRef.current
    const shouldReuseInFlight = !options?.force && currentReportLoad?.key === requestKey
    const reportPromise = shouldReuseInFlight
      ? currentReportLoad.promise
      : getPoolRunReport(runId)

    if (!shouldReuseInFlight) {
      loadReportInFlightRef.current = {
        key: requestKey,
        promise: reportPromise,
      }
    }

    setLoadingReport(true)
    setReport((currentReport) => (currentReport?.run?.id === runId ? currentReport : null))
    try {
      const data = await reportPromise
      if (loadReportRequestRef.current !== requestId || selectedRunIdRef.current !== runId) {
        return
      }
      setReport(data)
    } catch {
      if (loadReportRequestRef.current === requestId) {
        setError(t('runs.page.messages.failedToLoadReport'))
      }
    } finally {
      if (
        loadReportInFlightRef.current?.key === requestKey
        && loadReportInFlightRef.current.promise === reportPromise
      ) {
        loadReportInFlightRef.current = null
      }
      if (loadReportRequestRef.current === requestId) {
        setLoadingReport(false)
      }
    }
  }, [selectedRunId, t])

  useEffect(() => {
    const nextSelectedPoolId = poolFromUrl
      ? poolFromUrl
      : (selectedPoolIdRef.current === undefined ? undefined : null)

    pendingRouteSyncRef.current = {
      selectedPoolId: nextSelectedPoolId,
      selectedRunId: runFromUrl,
      activeStage: stageFromUrl,
      graphDate: graphDateFromUrl,
      detailOpen: detailOpenFromUrl,
    }

    setSelectedPoolId((current) => (
      current === nextSelectedPoolId ? current : nextSelectedPoolId
    ))
    setSelectedRunId((current) => (
      current === runFromUrl ? current : runFromUrl
    ))
    setActiveStageTab((current) => (
      current === stageFromUrl ? current : stageFromUrl
    ))
    setGraphDate((current) => (
      current === graphDateFromUrl ? current : graphDateFromUrl
    ))
    setIsRunDetailOpen((current) => (
      current === detailOpenFromUrl ? current : detailOpenFromUrl
    ))
  }, [detailOpenFromUrl, graphDateFromUrl, poolFromUrl, runFromUrl, stageFromUrl])

  useEffect(() => {
    const pendingRouteSync = pendingRouteSyncRef.current
    if (pendingRouteSync) {
      const poolMatches = selectedPoolId === pendingRouteSync.selectedPoolId
      const runMatches = selectedRunId === pendingRouteSync.selectedRunId
      const stageMatches = activeStageTab === pendingRouteSync.activeStage
      const dateMatches = graphDate === pendingRouteSync.graphDate
      const detailMatches = isRunDetailOpen === pendingRouteSync.detailOpen

      if (!poolMatches || !runMatches || !stageMatches || !dateMatches || !detailMatches) {
        return
      }

      pendingRouteSyncRef.current = null
      return
    }

    const next = new URLSearchParams(searchParams)

    if (selectedPoolId) {
      next.set('pool', selectedPoolId)
    } else {
      next.delete('pool')
    }

    if (graphDate && graphDate !== defaultGraphDateRef.current) {
      next.set('date', graphDate)
    } else {
      next.delete('date')
    }

    if (selectedRunId) {
      next.set('run', selectedRunId)
    } else {
      next.delete('run')
    }

    if (activeStageTab === DEFAULT_STAGE) {
      next.delete('stage')
    } else {
      next.set('stage', activeStageTab)
    }

    if (activeStageTab !== DEFAULT_STAGE && selectedRunId && isRunDetailOpen) {
      next.set('detail', '1')
    } else {
      next.delete('detail')
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [
    activeStageTab,
    graphDate,
    isRunDetailOpen,
    searchParams,
    selectedPoolId,
    selectedRunId,
    setSearchParams,
  ])

  useEffect(() => {
    void loadPools()
    void loadSchemaTemplates()
  }, [loadPools, loadSchemaTemplates])

  useEffect(() => {
    void loadGraph()
  }, [loadGraph])

  useEffect(() => {
    void loadReceiptBatches()
  }, [loadReceiptBatches])

  useEffect(() => {
    void loadRuns()
  }, [loadRuns])

  useEffect(() => {
    if (!hasResolvedPoolsLoad) {
      return
    }

    if (loadingPools) {
      return
    }

    if (!pools.length) {
      if (selectedPoolId !== null) {
        routeUpdateModeRef.current = 'replace'
        setSelectedPoolId(null)
      }
      return
    }

    if (selectedPoolId && pools.some((item) => item.id === selectedPoolId)) {
      return
    }

    if (selectedPoolId === undefined || selectedPoolId === null || !pools.some((item) => item.id === selectedPoolId)) {
      routeUpdateModeRef.current = 'replace'
      setSelectedPoolId(pools[0].id)
    }
  }, [hasResolvedPoolsLoad, loadingPools, pools, selectedPoolId])

  useEffect(() => {
    if (previousSelectedPoolIdRef.current === selectedPoolId) {
      return
    }
    previousSelectedPoolIdRef.current = selectedPoolId
    setRuns([])
    setSelectedRunId(null)
    setReport(null)
    setIsRunDetailOpen(false)
  }, [selectedPoolId])

  useEffect(() => {
    void loadReport()
  }, [loadReport])

  useEffect(() => {
    const pendingRouteSync = pendingRouteSyncRef.current
    const stageChanged = previousStageRef.current !== activeStageTab
    const runChanged = previousSelectedRunIdRef.current !== selectedRunId

    previousStageRef.current = activeStageTab
    previousSelectedRunIdRef.current = selectedRunId

    if (pendingRouteSync) {
      return
    }

    if (activeStageTab === DEFAULT_STAGE) {
      if (stageChanged && isRunDetailOpen) {
        routeUpdateModeRef.current = 'replace'
        setIsRunDetailOpen(false)
      }
      return
    }

    if (selectedRunId && (stageChanged || runChanged)) {
      routeUpdateModeRef.current = 'replace'
      setIsRunDetailOpen(true)
    }
  }, [activeStageTab, isRunDetailOpen, selectedRunId])

  useEffect(() => {
    const currentBindingId = createForm.getFieldValue('pool_workflow_binding_id') as string | undefined
    const normalizedCurrentBindingId = currentBindingId?.trim() || ''
    const matchingBindingIds = new Set(
      matchingWorkflowBindings
        .map((item) => item.binding_id?.trim() || '')
        .filter((item) => item.length > 0)
    )
    if (matchingWorkflowBindings.length === 1) {
      const nextBindingId = matchingWorkflowBindings[0].binding_id?.trim() || ''
      if (nextBindingId && nextBindingId !== normalizedCurrentBindingId) {
        createForm.setFieldValue('pool_workflow_binding_id', nextBindingId)
      }
      return
    }
    if (normalizedCurrentBindingId && !matchingBindingIds.has(normalizedCurrentBindingId)) {
      createForm.setFieldValue('pool_workflow_binding_id', undefined)
    }
  }, [createForm, matchingWorkflowBindings])

  useEffect(() => {
    setBindingPreview(null)
  }, [
    createBindingId,
    createDirection,
    createMode,
    createPeriodStart,
    createTopDownInputMode,
    createBatchId,
    createStartOrganizationId,
    createSchemaTemplateId,
    createSourceArtifactId,
    createSourcePayloadJson,
    createStartingAmount,
    selectedPoolId,
  ])

  const handleCreateRun = useCallback(async () => {
    if (!selectedPoolId) {
      setError(t('runs.create.messages.selectPoolBeforeCreate'))
      return
    }
    let values: CreateRunFormValues
    let direction: CreateRunFormValues['direction'] = 'top_down'
    try {
      values = await createForm.validateFields()
      direction = values.direction
    } catch {
      return
    }

    setCreatingRun(true)
    setError(null)
    try {
      const requestPayload = buildCreateRunPayload({
        poolId: selectedPoolId,
        values,
      })
      const payload = await createPoolRun(requestPayload)
      message.success(payload.created ? t('runs.create.messages.runCreated') : t('runs.create.messages.runReused'))
      setBindingPreview(null)
      await loadRuns({ preferredRunId: payload.run.id, force: true })
    } catch (err) {
      const problem = parseProblemDetails(err)
      if (problem) {
        if (problem.code === 'VALIDATION_ERROR' && problem.detail) {
          const fieldErrors = resolveCreateRunFieldErrors({
            direction,
            detail: problem.detail,
          })

          if (fieldErrors.length > 0) {
            createForm.setFields(fieldErrors)
          }
          setError(resolveCreateRunPageLevelMessage({
            problem,
            fallbackMessage: t('runs.create.messages.failedToCreateRun'),
            hasFieldErrors: fieldErrors.length > 0,
          }))
        } else {
          setError(resolveCreateRunProblemMessage(problem, t('runs.create.messages.failedToCreateRun')))
        }
        if (
          problem.code === 'POOL_WORKFLOW_BINDING_REQUIRED'
          || problem.code === 'POOL_WORKFLOW_BINDING_NOT_FOUND'
          || problem.code === 'POOL_WORKFLOW_BINDING_NOT_RESOLVED'
          || problem.code === 'POOL_WORKFLOW_BINDING_AMBIGUOUS'
          || problem.code === 'POOL_WORKFLOW_BINDING_INVALID'
        ) {
          createForm.setFields([
            {
              name: 'pool_workflow_binding_id',
              errors: [resolveCreateRunProblemMessage(problem, t('runs.create.messages.failedToSelectWorkflowBinding'))],
            },
          ])
        }
      } else if (err instanceof Error && err.message) {
        setError(err.message)
      } else {
        setError(t('runs.create.messages.failedToCreateRun'))
      }
    } finally {
      setCreatingRun(false)
    }
  }, [createForm, loadRuns, message, selectedPoolId, t])

  const handlePreviewBinding = useCallback(async () => {
    if (!selectedPoolId) {
      setError(t('runs.create.messages.selectPoolBeforePreview'))
      return
    }
    let values: CreateRunFormValues
    let direction: CreateRunFormValues['direction'] = 'top_down'
    try {
      values = await createForm.validateFields()
      direction = values.direction
    } catch {
      return
    }

    setPreviewingBinding(true)
    setError(null)
    try {
      const requestPayload = buildCreateRunPayload({
        poolId: selectedPoolId,
        values,
      })
      const preview = await previewPoolWorkflowBinding(requestPayload)
      setBindingPreview(preview)
      message.success(t('runs.create.messages.bindingPreviewUpdated'))
    } catch (err) {
      const problem = parseProblemDetails(err)
      if (problem) {
        if (problem.code === 'VALIDATION_ERROR' && problem.detail) {
          const fieldErrors = resolveCreateRunFieldErrors({
            direction,
            detail: problem.detail,
          })

          if (fieldErrors.length > 0) {
            createForm.setFields(fieldErrors)
          }
          setError(resolveCreateRunPageLevelMessage({
            problem,
            fallbackMessage: t('runs.create.messages.failedToBuildBindingPreview'),
            hasFieldErrors: fieldErrors.length > 0,
          }))
        } else {
          setError(resolveCreateRunProblemMessage(problem, t('runs.create.messages.failedToBuildBindingPreview')))
        }
        if (
          problem.code === 'POOL_WORKFLOW_BINDING_REQUIRED'
          || problem.code === 'POOL_WORKFLOW_BINDING_NOT_FOUND'
          || problem.code === 'POOL_WORKFLOW_BINDING_NOT_RESOLVED'
          || problem.code === 'POOL_WORKFLOW_BINDING_AMBIGUOUS'
          || problem.code === 'POOL_WORKFLOW_BINDING_INVALID'
        ) {
          createForm.setFields([
            {
              name: 'pool_workflow_binding_id',
              errors: [resolveCreateRunProblemMessage(problem, t('runs.create.messages.failedToSelectWorkflowBinding'))],
            },
          ])
        }
        setBindingPreview(null)
      } else if (err instanceof Error && err.message) {
        setBindingPreview(null)
        setError(err.message)
      } else {
        setBindingPreview(null)
        setError(t('runs.create.messages.failedToBuildBindingPreview'))
      }
    } finally {
      setPreviewingBinding(false)
    }
  }, [createForm, message, selectedPoolId, t])

  const handleRetryFailed = useCallback(async () => {
    if (!selectedRunId) {
      setError(t('runs.retry.messages.selectRun'))
      return
    }
    let values: RetryFormValues
    try {
      values = await retryForm.validateFields()
    } catch {
      return
    }
    let documentsByDatabase: Record<string, Array<Record<string, unknown>>>
    try {
      documentsByDatabase = parseDocumentsPayload(values.documents_json)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('runs.retry.messages.invalidPayload'))
      return
    }

    setRetrying(true)
    setError(null)
    try {
      const idempotencyKey = generateIdempotencyKey()
      const response = await retryPoolRunFailed(selectedRunId, {
        entity_name: values.entity_name,
        max_attempts: values.max_attempts,
        retry_interval_seconds: values.retry_interval_seconds,
        documents_by_database: documentsByDatabase,
      }, idempotencyKey)
      const summary = response.retry_target_summary
      const enqueuedTargets = summary?.enqueued_targets ?? 0
      const failedTargets = summary?.failed_targets ?? 0
      if (response.accepted) {
        message.success(t('runs.retry.messages.accepted', { enqueuedTargets, failedTargets }))
      } else {
        message.warning(t('runs.retry.messages.notAccepted'))
      }
      await loadRuns({ force: true })
      await loadReport({ force: true })
    } catch (err) {
      const conflict = parseSafeCommandConflict(err)
      if (conflict) {
        setError(`${conflict.error_message} (${conflict.conflict_reason})`)
      } else {
        setError(t('runs.retry.messages.failed'))
      }
    } finally {
      setRetrying(false)
    }
  }, [loadReport, loadRuns, message, retryForm, selectedRunId, t])

  const handleSafeCommand = useCallback(async (commandType: PoolRunSafeCommandType) => {
    if (!selectedRunId || !runDetails) {
      setError(t('runs.safe.messages.selectRun'))
      return
    }
    if (runDetails.mode !== 'safe') {
      setError(t('runs.safe.messages.safeOnly'))
      return
    }

    const idempotencyKey = generateIdempotencyKey()
    setSafeActionLoading(commandType)
    setError(null)
    try {
      const response = commandType === 'confirm-publication'
        ? await confirmPoolRunPublication(selectedRunId, idempotencyKey)
        : await abortPoolRunPublication(selectedRunId, idempotencyKey)
      if (response.result === 'accepted') {
        message.success(
          commandType === 'confirm-publication'
            ? t('runs.safe.messages.confirmAccepted')
            : t('runs.safe.messages.abortAccepted')
        )
      } else {
        message.info(
          commandType === 'confirm-publication'
            ? t('runs.safe.messages.confirmReplay')
            : t('runs.safe.messages.abortReplay')
        )
      }
      await loadRuns({ preferredRunId: response.run.id, force: true })
      await loadReport({ force: true })
    } catch (err) {
      const conflict = parseSafeCommandConflict(err)
      if (conflict) {
        setError(`${conflict.error_message} (${conflict.conflict_reason})`)
      } else {
        const problem = parseProblemDetails(err)
        if (problem) {
          setError(
            resolveSafeCommandProblemMessage(
              problem,
              commandType === 'confirm-publication'
                ? t('runs.safe.messages.failedConfirm')
                : t('runs.safe.messages.failedAbort')
            )
          )
        } else {
          setError(
            commandType === 'confirm-publication'
              ? t('runs.safe.messages.failedConfirm')
              : t('runs.safe.messages.failedAbort')
          )
        }
      }
    } finally {
      setSafeActionLoading(null)
    }
  }, [loadReport, loadRuns, message, runDetails, selectedRunId, t])

  const handleSelectPool = useCallback((nextPoolId: string) => {
    routeUpdateModeRef.current = 'push'
    setSelectedPoolId(nextPoolId)
    setSelectedRunId(null)
    setIsRunDetailOpen(false)
  }, [])

  const handleGraphDateChange = useCallback((nextDate: string) => {
    routeUpdateModeRef.current = 'push'
    setGraphDate(nextDate || defaultGraphDateRef.current)
  }, [])

  const handleRefreshData = useCallback(() => {
    void loadGraph({ force: true })
    void loadReceiptBatches()
    void loadRuns({ force: true })
    void loadReport({ force: true })
  }, [loadGraph, loadReceiptBatches, loadReport, loadRuns])

  const handleBatchCreated = useCallback(async (
    response: {
      batch: PoolBatch
      run?: PoolRun | null
    },
    context: {
      batchKind: 'receipt' | 'sale'
      periodStart: string
      periodEnd: string | null
      poolWorkflowBindingId: string | null
      startOrganizationId: string | null
    },
  ) => {
    setIsBatchIntakeDrawerOpen(false)
    createForm.setFieldsValue({
      period_start: context.periodStart,
      period_end: context.periodEnd ?? '',
    })

    if (response.batch.batch_kind === 'receipt') {
      createForm.setFieldsValue({
        direction: 'top_down',
        mode: 'safe',
        top_down_input_mode: 'batch_backed',
        batch_id: response.batch.id,
        pool_workflow_binding_id: context.poolWorkflowBindingId ?? undefined,
        start_organization_id: context.startOrganizationId ?? undefined,
      })
      setReceiptBatches((current) => [
        response.batch,
        ...current.filter((item) => item.id !== response.batch.id),
      ])
      if (response.run?.id) {
        routeUpdateModeRef.current = 'push'
        setActiveStageTab('inspect')
        setIsRunDetailOpen(true)
        setSelectedRunId(response.run.id)
        await loadRuns({ preferredRunId: response.run.id, force: true })
        return
      }
    }

    await loadReceiptBatches()
  }, [createForm, loadReceiptBatches, loadRuns])

  const handleSelectStage = useCallback((nextStage: PoolRunsStage) => {
    routeUpdateModeRef.current = 'push'
    setActiveStageTab(nextStage)
  }, [])

  const handleSelectRun = useCallback((runId: string) => {
    routeUpdateModeRef.current = 'push'
    setSelectedRunId(runId)
    if (activeStageTab !== DEFAULT_STAGE) {
      setIsRunDetailOpen(true)
    }
  }, [activeStageTab])

  const handleCloseRunDetail = useCallback(() => {
    routeUpdateModeRef.current = 'push'
    setIsRunDetailOpen(false)
  }, [])

  const runColumns: ColumnsType<PoolRun> = useMemo(
    () => [
      {
        title: t('runs.inspect.columns.run'),
        dataIndex: 'id',
        key: 'id',
        width: 220,
        render: (value: string, record) => (
          <Space direction="vertical" size={4}>
            <Button
              type="link"
              aria-label={t('runs.inspect.columns.openRun', { runId: record.id })}
              aria-pressed={record.id === selectedRunId}
              style={{
                paddingInline: 0,
                minHeight: 36,
                justifyContent: 'flex-start',
                whiteSpace: 'normal',
                height: 'auto',
              }}
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                handleSelectRun(record.id)
              }}
            >
              <Text code>{formatShortId(value)}</Text>
            </Button>
            <Tag color={record.mode === 'safe' ? 'geekblue' : 'default'}>{record.mode}</Tag>
          </Space>
        ),
      },
      {
        title: t('runs.inspect.columns.status'),
        dataIndex: 'status',
        key: 'status',
        width: 220,
        render: (_value, record) => (
          <Space size={4} wrap>
            <Tag color={getStatusColor(record.status)}>{record.status}</Tag>
            {record.status_reason && (
              <Tag color={getStatusReasonColor(record.status_reason)}>{record.status_reason}</Tag>
            )}
          </Space>
        ),
      },
      {
        title: t('runs.inspect.columns.approval'),
        key: 'approval',
        width: 220,
        render: (_value, record) => (
          <Space size={4} wrap>
            {record.approval_state ? (
              <Tag color={getApprovalStateColor(record.approval_state)}>{record.approval_state}</Tag>
            ) : (
              <Tag>n/a</Tag>
            )}
            {record.publication_step_state ? (
              <Tag color={getPublicationStepColor(record.publication_step_state)}>{record.publication_step_state}</Tag>
            ) : null}
          </Space>
        ),
      },
      {
        title: t('runs.inspect.columns.workflow'),
        key: 'workflow',
        width: 240,
        render: (_value, record) => {
          const workflowRunId = record.provenance?.workflow_run_id ?? record.workflow_execution_id
          const workflowStatus = record.provenance?.workflow_status ?? record.workflow_status
          const executionBackend = record.provenance?.execution_backend ?? record.execution_backend
          return (
            <Space direction="vertical" size={2}>
              <Text code>{formatShortId(workflowRunId)}</Text>
              <Space size={4} wrap>
                {workflowStatus ? <Tag color="processing">{workflowStatus}</Tag> : <Tag>{t('runs.inspect.runtime.legacy')}</Tag>}
                {executionBackend ? <Tag>{executionBackend}</Tag> : null}
              </Space>
            </Space>
          )
        },
      },
      {
        title: t('runs.inspect.columns.input'),
        key: 'input',
        width: 220,
        render: (_value, record) => {
          const contractVersion = resolveInputContractVersion(record)
          return (
            <Space direction="vertical" size={2}>
              <Tag color={getInputContractColor(contractVersion)}>{contractVersion}</Tag>
              <Text type="secondary">{summarizeRunInput(record)}</Text>
            </Space>
          )
        },
      },
      {
        title: t('runs.inspect.columns.period'),
        key: 'period',
        render: (_value, record) => `${record.period_start}${record.period_end ? `..${record.period_end}` : ''}`,
      },
      {
        title: t('runs.inspect.columns.updated'),
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 190,
        render: (value: string) => formatDate(value),
      },
    ],
    [handleSelectRun, selectedRunId, t]
  )

  const publicationAttemptColumns: ColumnsType<PoolPublicationAttemptDiagnostics> = useMemo(
    () => [
      {
        title: t('runs.inspect.publicationAttempts.columns.targetDb'),
        dataIndex: 'target_database_id',
        key: 'target_database_id',
        width: 180,
        render: (value: string) => <Text code>{formatShortId(value)}</Text>,
      },
      {
        title: t('runs.inspect.publicationAttempts.columns.status'),
        dataIndex: 'status',
        key: 'status',
        width: 130,
        render: (value: string) => (
          <Tag color={value === 'success' ? 'success' : value === 'failed' ? 'error' : 'processing'}>
            {value}
          </Tag>
        ),
      },
      {
        title: t('runs.inspect.publicationAttempts.columns.attempt'),
        dataIndex: 'attempt_number',
        key: 'attempt_number',
        width: 90,
      },
      {
        title: t('runs.inspect.publicationAttempts.columns.timestamp'),
        dataIndex: 'attempt_timestamp',
        key: 'attempt_timestamp',
        width: 180,
        render: (value?: string) => formatDate(value ?? null),
      },
      {
        title: t('runs.inspect.publicationAttempts.columns.identity'),
        key: 'identity',
        width: 220,
        render: (_value, record) => (
          <Space direction="vertical" size={0}>
            <Text>{record.publication_identity_strategy || '-'}</Text>
            <Text type="secondary">{record.external_document_identity || '-'}</Text>
          </Space>
        ),
      },
      {
        title: t('runs.inspect.publicationAttempts.columns.error'),
        key: 'error',
        render: (_value, record) => {
          const code = record.domain_error_code || '-'
          const messageText = record.domain_error_message || '-'
          const httpStatusValue = record.http_error?.status
          const transportMessage = record.transport_error?.message ?? null
          return (
            <Space direction="vertical" size={0}>
              <Text>{code}</Text>
              <Text type="secondary">{messageText}</Text>
              {PUBLICATION_MAPPING_ERROR_CODES.has(code) ? (
                <Text type="secondary">{t('runs.inspect.publicationAttempts.remediation')}</Text>
              ) : null}
              {httpStatusValue ? <Text type="secondary">HTTP {httpStatusValue}</Text> : null}
              {transportMessage ? <Text type="secondary">{transportMessage}</Text> : null}
            </Space>
          )
        },
      },
    ],
    [t]
  )

  const verificationMismatchColumns: ColumnsType<PoolRunVerificationMismatch> = useMemo(
    () => [
      {
        title: t('runs.inspect.verification.columns.database'),
        dataIndex: 'database_id',
        key: 'database_id',
        width: 180,
        render: (value?: string | null) => <Text code>{value ? formatShortId(value) : '-'}</Text>,
      },
      {
        title: t('runs.inspect.verification.columns.entity'),
        dataIndex: 'entity_name',
        key: 'entity_name',
        width: 180,
        render: (value?: string | null) => value || '-',
      },
      {
        title: t('runs.inspect.verification.columns.document'),
        dataIndex: 'document_idempotency_key',
        key: 'document_idempotency_key',
        width: 180,
        render: (value?: string | null) => value || '-',
      },
      {
        title: t('runs.inspect.verification.columns.path'),
        dataIndex: 'field_or_table_path',
        key: 'field_or_table_path',
        render: (value?: string | null) => value || '-',
      },
      {
        title: t('runs.inspect.verification.columns.kind'),
        dataIndex: 'kind',
        key: 'kind',
        width: 180,
        render: (value?: string | null) => value || '-',
      },
    ],
    [t]
  )

  const workflowRunId = runDetails?.provenance?.workflow_run_id ?? null
  const workflowStatus = runDetails?.provenance?.workflow_status ?? null
  const executionBackend = runDetails?.provenance?.execution_backend ?? runDetails?.execution_backend ?? null
  const rootOperationId = runDetails?.provenance?.root_operation_id ?? null
  const executionConsumer = runDetails?.provenance?.execution_consumer ?? null
  const lane = runDetails?.provenance?.lane ?? null
  const retryChain = runDetails?.provenance?.retry_chain ?? []
  const workflowBinding = runDetails?.workflow_binding ?? null
  const runtimeProjection = runDetails?.runtime_projection ?? null
  const previewWorkflowBinding = bindingPreview?.workflow_binding ?? null
  const previewBindingWorkflow = useMemo(
    () => resolvePoolWorkflowBindingWorkflow(previewWorkflowBinding),
    [previewWorkflowBinding]
  )
  const previewBindingDecisionRefs = useMemo(
    () => resolvePoolWorkflowBindingDecisionRefs(previewWorkflowBinding),
    [previewWorkflowBinding]
  )
  const previewBindingLifecycleWarning = useMemo(
    () => resolvePoolWorkflowBindingLifecycleWarning(previewWorkflowBinding),
    [previewWorkflowBinding]
  )
  const workflowBindingWorkflow = useMemo(
    () => resolvePoolWorkflowBindingWorkflow(workflowBinding),
    [workflowBinding]
  )
  const workflowBindingLifecycleWarning = useMemo(
    () => resolvePoolWorkflowBindingLifecycleWarning(workflowBinding),
    [workflowBinding]
  )
  const workflowBindingAttachmentRevision = resolvePoolWorkflowBindingAttachmentRevision({
    binding: workflowBinding,
    runtimeProjection,
  })
  const workflowBindingProfileId = resolvePoolWorkflowBindingProfileId({
    binding: workflowBinding,
    runtimeProjection,
  })
  const workflowBindingProfileRevisionId = resolvePoolWorkflowBindingProfileRevisionId({
    binding: workflowBinding,
    runtimeProjection,
  })
  const workflowBindingProfileRevisionNumber = resolvePoolWorkflowBindingProfileRevisionNumber({
    binding: workflowBinding,
    runtimeProjection,
  })
  const workflowBindingProfileStatus = resolvePoolWorkflowBindingProfileStatus(workflowBinding)
  const bindingDecisionRefs = useMemo(
    () => resolvePoolWorkflowBindingDecisionRefs(workflowBinding),
    [workflowBinding]
  )
  const workflowDecisionRefs = useMemo(
    () => (
      bindingDecisionRefs.length > 0
        ? bindingDecisionRefs
        : (runtimeProjection?.workflow_binding.decision_refs ?? [])
    ),
    [bindingDecisionRefs, runtimeProjection]
  )
  const bindingPreviewCoverageSummary = useMemo(() => {
    if (!bindingPreview) {
      return null
    }
    return normalizePreviewSlotCoverageSummary(bindingPreview.slot_coverage_summary)
  }, [bindingPreview])
  const runLineageCoverageSummary = useMemo(() => {
    const persistedSummary = normalizePreviewSlotCoverageSummary(
      runtimeProjection?.document_policy_projection.slot_coverage_summary
    )
    if (persistedSummary) {
      return persistedSummary
    }
    if (!workflowBinding && !runtimeProjection) {
      return null
    }
    const bindingLabel = workflowBinding
      ? describePoolWorkflowBindingCoverage(workflowBinding)
      : [
        String(runtimeProjection?.workflow_binding.binding_id || '').trim() || t('runs.inspect.preview.runBindingFallback'),
        String(runtimeProjection?.workflow_binding.workflow_name || '').trim(),
      ].filter((item) => item).join(' · ')
    return buildTopologyCoverageSummary({
      bindingLabel,
      decisions: workflowDecisionRefs,
      detail: t('runs.inspect.preview.coverageDetail', { bindingLabel }),
      selectors: topologyEdgeSelectors,
      source: 'selected',
    })
  }, [runtimeProjection, t, topologyEdgeSelectors, workflowBinding, workflowDecisionRefs])
  const runLineageSlotProjection = runtimeProjection?.document_policy_projection.compiled_document_policy_slots ?? null
  const workflowDiagnosticsId = runDetails?.workflow_execution_id
    ?? (retryChain.length > 0 ? retryChain[retryChain.length - 1].workflow_run_id : null)
    ?? workflowRunId
    ?? null
  const selectedPoolLabel = selectedPool
    ? `${selectedPool.code} - ${selectedPool.name}`
    : runDetails?.pool_id
      ? formatShortId(runDetails.pool_id)
      : '-'
  const masterDataGate = runDetails?.master_data_gate ?? null
  const masterDataGateHint = masterDataGate?.error_code
    ? resolveMasterDataGateHint(masterDataGate.error_code)
    : null
  const masterDataGateRemediationTarget = masterDataGate
    ? resolveMasterDataRemediationTarget({
      code: masterDataGate.error_code,
      diagnostic: masterDataGate.diagnostic,
    })
    : null
  const masterDataGateContextLines = masterDataGate
    ? buildMasterDataGateContextLines(masterDataGate)
    : []
  const readinessBlockers = runDetails?.readiness_blockers ?? []
  const readinessChecklist = runDetails?.readiness_checklist ?? buildLegacyReadinessChecklist(readinessBlockers)
  const verificationStatus = runDetails?.verification_status ?? 'not_verified'
  const verificationSummary = runDetails?.verification_summary ?? null
  const reportDetails = report?.run?.id === runDetails?.id ? report : null
  const factualWorkspaceHref = buildPoolFactualRoute({
    poolId: selectedPoolId,
    runId: selectedRunId,
    quarterStart: runDetails?.period_start ?? null,
    focus: 'settlement',
    detail: true,
  })

  const isSafeRun = runDetails?.mode === 'safe'
  const isPublishedOrPartial = runDetails?.status === 'published' || runDetails?.status === 'partial_success'
  const isTerminalNonAbortFailed = runDetails?.status === 'failed' && runDetails?.terminal_reason !== 'aborted_by_operator'
  const isSafePrePublishPreparing = isSafeRun && runDetails?.approval_state === 'preparing'
  const canConfirm = Boolean(
    isSafeRun
    && runDetails
    && runDetails.approval_state === 'awaiting_approval'
    && readinessChecklist.status === 'ready'
    && !isPublishedOrPartial
    && runDetails.status !== 'failed'
  )
  const canAbort = Boolean(
    isSafeRun
    && runDetails
    && runDetails.approval_state !== 'not_required'
    && !isPublishedOrPartial
    && !isTerminalNonAbortFailed
  )
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const detailDescriptionColumns = hasMatchedBreakpoint
    ? (screens.lg ? 2 : 1)
    : (
      typeof window !== 'undefined' && window.innerWidth >= 992
        ? 2
        : 1
    )

  if (!ready) {
    return null
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t('runs.page.title')}
          subtitle={t('runs.page.subtitle', { route: POOL_RUNS_ROUTE })}
          actions={(
            <Space wrap size={16} align="start">
              <Space direction="vertical" size={4}>
                <Text strong>{t('runs.page.contextPoolLabel')}</Text>
                <Select
                  aria-label={t('runs.page.contextPoolAriaLabel')}
                  data-testid="pool-runs-context-pool"
                  style={{ width: 320 }}
                  placeholder={t('catalog.fields.selectPool')}
                  value={selectedPoolId ?? undefined}
                  options={pools.map((pool) => ({
                    value: pool.id,
                    label: `${pool.code} - ${pool.name}`,
                  }))}
                  onChange={handleSelectPool}
                />
              </Space>
              <Space direction="vertical" size={4}>
                <Text strong>{t('runs.page.graphDateLabel')}</Text>
                <Input
                  aria-label={t('runs.page.graphDateAriaLabel')}
                  type="date"
                  value={graphDate}
                  onChange={(event) => handleGraphDateChange(event.target.value)}
                  style={{ width: 180 }}
                />
              </Space>
              <Button
                onClick={handleRefreshData}
                loading={loadingGraph || loadingRuns || loadingReport}
                style={{ marginTop: 28 }}
              >
                {t('runs.page.refresh')}
              </Button>
            </Space>
          )}
        />
      )}
    >
      <Alert
        type="info"
        showIcon
        message={t('runs.page.lifecycleStage', { stage: stageLabels[activeStageTab] })}
        description={stageMessages[activeStageTab]}
      />

      {error && <Alert type="error" message={error} />}

      <Card title={t('runs.page.runContextTitle')} loading={loadingPools}>
        <Space wrap>
          <Text>
            {t('runs.page.selectedPool')}
            {' '}
            <Text strong>{selectedPool ? `${selectedPool.code} - ${selectedPool.name}` : t('runs.page.none')}</Text>
          </Text>
          <Text>
            {t('runs.page.graphDate')}
            {' '}
            <Text strong>{graphDate}</Text>
          </Text>
          <Text>
            {t('runs.page.selectedRun')}
            {' '}
            <Text strong>{selectedRunId ? formatShortId(selectedRunId) : t('runs.page.none')}</Text>
          </Text>
        </Space>
      </Card>

      <Tabs
        activeKey={activeStageTab}
        destroyOnHidden
        onChange={(key) => handleSelectStage(key as PoolRunsStage)}
        data-testid="pool-runs-stage-tabs"
        items={[
          {
            key: 'create',
            label: stageLabels.create,
            children: (
              <Card title={t('runs.create.title')}>
                <Form form={createForm} layout="vertical" initialValues={CREATE_RUN_FORM_INITIAL_VALUES}>
                  <Alert
                    type="info"
                    showIcon
                    message={t('runs.create.alerts.odataSourceTitle')}
                    description={t('runs.create.alerts.odataSourceDescription')}
                    style={{ marginBottom: 12 }}
                  />
                  <Alert
                    type="info"
                    showIcon
                    message={t('runs.create.alerts.batchIntakeTitle')}
                    description={t('runs.create.alerts.batchIntakeDescription')}
                    action={(
                      <Button
                        type="primary"
                        size="small"
                        data-testid="pool-runs-open-batch-intake"
                        disabled={!selectedPoolId}
                        onClick={() => setIsBatchIntakeDrawerOpen(true)}
                      >
                        {t('runs.create.actions.createCanonicalBatch')}
                      </Button>
                    )}
                    style={{ marginBottom: 12 }}
                  />
                  {selectedPoolWorkflowBindingsReadError ? (
                    <Alert
                      type="error"
                      showIcon
                      data-testid="pool-runs-create-binding-read-error"
                      message={t('runs.create.alerts.bindingDiagnostics', {
                        code: selectedPoolWorkflowBindingsReadError.code,
                      })}
                      description={selectedPoolWorkflowBindingsReadError.detail}
                      style={{ marginBottom: 12 }}
                    />
                  ) : null}
                  <Row gutter={12}>
                    <Col span={5}>
                      <Form.Item name="period_start" label={t('runs.create.fields.periodStart')} rules={[{ required: true }]}>
                        <Input type="date" />
                      </Form.Item>
                    </Col>
                    <Col span={5}>
                      <Form.Item name="period_end" label={t('runs.create.fields.periodEnd')}>
                        <Input type="date" />
                      </Form.Item>
                    </Col>
                    <Col span={4}>
                      <Form.Item name="direction" label={t('runs.create.fields.direction')} rules={[{ required: true }]}>
                        <Radio.Group data-testid="pool-runs-create-direction" optionType="button" buttonStyle="solid">
                          <Radio.Button value="top_down">{t('runs.create.options.topDown')}</Radio.Button>
                          <Radio.Button value="bottom_up">{t('runs.create.options.bottomUp')}</Radio.Button>
                        </Radio.Group>
                      </Form.Item>
                    </Col>
                    <Col span={4}>
                      <Form.Item name="mode" label={t('runs.create.fields.mode')} rules={[{ required: true }]}>
                        <Select
                          data-testid="pool-runs-create-mode"
                          options={[
                            { value: 'safe', label: t('runs.create.options.safe') },
                            { value: 'unsafe', label: t('runs.create.options.unsafe') },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      {createDirection === 'top_down' ? (
                        <Form.Item name="top_down_input_mode" label={t('runs.create.fields.topDownSource')} rules={[{ required: true }]}>
                          <Radio.Group
                            data-testid="pool-runs-create-top-down-input-mode"
                            optionType="button"
                            buttonStyle="solid"
                          >
                            <Radio.Button value="manual">{t('runs.create.options.manualAmount')}</Radio.Button>
                            <Radio.Button value="batch_backed">{t('runs.create.options.receiptBatch')}</Radio.Button>
                          </Radio.Group>
                        </Form.Item>
                      ) : (
                        <Form.Item name="schema_template_id" label={t('runs.create.fields.schemaTemplate')}>
                          <Select
                            data-testid="pool-runs-create-schema-template"
                            allowClear
                            loading={loadingSchemaTemplates}
                            placeholder={t('runs.create.placeholders.optionalTemplate')}
                            options={schemaTemplates.map((item) => ({
                              value: item.id,
                              label: `${item.code} - ${item.name}`,
                            }))}
                          />
                        </Form.Item>
                      )}
                    </Col>
                  </Row>
                  {createDirection === 'top_down' ? (
                    <Row gutter={12}>
                      {createTopDownInputMode === 'batch_backed' ? (
                        <>
                          <Col span={8}>
                            <Form.Item
                              name="batch_id"
                              label={t('runs.create.fields.receiptBatch')}
                              rules={[
                                { required: true, message: t('runs.create.validation.batchIdRequired') },
                                {
                                  validator: async (_rule, value) => {
                                    const normalized = String(value || '').trim()
                                    if (!normalized) {
                                      throw new Error(t('runs.create.validation.batchIdRequired'))
                                    }
                                  },
                                },
                              ]}
                              extra={
                                receiptBatchOptions.length === 0
                                  ? t('runs.create.extras.createCanonicalReceiptBatchFirst')
                                  : t('runs.create.extras.selectExistingCanonicalReceiptBatch')
                              }
                            >
                              <Select
                                data-testid="pool-runs-create-batch-id"
                                loading={loadingReceiptBatches}
                                showSearch
                                optionFilterProp="label"
                                placeholder={t('runs.create.placeholders.selectCanonicalReceiptBatch')}
                                options={receiptBatchOptions}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item
                              name="start_organization_id"
                              label={t('runs.create.fields.startOrganization')}
                              rules={[{ required: true, message: t('runs.create.validation.startOrganizationRequired') }]}
                              extra={
                                activeTopologyOrganizations.length === 0
                                  ? t('runs.create.extras.noActiveTopologyForPeriod')
                                  : t('runs.create.extras.chooseOrganizationFromTopology')
                              }
                            >
                              <Select
                                data-testid="pool-runs-create-start-organization"
                                placeholder={t('runs.create.placeholders.selectStartOrganization')}
                                options={activeTopologyOrganizations}
                              />
                            </Form.Item>
                          </Col>
                        </>
                      ) : (
                        <Col span={8}>
                          <Form.Item
                            name="starting_amount"
                            label={t('runs.create.fields.startingAmount')}
                            rules={[
                              { required: true, message: t('runs.create.validation.startingAmountRequired') },
                              {
                                validator: async (_rule, value) => {
                                  if (value == null || Number(value) <= 0) {
                                    throw new Error(t('runs.create.validation.startingAmountPositive'))
                                  }
                                },
                              },
                            ]}
                          >
                            <InputNumber data-testid="pool-runs-create-starting-amount" min={0.01} step={0.01} style={{ width: '100%' }} />
                          </Form.Item>
                        </Col>
                      )}
                    </Row>
                  ) : null}

                  <Row gutter={12}>
                    <Col span={12}>
                      <Form.Item
                        name="pool_workflow_binding_id"
                        label={t('runs.create.fields.workflowBinding')}
                        rules={[{ required: true, message: t('runs.create.validation.workflowBindingRequired') }]}
                        extra={
                          selectedPoolWorkflowBindingsReadError
                            ? t('runs.create.extras.activeBindingsUnavailable', {
                              detail: selectedPoolWorkflowBindingsReadError.detail,
                            })
                            : matchingWorkflowBindings.length === 0
                              ? t('runs.create.extras.noMatchingBinding')
                              : t('runs.create.extras.pinnedWorkflowBinding')
                        }
                      >
                        <Select
                          data-testid="pool-runs-create-workflow-binding"
                          aria-label={t('runs.create.fields.workflowBinding')}
                          aria-disabled={Boolean(selectedPoolWorkflowBindingsReadError) || matchingWorkflowBindings.length === 0}
                          allowClear={matchingWorkflowBindings.length > 1}
                          disabled={Boolean(selectedPoolWorkflowBindingsReadError) || matchingWorkflowBindings.length === 0}
                          placeholder={
                            selectedPoolWorkflowBindingsReadError
                              ? t('runs.create.placeholders.bindingsUnavailable')
                              : matchingWorkflowBindings.length === 0
                                ? t('runs.create.placeholders.noMatchingBinding')
                                : t('runs.create.placeholders.selectBinding')
                          }
                          options={matchingWorkflowBindings.map((binding) => ({
                            value: binding.binding_id,
                            label: formatWorkflowBindingOptionLabel(binding),
                          }))}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  {isCreateBindingContextAmbiguous ? (
                    <Alert
                      type="warning"
                      showIcon
                      data-testid="pool-runs-create-binding-ambiguity"
                      message={t('runs.create.alerts.ambiguousContextTitle')}
                      description={t('runs.create.alerts.ambiguousContextDescription')}
                    />
                  ) : null}
                  {selectedCreateBinding ? (
                    <Card
                      size="small"
                      title={t('runs.create.fields.selectedAttachmentTitle')}
                      data-testid="pool-runs-create-selected-binding"
                      style={{ marginBottom: 12 }}
                    >
                      <Descriptions bordered size="small" column={detailDescriptionColumns}>
                        <Descriptions.Item label={t('runs.create.fields.attachmentId')} span={1}>
                          <Text code>{selectedCreateBinding.binding_id ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.attachmentRevision')} span={1}>
                          <Text data-testid="pool-runs-create-attachment-revision">
                            {selectedCreateBinding.revision != null ? `r${selectedCreateBinding.revision}` : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.executionPack')} span={1}>
                          <Text data-testid="pool-runs-create-profile">{resolvePoolWorkflowBindingProfileLabel(selectedCreateBinding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.pinnedPackRevision')} span={1}>
                          <Text data-testid="pool-runs-create-profile-revision">
                            {selectedCreateBinding.binding_profile_revision_number != null
                              ? `r${selectedCreateBinding.binding_profile_revision_number}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.workflowScheme')} span={1}>
                          <Text>
                            {selectedCreateBindingWorkflow?.workflow_name
                              || selectedCreateBindingWorkflow?.workflow_definition_key
                              || '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.workflowRevision')} span={1}>
                          <Text>
                            {selectedCreateBindingWorkflow?.workflow_revision != null
                              ? `r${selectedCreateBindingWorkflow.workflow_revision}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.bindingScope')} span={1}>
                          <Text>{formatWorkflowBindingScope(selectedCreateBinding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.effectivePeriod')} span={1}>
                          <Text>{formatWorkflowBindingEffectivePeriod(selectedCreateBinding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.packStatus')} span={1}>
                          <Text>{resolvePoolWorkflowBindingProfileStatus(selectedCreateBinding) ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.pinnedRevisionId')} span={1}>
                          <Text code>{selectedCreateBinding.binding_profile_revision_id ?? '-'}</Text>
                        </Descriptions.Item>
                        {selectedCreateBindingLifecycleWarning ? (
                          <Descriptions.Item label={t('runs.create.fields.lifecycleWarning')} span={2}>
                            <Alert
                              type="warning"
                              showIcon
                              message={selectedCreateBindingLifecycleWarning.title}
                              description={selectedCreateBindingLifecycleWarning.detail}
                            />
                          </Descriptions.Item>
                        ) : null}
                      </Descriptions>
                    </Card>
                  ) : null}
                  {selectedCreateBinding && !bindingPreview ? (
                    <Card
                      size="small"
                      title={t('runs.create.preview.topologySlotCoverageTitle')}
                      data-testid="pool-runs-create-binding-coverage"
                    >
                      <TopologySlotCoveragePanel
                        summary={createBindingCoverageSummary}
                        summaryTestId="pool-runs-create-slot-coverage-summary"
                        itemTestIdPrefix="pool-runs-create-slot-coverage-item"
                        emptyMessage={t('runs.create.preview.noTopologyEdges')}
                        resolvedMessage={t('runs.create.preview.allTopologyEdgesCoveredBeforePreview')}
                      />
                    </Card>
                  ) : null}

                  {createDirection === 'bottom_up' && (
                    <Row gutter={12}>
                      <Col span={16}>
                        <Form.Item name="source_payload_json" label={t('runs.create.fields.sourcePayloadJson')}>
                          <Input.TextArea data-testid="pool-runs-create-source-payload" rows={6} placeholder='[{"inn":"730000000001","amount":"100.00"}]' />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="source_artifact_id" label={t('runs.create.fields.sourceArtifactId')}>
                          <Input data-testid="pool-runs-create-source-artifact" placeholder={t('runs.create.placeholders.sourceArtifactId')} />
                        </Form.Item>
                        <Upload
                          accept=".json,application/json,text/plain"
                          maxCount={1}
                          showUploadList={false}
                          beforeUpload={async (file) => {
                            try {
                              const text = await file.text()
                              createForm.setFieldValue('source_payload_json', text)
                              message.success(t('runs.create.messages.sourcePayloadLoadedFromFile'))
                            } catch {
                              message.error(t('runs.create.messages.failedToReadSelectedFile'))
                            }
                            return false
                          }}
                        >
                          <Button icon={<UploadOutlined />}>{t('runs.create.actions.loadPayloadFile')}</Button>
                        </Upload>
                      </Col>
                    </Row>
                  )}

                  <Space wrap>
                    <Button
                      onClick={() => void handlePreviewBinding()}
                      loading={previewingBinding}
                      disabled={!selectedPoolId || !createBindingId}
                      data-testid="pool-runs-create-preview"
                    >
                      {t('runs.create.actions.previewBinding')}
                    </Button>
                    <Button type="primary" loading={creatingRun} onClick={() => void handleCreateRun()} data-testid="pool-runs-create-submit">
                      {t('runs.create.actions.createOrUpsertRun')}
                    </Button>
                  </Space>

                  {bindingPreview && (
                    <Card
                      size="small"
                      title={t('runs.create.preview.title')}
                      data-testid="pool-runs-binding-preview"
                      style={{ marginTop: 16 }}
                    >
                      <Descriptions bordered size="small" column={detailDescriptionColumns}>
                        <Descriptions.Item label={t('runs.create.fields.attachmentId')} span={1}>
                          <Text code>{bindingPreview.workflow_binding.binding_id ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.attachmentRevision')} span={1}>
                          <Text data-testid="pool-runs-binding-preview-attachment-revision">
                            {bindingPreview.workflow_binding.revision != null
                              ? `r${bindingPreview.workflow_binding.revision}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.executionPack')} span={1}>
                          <Text data-testid="pool-runs-binding-preview-profile">
                            {resolvePoolWorkflowBindingProfileLabel(bindingPreview.workflow_binding)}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.pinnedPackRevision')} span={1}>
                          <Text data-testid="pool-runs-binding-preview-profile-revision">
                            {bindingPreview.workflow_binding.binding_profile_revision_number != null
                              ? `r${bindingPreview.workflow_binding.binding_profile_revision_number}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.pinnedRevisionId')} span={2}>
                          <Text code>{bindingPreview.workflow_binding.binding_profile_revision_id ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.workflowScheme')} span={1}>
                          <Text>
                            {previewBindingWorkflow?.workflow_name
                              || previewBindingWorkflow?.workflow_definition_key
                              || '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.workflowRevision')} span={1}>
                          <Text>
                            {previewBindingWorkflow?.workflow_revision != null
                              ? `r${previewBindingWorkflow.workflow_revision}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.bindingScope')} span={1}>
                          <Text>{formatWorkflowBindingScope(bindingPreview.workflow_binding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.fields.packStatus')} span={1}>
                          <Text>{resolvePoolWorkflowBindingProfileStatus(bindingPreview.workflow_binding) ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.preview.decisionSnapshot')} span={2}>
                          {previewBindingDecisionRefs.length > 0 ? (
                            <Space size={[4, 4]} wrap>
                                {previewBindingDecisionRefs.map((decision) => (
                                  <Tag key={`${decision.decision_table_id}:${decision.decision_revision}`}>
                                    {decision.slot_key
                                      ? `${decision.slot_key} -> ${decision.decision_key} r${decision.decision_revision}`
                                      : `${decision.decision_key} r${decision.decision_revision}`}
                                  </Tag>
                                ))}
                            </Space>
                          ) : (
                            <Text type="secondary">{t('runs.create.preview.noPinnedDecisionRefs')}</Text>
                          )}
                        </Descriptions.Item>
                        {previewBindingLifecycleWarning ? (
                          <Descriptions.Item label={t('runs.create.fields.lifecycleWarning')} span={2}>
                            <Alert
                              type="warning"
                              showIcon
                              message={previewBindingLifecycleWarning.title}
                              description={previewBindingLifecycleWarning.detail}
                            />
                          </Descriptions.Item>
                        ) : null}
                        <Descriptions.Item label={t('runs.create.preview.slotCoverage')} span={2}>
                          <TopologySlotCoveragePanel
                            summary={bindingPreviewCoverageSummary}
                            summaryTestId="pool-runs-binding-preview-slot-coverage"
                            itemTestIdPrefix="pool-runs-binding-preview-slot-coverage-item"
                            emptyMessage={t('runs.create.preview.noTopologyEdges')}
                            resolvedMessage={t('runs.create.preview.allTopologyEdgesCovered')}
                          />
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.preview.documentPolicySource')} span={1}>
                          <Text>{bindingPreview.runtime_projection.document_policy_projection.source_mode}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.preview.compilePlan')} span={1}>
                          <Text code>{bindingPreview.runtime_projection.workflow_definition.plan_key}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.preview.compileSummary')} span={2}>
                          <Space size={[4, 4]} wrap>
                            <Tag>{t('runs.create.preview.compiledTargets', { count: bindingPreview.runtime_projection.compile_summary.compiled_targets_count })}</Tag>
                            <Tag>{t('runs.create.preview.policyRefs', { count: bindingPreview.runtime_projection.document_policy_projection.policy_refs_count })}</Tag>
                            <Tag>{t('runs.create.preview.steps', { count: bindingPreview.runtime_projection.compile_summary.steps_count })}</Tag>
                            <Tag>{t('runs.create.preview.atomicPublication', { count: bindingPreview.runtime_projection.compile_summary.atomic_publication_steps_count })}</Tag>
                          </Space>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('runs.create.preview.compiledSlotProjection')} span={2}>
                          <TextArea
                            value={JSON.stringify(bindingPreview.compiled_document_policy_slots ?? {}, null, 2)}
                            rows={8}
                            readOnly
                            data-testid="pool-runs-binding-preview-slot-projection"
                          />
                        </Descriptions.Item>
                        {bindingPreview.compiled_document_policy ? (
                          <Descriptions.Item label={t('runs.create.preview.compatibilityPolicyProjection')} span={2}>
                            <TextArea
                              value={JSON.stringify(bindingPreview.compiled_document_policy, null, 2)}
                              rows={6}
                              readOnly
                            />
                          </Descriptions.Item>
                        ) : null}
                      </Descriptions>
                    </Card>
                  )}

                  <PoolBatchIntakeDrawer
                    open={isBatchIntakeDrawerOpen}
                    poolId={selectedPoolId ?? null}
                    poolLabel={selectedPool ? `${selectedPool.code} - ${selectedPool.name}` : t('runs.create.preview.noPoolSelected')}
                    schemaTemplates={schemaTemplates}
                    loadingSchemaTemplates={loadingSchemaTemplates}
                    workflowBindingOptions={receiptBatchWorkflowBindingOptions}
                    startOrganizationOptions={activeTopologyOrganizations}
                    initialValues={{
                      batchKind: 'receipt',
                      periodStart: createPeriodStart,
                      periodEnd: createPeriodEnd || null,
                      poolWorkflowBindingId: createBindingId ?? null,
                      startOrganizationId: createStartOrganizationId ?? null,
                    }}
                    onClose={() => setIsBatchIntakeDrawerOpen(false)}
                    onCreated={handleBatchCreated}
                  />
                </Form>
              </Card>
            ),
          },
          {
            key: 'inspect',
            label: stageLabels.inspect,
            children: (
              <MasterDetailShell
                detailOpen={Boolean(selectedRunId) && isRunDetailOpen}
                onCloseDetail={handleCloseRunDetail}
                detailDrawerTitle={selectedRunId
                  ? `${stageDetailTitles.inspect} · ${formatShortId(selectedRunId)}`
                  : stageDetailTitles.inspect}
                list={(
                  <EntityTable
                    title={t('runs.inspect.listTitle')}
                    loading={loadingRuns}
                    emptyDescription={selectedPoolId
                      ? t('runs.inspect.emptySelectedPool')
                      : t('runs.inspect.emptySelectPool')}
                    dataSource={runs}
                    columns={runColumns}
                    rowKey="id"
                    pagination={{ pageSize: 8 }}
                    onRow={(record) => ({
                      onClick: () => handleSelectRun(record.id),
                      style: { cursor: 'pointer' },
                    })}
                    rowClassName={(record) => (
                      record.id === selectedRunId ? 'ant-table-row-selected' : ''
                    )}
                  />
                )}
                detail={(
                  <Space direction="vertical" size="large" style={{ width: '100%' }}>
                    <Card title={t('runs.inspect.poolGraphTitle')} loading={loadingGraph}>
                      <div style={{ height: 460 }}>
                        <ReactFlow nodes={flow.nodes} edges={flow.edges} fitView>
                          <MiniMap />
                          <Controls />
                          <Background />
                        </ReactFlow>
                      </div>
                    </Card>

                    <Card title={t('runs.inspect.reportTitle')}>
                  {!runDetails && (
                    <Text type="secondary">{t('runs.inspect.selectRunToInspect')}</Text>
                  )}
                  {runDetails && (
                    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                      {reportDetails ? (
                        <Space size="small" wrap>
                          <Tag color="blue">{t('runs.inspect.report.runTag', { runId: formatShortId(runDetails.id) })}</Tag>
                          <Tag color={getStatusColor(runDetails.status)}>{runDetails.status}</Tag>
                          {runDetails.status_reason ? (
                            <Tag color={getStatusReasonColor(runDetails.status_reason)}>{runDetails.status_reason}</Tag>
                          ) : null}
                          <Tag>{t('runs.inspect.report.attempts', { count: reportDetails.publication_attempts.length })}</Tag>
                          {Object.entries(reportDetails.attempts_by_status ?? {}).map(([status, count]) => (
                            <Tag key={status}>{t('runs.inspect.report.attemptStatus', { status, count })}</Tag>
                          ))}
                        </Space>
                      ) : (
                        <Alert
                          type="info"
                          showIcon
                          message={loadingReport
                            ? t('runs.inspect.report.loadingTitle')
                            : t('runs.inspect.report.unavailableTitle')}
                          description={loadingReport
                            ? t('runs.inspect.report.loadingDescription')
                            : t('runs.inspect.report.unavailableDescription')}
                        />
                      )}

                      <Alert
                        type="info"
                        showIcon
                        message={t('runs.inspect.lineage.primaryContextTitle')}
                        description={t('runs.inspect.lineage.primaryContextDescription')}
                      />

                      <Alert
                        type="success"
                        showIcon
                        message={t('runs.inspect.factualWorkspace.title')}
                        description={t('runs.inspect.factualWorkspace.description')}
                        action={(
                          <RouteButton type="primary" size="small" to={factualWorkspaceHref} disabled={!selectedPoolId}>
                            {t('runs.inspect.factualWorkspace.open')}
                          </RouteButton>
                        )}
                      />

                      <Card size="small" title={t('runs.inspect.lineage.title')}>
                        <Descriptions bordered size="small" column={detailDescriptionColumns}>
                        <Descriptions.Item label={t('runs.inspect.lineage.pool')} span={1}>
                            <Text data-testid="pool-runs-lineage-pool">{selectedPoolLabel}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.attachmentId')} span={1}>
                            <Text code data-testid="pool-runs-lineage-binding-id">
                              {workflowBinding?.binding_id ?? runtimeProjection?.workflow_binding.binding_id ?? '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.attachmentRevision')} span={1}>
                            <Text data-testid="pool-runs-lineage-attachment-revision">
                              {workflowBindingAttachmentRevision != null ? `r${workflowBindingAttachmentRevision}` : '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.executionPack')} span={1}>
                            <Text data-testid="pool-runs-lineage-profile">
                              {resolvePoolWorkflowBindingProfileLabel(workflowBinding) !== '-'
                                ? resolvePoolWorkflowBindingProfileLabel(workflowBinding)
                                : (workflowBindingProfileId ?? '-')}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.pinnedPackRevision')} span={1}>
                            <Text data-testid="pool-runs-lineage-profile-revision">
                              {workflowBindingProfileRevisionNumber != null ? `r${workflowBindingProfileRevisionNumber}` : '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.workflowScheme')} span={1}>
                            <Text data-testid="pool-runs-lineage-workflow">
                              {resolveWorkflowLineageName({
                                binding: workflowBinding,
                                runtimeProjection,
                                workflowTemplateName: runDetails.workflow_template_name,
                              })}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.workflowRevision')} span={1}>
                            <Text>
                              {workflowBindingWorkflow?.workflow_revision != null
                                ? `r${workflowBindingWorkflow.workflow_revision}`
                                : runtimeProjection?.workflow_binding.workflow_revision != null
                                  ? `r${runtimeProjection.workflow_binding.workflow_revision}`
                                  : '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.bindingScope')} span={1}>
                            <Text>{formatWorkflowBindingScope(workflowBinding)}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.effectivePeriod')} span={1}>
                            <Text>{formatWorkflowBindingEffectivePeriod(workflowBinding)}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.packStatus')} span={1}>
                            <Text>{workflowBindingProfileStatus ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.fields.pinnedRevisionId')} span={1}>
                            <Text code>{workflowBindingProfileRevisionId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.lineage.executionPackId')} span={1}>
                            <Text code>{workflowBindingProfileId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.preview.decisionSnapshot')} span={2}>
                            {workflowDecisionRefs.length > 0 ? (
                              <Space size={[4, 4]} wrap>
                                {workflowDecisionRefs.map((decision) => (
                                  <Tag key={`${decision.decision_table_id}:${decision.decision_revision}`}>
                                    {decision.slot_key
                                      ? `${decision.slot_key} -> ${decision.decision_key} r${decision.decision_revision}`
                                      : `${decision.decision_key} r${decision.decision_revision}`}
                                  </Tag>
                                ))}
                              </Space>
                            ) : (
                              <Text type="secondary">{t('runs.create.preview.noPinnedDecisionRefs')}</Text>
                            )}
                          </Descriptions.Item>
                          {workflowBindingLifecycleWarning ? (
                            <Descriptions.Item label={t('runs.create.fields.lifecycleWarning')} span={2}>
                              <Alert
                                type="warning"
                                showIcon
                                message={workflowBindingLifecycleWarning.title}
                                description={workflowBindingLifecycleWarning.detail}
                              />
                            </Descriptions.Item>
                          ) : null}
                          <Descriptions.Item label={t('runs.create.preview.slotCoverage')} span={2}>
                            <TopologySlotCoveragePanel
                              summary={runLineageCoverageSummary}
                              summaryTestId="pool-runs-lineage-slot-coverage"
                              itemTestIdPrefix="pool-runs-lineage-slot-coverage-item"
                              emptyMessage={t('runs.create.preview.noTopologyEdges')}
                              resolvedMessage={t('runs.inspect.preview.lineageCoverageResolved')}
                            />
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.lineage.slotProjection')} span={2}>
                            {runtimeProjection ? (
                              <TextArea
                                data-testid="pool-runs-lineage-slot-projection"
                                value={JSON.stringify(runLineageSlotProjection ?? {}, null, 2)}
                                autoSize={{ minRows: 8, maxRows: 20 }}
                                readOnly
                              />
                            ) : (
                              <Text type="secondary">{t('runs.inspect.preview.noPersistedSlotProjection')}</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.lineage.compiledRuntime')} span={1}>
                            <Text>{runtimeProjection?.workflow_definition.workflow_template_name ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.preview.compilePlan')} span={1}>
                            <Text code>{runtimeProjection?.workflow_definition.plan_key ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.create.preview.compileSummary')} span={2}>
                            {runtimeProjection ? (
                              <Space size={[4, 4]} wrap>
                                <Tag>{t('runs.create.preview.compiledTargets', { count: runtimeProjection.compile_summary.compiled_targets_count })}</Tag>
                                <Tag>{t('runs.create.preview.policyRefs', { count: runtimeProjection.document_policy_projection.policy_refs_count })}</Tag>
                                <Tag>{t('runs.create.preview.steps', { count: runtimeProjection.compile_summary.steps_count })}</Tag>
                                <Tag>{t('runs.create.preview.atomicPublication', { count: runtimeProjection.compile_summary.atomic_publication_steps_count })}</Tag>
                              </Space>
                            ) : (
                              <Text type="secondary">{t('runs.inspect.preview.noCompiledRuntimeProjection')}</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.lineage.workflowDiagnostics')} span={2}>
                            {workflowDiagnosticsId ? (
                              <RouteButton
                                type="link"
                                to={`/workflows/executions/${workflowDiagnosticsId}`}
                                style={{ paddingInline: 0 }}
                              >
                                {t('runs.inspect.lineage.openWorkflowDiagnostics')}
                              </RouteButton>
                            ) : (
                              <Text type="secondary">{t('runs.inspect.preview.noWorkflowDiagnostics')}</Text>
                            )}
                          </Descriptions.Item>
                        </Descriptions>
                      </Card>

                      <Card size="small" title={t('runs.inspect.runtime.title')}>
                        <Descriptions bordered size="small" column={detailDescriptionColumns}>
                          <Descriptions.Item label={t('runs.inspect.runtime.workflowRun')} span={1}>
                            <Text code data-testid="pool-runs-provenance-workflow-id">{workflowRunId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.workflowStatus')} span={1}>
                            {workflowStatus ? <Tag color="processing">{workflowStatus}</Tag> : <Text type="secondary">{t('runs.inspect.runtime.legacy')}</Text>}
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.rootOperation')} span={1}>
                            <Text code data-testid="pool-runs-provenance-root-operation-id">{rootOperationId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.executionConsumer')} span={1}>
                            <Text data-testid="pool-runs-provenance-execution-consumer">{executionConsumer ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.lane')} span={1}>
                            <Text data-testid="pool-runs-provenance-lane">{lane ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.executionBackend')} span={1}>
                            <Text>{executionBackend ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.workflowTemplate')} span={1}>
                            <Text>{runDetails.workflow_template_name ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.inputContract')} span={1}>
                            <Tag color={getInputContractColor(resolveInputContractVersion(runDetails))}>
                              {resolveInputContractVersion(runDetails)}
                            </Tag>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.runInput')} span={2}>
                            <Text>{summarizeRunInput(runDetails)}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.approvalState')} span={1}>
                            {runDetails.approval_state ? (
                              <Tag color={getApprovalStateColor(runDetails.approval_state)}>{runDetails.approval_state}</Tag>
                            ) : (
                              <Text type="secondary">{t('runs.inspect.runtime.notAvailable')}</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.publicationStep')} span={1}>
                            {runDetails.publication_step_state ? (
                              <Tag color={getPublicationStepColor(runDetails.publication_step_state)}>{runDetails.publication_step_state}</Tag>
                            ) : (
                              <Text type="secondary">{t('runs.inspect.runtime.notAvailable')}</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.terminalReason')} span={2}>
                            <Text>{runDetails.terminal_reason ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={t('runs.inspect.runtime.retryChain')} span={2}>
                            {retryChain.length > 0 ? (
                              <Space direction="vertical" size={4}>
                                {retryChain.map((item: PoolRunRetryChainAttempt) => (
                                  <Space key={item.workflow_run_id} size={4} wrap>
                                    <Tag color={getWorkflowAttemptKindColor(item.attempt_kind)}>
                                      #{item.attempt_number} {item.attempt_kind}
                                    </Tag>
                                    <Tag color={getWorkflowExecutionStatusColor(item.status)}>{item.status}</Tag>
                                    <Text code>{formatShortId(item.workflow_run_id)}</Text>
                                    {item.parent_workflow_run_id ? (
                                      <Text type="secondary">{t('runs.inspect.runtime.parentRun', { runId: formatShortId(item.parent_workflow_run_id) })}</Text>
                                    ) : (
                                      <Text type="secondary">{t('runs.inspect.runtime.rootRun')}</Text>
                                    )}
                                  </Space>
                                ))}
                              </Space>
                            ) : (
                              <Text type="secondary">{t('runs.inspect.runtime.empty')}</Text>
                            )}
                          </Descriptions.Item>
                        </Descriptions>
                      </Card>

                      <Card size="small" title={t('runs.inspect.masterDataGate.title')}>
                        {!masterDataGate && (
                          <Text type="secondary">
                            {t('runs.inspect.masterDataGate.historicalNotCaptured')}
                          </Text>
                        )}
                        {masterDataGate && (
                          <Space direction="vertical" size="small" style={{ width: '100%' }}>
                            <Space size="small" wrap>
                              <Tag color={MASTER_DATA_GATE_STATUS_COLORS[masterDataGate.status] ?? 'default'}>
                                {t('runs.inspect.masterDataGate.tags.status', { value: masterDataGate.status })}
                              </Tag>
                              <Tag>{t('runs.inspect.masterDataGate.tags.mode', { value: masterDataGate.mode })}</Tag>
                              <Tag>{t('runs.inspect.masterDataGate.tags.targets', { count: masterDataGate.targets_count })}</Tag>
                              <Tag>{t('runs.inspect.masterDataGate.tags.bindings', { count: masterDataGate.bindings_count })}</Tag>
                            </Space>
                            {masterDataGate.error_code && (
                              <Alert
                                type="error"
                                showIcon
                                message={masterDataGate.error_code}
                                description={masterDataGate.detail || t('runs.inspect.masterDataGate.failedFallback')}
                              />
                            )}
                            {masterDataGateHint && (
                              <Alert
                                type="info"
                                showIcon
                                message={t('runs.inspect.masterDataGate.remediationHintTitle')}
                                description={masterDataGateHint}
                              />
                            )}
                            {masterDataGateRemediationTarget && (
                              <RouteButton
                                type="link"
                                to={masterDataGateRemediationTarget.href}
                                style={{ paddingInline: 0 }}
                              >
                                {masterDataGateRemediationTarget.label}
                              </RouteButton>
                            )}
                            {masterDataGateContextLines.length > 0 && (
                              <Space direction="vertical" size={0}>
                                <Text strong>{t('runs.inspect.masterDataGate.diagnosticContext')}</Text>
                                {masterDataGateContextLines.map((line) => (
                                  <Text key={line} code>
                                    {line}
                                  </Text>
                                ))}
                              </Space>
                            )}
                          </Space>
                        )}
                      </Card>

                      <Card size="small" title={t('runs.inspect.readiness.title')}>
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <Space size="small" wrap>
                            <Tag
                              color={READINESS_STATUS_COLORS[readinessChecklist.status] ?? 'default'}
                              data-testid="pool-runs-readiness-status"
                            >
                              {t('runs.inspect.readiness.tags.status', { value: readinessChecklist.status })}
                            </Tag>
                            <Tag>{t('runs.inspect.readiness.tags.checks', { count: readinessChecklist.checks.length })}</Tag>
                            <Tag>{t('runs.inspect.readiness.tags.blockers', { count: readinessBlockers.length })}</Tag>
                          </Space>
                          {readinessChecklist.checks.map((check) => (
                            <Alert
                              key={check.code}
                              type={check.status === 'ready' ? 'success' : check.blockers.length > 0 ? 'error' : 'warning'}
                              showIcon
                              message={resolveReadinessCheckLabel(check.code)}
                              description={(
                                <Space direction="vertical" size={2}>
                                  <Text>{t('runs.inspect.readiness.tags.status', { value: check.status })}</Text>
                                  {check.blockers.length === 0 ? (
                                    <Text type="secondary">{t('runs.inspect.readiness.noBlockingDiagnostics')}</Text>
                                  ) : (
                                    check.blockers.map((blocker, index) => {
                                      const contextLines = buildReadinessBlockerContextLines(blocker)
                                      const hint = resolveReadinessBlockerHint(blocker)
                                      const remediationTarget = resolveMasterDataRemediationTarget({
                                        code: typeof blocker.code === 'string' ? blocker.code : null,
                                        diagnostic: blocker.diagnostic,
                                        requiredRole: blocker.required_role ?? null,
                                      })
                                      const title = blocker.code || blocker.kind || `${check.code}_${index + 1}`

                                      return (
                                        <Space key={`${title}-${index}`} direction="vertical" size={2}>
                                          <Text strong>{title}</Text>
                                          <Text>{blocker.detail || t('runs.inspect.readiness.blockedFallback')}</Text>
                                          {contextLines.map((line) => (
                                            <Text key={line} code>{line}</Text>
                                          ))}
                                          {hint ? <Text type="secondary">{hint}</Text> : null}
                                          {remediationTarget ? (
                                            <RouteButton
                                              type="link"
                                              to={remediationTarget.href}
                                              style={{ paddingInline: 0 }}
                                            >
                                              {remediationTarget.label}
                                            </RouteButton>
                                          ) : null}
                                        </Space>
                                      )
                                    })
                                  )}
                                </Space>
                              )}
                            />
                          ))}
                        </Space>
                      </Card>

                      <Card size="small" title={t('runs.inspect.verification.title')}>
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <Space size="small" wrap>
                            <Tag
                              color={VERIFICATION_STATUS_COLORS[verificationStatus] ?? 'default'}
                              data-testid="pool-runs-verification-status"
                            >
                              {t('runs.inspect.verification.tags.status', { value: verificationStatus })}
                            </Tag>
                            {verificationSummary ? <Tag>{t('runs.inspect.verification.tags.targets', { count: verificationSummary.checked_targets })}</Tag> : null}
                            {verificationSummary ? <Tag>{t('runs.inspect.verification.tags.documents', { count: verificationSummary.verified_documents })}</Tag> : null}
                            {verificationSummary ? <Tag>{t('runs.inspect.verification.tags.mismatches', { count: verificationSummary.mismatches_count })}</Tag> : null}
                          </Space>
                          {verificationStatus === 'not_verified' && (
                            <Alert
                              type="info"
                              showIcon
                              message={t('runs.inspect.verification.notStartedTitle')}
                              description={t('runs.inspect.verification.notStartedDescription')}
                            />
                          )}
                          {verificationStatus === 'passed' && verificationSummary && (
                            <Alert
                              type="success"
                              showIcon
                              message={t('runs.inspect.verification.verifiedTitle')}
                              description={t('runs.inspect.verification.verifiedDescription', {
                                checkedTargets: verificationSummary.checked_targets,
                                verifiedDocuments: verificationSummary.verified_documents,
                              })}
                            />
                          )}
                          {verificationStatus === 'failed' && verificationSummary && (
                            <Collapse
                              items={[
                                {
                                  key: 'verification-mismatches',
                                  label: t('runs.inspect.verification.mismatches', { count: verificationSummary.mismatches_count }),
                                  children: (
                                    <Table
                                      rowKey={(item) => [
                                        item.database_id ?? '-',
                                        item.document_idempotency_key ?? '-',
                                        item.field_or_table_path ?? '-',
                                        item.kind ?? '-',
                                      ].join(':')}
                                      size="small"
                                      columns={verificationMismatchColumns}
                                      dataSource={verificationSummary.mismatches}
                                      pagination={{ pageSize: 5 }}
                                    />
                                  ),
                                },
                              ]}
                            />
                          )}
                        </Space>
                      </Card>

                      {reportDetails ? (
                        <>
                          <Text strong>{t('runs.inspect.publicationAttempts.title')}</Text>
                          <Table
                            rowKey="id"
                            size="small"
                            columns={publicationAttemptColumns}
                            dataSource={reportDetails.publication_attempts}
                            pagination={{ pageSize: 5 }}
                          />

                          <Collapse
                            items={[
                              {
                                key: 'diagnostics-json',
                                label: t('runs.inspect.diagnostics.title'),
                                children: (
                                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                                    <Text strong>{t('runs.inspect.diagnostics.runInput')}</Text>
                                    <TextArea
                                      data-testid="pool-runs-run-input"
                                      readOnly
                                      rows={6}
                                      value={JSON.stringify(runDetails.run_input ?? null, null, 2)}
                                    />
                                    <Text strong>{t('runs.inspect.diagnostics.validationSummary')}</Text>
                                    <TextArea
                                      readOnly
                                      rows={4}
                                      value={JSON.stringify(reportDetails.validation_summary ?? {}, null, 2)}
                                    />
                                    <Text strong>{t('runs.inspect.diagnostics.publicationSummary')}</Text>
                                    <TextArea
                                      readOnly
                                      rows={4}
                                      value={JSON.stringify(reportDetails.publication_summary ?? {}, null, 2)}
                                    />
                                    <Text strong>{t('runs.inspect.diagnostics.stepDiagnostics')}</Text>
                                    <TextArea
                                      readOnly
                                      rows={6}
                                      value={JSON.stringify(reportDetails.diagnostics ?? [], null, 2)}
                                    />
                                  </Space>
                                ),
                              },
                            ]}
                          />
                        </>
                      ) : null}
                    </Space>
                  )}
                    </Card>
                  </Space>
                )}
              />
            ),
          },
          {
            key: 'safe',
            label: stageLabels.safe,
            children: (
              <Card
                title={t('runs.safe.title')}
                extra={<Text type="secondary">{t('runs.safe.idempotencyHint')}</Text>}
              >
                {!runDetails && <Text type="secondary">{t('runs.safe.selectRun')}</Text>}
                {runDetails && runDetails.mode !== 'safe' && (
                  <Alert type="info" showIcon message={t('runs.safe.unsafeMode')} />
                )}
                {runDetails && runDetails.mode === 'safe' && (
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag color="geekblue">{t('runs.create.options.safe')}</Tag>
                      {runDetails.status_reason ? <Tag color={getStatusReasonColor(runDetails.status_reason)}>{runDetails.status_reason}</Tag> : null}
                      {runDetails.approval_state ? <Tag color={getApprovalStateColor(runDetails.approval_state)}>{runDetails.approval_state}</Tag> : null}
                      {runDetails.publication_step_state ? <Tag color={getPublicationStepColor(runDetails.publication_step_state)}>{runDetails.publication_step_state}</Tag> : null}
                    </Space>
                    {isSafePrePublishPreparing && (
                      <Alert
                        type="info"
                        showIcon
                        message={t('runs.safe.prePublishTitle')}
                        description={t('runs.safe.prePublishDescription')}
                      />
                    )}
                    {readinessBlockers.length > 0 && (
                      <Alert
                        type="error"
                        showIcon
                        message={t('runs.safe.readinessBlockedTitle')}
                        description={t('runs.safe.readinessBlockedDescription', { count: readinessBlockers.length })}
                      />
                    )}
                    <Text type="secondary">
                      {t('runs.safe.diagnosticsNote')}
                    </Text>
                    <Space>
                      <Button
                        type="primary"
                        data-testid="pool-runs-safe-confirm"
                        loading={safeActionLoading === 'confirm-publication'}
                        title={isSafePrePublishPreparing ? t('runs.safe.confirmAvailableAfter') : undefined}
                        disabled={!canConfirm}
                        onClick={() => void handleSafeCommand('confirm-publication')}
                      >
                        {t('runs.safe.confirmPublication')}
                      </Button>
                      <Button
                        danger
                        data-testid="pool-runs-safe-abort"
                        loading={safeActionLoading === 'abort-publication'}
                        disabled={!canAbort}
                        onClick={() => void handleSafeCommand('abort-publication')}
                      >
                        {t('runs.safe.abortPublication')}
                      </Button>
                    </Space>
                  </Space>
                )}
              </Card>
            ),
          },
          {
            key: 'retry',
            label: stageLabels.retry,
            children: (
              <Card title={t('runs.retry.title')}>
                <Form form={retryForm} layout="vertical" initialValues={RETRY_FORM_INITIAL_VALUES}>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item name="entity_name" label={t('runs.retry.fields.entityName')} rules={[{ required: true }]}>
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="max_attempts" label={t('runs.retry.fields.maxAttempts')} rules={[{ required: true }]}>
                        <InputNumber min={1} max={5} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item
                        name="retry_interval_seconds"
                        label={t('runs.retry.fields.retryIntervalSeconds')}
                        rules={[{ required: true }]}
                      >
                        <InputNumber min={0} max={120} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item
                    name="documents_json"
                    label={t('runs.retry.fields.documentsJson')}
                    rules={[{ required: true }]}
                  >
                    <TextArea rows={8} />
                  </Form.Item>
                  <Button type="primary" loading={retrying} onClick={() => void handleRetryFailed()} disabled={!selectedRunId}>
                    {t('runs.retry.submit')}
                  </Button>
                </Form>
              </Card>
            ),
          },
        ]}
      />
    </WorkspacePage>
  )
}
