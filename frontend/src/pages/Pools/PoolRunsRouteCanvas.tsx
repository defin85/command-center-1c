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
  listPoolRuns,
  listPoolSchemaTemplates,
  previewPoolWorkflowBinding,
  retryPoolRunFailed,
  type CreatePoolRunPayload,
  type OrganizationPool,
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
import { POOL_RUNS_ROUTE } from './routes'

const { Text } = Typography
const { TextArea } = Input
const { useBreakpoint } = Grid

type CreateRunFormValues = {
  period_start: string
  period_end?: string
  direction: 'top_down' | 'bottom_up'
  mode: 'safe' | 'unsafe'
  pool_workflow_binding_id?: string
  starting_amount?: number
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
  starting_amount: 100,
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

const CREATE_RUN_PROBLEM_CODE_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: 'Проверьте корректность параметров запуска.',
  TENANT_CONTEXT_REQUIRED: 'Для запуска run требуется активный tenant context.',
  POOL_NOT_FOUND: 'Пул не найден в текущем tenant context.',
  POOL_WORKFLOW_BINDING_REQUIRED: 'Перед продолжением выберите workflow binding.',
  POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID: (
    'Исправьте topology-aware alias в document policy: malformed alias блокирует compile до публикации.'
  ),
  MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING: (
    'Создайте Organization->Party binding для topology participant и повторите запуск.'
  ),
  MASTER_DATA_PARTY_ROLE_MISSING: (
    'Проверьте Organization->Party binding и требуемую роль topology participant перед повторным запуском.'
  ),
  POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING: 'Сохранённые workflow bindings ссылаются на отсутствующий execution-pack revision. Выполните destructive reset затронутых данных и пересоздайте attachment.',
  POOL_WORKFLOW_BINDING_NOT_FOUND: 'Выбранный attachment больше не найден в текущем пуле.',
  POOL_WORKFLOW_BINDING_NOT_RESOLVED: 'Выбранный attachment неактивен или не попадает в effective scope для текущего запуска.',
  POOL_WORKFLOW_BINDING_AMBIGUOUS: 'Найдено несколько подходящих workflow bindings. Нужен явный выбор binding.',
  POOL_WORKFLOW_BINDING_INVALID: 'Сохранённые workflow bindings невалидны и не могут быть использованы для запуска.',
  SCHEMA_TEMPLATE_NOT_FOUND: 'Выбранный schema template недоступен в текущем tenant context.',
  ODATA_MAPPING_NOT_CONFIGURED: 'Для target databases не настроены OData Infobase Users. Проверьте /rbac → Infobase Users.',
  ODATA_MAPPING_AMBIGUOUS: 'Обнаружены неоднозначные OData Infobase Users mappings. Исправьте дубликаты в /rbac → Infobase Users.',
  ODATA_PUBLICATION_AUTH_CONTEXT_INVALID: 'Некорректный publication auth context. Проверьте запуск run и настройки /rbac → Infobase Users.',
}

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

const READINESS_CHECK_LABELS: Record<string, string> = {
  master_data_coverage: 'Master data coverage',
  organization_party_bindings: 'Organization->Party bindings',
  policy_completeness: 'Policy completeness',
  odata_verify_readiness: 'OData verify readiness',
}

const READINESS_CHECK_ORDER: PoolRunReadinessCheck['code'][] = [
  'master_data_coverage',
  'organization_party_bindings',
  'policy_completeness',
  'odata_verify_readiness',
]

const MASTER_DATA_GATE_REMEDIATION_HINTS: Record<string, string> = {
  MASTER_DATA_GATE_CONFIG_INVALID: (
    'Проверьте runtime setting pools.master_data.gate_enabled: значение должно приводиться к bool.'
  ),
  MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING: (
    'Выполните backfill Organization->Party и закройте remediation-list перед повторным запуском run.'
  ),
  MASTER_DATA_PARTY_ROLE_MISSING: (
    'Проверьте роль master_party для выбранного topology participant и обновите Organization->Party binding.'
  ),
  MASTER_DATA_ENTITY_NOT_FOUND: (
    'Создайте/исправьте canonical сущность в /pools/master-data и повторите run.'
  ),
  MASTER_DATA_BINDING_AMBIGUOUS: (
    'Уберите дубли scope в Bindings (entity+canonical+database+qualifier) и повторите run.'
  ),
  MASTER_DATA_BINDING_CONFLICT: (
    'Проверьте token scope, owner qualifier и ib_ref_key для target database.'
  ),
  POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID: (
    'Исправьте topology-aware alias в document policy: допустимы только parent/child participant aliases.'
  ),
  POOL_DOCUMENT_POLICY_MAPPING_INVALID: (
    'Дополните document policy: обязательные поля и табличные части должны присутствовать в completeness profile и mapping.'
  ),
}

const MASTER_DATA_WORKSPACE_TAB_LABELS: Record<string, string> = {
  party: 'Party',
  item: 'Item',
  contract: 'Contract',
  'tax-profile': 'TaxProfile',
  bindings: 'Bindings',
}

const DEFAULT_STAGE: PoolRunsStage = 'create'
const STAGE_LABELS: Record<PoolRunsStage, string> = {
  create: 'Create',
  inspect: 'Inspect',
  safe: 'Safe Actions',
  retry: 'Retry Failed',
}
const STAGE_DETAIL_TITLES: Record<PoolRunsStage, string> = {
  create: 'Create run',
  inspect: 'Inspect run',
  safe: 'Safe actions',
  retry: 'Retry failed targets',
}
const STAGE_MESSAGES: Record<PoolRunsStage, string> = {
  create: (
    'Start a run from the selected pool context, preview the pinned workflow binding, and keep heavy runtime lineage out of the primary authoring flow.'
  ),
  inspect: (
    'Inspect lineage, readiness, master-data gate, verification, and workflow runtime for the selected run without mixing authoring and remediation as primary content.'
  ),
  safe: (
    'Confirm or abort safe publication only after inspect stage shows that readiness blockers are resolved and the selected run is in the correct approval state.'
  ),
  retry: (
    'Retry failed targets for the selected run from a dedicated remediation stage with explicit payload review, instead of mixing retry controls into the default inspect canvas.'
  ),
}

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
  return new Date(value).toLocaleString()
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
    throw new Error('documents_by_database: invalid JSON')
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('documents_by_database: object expected')
  }

  const asObject = parsed as Record<string, unknown>
  const result: Record<string, Array<Record<string, unknown>>> = {}
  for (const [databaseId, rows] of Object.entries(asObject)) {
    if (!Array.isArray(rows)) {
      throw new Error(`documents_by_database.${databaseId}: array expected`)
    }
    result[databaseId] = rows.map((item) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        throw new Error(`documents_by_database.${databaseId}: object rows expected`)
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
    throw new Error('source_payload: invalid JSON')
  }
  if (!parsed || (typeof parsed !== 'object' && !Array.isArray(parsed))) {
    throw new Error('source_payload: object or array expected')
  }
  if (!Array.isArray(parsed)) {
    return parsed as Record<string, unknown>
  }
  return parsed.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new Error('source_payload: array items must be objects')
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
  const runInput: Record<string, unknown> = {}
  const workflowBindingId = values.pool_workflow_binding_id?.trim() || ''
  let schemaTemplateId: string | null | undefined = undefined

  if (!workflowBindingId) {
    throw new Error('Выберите workflow binding для запуска run.')
  }

  if (values.direction === 'top_down') {
    const startingAmount = Number(values.starting_amount)
    if (!Number.isFinite(startingAmount) || startingAmount <= 0) {
      throw new Error('top_down: starting amount должен быть положительным числом.')
    }
    runInput.starting_amount = startingAmount.toFixed(2)
  } else {
    const artifactId = values.source_artifact_id?.trim()
    const sourcePayloadRaw = values.source_payload_json?.trim() || ''
    if (sourcePayloadRaw.length > 0) {
      runInput.source_payload = parseBottomUpSourcePayload(sourcePayloadRaw)
    }
    if (artifactId) {
      runInput.source_artifact_id = artifactId
    }
    if (!Object.prototype.hasOwnProperty.call(runInput, 'source_payload') && !artifactId) {
      throw new Error('bottom_up: укажите source payload JSON или source artifact ID.')
    }
    schemaTemplateId = values.schema_template_id?.trim() || null
  }

  return {
    pool_id: poolId,
    pool_workflow_binding_id: workflowBindingId,
    direction: values.direction,
    period_start: values.period_start,
    period_end: values.period_end?.trim() || null,
    run_input: runInput,
    mode: values.mode,
    schema_template_id: schemaTemplateId,
  }
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
    return `target database ${targetDatabaseIds[0]}`
  }
  return `target databases ${targetDatabaseIds.join(', ')}`
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
      return (
        `Для пользователя ${actorUsername} не настроен actor OData Infobase User `
        + `для ${targetLabel}. Проверьте /rbac → Infobase Users.`
      )
    }
    if (targetLabel) {
      return `Для ${targetLabel} не настроены OData Infobase Users. Проверьте /rbac → Infobase Users.`
    }
  }

  const codeMessage = CREATE_RUN_PROBLEM_CODE_MESSAGES[problem.code]
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
  const codeMessage = problem.code ? CREATE_RUN_PROBLEM_CODE_MESSAGES[problem.code] : undefined
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
    blockers.push({
      code: typeof raw.code === 'string' ? raw.code : null,
      detail: typeof raw.detail === 'string' ? raw.detail : null,
      kind: typeof raw.kind === 'string' ? raw.kind : null,
      entity_name: typeof raw.entity_name === 'string' ? raw.entity_name : null,
      field_or_table_path: typeof raw.field_or_table_path === 'string' ? raw.field_or_table_path : null,
      database_id: typeof raw.database_id === 'string' ? raw.database_id : null,
      organization_id: typeof raw.organization_id === 'string' ? raw.organization_id : null,
      edge_ref: raw.edge_ref && typeof raw.edge_ref === 'object' && !Array.isArray(raw.edge_ref)
        ? {
          parent_node_id: typeof (raw.edge_ref as Record<string, unknown>).parent_node_id === 'string'
            ? (raw.edge_ref as Record<string, unknown>).parent_node_id as string
            : null,
          child_node_id: typeof (raw.edge_ref as Record<string, unknown>).child_node_id === 'string'
            ? (raw.edge_ref as Record<string, unknown>).child_node_id as string
            : null,
        }
        : null,
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

const resolveReadinessCheckLabel = (checkCode: PoolRunReadinessCheck['code']): string => (
  READINESS_CHECK_LABELS[checkCode] ?? checkCode
)

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
  return MASTER_DATA_GATE_REMEDIATION_HINTS[errorCode] ?? null
}

const buildMasterDataWorkspaceHref = ({
  tab,
  entityType,
  canonicalId,
  databaseId,
  role,
}: {
  tab: string
  entityType?: string
  canonicalId?: string
  databaseId?: string
  role?: string
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

  if (code === 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING' || code === 'MASTER_DATA_PARTY_ROLE_MISSING') {
    return {
      label: 'Open Bindings workspace',
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
      label: 'Open Bindings workspace',
      href: buildMasterDataWorkspaceHref({
        tab: 'bindings',
        entityType: normalizeMasterDataBindingEntityType(entityType),
        canonicalId,
        databaseId,
      }),
    }
  }

  if (code === 'MASTER_DATA_ENTITY_NOT_FOUND') {
    const tab = resolveMasterDataEntityWorkspaceTab(entityType)
    if (!tab) {
      return {
        label: 'Open Master Data workspace',
        href: '/pools/master-data',
      }
    }
    return {
      label: `Open ${MASTER_DATA_WORKSPACE_TAB_LABELS[tab] ?? 'Master Data'} workspace`,
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
  return MASTER_DATA_GATE_REMEDIATION_HINTS[code] ?? null
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
  const workflowName = workflow?.workflow_name || workflow?.workflow_definition_key || 'workflow'
  const bindingId = binding.binding_id || 'binding'
  const profileRevision = binding.binding_profile_revision_number != null
    ? `profile r${binding.binding_profile_revision_number}`
    : ''
  const attachmentRevision = binding.revision != null ? `attach r${binding.revision}` : ''
  return [workflowName, profileRevision, attachmentRevision, bindingId.slice(0, 8)]
    .filter((part) => part && part.trim().length > 0)
    .join(' · ')
}

const formatWorkflowBindingScope = (binding: PoolWorkflowBinding | null | undefined): string => {
  const selector = binding?.selector ?? {}
  const parts: string[] = []
  if (selector.direction) {
    parts.push(`direction=${selector.direction}`)
  }
  if (selector.mode) {
    parts.push(`mode=${selector.mode}`)
  }
  if (selector.tags && selector.tags.length > 0) {
    parts.push(`tags=${selector.tags.join(', ')}`)
  }
  return parts.length > 0 ? parts.join(' · ') : 'unscoped'
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
        <Tag>edges: {summary.totalEdges}</Tag>
        <Tag color="success">resolved: {summary.counts.resolved}</Tag>
        {summary.counts.missing_slot > 0 ? (
          <Tag color="error">missing slot: {summary.counts.missing_slot}</Tag>
        ) : null}
        {summary.counts.missing_selector > 0 ? (
          <Tag color="default">missing selector: {summary.counts.missing_selector}</Tag>
        ) : null}
        {summary.counts.ambiguous_slot > 0 ? (
          <Tag color="warning">ambiguous slot: {summary.counts.ambiguous_slot}</Tag>
        ) : null}
        {summary.counts.ambiguous_context > 0 ? (
          <Tag color="warning">ambiguous context: {summary.counts.ambiguous_context}</Tag>
        ) : null}
        {summary.counts.unavailable_context > 0 ? (
          <Tag color="default">context unavailable: {summary.counts.unavailable_context}</Tag>
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
              {`${item.edgeLabel} · ${item.slotKey || 'slot not set'} · ${item.coverage.label}`}
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
  const screens = useBreakpoint()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const pendingRouteSyncRef = useRef<RouteSyncState | null>(null)
  const previousStageRef = useRef<PoolRunsStage>(DEFAULT_STAGE)
  const previousSelectedRunIdRef = useRef<string | null>(null)
  const defaultGraphDateRef = useRef(getDefaultGraphDate())
  const poolFromUrl = normalizeRouteParam(searchParams.get('pool'))
  const runFromUrl = normalizeRouteParam(searchParams.get('run'))
  const stageFromUrl = parsePoolRunsStage(searchParams.get('stage'))
  const graphDateFromUrl = parseGraphDate(searchParams.get('date'), defaultGraphDateRef.current)
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [schemaTemplates, setSchemaTemplates] = useState<PoolSchemaTemplate[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null | undefined>(
    () => poolFromUrl ?? undefined
  )
  const [graphDate, setGraphDate] = useState<string>(graphDateFromUrl)
  const [graph, setGraph] = useState<PoolGraph | null>(null)
  const [runs, setRuns] = useState<PoolRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(() => runFromUrl)
  const [report, setReport] = useState<PoolRunReport | null>(null)
  const [loadingPools, setLoadingPools] = useState(false)
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
  const [createForm] = Form.useForm<CreateRunFormValues>()
  const [retryForm] = Form.useForm<RetryFormValues>()
  const selectedPoolIdRef = useRef<string | null | undefined>(selectedPoolId)
  const selectedRunIdRef = useRef<string | null>(selectedRunId)
  const loadRunsRequestRef = useRef(0)
  const loadReportRequestRef = useRef(0)

  selectedPoolIdRef.current = selectedPoolId
  selectedRunIdRef.current = selectedRunId

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
  const createBindingId = Form.useWatch('pool_workflow_binding_id', createForm)
  const createStartingAmount = Form.useWatch('starting_amount', createForm)
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
      detail: `Coverage is evaluated against selected binding ${bindingLabel}.`,
      selectors: topologyEdgeSelectors,
      source: 'selected',
    })
  }, [selectedCreateBinding, topologyEdgeSelectors])
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
      setError('Не удалось загрузить список пулов.')
    } finally {
      setLoadingPools(false)
    }
  }, [])

  const loadSchemaTemplates = useCallback(async () => {
    setLoadingSchemaTemplates(true)
    try {
      const data = await listPoolSchemaTemplates({ isPublic: true, isActive: true })
      setSchemaTemplates(data)
    } catch {
      setError('Не удалось загрузить шаблоны импорта.')
    } finally {
      setLoadingSchemaTemplates(false)
    }
  }, [])

  const loadGraph = useCallback(async () => {
    if (!selectedPoolId) {
      setGraph(null)
      return
    }
    setLoadingGraph(true)
    try {
      const data = await getPoolGraph(selectedPoolId, graphDate || undefined)
      setGraph(data)
    } catch {
      setError('Не удалось загрузить граф пула.')
    } finally {
      setLoadingGraph(false)
    }
  }, [graphDate, selectedPoolId])

  const loadRuns = useCallback(async (options?: { preferredRunId?: string | null }) => {
    const poolId = selectedPoolId
    if (!poolId) {
      setRuns([])
      setSelectedRunId(null)
      return
    }
    const requestId = loadRunsRequestRef.current + 1
    loadRunsRequestRef.current = requestId
    setLoadingRuns(true)
    try {
      const data = await listPoolRuns({ poolId, limit: 100 })
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
        setError('Не удалось загрузить список run.')
      }
    } finally {
      if (loadRunsRequestRef.current === requestId) {
        setLoadingRuns(false)
      }
    }
  }, [selectedPoolId])

  const loadReport = useCallback(async () => {
    const runId = selectedRunId
    if (!runId) {
      setReport(null)
      return
    }
    const requestId = loadReportRequestRef.current + 1
    loadReportRequestRef.current = requestId
    setLoadingReport(true)
    setReport((currentReport) => (currentReport?.run?.id === runId ? currentReport : null))
    try {
      const data = await getPoolRunReport(runId)
      if (loadReportRequestRef.current !== requestId || selectedRunIdRef.current !== runId) {
        return
      }
      setReport(data)
    } catch {
      if (loadReportRequestRef.current === requestId) {
        setError('Не удалось загрузить run report.')
      }
    } finally {
      if (loadReportRequestRef.current === requestId) {
        setLoadingReport(false)
      }
    }
  }, [selectedRunId])

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
    void loadRuns()
  }, [loadRuns])

  useEffect(() => {
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
  }, [loadingPools, pools, selectedPoolId])

  useEffect(() => {
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
    createSchemaTemplateId,
    createSourceArtifactId,
    createSourcePayloadJson,
    createStartingAmount,
    selectedPoolId,
  ])

  const handleCreateRun = useCallback(async () => {
    if (!selectedPoolId) {
      setError('Выберите пул перед созданием run.')
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
      message.success(payload.created ? 'Run создан' : 'Run переиспользован по idempotency key')
      setBindingPreview(null)
      await loadRuns({ preferredRunId: payload.run.id })
    } catch (err) {
      const problem = parseProblemDetails(err)
      if (problem) {
        if (problem.code === 'VALIDATION_ERROR' && problem.detail) {
          const normalizedDetail = problem.detail.toLowerCase()
          const fieldErrors: Array<{ name: keyof CreateRunFormValues; errors: string[] }> = []

          if (direction === 'top_down' && normalizedDetail.includes('starting_amount')) {
            fieldErrors.push({ name: 'starting_amount', errors: [problem.detail] })
          }
          if (
            direction === 'bottom_up'
            && (
              normalizedDetail.includes('source_payload')
              || normalizedDetail.includes('source_artifact_id')
              || normalizedDetail.includes('bottom_up run_input')
            )
          ) {
            fieldErrors.push({ name: 'source_payload_json', errors: [problem.detail] })
            fieldErrors.push({ name: 'source_artifact_id', errors: [problem.detail] })
          }
          if (normalizedDetail.includes('schema_template')) {
            fieldErrors.push({ name: 'schema_template_id', errors: [problem.detail] })
          }
          if (normalizedDetail.includes('pool_workflow_binding')) {
            fieldErrors.push({ name: 'pool_workflow_binding_id', errors: [problem.detail] })
          }

          if (fieldErrors.length > 0) {
            createForm.setFields(fieldErrors)
          }
          setError(resolveCreateRunPageLevelMessage({
            problem,
            fallbackMessage: 'Не удалось создать run.',
            hasFieldErrors: fieldErrors.length > 0,
          }))
        } else {
          setError(resolveCreateRunProblemMessage(problem, 'Не удалось создать run.'))
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
              errors: [resolveCreateRunProblemMessage(problem, 'Не удалось выбрать workflow binding.')],
            },
          ])
        }
      } else if (err instanceof Error && err.message) {
        setError(err.message)
      } else {
        setError('Не удалось создать run.')
      }
    } finally {
      setCreatingRun(false)
    }
  }, [createForm, loadRuns, message, selectedPoolId])

  const handlePreviewBinding = useCallback(async () => {
    if (!selectedPoolId) {
      setError('Выберите пул перед preview workflow binding.')
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
      message.success('Binding preview updated')
    } catch (err) {
      const problem = parseProblemDetails(err)
      if (problem) {
        if (problem.code === 'VALIDATION_ERROR' && problem.detail) {
          const normalizedDetail = problem.detail.toLowerCase()
          const fieldErrors: Array<{ name: keyof CreateRunFormValues; errors: string[] }> = []

          if (direction === 'top_down' && normalizedDetail.includes('starting_amount')) {
            fieldErrors.push({ name: 'starting_amount', errors: [problem.detail] })
          }
          if (
            direction === 'bottom_up'
            && (
              normalizedDetail.includes('source_payload')
              || normalizedDetail.includes('source_artifact_id')
              || normalizedDetail.includes('bottom_up run_input')
            )
          ) {
            fieldErrors.push({ name: 'source_payload_json', errors: [problem.detail] })
            fieldErrors.push({ name: 'source_artifact_id', errors: [problem.detail] })
          }
          if (normalizedDetail.includes('schema_template')) {
            fieldErrors.push({ name: 'schema_template_id', errors: [problem.detail] })
          }
          if (normalizedDetail.includes('pool_workflow_binding')) {
            fieldErrors.push({ name: 'pool_workflow_binding_id', errors: [problem.detail] })
          }

          if (fieldErrors.length > 0) {
            createForm.setFields(fieldErrors)
          }
          setError(resolveCreateRunPageLevelMessage({
            problem,
            fallbackMessage: 'Не удалось построить binding preview.',
            hasFieldErrors: fieldErrors.length > 0,
          }))
        } else {
          setError(resolveCreateRunProblemMessage(problem, 'Не удалось построить binding preview.'))
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
              errors: [resolveCreateRunProblemMessage(problem, 'Не удалось выбрать workflow binding.')],
            },
          ])
        }
        setBindingPreview(null)
      } else if (err instanceof Error && err.message) {
        setBindingPreview(null)
        setError(err.message)
      } else {
        setBindingPreview(null)
        setError('Не удалось построить binding preview.')
      }
    } finally {
      setPreviewingBinding(false)
    }
  }, [createForm, message, selectedPoolId])

  const handleRetryFailed = useCallback(async () => {
    if (!selectedRunId) {
      setError('Выберите run для retry.')
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
      setError(err instanceof Error ? err.message : 'Некорректный payload для retry.')
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
        message.success(`Retry accepted: ${enqueuedTargets}/${failedTargets} failed targets enqueued`)
      } else {
        message.warning('Retry request was not accepted by workflow runtime.')
      }
      await loadRuns()
      await loadReport()
    } catch (err) {
      const conflict = parseSafeCommandConflict(err)
      if (conflict) {
        setError(`${conflict.error_message} (${conflict.conflict_reason})`)
      } else {
        setError('Retry завершился ошибкой.')
      }
    } finally {
      setRetrying(false)
    }
  }, [loadReport, loadRuns, message, retryForm, selectedRunId])

  const handleSafeCommand = useCallback(async (commandType: PoolRunSafeCommandType) => {
    if (!selectedRunId || !runDetails) {
      setError('Выберите safe run для команды публикации.')
      return
    }
    if (runDetails.mode !== 'safe') {
      setError('Команды confirm/abort доступны только для safe run.')
      return
    }

    const idempotencyKey = generateIdempotencyKey()
    setSafeActionLoading(commandType)
    setError(null)
    try {
      const response = commandType === 'confirm-publication'
        ? await confirmPoolRunPublication(selectedRunId, idempotencyKey)
        : await abortPoolRunPublication(selectedRunId, idempotencyKey)
      const commandLabel = commandType === 'confirm-publication' ? 'Confirm publication' : 'Abort publication'
      if (response.result === 'accepted') {
        message.success(`${commandLabel}: accepted`)
      } else {
        message.info(`${commandLabel}: idempotent replay`)
      }
      await loadRuns({ preferredRunId: response.run.id })
      await loadReport()
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
                ? 'Не удалось выполнить confirm-publication.'
                : 'Не удалось выполнить abort-publication.'
            )
          )
        } else {
          setError(
            commandType === 'confirm-publication'
              ? 'Не удалось выполнить confirm-publication.'
              : 'Не удалось выполнить abort-publication.'
          )
        }
      }
    } finally {
      setSafeActionLoading(null)
    }
  }, [loadReport, loadRuns, message, runDetails, selectedRunId])

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
    void loadGraph()
    void loadRuns()
    void loadReport()
  }, [loadGraph, loadReport, loadRuns])

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
        title: 'Run',
        dataIndex: 'id',
        key: 'id',
        width: 220,
        render: (value: string, record) => (
          <Space direction="vertical" size={4}>
            <Button
              type="link"
              aria-label={`Open run ${record.id}`}
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
        title: 'Status',
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
        title: 'Approval',
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
        title: 'Workflow',
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
                {workflowStatus ? <Tag color="processing">{workflowStatus}</Tag> : <Tag>legacy</Tag>}
                {executionBackend ? <Tag>{executionBackend}</Tag> : null}
              </Space>
            </Space>
          )
        },
      },
      {
        title: 'Input',
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
        title: 'Period',
        key: 'period',
        render: (_value, record) => `${record.period_start}${record.period_end ? `..${record.period_end}` : ''}`,
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 190,
        render: (value: string) => formatDate(value),
      },
    ],
    [handleSelectRun, selectedRunId]
  )

  const publicationAttemptColumns: ColumnsType<PoolPublicationAttemptDiagnostics> = useMemo(
    () => [
      {
        title: 'Target DB',
        dataIndex: 'target_database_id',
        key: 'target_database_id',
        width: 180,
        render: (value: string) => <Text code>{formatShortId(value)}</Text>,
      },
      {
        title: 'Status',
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
        title: 'Attempt',
        dataIndex: 'attempt_number',
        key: 'attempt_number',
        width: 90,
      },
      {
        title: 'Timestamp',
        dataIndex: 'attempt_timestamp',
        key: 'attempt_timestamp',
        width: 180,
        render: (value?: string) => formatDate(value ?? null),
      },
      {
        title: 'Identity',
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
        title: 'Error',
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
                <Text type="secondary">Remediation: /rbac - Infobase Users</Text>
              ) : null}
              {httpStatusValue ? <Text type="secondary">HTTP {httpStatusValue}</Text> : null}
              {transportMessage ? <Text type="secondary">{transportMessage}</Text> : null}
            </Space>
          )
        },
      },
    ],
    []
  )

  const verificationMismatchColumns: ColumnsType<PoolRunVerificationMismatch> = useMemo(
    () => [
      {
        title: 'Database',
        dataIndex: 'database_id',
        key: 'database_id',
        width: 180,
        render: (value?: string | null) => <Text code>{value ? formatShortId(value) : '-'}</Text>,
      },
      {
        title: 'Entity',
        dataIndex: 'entity_name',
        key: 'entity_name',
        width: 180,
        render: (value?: string | null) => value || '-',
      },
      {
        title: 'Document',
        dataIndex: 'document_idempotency_key',
        key: 'document_idempotency_key',
        width: 180,
        render: (value?: string | null) => value || '-',
      },
      {
        title: 'Path',
        dataIndex: 'field_or_table_path',
        key: 'field_or_table_path',
        render: (value?: string | null) => value || '-',
      },
      {
        title: 'Kind',
        dataIndex: 'kind',
        key: 'kind',
        width: 180,
        render: (value?: string | null) => value || '-',
      },
    ],
    []
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
        String(runtimeProjection?.workflow_binding.binding_id || '').trim() || 'run binding',
        String(runtimeProjection?.workflow_binding.workflow_name || '').trim(),
      ].filter((item) => item).join(' · ')
    return buildTopologyCoverageSummary({
      bindingLabel,
      decisions: workflowDecisionRefs,
      detail: `Coverage is evaluated against run lineage binding ${bindingLabel}.`,
      selectors: topologyEdgeSelectors,
      source: 'selected',
    })
  }, [runtimeProjection, topologyEdgeSelectors, workflowBinding, workflowDecisionRefs])
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

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Pool Runs"
          subtitle={(
            <>
              Stage-based operator workspace on
              {' '}
              <Text code>{POOL_RUNS_ROUTE}</Text>
              {' '}
              for create, inspect, safe actions, and retry against one selected run context.
            </>
          )}
          actions={(
            <Space wrap size={16} align="start">
              <Space direction="vertical" size={4}>
                <Text strong>Pool</Text>
                <Select
                  aria-label="Run pool"
                  data-testid="pool-runs-context-pool"
                  style={{ width: 320 }}
                  placeholder="Select pool"
                  value={selectedPoolId ?? undefined}
                  options={pools.map((pool) => ({
                    value: pool.id,
                    label: `${pool.code} - ${pool.name}`,
                  }))}
                  onChange={handleSelectPool}
                />
              </Space>
              <Space direction="vertical" size={4}>
                <Text strong>Graph date</Text>
                <Input
                  aria-label="Graph date"
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
                Refresh Data
              </Button>
            </Space>
          )}
        />
      )}
    >
      <Alert
        type="info"
        showIcon
        message={`Lifecycle stage: ${STAGE_LABELS[activeStageTab]}`}
        description={STAGE_MESSAGES[activeStageTab]}
      />

      {error && <Alert type="error" message={error} />}

      <Card title="Run Context" loading={loadingPools}>
        <Space wrap>
          <Text>
            Selected pool:
            {' '}
            <Text strong>{selectedPool ? `${selectedPool.code} - ${selectedPool.name}` : 'none'}</Text>
          </Text>
          <Text>
            Graph date:
            {' '}
            <Text strong>{graphDate}</Text>
          </Text>
          <Text>
            Selected run:
            {' '}
            <Text strong>{selectedRunId ? formatShortId(selectedRunId) : 'none'}</Text>
          </Text>
        </Space>
      </Card>

      <Tabs
        activeKey={activeStageTab}
        onChange={(key) => handleSelectStage(key as PoolRunsStage)}
        data-testid="pool-runs-stage-tabs"
        items={[
          {
            key: 'create',
            label: STAGE_LABELS.create,
            children: (
              <Card title="Create Run">
                <Form form={createForm} layout="vertical" initialValues={CREATE_RUN_FORM_INITIAL_VALUES}>
                  <Alert
                    type="info"
                    showIcon
                    message="Pool publication OData credentials source: /rbac"
                    description="`odata_url` берётся из Databases, а OData user/password для публикации — из /rbac → Infobase Users (actor/service mapping)."
                    style={{ marginBottom: 12 }}
                  />
                  {selectedPoolWorkflowBindingsReadError ? (
                    <Alert
                      type="error"
                      showIcon
                      data-testid="pool-runs-create-binding-read-error"
                      message={`Binding diagnostics: ${selectedPoolWorkflowBindingsReadError.code}`}
                      description={selectedPoolWorkflowBindingsReadError.detail}
                      style={{ marginBottom: 12 }}
                    />
                  ) : null}
                  <Row gutter={12}>
                    <Col span={5}>
                      <Form.Item name="period_start" label="Period start" rules={[{ required: true }]}>
                        <Input type="date" />
                      </Form.Item>
                    </Col>
                    <Col span={5}>
                      <Form.Item name="period_end" label="Period end">
                        <Input type="date" />
                      </Form.Item>
                    </Col>
                    <Col span={4}>
                      <Form.Item name="direction" label="Direction" rules={[{ required: true }]}>
                        <Radio.Group data-testid="pool-runs-create-direction" optionType="button" buttonStyle="solid">
                          <Radio.Button value="top_down">top_down</Radio.Button>
                          <Radio.Button value="bottom_up">bottom_up</Radio.Button>
                        </Radio.Group>
                      </Form.Item>
                    </Col>
                    <Col span={4}>
                      <Form.Item name="mode" label="Mode" rules={[{ required: true }]}>
                        <Select
                          data-testid="pool-runs-create-mode"
                          options={[
                            { value: 'safe', label: 'safe' },
                            { value: 'unsafe', label: 'unsafe' },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      {createDirection === 'top_down' ? (
                        <Form.Item
                          name="starting_amount"
                          label="Starting amount"
                          rules={[
                            { required: true, message: 'starting_amount required' },
                            {
                              validator: async (_rule, value) => {
                                if (value == null || Number(value) <= 0) {
                                  throw new Error('starting_amount must be > 0')
                                }
                              },
                            },
                          ]}
                        >
                          <InputNumber data-testid="pool-runs-create-starting-amount" min={0.01} step={0.01} style={{ width: '100%' }} />
                        </Form.Item>
                      ) : (
                        <Form.Item name="schema_template_id" label="Schema template">
                          <Select
                            data-testid="pool-runs-create-schema-template"
                            allowClear
                            loading={loadingSchemaTemplates}
                            placeholder="Optional template"
                            options={schemaTemplates.map((item) => ({
                              value: item.id,
                              label: `${item.code} - ${item.name}`,
                            }))}
                          />
                        </Form.Item>
                      )}
                    </Col>
                  </Row>

                  <Row gutter={12}>
                    <Col span={12}>
                      <Form.Item
                        name="pool_workflow_binding_id"
                        label="Workflow binding"
                        rules={[{ required: true, message: 'workflow binding required' }]}
                        extra={
                          selectedPoolWorkflowBindingsReadError
                            ? `Active bindings are unavailable: ${selectedPoolWorkflowBindingsReadError.detail}`
                            : matchingWorkflowBindings.length === 0
                            ? 'Для выбранного pool/direction/mode/period_start нет активного workflow binding.'
                            : 'Run запускается по pinned workflow binding, а не по raw selector.'
                        }
                      >
                        <Select
                          data-testid="pool-runs-create-workflow-binding"
                          aria-label="Workflow binding"
                          aria-disabled={Boolean(selectedPoolWorkflowBindingsReadError) || matchingWorkflowBindings.length === 0}
                          allowClear={matchingWorkflowBindings.length > 1}
                          disabled={Boolean(selectedPoolWorkflowBindingsReadError) || matchingWorkflowBindings.length === 0}
                          placeholder={
                            selectedPoolWorkflowBindingsReadError
                              ? 'Bindings unavailable'
                              : matchingWorkflowBindings.length === 0
                                ? 'No matching binding'
                                : 'Select binding'
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
                      message="Binding context is ambiguous"
                      description="Для выбранного pool/direction/mode найдено несколько active bindings. Выберите binding явно, чтобы увидеть slot coverage и построить preview."
                    />
                  ) : null}
                  {selectedCreateBinding ? (
                    <Card
                      size="small"
                      title="Selected Attachment"
                      data-testid="pool-runs-create-selected-binding"
                      style={{ marginBottom: 12 }}
                    >
                      <Descriptions bordered size="small" column={detailDescriptionColumns}>
                        <Descriptions.Item label="Attachment ID" span={1}>
                          <Text code>{selectedCreateBinding.binding_id ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Attachment Revision" span={1}>
                          <Text data-testid="pool-runs-create-attachment-revision">
                            {selectedCreateBinding.revision != null ? `r${selectedCreateBinding.revision}` : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Execution Pack" span={1}>
                          <Text data-testid="pool-runs-create-profile">{resolvePoolWorkflowBindingProfileLabel(selectedCreateBinding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Pinned Pack Revision" span={1}>
                          <Text data-testid="pool-runs-create-profile-revision">
                            {selectedCreateBinding.binding_profile_revision_number != null
                              ? `r${selectedCreateBinding.binding_profile_revision_number}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Workflow Scheme" span={1}>
                          <Text>
                            {selectedCreateBindingWorkflow?.workflow_name
                              || selectedCreateBindingWorkflow?.workflow_definition_key
                              || '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Workflow Revision" span={1}>
                          <Text>
                            {selectedCreateBindingWorkflow?.workflow_revision != null
                              ? `r${selectedCreateBindingWorkflow.workflow_revision}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Binding Scope" span={1}>
                          <Text>{formatWorkflowBindingScope(selectedCreateBinding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Effective Period" span={1}>
                          <Text>{formatWorkflowBindingEffectivePeriod(selectedCreateBinding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Pack Status" span={1}>
                          <Text>{resolvePoolWorkflowBindingProfileStatus(selectedCreateBinding) ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Pinned Revision ID" span={1}>
                          <Text code>{selectedCreateBinding.binding_profile_revision_id ?? '-'}</Text>
                        </Descriptions.Item>
                        {selectedCreateBindingLifecycleWarning ? (
                          <Descriptions.Item label="Lifecycle Warning" span={2}>
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
                      title="Topology slot coverage"
                      data-testid="pool-runs-create-binding-coverage"
                    >
                      <TopologySlotCoveragePanel
                        summary={createBindingCoverageSummary}
                        summaryTestId="pool-runs-create-slot-coverage-summary"
                        itemTestIdPrefix="pool-runs-create-slot-coverage-item"
                        emptyMessage="No topology edges in the selected snapshot yet."
                        resolvedMessage="All topology edges are covered by the selected binding before preview."
                      />
                    </Card>
                  ) : null}

                  {createDirection === 'bottom_up' && (
                    <Row gutter={12}>
                      <Col span={16}>
                        <Form.Item name="source_payload_json" label="Source payload JSON">
                          <Input.TextArea data-testid="pool-runs-create-source-payload" rows={6} placeholder='[{"inn":"730000000001","amount":"100.00"}]' />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="source_artifact_id" label="Source artifact ID">
                          <Input data-testid="pool-runs-create-source-artifact" placeholder="artifact://..." />
                        </Form.Item>
                        <Upload
                          accept=".json,application/json,text/plain"
                          maxCount={1}
                          showUploadList={false}
                          beforeUpload={async (file) => {
                            try {
                              const text = await file.text()
                              createForm.setFieldValue('source_payload_json', text)
                              message.success('Source payload loaded from file.')
                            } catch {
                              message.error('Не удалось прочитать выбранный файл.')
                            }
                            return false
                          }}
                        >
                          <Button icon={<UploadOutlined />}>Load payload file</Button>
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
                      Preview Binding
                    </Button>
                    <Button type="primary" loading={creatingRun} onClick={() => void handleCreateRun()} data-testid="pool-runs-create-submit">
                      Create / Upsert Run
                    </Button>
                  </Space>

                  {bindingPreview && (
                    <Card
                      size="small"
                      title="Binding Preview"
                      data-testid="pool-runs-binding-preview"
                      style={{ marginTop: 16 }}
                    >
                      <Descriptions bordered size="small" column={detailDescriptionColumns}>
                        <Descriptions.Item label="Attachment ID" span={1}>
                          <Text code>{bindingPreview.workflow_binding.binding_id ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Attachment Revision" span={1}>
                          <Text data-testid="pool-runs-binding-preview-attachment-revision">
                            {bindingPreview.workflow_binding.revision != null
                              ? `r${bindingPreview.workflow_binding.revision}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Execution Pack" span={1}>
                          <Text data-testid="pool-runs-binding-preview-profile">
                            {resolvePoolWorkflowBindingProfileLabel(bindingPreview.workflow_binding)}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Pinned Pack Revision" span={1}>
                          <Text data-testid="pool-runs-binding-preview-profile-revision">
                            {bindingPreview.workflow_binding.binding_profile_revision_number != null
                              ? `r${bindingPreview.workflow_binding.binding_profile_revision_number}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Pinned Revision ID" span={2}>
                          <Text code>{bindingPreview.workflow_binding.binding_profile_revision_id ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Workflow Scheme" span={1}>
                          <Text>
                            {previewBindingWorkflow?.workflow_name
                              || previewBindingWorkflow?.workflow_definition_key
                              || '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Workflow Revision" span={1}>
                          <Text>
                            {previewBindingWorkflow?.workflow_revision != null
                              ? `r${previewBindingWorkflow.workflow_revision}`
                              : '-'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Binding Scope" span={1}>
                          <Text>{formatWorkflowBindingScope(bindingPreview.workflow_binding)}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Pack Status" span={1}>
                          <Text>{resolvePoolWorkflowBindingProfileStatus(bindingPreview.workflow_binding) ?? '-'}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Decision Snapshot" span={2}>
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
                            <Text type="secondary">No pinned decision refs.</Text>
                          )}
                        </Descriptions.Item>
                        {previewBindingLifecycleWarning ? (
                          <Descriptions.Item label="Lifecycle Warning" span={2}>
                            <Alert
                              type="warning"
                              showIcon
                              message={previewBindingLifecycleWarning.title}
                              description={previewBindingLifecycleWarning.detail}
                            />
                          </Descriptions.Item>
                        ) : null}
                        <Descriptions.Item label="Slot Coverage" span={2}>
                          <TopologySlotCoveragePanel
                            summary={bindingPreviewCoverageSummary}
                            summaryTestId="pool-runs-binding-preview-slot-coverage"
                            itemTestIdPrefix="pool-runs-binding-preview-slot-coverage-item"
                            emptyMessage="No topology edges in the selected snapshot yet."
                            resolvedMessage="All topology edges are covered by this binding preview."
                          />
                        </Descriptions.Item>
                        <Descriptions.Item label="Document Policy Source" span={1}>
                          <Text>{bindingPreview.runtime_projection.document_policy_projection.source_mode}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Compile Plan" span={1}>
                          <Text code>{bindingPreview.runtime_projection.workflow_definition.plan_key}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Compile Summary" span={2}>
                          <Space size={[4, 4]} wrap>
                            <Tag>compiled targets: {bindingPreview.runtime_projection.compile_summary.compiled_targets_count}</Tag>
                            <Tag>policy refs: {bindingPreview.runtime_projection.document_policy_projection.policy_refs_count}</Tag>
                            <Tag>steps: {bindingPreview.runtime_projection.compile_summary.steps_count}</Tag>
                            <Tag>atomic publication: {bindingPreview.runtime_projection.compile_summary.atomic_publication_steps_count}</Tag>
                          </Space>
                        </Descriptions.Item>
                        <Descriptions.Item label="Compiled Slot Projection" span={2}>
                          <TextArea
                            value={JSON.stringify(bindingPreview.compiled_document_policy_slots ?? {}, null, 2)}
                            rows={8}
                            readOnly
                            data-testid="pool-runs-binding-preview-slot-projection"
                          />
                        </Descriptions.Item>
                        {bindingPreview.compiled_document_policy ? (
                          <Descriptions.Item label="Compatibility Policy Projection" span={2}>
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
                </Form>
              </Card>
            ),
          },
          {
            key: 'inspect',
            label: STAGE_LABELS.inspect,
            children: (
              <MasterDetailShell
                detailOpen={Boolean(selectedRunId) && isRunDetailOpen}
                onCloseDetail={handleCloseRunDetail}
                detailDrawerTitle={selectedRunId ? `${STAGE_DETAIL_TITLES.inspect} · ${formatShortId(selectedRunId)}` : STAGE_DETAIL_TITLES.inspect}
                list={(
                  <EntityTable
                    title="Runs"
                    loading={loadingRuns}
                    emptyDescription={selectedPoolId ? 'No runs found for the selected pool.' : 'Select a pool to load runs.'}
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
                    <Card title="Pool Graph" loading={loadingGraph}>
                      <div style={{ height: 460 }}>
                        <ReactFlow nodes={flow.nodes} edges={flow.edges} fitView>
                          <MiniMap />
                          <Controls />
                          <Background />
                        </ReactFlow>
                      </div>
                    </Card>

                    <Card title="Run Lineage / Operator Report" loading={loadingReport}>
                  {!runDetails && (
                    <Text type="secondary">Select a run to inspect report.</Text>
                  )}
                  {runDetails && report && (
                    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                      <Space size="small" wrap>
                        <Tag color="blue">run: {formatShortId(runDetails.id)}</Tag>
                        <Tag color={getStatusColor(runDetails.status)}>{runDetails.status}</Tag>
                        {runDetails.status_reason && <Tag color={getStatusReasonColor(runDetails.status_reason)}>{runDetails.status_reason}</Tag>}
                        <Tag>attempts: {report.publication_attempts.length}</Tag>
                        {Object.entries(report.attempts_by_status ?? {}).map(([status, count]) => (
                          <Tag key={status}>{status}: {count}</Tag>
                        ))}
                      </Space>

                      <Alert
                        type="info"
                        showIcon
                        message="Run Lineage is the primary operator context"
                        description="Pool, selected binding, pinned workflow revision and compiled runtime projection stay on this screen. Generic workflow execution remains a secondary diagnostics surface."
                      />

                      <Card size="small" title="Run Lineage">
                        <Descriptions bordered size="small" column={detailDescriptionColumns}>
                        <Descriptions.Item label="Pool" span={1}>
                            <Text data-testid="pool-runs-lineage-pool">{selectedPoolLabel}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Attachment ID" span={1}>
                            <Text code data-testid="pool-runs-lineage-binding-id">
                              {workflowBinding?.binding_id ?? runtimeProjection?.workflow_binding.binding_id ?? '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Attachment Revision" span={1}>
                            <Text data-testid="pool-runs-lineage-attachment-revision">
                              {workflowBindingAttachmentRevision != null ? `r${workflowBindingAttachmentRevision}` : '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Execution Pack" span={1}>
                            <Text data-testid="pool-runs-lineage-profile">
                              {resolvePoolWorkflowBindingProfileLabel(workflowBinding) !== '-'
                                ? resolvePoolWorkflowBindingProfileLabel(workflowBinding)
                                : (workflowBindingProfileId ?? '-')}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Pinned Pack Revision" span={1}>
                            <Text data-testid="pool-runs-lineage-profile-revision">
                              {workflowBindingProfileRevisionNumber != null ? `r${workflowBindingProfileRevisionNumber}` : '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Workflow Scheme" span={1}>
                            <Text data-testid="pool-runs-lineage-workflow">
                              {resolveWorkflowLineageName({
                                binding: workflowBinding,
                                runtimeProjection,
                                workflowTemplateName: runDetails.workflow_template_name,
                              })}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Workflow Revision" span={1}>
                            <Text>
                              {workflowBindingWorkflow?.workflow_revision != null
                                ? `r${workflowBindingWorkflow.workflow_revision}`
                                : runtimeProjection?.workflow_binding.workflow_revision != null
                                  ? `r${runtimeProjection.workflow_binding.workflow_revision}`
                                  : '-'}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Binding Scope" span={1}>
                            <Text>{formatWorkflowBindingScope(workflowBinding)}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Effective Period" span={1}>
                            <Text>{formatWorkflowBindingEffectivePeriod(workflowBinding)}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Pack Status" span={1}>
                            <Text>{workflowBindingProfileStatus ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Pinned Revision ID" span={1}>
                            <Text code>{workflowBindingProfileRevisionId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Execution Pack ID" span={1}>
                            <Text code>{workflowBindingProfileId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Decision Snapshot" span={2}>
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
                              <Text type="secondary">No pinned decision refs.</Text>
                            )}
                          </Descriptions.Item>
                          {workflowBindingLifecycleWarning ? (
                            <Descriptions.Item label="Lifecycle Warning" span={2}>
                              <Alert
                                type="warning"
                                showIcon
                                message={workflowBindingLifecycleWarning.title}
                                description={workflowBindingLifecycleWarning.detail}
                              />
                            </Descriptions.Item>
                          ) : null}
                          <Descriptions.Item label="Slot Coverage" span={2}>
                            <TopologySlotCoveragePanel
                              summary={runLineageCoverageSummary}
                              summaryTestId="pool-runs-lineage-slot-coverage"
                              itemTestIdPrefix="pool-runs-lineage-slot-coverage-item"
                              emptyMessage="No topology edges in the selected snapshot yet."
                              resolvedMessage="All topology edges are covered by the persisted run lineage binding."
                            />
                          </Descriptions.Item>
                          <Descriptions.Item label="Slot Projection" span={2}>
                            {runtimeProjection ? (
                              <TextArea
                                data-testid="pool-runs-lineage-slot-projection"
                                value={JSON.stringify(runLineageSlotProjection ?? {}, null, 2)}
                                autoSize={{ minRows: 8, maxRows: 20 }}
                                readOnly
                              />
                            ) : (
                              <Text type="secondary">Historical run without persisted slot projection.</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label="Compiled Runtime" span={1}>
                            <Text>{runtimeProjection?.workflow_definition.workflow_template_name ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Compile Plan" span={1}>
                            <Text code>{runtimeProjection?.workflow_definition.plan_key ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Compile Summary" span={2}>
                            {runtimeProjection ? (
                              <Space size={[4, 4]} wrap>
                                <Tag>compiled targets: {runtimeProjection.compile_summary.compiled_targets_count}</Tag>
                                <Tag>policy refs: {runtimeProjection.document_policy_projection.policy_refs_count}</Tag>
                                <Tag>steps: {runtimeProjection.compile_summary.steps_count}</Tag>
                                <Tag>atomic publication: {runtimeProjection.compile_summary.atomic_publication_steps_count}</Tag>
                              </Space>
                            ) : (
                              <Text type="secondary">Historical run without compiled runtime projection.</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label="Workflow Diagnostics" span={2}>
                            {workflowDiagnosticsId ? (
                              <RouteButton
                                type="link"
                                to={`/workflows/executions/${workflowDiagnosticsId}`}
                                style={{ paddingInline: 0 }}
                              >
                                Open Workflow Diagnostics
                              </RouteButton>
                            ) : (
                              <Text type="secondary">No linked workflow execution diagnostics.</Text>
                            )}
                          </Descriptions.Item>
                        </Descriptions>
                      </Card>

                      <Card size="small" title="Underlying Workflow Runtime">
                        <Descriptions bordered size="small" column={detailDescriptionColumns}>
                          <Descriptions.Item label="Workflow Run" span={1}>
                            <Text code data-testid="pool-runs-provenance-workflow-id">{workflowRunId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Workflow Status" span={1}>
                            {workflowStatus ? <Tag color="processing">{workflowStatus}</Tag> : <Text type="secondary">legacy</Text>}
                          </Descriptions.Item>
                          <Descriptions.Item label="Root Operation" span={1}>
                            <Text code data-testid="pool-runs-provenance-root-operation-id">{rootOperationId ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Execution Consumer" span={1}>
                            <Text data-testid="pool-runs-provenance-execution-consumer">{executionConsumer ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Lane" span={1}>
                            <Text data-testid="pool-runs-provenance-lane">{lane ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Execution Backend" span={1}>
                            <Text>{executionBackend ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Workflow Template" span={1}>
                            <Text>{runDetails.workflow_template_name ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Input Contract" span={1}>
                            <Tag color={getInputContractColor(resolveInputContractVersion(runDetails))}>
                              {resolveInputContractVersion(runDetails)}
                            </Tag>
                          </Descriptions.Item>
                          <Descriptions.Item label="Run Input" span={2}>
                            <Text>{summarizeRunInput(runDetails)}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Approval State" span={1}>
                            {runDetails.approval_state ? (
                              <Tag color={getApprovalStateColor(runDetails.approval_state)}>{runDetails.approval_state}</Tag>
                            ) : (
                              <Text type="secondary">n/a</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label="Publication Step" span={1}>
                            {runDetails.publication_step_state ? (
                              <Tag color={getPublicationStepColor(runDetails.publication_step_state)}>{runDetails.publication_step_state}</Tag>
                            ) : (
                              <Text type="secondary">n/a</Text>
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label="Terminal Reason" span={2}>
                            <Text>{runDetails.terminal_reason ?? '-'}</Text>
                          </Descriptions.Item>
                          <Descriptions.Item label="Retry Chain" span={2}>
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
                                      <Text type="secondary">parent: {formatShortId(item.parent_workflow_run_id)}</Text>
                                    ) : (
                                      <Text type="secondary">root</Text>
                                    )}
                                  </Space>
                                ))}
                              </Space>
                            ) : (
                              <Text type="secondary">empty</Text>
                            )}
                          </Descriptions.Item>
                        </Descriptions>
                      </Card>

                      <Card size="small" title="Master Data Gate">
                        {!masterDataGate && (
                          <Text type="secondary">
                            Historical run or gate step was not captured in this execution context.
                          </Text>
                        )}
                        {masterDataGate && (
                          <Space direction="vertical" size="small" style={{ width: '100%' }}>
                            <Space size="small" wrap>
                              <Tag color={MASTER_DATA_GATE_STATUS_COLORS[masterDataGate.status] ?? 'default'}>
                                status: {masterDataGate.status}
                              </Tag>
                              <Tag>mode: {masterDataGate.mode}</Tag>
                              <Tag>targets: {masterDataGate.targets_count}</Tag>
                              <Tag>bindings: {masterDataGate.bindings_count}</Tag>
                            </Space>
                            {masterDataGate.error_code && (
                              <Alert
                                type="error"
                                showIcon
                                message={masterDataGate.error_code}
                                description={masterDataGate.detail || 'Master data gate failed.'}
                              />
                            )}
                            {masterDataGateHint && (
                              <Alert
                                type="info"
                                showIcon
                                message="Remediation Hint"
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
                                <Text strong>Diagnostic Context</Text>
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

                      <Card size="small" title="Readiness Checklist">
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <Space size="small" wrap>
                            <Tag
                              color={READINESS_STATUS_COLORS[readinessChecklist.status] ?? 'default'}
                              data-testid="pool-runs-readiness-status"
                            >
                              status: {readinessChecklist.status}
                            </Tag>
                            <Tag>checks: {readinessChecklist.checks.length}</Tag>
                            <Tag>blockers: {readinessBlockers.length}</Tag>
                          </Space>
                          {readinessChecklist.checks.map((check) => (
                            <Alert
                              key={check.code}
                              type={check.status === 'ready' ? 'success' : check.blockers.length > 0 ? 'error' : 'warning'}
                              showIcon
                              message={resolveReadinessCheckLabel(check.code)}
                              description={(
                                <Space direction="vertical" size={2}>
                                  <Text>status: {check.status}</Text>
                                  {check.blockers.length === 0 ? (
                                    <Text type="secondary">No blocking diagnostics.</Text>
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
                                          <Text>{blocker.detail || 'Run readiness blocked.'}</Text>
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

                      <Card size="small" title="OData Verification">
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <Space size="small" wrap>
                            <Tag
                              color={VERIFICATION_STATUS_COLORS[verificationStatus] ?? 'default'}
                              data-testid="pool-runs-verification-status"
                            >
                              status: {verificationStatus}
                            </Tag>
                            {verificationSummary ? <Tag>targets: {verificationSummary.checked_targets}</Tag> : null}
                            {verificationSummary ? <Tag>documents: {verificationSummary.verified_documents}</Tag> : null}
                            {verificationSummary ? <Tag>mismatches: {verificationSummary.mismatches_count}</Tag> : null}
                          </Space>
                          {verificationStatus === 'not_verified' && (
                            <Alert
                              type="info"
                              showIcon
                              message="Verification has not started yet"
                              description="Post-run OData verification ещё не дала результата для этого run."
                            />
                          )}
                          {verificationStatus === 'passed' && verificationSummary && (
                            <Alert
                              type="success"
                              showIcon
                              message="Published documents verified"
                              description={`Проверено ${verificationSummary.verified_documents} документ(ов) по ${verificationSummary.checked_targets} target(s) без mismatches.`}
                            />
                          )}
                          {verificationStatus === 'failed' && verificationSummary && (
                            <Collapse
                              items={[
                                {
                                  key: 'verification-mismatches',
                                  label: `Mismatches (${verificationSummary.mismatches_count})`,
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

                      <Text strong>Publication Attempts</Text>
                      <Table
                        rowKey="id"
                        size="small"
                        columns={publicationAttemptColumns}
                        dataSource={report.publication_attempts}
                        pagination={{ pageSize: 5 }}
                      />

                      <Collapse
                        items={[
                          {
                            key: 'diagnostics-json',
                            label: 'Diagnostics JSON (Run Input, Validation, Publication, Step Diagnostics)',
                            children: (
                              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                                <Text strong>Run Input</Text>
                                <TextArea
                                  data-testid="pool-runs-run-input"
                                  readOnly
                                  rows={6}
                                  value={JSON.stringify(runDetails.run_input ?? null, null, 2)}
                                />
                                <Text strong>Validation Summary</Text>
                                <TextArea readOnly rows={4} value={JSON.stringify(report.validation_summary ?? {}, null, 2)} />
                                <Text strong>Publication Summary</Text>
                                <TextArea readOnly rows={4} value={JSON.stringify(report.publication_summary ?? {}, null, 2)} />
                                <Text strong>Step Diagnostics</Text>
                                <TextArea readOnly rows={6} value={JSON.stringify(report.diagnostics ?? [], null, 2)} />
                              </Space>
                            ),
                          },
                        ]}
                      />
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
            label: STAGE_LABELS.safe,
            children: (
              <Card
                title="Safe Mode Actions"
                extra={<Text type="secondary">`Idempotency-Key` генерируется автоматически на каждый action.</Text>}
              >
                {!runDetails && <Text type="secondary">Выберите run для управления safe-публикацией.</Text>}
                {runDetails && runDetails.mode !== 'safe' && (
                  <Alert type="info" showIcon message="Этот run создан в unsafe режиме: confirm/abort недоступны." />
                )}
                {runDetails && runDetails.mode === 'safe' && (
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag color="geekblue">safe</Tag>
                      {runDetails.status_reason ? <Tag color={getStatusReasonColor(runDetails.status_reason)}>{runDetails.status_reason}</Tag> : null}
                      {runDetails.approval_state ? <Tag color={getApprovalStateColor(runDetails.approval_state)}>{runDetails.approval_state}</Tag> : null}
                      {runDetails.publication_step_state ? <Tag color={getPublicationStepColor(runDetails.publication_step_state)}>{runDetails.publication_step_state}</Tag> : null}
                    </Space>
                    {isSafePrePublishPreparing && (
                      <Alert
                        type="info"
                        showIcon
                        message="Pre-publish ещё выполняется"
                        description="Safe run находится на этапе предпросмотра. Дождитесь состояния awaiting_approval, затем станет доступен Confirm publication."
                      />
                    )}
                    {readinessBlockers.length > 0 && (
                      <Alert
                        type="error"
                        showIcon
                        message="Readiness blockers detected"
                        description={`Inspect stage показывает ${readinessBlockers.length} blocker(s). Confirm publication будет недоступен до их устранения.`}
                      />
                    )}
                    <Text type="secondary">
                      `preparing` — выполняется pre-publish (prepare/distribution/reconciliation/approval_gate).
                      `awaiting_approval` — pre-publish завершён и run ждёт ручного подтверждения.
                      Диагностика вынесена в Inspect stage (Diagnostics JSON).
                    </Text>
                    <Space>
                      <Button
                        type="primary"
                        data-testid="pool-runs-safe-confirm"
                        loading={safeActionLoading === 'confirm-publication'}
                        title={isSafePrePublishPreparing ? 'Доступно после завершения pre-publish (awaiting_approval)' : undefined}
                        disabled={!canConfirm}
                        onClick={() => void handleSafeCommand('confirm-publication')}
                      >
                        Confirm publication
                      </Button>
                      <Button
                        danger
                        data-testid="pool-runs-safe-abort"
                        loading={safeActionLoading === 'abort-publication'}
                        disabled={!canAbort}
                        onClick={() => void handleSafeCommand('abort-publication')}
                      >
                        Abort publication
                      </Button>
                    </Space>
                  </Space>
                )}
              </Card>
            ),
          },
          {
            key: 'retry',
            label: STAGE_LABELS.retry,
            children: (
              <Card title="Retry Failed Targets">
                <Form form={retryForm} layout="vertical" initialValues={RETRY_FORM_INITIAL_VALUES}>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item name="entity_name" label="Entity Name" rules={[{ required: true }]}>
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="max_attempts" label="Max Attempts" rules={[{ required: true }]}>
                        <InputNumber min={1} max={5} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="retry_interval_seconds" label="Retry Interval (sec)" rules={[{ required: true }]}>
                        <InputNumber min={0} max={120} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item name="documents_json" label="documents_by_database JSON" rules={[{ required: true }]}>
                    <TextArea rows={8} />
                  </Form.Item>
                  <Button type="primary" loading={retrying} onClick={() => void handleRetryFailed()} disabled={!selectedRunId}>
                    Retry Failed
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
