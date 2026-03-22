import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import { ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import type { ColumnsType } from 'antd/es/table'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import { useNavigate, useSearchParams } from 'react-router-dom'
import 'reactflow/dist/style.css'

import { useAuthz } from '../../authz/useAuthz'
import { getBindingProfileDetail, type BindingProfileDetail } from '../../api/poolBindingProfiles'
import { useDatabases } from '../../api/queries/databases'
import { useBindingProfiles } from '../../api/queries/poolBindingProfiles'
import { queryKeys } from '../../api/queries/queryKeys'
import {
  getOrganization,
  getPoolGraph,
  listPoolWorkflowBindings,
  listMasterDataContracts,
  listMasterDataItems,
  listMasterDataParties,
  listMasterDataTaxProfiles,
  listPoolTopologyTemplates,
  listPoolTopologySnapshots,
  listOrganizationPools,
  listOrganizations,
  syncOrganizationsCatalog,
  upsertOrganizationPool,
  upsertOrganization,
  upsertPoolTopologySnapshot,
  type Organization,
  type OrganizationPool,
  type OrganizationPoolBinding,
  type OrganizationStatus,
  type PoolGraph,
  type PoolMasterContract,
  type PoolMasterItem,
  type PoolMasterParty,
  type PoolMasterTaxProfile,
  type PoolTopologyTemplate,
  type PoolTopologyTemplateRevision,
  type PoolTopologyTemplateEdge,
  type PoolWorkflowBindingBlockingRemediation,
  type PoolTopologySnapshotPeriod,
  type PoolTopologySnapshotEdgeInput,
  type PoolTopologySnapshotNodeInput,
  type PoolTopologyTemplateEdgeSelectorOverrideInput,
  type PoolTopologyTemplateSlotAssignmentInput,
  type PoolWorkflowBinding,
} from '../../api/intercompanyPools'
import { getV2 } from '../../api/generated/v2/v2'
import type {
  PoolODataMetadataCatalogDocument,
  PoolODataMetadataCatalogResponse,
} from '../../api/generated/model'
import { withQueryPolicy } from '../../lib/queryRuntime'
import {
  DrawerFormShell,
  PageHeader,
  RouteButton,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { PoolWorkflowBindingsEditor } from './PoolWorkflowBindingsEditor'
import {
  buildWorkflowBindingsFromForm,
  getWorkflowBindingCardTitle,
  summarizeWorkflowBindings,
  workflowBindingsToFormValues,
  type PoolWorkflowBindingFormValue,
} from './poolWorkflowBindingsForm'
import { syncPoolWorkflowBindings } from './poolWorkflowBindingsSync'
import {
  buildTopologyCoverageContext,
  describePoolWorkflowBindingCoverage,
  resolveTopologyCoverageContext,
  resolveTopologySlotCoverage,
  summarizeTopologySlotCoverage,
  type TopologyEdgeSelector,
} from './topologySlotCoverage'
import { POOL_BINDING_PROFILES_ROUTE, POOL_CATALOG_ROUTE } from './routes'

const { Text } = Typography
const { TextArea } = Input

const SYNC_MAX_ROWS = 1000
const MASTER_DATA_TOKEN_CATALOG_LIMIT = 200
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const STATUS_OPTIONS: OrganizationStatus[] = ['active', 'inactive', 'archived']
const TOPOLOGY_DOCUMENT_POLICY_BUILDER_ENABLED = false

const API_ERROR_MESSAGE_MAP: Record<string, string> = {
  DATABASE_ALREADY_LINKED: 'Выбранная база уже привязана к другой организации.',
  DUPLICATE_ORGANIZATION_INN: 'Организация с таким ИНН уже существует в текущем tenant.',
  DUPLICATE_POOL_CODE: 'Пул с таким code уже существует в текущем tenant.',
  DATABASE_NOT_FOUND: 'База данных не найдена в текущем tenant context.',
  POOL_NOT_FOUND: 'Пул не найден в текущем tenant context.',
  ORGANIZATION_NOT_FOUND: 'Организация не найдена в текущем tenant context.',
  TENANT_NOT_FOUND: 'Текущий tenant context невалиден.',
  TENANT_CONTEXT_REQUIRED: 'Для изменения каталога выберите активный tenant.',
  TOPOLOGY_VERSION_CONFLICT: 'Топология уже была изменена другим оператором. Обновите граф и повторите сохранение.',
  VALIDATION_ERROR: 'Проверьте корректность данных.',
  ODATA_MAPPING_NOT_CONFIGURED: 'Не настроен Infobase mapping для чтения metadata. Проверьте /rbac.',
  ODATA_MAPPING_AMBIGUOUS: 'Найдено несколько mapping для metadata path. Проверьте /rbac.',
  POOL_METADATA_REFERENCE_INVALID: 'Document policy содержит ссылки на отсутствующие metadata поля.',
  POOL_METADATA_SNAPSHOT_UNAVAILABLE: 'Metadata snapshot недоступен для выбранной базы.',
  POOL_METADATA_REFRESH_IN_PROGRESS: 'Metadata refresh уже выполняется для этой базы.',
  POOL_WORKFLOW_BINDING_REVISION_CONFLICT: 'Workflow binding уже был изменён другим оператором. Обновите bindings и повторите сохранение.',
  POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT: 'Набор workflow bindings уже был изменён другим оператором. Обновите bindings и повторите сохранение.',
}

const METADATA_HANDOFF_ERROR_CODES = new Set([
  'ODATA_MAPPING_NOT_CONFIGURED',
  'ODATA_MAPPING_AMBIGUOUS',
  'POOL_METADATA_REFERENCE_INVALID',
  'POOL_METADATA_SNAPSHOT_UNAVAILABLE',
  'POOL_METADATA_PROFILE_UNAVAILABLE',
  'POOL_METADATA_REFRESH_IN_PROGRESS',
  'POOL_METADATA_FETCH_FAILED',
  'POOL_METADATA_PARSE_FAILED',
])

type PoolCatalogWorkspaceTab = 'organizations' | 'pools' | 'bindings' | 'topology' | 'graph'

const DEFAULT_WORKSPACE_TAB: PoolCatalogWorkspaceTab = 'pools'

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const parseWorkspaceTab = (value: string | null): PoolCatalogWorkspaceTab => {
  const normalized = normalizeRouteParam(value)
  if (
    normalized === 'organizations'
    || normalized === 'pools'
    || normalized === 'bindings'
    || normalized === 'topology'
    || normalized === 'graph'
  ) {
    return normalized
  }
  return DEFAULT_WORKSPACE_TAB
}

const getDefaultGraphDate = () => new Date().toISOString().slice(0, 10)

const normalizeGraphDateParam = (value: string | null): string | null => {
  const normalized = normalizeRouteParam(value)
  if (normalized && /^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    return normalized
  }
  return null
}

const parseGraphDateInput = (value: string): string => normalizeGraphDateParam(value) ?? getDefaultGraphDate()

type OrganizationFormValues = {
  inn: string
  name: string
  full_name: string
  kpp: string
  status: OrganizationStatus
  database_id?: string
  external_ref: string
}

type PoolFormValues = {
  code: string
  name: string
  description: string
  is_active: boolean
}

type PoolBindingsFormValues = {
  workflow_bindings?: PoolWorkflowBindingFormValue[]
}

type TopologyNodeFormValue = {
  organization_id?: string
  is_root?: boolean
  metadata_json?: string
}

type TopologyTemplateSlotAssignmentFormValue = {
  slot_key?: string
  organization_id?: string
}

type TopologyTemplateEdgeSelectorOverrideFormValue = {
  parent_slot_key?: string
  child_slot_key?: string
  document_policy_key?: string
}

type TopologyEdgeFormValue = {
  edge_version_id?: string
  parent_organization_id?: string
  child_organization_id?: string
  weight?: number
  min_amount?: number | null
  max_amount?: number | null
  document_policy_key?: string
  document_policy_mode?: 'builder' | 'raw'
  document_policy_json?: string
  document_policy_builder?: DocumentPolicyBuilderChainFormValue[]
  edge_metadata_mode?: 'builder' | 'raw'
  edge_metadata_builder?: EdgeMetadataBuilderFieldFormValue[]
  metadata_json?: string
}

type TopologyFormValues = {
  authoring_mode?: 'template' | 'manual'
  effective_from: string
  effective_to?: string
  topology_template_revision_id?: string
  slot_assignments?: TopologyTemplateSlotAssignmentFormValue[]
  edge_selector_overrides?: TopologyTemplateEdgeSelectorOverrideFormValue[]
  nodes: TopologyNodeFormValue[]
  edges: TopologyEdgeFormValue[]
}

type DocumentPolicySourceType = 'expression' | 'master_data_token'
type MasterDataTokenEntityType = 'party' | 'item' | 'contract' | 'tax_profile'
type MasterDataTokenPartyRole = 'organization' | 'counterparty'

type DocumentPolicyBuilderSourceValue = {
  source_type?: DocumentPolicySourceType
  source?: string
  expression_source?: string
  token_entity_type?: MasterDataTokenEntityType
  token_canonical_id?: string
  token_party_role?: MasterDataTokenPartyRole
  token_owner_counterparty_canonical_id?: string
}

type DocumentPolicyBuilderFieldMappingRow = DocumentPolicyBuilderSourceValue & {
  target_field?: string
}

type DocumentPolicyBuilderLinkRuleRow = {
  target_field?: string
  source?: string
}

type DocumentPolicyBuilderTablePartRowMapping = DocumentPolicyBuilderSourceValue & {
  target_row_field?: string
}

type DocumentPolicyBuilderTablePartFormValue = {
  table_part?: string
  row_mappings?: DocumentPolicyBuilderTablePartRowMapping[]
}

type DocumentPolicyBuilderDocumentFormValue = {
  document_id?: string
  entity_name?: string
  document_role?: string
  invoice_mode?: 'optional' | 'required'
  link_to?: string
  link_rule_mappings?: DocumentPolicyBuilderLinkRuleRow[]
  field_mappings?: DocumentPolicyBuilderFieldMappingRow[]
  table_part_mappings?: DocumentPolicyBuilderTablePartFormValue[]
}

type DocumentPolicyBuilderChainFormValue = {
  chain_id?: string
  documents?: DocumentPolicyBuilderDocumentFormValue[]
}

type EdgeMetadataBuilderFieldFormValue = {
  key?: string
  value_json?: string
}

const ORGANIZATION_FORM_FIELDS: Array<keyof OrganizationFormValues> = [
  'inn',
  'name',
  'full_name',
  'kpp',
  'status',
  'database_id',
  'external_ref',
]

type SyncPreflightResult = {
  rows: Array<Record<string, unknown>>
  errors: string[]
}

const formatDate = (value: string | null | undefined) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const isValidBindingProfileDetailResponse = (
  requestedBindingProfileId: string,
  detail: BindingProfileDetail,
): boolean => {
  if (detail.binding_profile_id !== requestedBindingProfileId) {
    return false
  }
  if (detail.latest_revision.binding_profile_id !== requestedBindingProfileId) {
    return false
  }
  const revisionIds = new Set<string>()
  return detail.revisions.every((revision) => {
    if (revision.binding_profile_id !== requestedBindingProfileId) {
      return false
    }
    const revisionId = String(revision.binding_profile_revision_id || '').trim()
    if (!revisionId || revisionIds.has(revisionId)) {
      return false
    }
    revisionIds.add(revisionId)
    return true
  })
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

  for (let index = 0; index < graph.nodes.length; index += 1) {
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
  for (const depth of Array.from(groupedByDepth.keys()).sort((a, b) => a - b)) {
    const nodesAtDepth = groupedByDepth.get(depth) ?? []
    nodesAtDepth.forEach((node, rowIndex) => {
      flowNodes.push({
        id: node.node_version_id,
        position: { x: depth * 280, y: rowIndex * 112 },
        data: { label: `${node.name}\n${node.inn}` },
        style: {
          border: node.is_root ? '2px solid #1677ff' : '1px solid #d9d9d9',
          borderRadius: 8,
          padding: 8,
          width: 230,
          background: '#ffffff',
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

const statusColor: Record<OrganizationStatus, string> = {
  active: 'success',
  inactive: 'default',
  archived: 'warning',
}

const normalizeFieldErrors = (value: unknown): Record<string, string[]> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  const result: Record<string, string[]> = {}
  const source = value as Record<string, unknown>
  for (const [key, raw] of Object.entries(source)) {
    if (raw == null) continue
    if (Array.isArray(raw)) {
      const messages = raw
        .map((item) => (item == null ? '' : String(item).trim()))
        .filter((item) => item.length > 0)
      if (messages.length > 0) {
        result[key] = messages
      }
      continue
    }
    const text = String(raw).trim()
    if (text.length > 0) {
      result[key] = [text]
    }
  }
  return result
}

const normalizeProblemErrorItems = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return []
  }
  const items: string[] = []
  value.forEach((rawItem) => {
    if (!rawItem || typeof rawItem !== 'object' || Array.isArray(rawItem)) {
      const text = String(rawItem ?? '').trim()
      if (text) {
        items.push(text)
      }
      return
    }
    const item = rawItem as Record<string, unknown>
    const code = String(item.code ?? '').trim()
    const path = String(item.path ?? '').trim()
    const detail = String(item.detail ?? '').trim()
    if (path && detail) {
      items.push(`${path}: ${detail}`)
      return
    }
    if (detail) {
      items.push(detail)
      return
    }
    if (path && code) {
      items.push(`${path}: ${code}`)
      return
    }
    if (code) {
      items.push(code)
    }
  })
  return Array.from(new Set(items)).slice(0, 5)
}

const buildFieldErrorLines = (fieldErrors: Record<string, string[]>): string[] => (
  Object.entries(fieldErrors).flatMap(([field, messages]) => (
    messages.map((message) => `${field}: ${message}`)
  ))
)

const mergeMessageParts = (parts: string[]): string => {
  const normalized = parts
    .map((item) => String(item || '').trim())
    .filter((item) => item.length > 0)
  if (normalized.length === 0) {
    return ''
  }
  return Array.from(new Set(normalized)).join(' | ')
}

const resolveApiError = (
  error: unknown,
  fallbackMessage: string,
  options?: {
    includeProblemDetail?: boolean
    includeProblemItems?: boolean
  }
): { message: string; fieldErrors: Record<string, string[]> } => {
  const err = error as {
    message?: string
    response?: {
      data?: {
        success?: boolean
        error?: unknown
      } | Record<string, unknown>
    }
  } | null

  const responseData = err?.response?.data
  if (responseData && typeof responseData === 'object' && !Array.isArray(responseData)) {
    const maybeProblem = responseData as {
      code?: unknown
      detail?: unknown
      title?: unknown
      errors?: unknown
    }
    const includeProblemDetail = Boolean(options?.includeProblemDetail)
    const includeProblemItems = Boolean(options?.includeProblemItems)
    const problemCode = typeof maybeProblem.code === 'string' ? maybeProblem.code : ''
    const problemDetail = typeof maybeProblem.detail === 'string' ? maybeProblem.detail.trim() : ''
    const problemFieldErrors = normalizeFieldErrors(maybeProblem.errors)
    const problemItems = normalizeProblemErrorItems(maybeProblem.errors)
    if (problemCode || problemDetail || Object.keys(problemFieldErrors).length > 0) {
      const hasProblemFieldErrors = Object.keys(problemFieldErrors).length > 0
      const mappedMessage = (
        problemCode === 'VALIDATION_ERROR' && problemDetail && !hasProblemFieldErrors
          ? problemDetail
          : (API_ERROR_MESSAGE_MAP[problemCode] ?? problemDetail)
      )
      const baseMessage = mappedMessage || (hasProblemFieldErrors
        ? 'Проверьте корректность заполнения полей.'
        : fallbackMessage)
      return {
        message: mergeMessageParts([
          baseMessage,
          includeProblemDetail && problemDetail !== baseMessage ? problemDetail : '',
          ...(includeProblemItems ? problemItems : []),
        ]) || baseMessage,
        fieldErrors: problemFieldErrors,
      }
    }
  }

  const errorNode = (responseData as { error?: unknown } | undefined)?.error
  if (errorNode && typeof errorNode === 'object' && !Array.isArray(errorNode)) {
    const structured = errorNode as { code?: unknown; message?: unknown }
    const code = typeof structured.code === 'string' ? structured.code : ''
    const backendMessage = typeof structured.message === 'string' ? structured.message.trim() : ''
    if (code) {
      const preferBackendValidationMessage = code === 'VALIDATION_ERROR' && backendMessage.length > 0
      return {
        message: preferBackendValidationMessage
          ? backendMessage
          : (API_ERROR_MESSAGE_MAP[code] ?? (backendMessage || fallbackMessage)),
        fieldErrors: {},
      }
    }
    const fieldErrors = normalizeFieldErrors(errorNode)
    if (Object.keys(fieldErrors).length > 0) {
      return {
        message: 'Проверьте корректность заполнения полей.',
        fieldErrors,
      }
    }
  }

  const fallbackFromError = typeof err?.message === 'string' ? err.message.trim() : ''
  return {
    message: fallbackFromError || fallbackMessage,
    fieldErrors: {},
  }
}

const getApiErrorCode = (error: unknown): string => {
  const err = error as {
    response?: {
      data?: {
        code?: unknown
        error?: {
          code?: unknown
        }
      }
    }
  } | null
  const responseData = err?.response?.data
  if (!responseData || typeof responseData !== 'object' || Array.isArray(responseData)) {
    return ''
  }
  if (typeof responseData.code === 'string') {
    return responseData.code
  }
  if (
    responseData.error
    && typeof responseData.error === 'object'
    && typeof responseData.error.code === 'string'
  ) {
    return responseData.error.code
  }
  return ''
}

const appendMetadataManagementHandoff = (message: string): string => {
  const handoff = 'Metadata context недоступен для topology editor. Откройте /databases, перепроверьте configuration identity или обновите metadata snapshot и повторите.'
  return mergeMessageParts([message, handoff]) || handoff
}

const hasLegacyDocumentPolicyPayload = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

type TopologyTemplateInstantiationMetadata = {
  topology_template_id?: string
  topology_template_code?: string
  topology_template_name?: string
  topology_template_revision_id?: string
  topology_template_revision_number?: number
  slot_assignments?: TopologyTemplateSlotAssignmentFormValue[]
  edge_selector_overrides?: TopologyTemplateEdgeSelectorOverrideFormValue[]
}

const readTopologyTemplateInstantiation = (
  pool: OrganizationPool | null | undefined
): TopologyTemplateInstantiationMetadata | null => {
  const metadata = pool?.metadata
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) {
    return null
  }
  const payload = (metadata as Record<string, unknown>).topology_template_instantiation
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null
  }
  return payload as TopologyTemplateInstantiationMetadata
}

const resolveInitialTopologyAuthoringMode = ({
  graph,
  topologyInstantiation,
}: {
  graph: PoolGraph | null
  topologyInstantiation: TopologyTemplateInstantiationMetadata | null
}): 'template' | 'manual' => {
  if (topologyInstantiation) {
    return 'template'
  }
  const hasConcreteGraph = Boolean(graph && (graph.nodes.length > 0 || graph.edges.length > 0))
  return hasConcreteGraph ? 'manual' : 'template'
}

const buildDraftTopologyEdgeSelectors = (
  edges: TopologyEdgeFormValue[] | undefined,
  organizationById: Record<string, Organization>
): TopologyEdgeSelector[] => (
  (Array.isArray(edges) ? edges : []).map((edge, index) => {
    const parentOrganizationId = String(edge.parent_organization_id || '').trim()
    const childOrganizationId = String(edge.child_organization_id || '').trim()
    const parentLabel = String(
      organizationById[parentOrganizationId]?.name
      || parentOrganizationId
      || `edge-${index + 1}-parent`
    ).trim()
    const childLabel = String(
      organizationById[childOrganizationId]?.name
      || childOrganizationId
      || `edge-${index + 1}-child`
    ).trim()
    return {
      edgeId: String(edge.edge_version_id || `${parentOrganizationId}:${childOrganizationId}:${index}`),
      edgeLabel: `${parentLabel} -> ${childLabel}`,
      slotKey: String(edge.document_policy_key || '').trim(),
    }
  })
)

const buildTemplateDraftTopologyEdgeSelectors = (
  revision: PoolTopologyTemplateRevision | null,
  overrides: TopologyTemplateEdgeSelectorOverrideFormValue[] | undefined
): TopologyEdgeSelector[] => {
  if (!revision) {
    return []
  }
  const labelBySlotKey = new Map(
    revision.nodes.map((node) => [
      String(node.slot_key || '').trim(),
      String(node.label || node.slot_key || '').trim(),
    ])
  )
  const overrideByEdge = new Map<string, string>()
  ;(Array.isArray(overrides) ? overrides : []).forEach((override) => {
    const parentSlotKey = String(override.parent_slot_key || '').trim()
    const childSlotKey = String(override.child_slot_key || '').trim()
    const documentPolicyKey = String(override.document_policy_key || '').trim()
    if (!parentSlotKey || !childSlotKey || !documentPolicyKey) {
      return
    }
    overrideByEdge.set(`${parentSlotKey}:${childSlotKey}`, documentPolicyKey)
  })
  return revision.edges.map((edge: PoolTopologyTemplateEdge, index: number) => {
    const parentSlotKey = String(edge.parent_slot_key || '').trim()
    const childSlotKey = String(edge.child_slot_key || '').trim()
    const edgeId = `${parentSlotKey}:${childSlotKey}:${index}`
    const parentLabel = labelBySlotKey.get(parentSlotKey) || parentSlotKey || `template-edge-${index + 1}-parent`
    const childLabel = labelBySlotKey.get(childSlotKey) || childSlotKey || `template-edge-${index + 1}-child`
    const slotKey = (
      overrideByEdge.get(`${parentSlotKey}:${childSlotKey}`)
      || String(edge.document_policy_key || '').trim()
    )
    return {
      edgeId,
      edgeLabel: `${parentLabel} -> ${childLabel}`,
      slotKey,
    }
  })
}

const buildBindingSlotRefsFromForm = (
  binding: PoolWorkflowBindingFormValue | undefined
): Array<{ slotKey: string; refLabel: string }> => (
  (binding?.resolved_profile?.decisions ?? [])
    .map((decision) => {
      const slotKey = String(decision?.slot_key || decision?.decision_key || '').trim()
      const decisionTableId = String(decision?.decision_table_id || '').trim()
      const decisionKey = String(decision?.decision_key || '').trim()
      const decisionRevision = String(decision?.decision_revision ?? '').trim()
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

const buildTopologySlotOptions = (
  slotRefs: Array<{ slotKey: string; refLabel: string }>
): Array<{ value: string; label: string }> => {
  const groupedRefs = new Map<string, Set<string>>()
  slotRefs.forEach((slotRef) => {
    const slotKey = String(slotRef.slotKey || '').trim()
    const refLabel = String(slotRef.refLabel || '').trim()
    if (!slotKey || !refLabel) {
      return
    }
    const labels = groupedRefs.get(slotKey) ?? new Set<string>()
    labels.add(refLabel)
    groupedRefs.set(slotKey, labels)
  })

  return Array.from(groupedRefs.entries())
    .map(([slotKey, refLabels]) => {
      const labels = Array.from(refLabels)
      return {
        value: slotKey,
        label: labels.length === 1
          ? `${slotKey} · ${labels[0]}`
          : `${slotKey} · ${labels.length} decision refs`,
      }
    })
    .sort((left, right) => left.label.localeCompare(right.label))
}

const buildLegacyTopologyBlockingRemediation = ({
  graph,
  pool,
}: {
  graph: PoolGraph | null
  pool: OrganizationPool | null | undefined
}): PoolWorkflowBindingBlockingRemediation | null => {
  const poolHasLegacyPolicy = hasLegacyDocumentPolicyPayload(pool?.metadata?.document_policy)
  const legacyEdgeLabels: string[] = []
  if (graph) {
    const nodeByVersionId = new Map(
      graph.nodes.map((node) => [node.node_version_id, node])
    )
    graph.edges.forEach((edge) => {
      const metadata = edge.metadata
      if (!hasLegacyDocumentPolicyPayload(metadata) || !hasLegacyDocumentPolicyPayload(metadata.document_policy)) {
        return
      }
      const parentNode = nodeByVersionId.get(edge.parent_node_version_id)
      const childNode = nodeByVersionId.get(edge.child_node_version_id)
      const parentLabel = String(parentNode?.name || parentNode?.organization_id || edge.parent_node_version_id).trim()
      const childLabel = String(childNode?.name || childNode?.organization_id || edge.child_node_version_id).trim()
      legacyEdgeLabels.push(`${parentLabel} -> ${childLabel}`)
    })
  }
  if (!poolHasLegacyPolicy && legacyEdgeLabels.length === 0) {
    return null
  }
  const detailParts: string[] = []
  if (poolHasLegacyPolicy) {
    detailParts.push('pool.metadata still contains legacy document_policy payload.')
  }
  if (legacyEdgeLabels.length > 0) {
    const suffix = legacyEdgeLabels.length > 2 ? ', …' : ''
    detailParts.push(
      `Legacy document_policy payload is still attached to ${legacyEdgeLabels.length} topology edge(s): ${legacyEdgeLabels.slice(0, 2).join(', ')}${suffix}.`
    )
  }
  detailParts.push('Move concrete policy authoring to /decisions, pin named slots in Bindings, then keep only document_policy_key on topology edges.')
  return {
    code: 'LEGACY_TOPOLOGY_DOCUMENT_POLICY_PRESENT',
    title: 'Legacy topology remediation required',
    detail: detailParts.join(' '),
  }
}

const buildCoverageBlockingRemediation = ({
  code,
  title,
  summary,
  unresolvedDetail,
}: {
  code: string
  title: string
  summary: ReturnType<typeof summarizeTopologySlotCoverage>
  unresolvedDetail: string
}): PoolWorkflowBindingBlockingRemediation | null => {
  const unresolvedItems = summary.items.filter((item) => item.coverage.status !== 'resolved')
  if (unresolvedItems.length === 0) {
    return null
  }
  const firstItem = unresolvedItems[0]
  return {
    code,
    title,
    detail: `${unresolvedDetail} First issue: ${firstItem?.edgeLabel || 'edge'} · ${firstItem?.slotKey || 'slot not set'} · ${firstItem?.coverage.label || 'Unresolved'}.`,
  }
}

const parseSyncPayload = (input: string): SyncPreflightResult => {
  let parsed: unknown
  try {
    parsed = JSON.parse(input)
  } catch {
    return { rows: [], errors: ['Payload должен быть валидным JSON.'] }
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { rows: [], errors: ['Payload должен быть объектом вида {"rows": [...]}'] }
  }

  const rowsRaw = (parsed as { rows?: unknown }).rows
  if (!Array.isArray(rowsRaw)) {
    return { rows: [], errors: ['Поле rows обязательно и должно быть массивом.'] }
  }
  if (rowsRaw.length === 0) {
    return { rows: [], errors: ['Поле rows не должно быть пустым.'] }
  }
  if (rowsRaw.length > SYNC_MAX_ROWS) {
    return { rows: [], errors: [`Превышен лимит batch: максимум ${SYNC_MAX_ROWS} строк.`] }
  }

  const rows: Array<Record<string, unknown>> = []
  const errors: string[] = []

  rowsRaw.forEach((raw, index) => {
    const rowNumber = index + 1
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      errors.push(`Строка ${rowNumber}: ожидается объект.`)
      return
    }

    const row = raw as Record<string, unknown>
    const normalized: Record<string, unknown> = { ...row }

    const inn = String(row.inn ?? '').trim()
    if (!inn) {
      errors.push(`Строка ${rowNumber}: поле inn обязательно.`)
    } else {
      normalized.inn = inn
    }

    const name = String(row.name ?? '').trim()
    if (!name) {
      errors.push(`Строка ${rowNumber}: поле name обязательно.`)
    } else {
      normalized.name = name
    }

    const statusRaw = row.status
    if (statusRaw !== undefined && statusRaw !== null && String(statusRaw).trim() !== '') {
      const status = String(statusRaw).trim().toLowerCase()
      if (!STATUS_OPTIONS.includes(status as OrganizationStatus)) {
        errors.push(`Строка ${rowNumber}: недопустимый status "${status}".`)
      } else {
        normalized.status = status
      }
    }

    if (Object.prototype.hasOwnProperty.call(row, 'database_id')) {
      const databaseIdRaw = row.database_id
      if (databaseIdRaw === null || String(databaseIdRaw).trim() === '') {
        normalized.database_id = null
      } else {
        const databaseId = String(databaseIdRaw).trim()
        if (!UUID_REGEX.test(databaseId)) {
          errors.push(`Строка ${rowNumber}: database_id должен быть UUID.`)
        } else {
          normalized.database_id = databaseId
        }
      }
    }

    rows.push(normalized)
  })

  return { rows, errors }
}

const formatOptionalDecimal = (value: number | null | undefined): string | null => {
  if (value == null || Number.isNaN(value)) return null
  return Number(value).toFixed(2)
}

const normalizeMetadataObject = (rawMetadata: unknown): Record<string, unknown> => {
  if (!rawMetadata || typeof rawMetadata !== 'object' || Array.isArray(rawMetadata)) {
    return {}
  }
  return { ...(rawMetadata as Record<string, unknown>) }
}

const parseTopologyMetadata = (
  rawMetadataJson: string | undefined,
  rowLabel: string
): {
  metadata: Record<string, unknown>
  errors: string[]
} => {
  const source = String(rawMetadataJson ?? '').trim()
  if (!source) {
    return { metadata: {}, errors: [] }
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(source)
  } catch {
    return {
      metadata: {},
      errors: [`${rowLabel}: metadata должен быть валидным JSON.`],
    }
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return {
      metadata: {},
      errors: [`${rowLabel}: metadata должен быть JSON object.`],
    }
  }

  return {
    metadata: { ...(parsed as Record<string, unknown>) },
    errors: [],
  }
}

const stringifyMetadataForForm = (rawMetadata: unknown): string => {
  const metadata = normalizeMetadataObject(rawMetadata)
  if (Object.keys(metadata).length === 0) {
    return ''
  }
  try {
    return JSON.stringify(metadata, null, 2)
  } catch {
    return ''
  }
}

const DOCUMENT_POLICY_VERSION = 'document_policy.v1'
const MASTER_DATA_TOKEN_PREFIX = 'master_data.'
const TOKEN_SOURCE_TYPE_OPTIONS: Array<{ value: DocumentPolicySourceType; label: string }> = [
  { value: 'expression', label: 'expression' },
  { value: 'master_data_token', label: 'master_data_token' },
]
const TOKEN_ENTITY_TYPE_OPTIONS: Array<{ value: MasterDataTokenEntityType; label: string }> = [
  { value: 'party', label: 'party' },
  { value: 'item', label: 'item' },
  { value: 'contract', label: 'contract' },
  { value: 'tax_profile', label: 'tax_profile' },
]
const TOKEN_PARTY_ROLE_OPTIONS: Array<{ value: MasterDataTokenPartyRole; label: string }> = [
  { value: 'organization', label: 'organization' },
  { value: 'counterparty', label: 'counterparty' },
]

type ParsedMasterDataToken = {
  entity_type: MasterDataTokenEntityType
  canonical_id: string
  party_role?: MasterDataTokenPartyRole
  owner_counterparty_canonical_id?: string
}

const parseMasterDataToken = (value: string): ParsedMasterDataToken | null => {
  const source = value.trim()
  if (!source.startsWith(MASTER_DATA_TOKEN_PREFIX)) {
    return null
  }
  const parts = source.split('.')
  if (parts[0] !== 'master_data' || parts[parts.length - 1] !== 'ref') {
    return null
  }
  if (parts[1] === 'party' && parts.length === 5) {
    const canonicalId = String(parts[2] || '').trim()
    const partyRole = String(parts[3] || '').trim()
    if (!canonicalId) return null
    if (partyRole !== 'organization' && partyRole !== 'counterparty') {
      return null
    }
    return {
      entity_type: 'party',
      canonical_id: canonicalId,
      party_role: partyRole as MasterDataTokenPartyRole,
    }
  }
  if (parts[1] === 'item' && parts.length === 4) {
    const canonicalId = String(parts[2] || '').trim()
    if (!canonicalId) return null
    return {
      entity_type: 'item',
      canonical_id: canonicalId,
    }
  }
  if (parts[1] === 'contract' && parts.length === 5) {
    const canonicalId = String(parts[2] || '').trim()
    const ownerCounterpartyCanonicalId = String(parts[3] || '').trim()
    if (!canonicalId || !ownerCounterpartyCanonicalId) return null
    return {
      entity_type: 'contract',
      canonical_id: canonicalId,
      owner_counterparty_canonical_id: ownerCounterpartyCanonicalId,
    }
  }
  if (parts[1] === 'tax_profile' && parts.length === 4) {
    const canonicalId = String(parts[2] || '').trim()
    if (!canonicalId) return null
    return {
      entity_type: 'tax_profile',
      canonical_id: canonicalId,
    }
  }
  return null
}

const isMasterDataTokenLike = (value: string): boolean => (
  value.trim().startsWith(MASTER_DATA_TOKEN_PREFIX)
)

const decodeDocumentPolicySourceValue = (rawSource: unknown): DocumentPolicyBuilderSourceValue => {
  const source = String(rawSource ?? '').trim()
  const parsedToken = parseMasterDataToken(source)
  if (!parsedToken) {
    return {
      source_type: 'expression',
      source,
      expression_source: source,
    }
  }
  return {
    source_type: 'master_data_token',
    source,
    expression_source: '',
    token_entity_type: parsedToken.entity_type,
    token_canonical_id: parsedToken.canonical_id,
    token_party_role: parsedToken.party_role,
    token_owner_counterparty_canonical_id: parsedToken.owner_counterparty_canonical_id,
  }
}

const buildMasterDataToken = (
  sourceValue: DocumentPolicyBuilderSourceValue
): string | null => {
  const entityType = String(sourceValue.token_entity_type ?? '').trim()
  const canonicalId = String(sourceValue.token_canonical_id ?? '').trim()
  if (!entityType || !canonicalId) {
    return null
  }
  if (entityType === 'party') {
    const partyRole = String(sourceValue.token_party_role ?? '').trim()
    if (partyRole !== 'organization' && partyRole !== 'counterparty') {
      return null
    }
    return `master_data.party.${canonicalId}.${partyRole}.ref`
  }
  if (entityType === 'item') {
    return `master_data.item.${canonicalId}.ref`
  }
  if (entityType === 'contract') {
    const ownerCounterpartyCanonicalId = String(
      sourceValue.token_owner_counterparty_canonical_id ?? ''
    ).trim()
    if (!ownerCounterpartyCanonicalId) {
      return null
    }
    return `master_data.contract.${canonicalId}.${ownerCounterpartyCanonicalId}.ref`
  }
  if (entityType === 'tax_profile') {
    return `master_data.tax_profile.${canonicalId}.ref`
  }
  return null
}

const hasDocumentPolicySourceInput = (sourceValue: DocumentPolicyBuilderSourceValue): boolean => (
  Boolean(
    String(sourceValue.source_type ?? '').trim()
    || String(sourceValue.source ?? '').trim()
    || String(sourceValue.expression_source ?? '').trim()
    || String(sourceValue.token_entity_type ?? '').trim()
    || String(sourceValue.token_canonical_id ?? '').trim()
    || String(sourceValue.token_party_role ?? '').trim()
    || String(sourceValue.token_owner_counterparty_canonical_id ?? '').trim()
  )
)

const resolveDocumentPolicySourceValue = (
  sourceValue: DocumentPolicyBuilderSourceValue,
  rowLabel: string
): { source: string | null; error: string | null } => {
  const sourceType = String(sourceValue.source_type ?? '').trim().toLowerCase() === 'master_data_token'
    ? 'master_data_token'
    : 'expression'

  if (sourceType === 'expression') {
    const expressionSource = String(sourceValue.expression_source ?? sourceValue.source ?? '').trim()
    if (!expressionSource) {
      return { source: null, error: null }
    }
    if (isMasterDataTokenLike(expressionSource)) {
      return {
        source: null,
        error: `${rowLabel}: canonical master_data token недопустим для source_type=expression.`,
      }
    }
    return { source: expressionSource, error: null }
  }

  const entityType = String(sourceValue.token_entity_type ?? '').trim()
  if (!entityType) {
    return {
      source: null,
      error: `${rowLabel}: source_type=master_data_token требует entity_type.`,
    }
  }
  const canonicalId = String(sourceValue.token_canonical_id ?? '').trim()
  if (!canonicalId) {
    return {
      source: null,
      error: `${rowLabel}: source_type=master_data_token требует canonical_id.`,
    }
  }
  if (entityType === 'party') {
    const partyRole = String(sourceValue.token_party_role ?? '').trim()
    if (partyRole !== 'organization' && partyRole !== 'counterparty') {
      return {
        source: null,
        error: `${rowLabel}: для entity_type=party требуется role organization|counterparty.`,
      }
    }
  }
  if (entityType === 'contract') {
    const ownerCounterpartyCanonicalId = String(
      sourceValue.token_owner_counterparty_canonical_id ?? ''
    ).trim()
    if (!ownerCounterpartyCanonicalId) {
      return {
        source: null,
        error: `${rowLabel}: для entity_type=contract требуется owner_counterparty_canonical_id.`,
      }
    }
  }

  const token = buildMasterDataToken(sourceValue)
  if (!token || !parseMasterDataToken(token)) {
    return {
      source: null,
      error: `${rowLabel}: token должен соответствовать canonical master_data.*.ref формату.`,
    }
  }
  return { source: token, error: null }
}

const validateDocumentPolicyObject = (
  policy: Record<string, unknown>,
  rowNo: number
): string[] => {
  const errors: string[] = []
  const version = String(policy.version ?? '').trim()
  if (version !== DOCUMENT_POLICY_VERSION) {
    errors.push(`Edge #${rowNo}: document_policy.version должен быть "${DOCUMENT_POLICY_VERSION}".`)
  }

  const chainsRaw = policy.chains
  if (!Array.isArray(chainsRaw) || chainsRaw.length === 0) {
    errors.push(`Edge #${rowNo}: document_policy.chains должен содержать хотя бы одну цепочку.`)
    return errors
  }

  chainsRaw.forEach((chain, chainIndex) => {
    const chainNo = chainIndex + 1
    if (!chain || typeof chain !== 'object' || Array.isArray(chain)) {
      errors.push(`Edge #${rowNo}: chain #${chainNo} должен быть объектом.`)
      return
    }
    const chainObject = chain as Record<string, unknown>
    const chainId = String(chainObject.chain_id ?? '').trim()
    if (!chainId) {
      errors.push(`Edge #${rowNo}: chain #${chainNo} должен содержать chain_id.`)
    }
    const documentsRaw = chainObject.documents
    if (!Array.isArray(documentsRaw) || documentsRaw.length === 0) {
      errors.push(`Edge #${rowNo}: chain #${chainNo} должен содержать documents[].`)
      return
    }

    documentsRaw.forEach((document, documentIndex) => {
      const documentNo = documentIndex + 1
      if (!document || typeof document !== 'object' || Array.isArray(document)) {
        errors.push(`Edge #${rowNo}: chain #${chainNo}, document #${documentNo} должен быть объектом.`)
        return
      }
      const documentObject = document as Record<string, unknown>
      const requiredFields = ['document_id', 'entity_name', 'document_role']
      requiredFields.forEach((fieldName) => {
        const fieldValue = String(documentObject[fieldName] ?? '').trim()
        if (!fieldValue) {
          errors.push(
            `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} должен содержать ${fieldName}.`
          )
        }
      })
      const invoiceModeRaw = String(documentObject.invoice_mode ?? '').trim()
      if (invoiceModeRaw && invoiceModeRaw !== 'optional' && invoiceModeRaw !== 'required') {
        errors.push(
          `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} содержит недопустимый invoice_mode.`
        )
      }
    })
  })
  return errors
}

const sortRecordByKeys = (value: Record<string, string>): Record<string, string> => (
  Object.fromEntries(
    Object.entries(value).sort(([left], [right]) => left.localeCompare(right))
  )
)

const metadataObjectToBuilderRows = (
  metadata: Record<string, unknown>
): EdgeMetadataBuilderFieldFormValue[] => (
  Object.entries(metadata)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => ({
      key,
      value_json: JSON.stringify(value, null, 2),
    }))
)

const documentPolicyToBuilderChains = (
  policy: Record<string, unknown> | null
): DocumentPolicyBuilderChainFormValue[] => {
  if (!policy) return []
  const chainsRaw = policy.chains
  if (!Array.isArray(chainsRaw)) return []

  return chainsRaw.map<DocumentPolicyBuilderChainFormValue>((chain) => {
    const chainObject = chain && typeof chain === 'object' && !Array.isArray(chain)
      ? chain as Record<string, unknown>
      : {}
    const documentsRaw = Array.isArray(chainObject.documents) ? chainObject.documents : []

    return {
      chain_id: String(chainObject.chain_id ?? '').trim(),
      documents: documentsRaw.map<DocumentPolicyBuilderDocumentFormValue>((document) => {
        const documentObject = document && typeof document === 'object' && !Array.isArray(document)
          ? document as Record<string, unknown>
          : {}

        const fieldMappingRaw = (
          documentObject.field_mapping
          && typeof documentObject.field_mapping === 'object'
          && !Array.isArray(documentObject.field_mapping)
            ? documentObject.field_mapping as Record<string, unknown>
            : {}
        )
        const tablePartsRaw = (
          documentObject.table_parts_mapping
          && typeof documentObject.table_parts_mapping === 'object'
          && !Array.isArray(documentObject.table_parts_mapping)
            ? documentObject.table_parts_mapping as Record<string, unknown>
            : {}
        )
        const linkRulesRaw = (
          documentObject.link_rules
          && typeof documentObject.link_rules === 'object'
          && !Array.isArray(documentObject.link_rules)
            ? documentObject.link_rules as Record<string, unknown>
            : {}
        )

        return {
          document_id: String(documentObject.document_id ?? '').trim(),
          entity_name: String(documentObject.entity_name ?? '').trim(),
          document_role: String(documentObject.document_role ?? '').trim(),
          invoice_mode: (
            String(documentObject.invoice_mode ?? 'optional').trim().toLowerCase() === 'required'
              ? 'required'
              : 'optional'
          ),
          link_to: String(documentObject.link_to ?? '').trim(),
          link_rule_mappings: Object.entries(linkRulesRaw).map(([targetField, source]) => ({
            target_field: String(targetField).trim(),
            source: String(source ?? '').trim(),
          })),
          field_mappings: Object.entries(fieldMappingRaw).map(([targetField, source]) => {
            const decoded = decodeDocumentPolicySourceValue(source)
            return {
              target_field: String(targetField).trim(),
              ...decoded,
            }
          }),
          table_part_mappings: Object.entries(tablePartsRaw).map(([tablePartName, rowMapping]) => {
            const rowObject = rowMapping && typeof rowMapping === 'object' && !Array.isArray(rowMapping)
              ? rowMapping as Record<string, unknown>
              : {}
            return {
              table_part: String(tablePartName).trim(),
              row_mappings: Object.entries(rowObject).map(([targetRowField, source]) => {
                const decoded = decodeDocumentPolicySourceValue(source)
                return {
                  target_row_field: String(targetRowField).trim(),
                  ...decoded,
                }
              }),
            }
          }),
        }
      }),
    }
  })
}

const buildDocumentPolicyFromBuilder = (
  chainsRaw: DocumentPolicyBuilderChainFormValue[] | undefined,
  rowNo: number
): {
  policy: Record<string, unknown> | null
  errors: string[]
} => {
  const chainsSource = Array.isArray(chainsRaw) ? chainsRaw : []
  const errors: string[] = []
  const normalizedChains: Array<Record<string, unknown>> = []

  if (chainsSource.length === 0) {
    errors.push(`Edge #${rowNo}: document_policy.chains должен содержать хотя бы одну цепочку.`)
    return { policy: null, errors }
  }

  chainsSource.forEach((rawChain, chainIndex) => {
    const chainNo = chainIndex + 1
    const chainId = String(rawChain?.chain_id ?? '').trim()
    if (!chainId) {
      errors.push(`Edge #${rowNo}: chain #${chainNo} должен содержать chain_id.`)
    }

    const documentsRaw = Array.isArray(rawChain?.documents) ? rawChain.documents : []
    if (documentsRaw.length === 0) {
      errors.push(`Edge #${rowNo}: chain #${chainNo} должен содержать documents[].`)
      return
    }

    const normalizedDocuments: Array<Record<string, unknown>> = []

    documentsRaw.forEach((rawDocument, documentIndex) => {
      const documentNo = documentIndex + 1
      const documentId = String(rawDocument?.document_id ?? '').trim()
      const entityName = String(rawDocument?.entity_name ?? '').trim()
      const documentRole = String(rawDocument?.document_role ?? '').trim()
      if (!documentId) {
        errors.push(
          `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} должен содержать document_id.`
        )
      }
      if (!entityName) {
        errors.push(
          `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} должен содержать entity_name.`
        )
      }
      if (!documentRole) {
        errors.push(
          `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} должен содержать document_role.`
        )
      }

      const invoiceModeRaw = String(rawDocument?.invoice_mode ?? 'optional').trim().toLowerCase()
      const invoiceMode = invoiceModeRaw || 'optional'
      if (invoiceMode !== 'optional' && invoiceMode !== 'required') {
        errors.push(
          `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} содержит недопустимый invoice_mode.`
        )
      }

      const fieldMappingsRaw = Array.isArray(rawDocument?.field_mappings) ? rawDocument.field_mappings : []
      const fieldMapping: Record<string, string> = {}
      fieldMappingsRaw.forEach((item) => {
        const targetField = String(item?.target_field ?? '').trim()
        const sourceValue: DocumentPolicyBuilderSourceValue = {
          source_type: item?.source_type,
          source: item?.source,
          expression_source: item?.expression_source,
          token_entity_type: item?.token_entity_type,
          token_canonical_id: item?.token_canonical_id,
          token_party_role: item?.token_party_role,
          token_owner_counterparty_canonical_id: item?.token_owner_counterparty_canonical_id,
        }
        const hasSourceInput = hasDocumentPolicySourceInput(sourceValue)
        if (!targetField && !hasSourceInput) return
        if (!targetField) {
          errors.push(
            `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} field_mapping должен содержать target и source.`
          )
          return
        }
        const resolvedSource = resolveDocumentPolicySourceValue(
          sourceValue,
          `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} field_mapping.${targetField}`
        )
        if (!resolvedSource.source) {
          errors.push(
            resolvedSource.error
            || `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} field_mapping должен содержать target и source.`
          )
          return
        }
        fieldMapping[targetField] = resolvedSource.source
      })

      const tablePartMappingsRaw = Array.isArray(rawDocument?.table_part_mappings) ? rawDocument.table_part_mappings : []
      const tablePartsMapping: Record<string, Record<string, string>> = {}
      tablePartMappingsRaw.forEach((tablePart) => {
        const tablePartName = String(tablePart?.table_part ?? '').trim()
        const rowMappingsRaw = Array.isArray(tablePart?.row_mappings) ? tablePart.row_mappings : []
        const rowMapping: Record<string, string> = {}
        rowMappingsRaw.forEach((row) => {
          const targetRowField = String(row?.target_row_field ?? '').trim()
          const sourceValue: DocumentPolicyBuilderSourceValue = {
            source_type: row?.source_type,
            source: row?.source,
            expression_source: row?.expression_source,
            token_entity_type: row?.token_entity_type,
            token_canonical_id: row?.token_canonical_id,
            token_party_role: row?.token_party_role,
            token_owner_counterparty_canonical_id: row?.token_owner_counterparty_canonical_id,
          }
          const hasSourceInput = hasDocumentPolicySourceInput(sourceValue)
          if (!targetRowField && !hasSourceInput) return
          if (!targetRowField) {
            errors.push(
              `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} table_parts_mapping должен содержать target и source.`
            )
            return
          }
          const resolvedSource = resolveDocumentPolicySourceValue(
            sourceValue,
            `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} table_parts_mapping.${tablePartName || '<table_part>'}.${targetRowField}`
          )
          if (!resolvedSource.source) {
            errors.push(
              resolvedSource.error
              || `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} table_parts_mapping должен содержать target и source.`
            )
            return
          }
          rowMapping[targetRowField] = resolvedSource.source
        })
        if (!tablePartName) {
          if (Object.keys(rowMapping).length > 0) {
            errors.push(
              `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} table_parts_mapping должен содержать table_part.`
            )
          }
          return
        }
        tablePartsMapping[tablePartName] = sortRecordByKeys(rowMapping)
      })

      const linkTo = String(rawDocument?.link_to ?? '').trim()
      const linkRulesRaw = Array.isArray(rawDocument?.link_rule_mappings) ? rawDocument.link_rule_mappings : []
      const linkRules: Record<string, string> = {}
      linkRulesRaw.forEach((item) => {
        const targetField = String(item?.target_field ?? '').trim()
        const source = String(item?.source ?? '').trim()
        if (!targetField && !source) return
        if (!targetField || !source) {
          errors.push(
            `Edge #${rowNo}: chain #${chainNo}, document #${documentNo} link_rules должен содержать target и source.`
          )
          return
        }
        linkRules[targetField] = source
      })

      const normalizedDocument: Record<string, unknown> = {
        document_id: documentId,
        entity_name: entityName,
        document_role: documentRole,
        invoice_mode: invoiceMode,
        field_mapping: sortRecordByKeys(fieldMapping),
        table_parts_mapping: Object.fromEntries(
          Object.entries(tablePartsMapping).sort(([left], [right]) => left.localeCompare(right))
        ),
        link_rules: sortRecordByKeys(linkRules),
      }
      if (linkTo) {
        normalizedDocument.link_to = linkTo
      }
      normalizedDocuments.push(normalizedDocument)
    })

    normalizedChains.push({
      chain_id: chainId,
      documents: normalizedDocuments,
    })
  })

  if (errors.length > 0) {
    return { policy: null, errors }
  }

  const policy: Record<string, unknown> = {
    version: DOCUMENT_POLICY_VERSION,
    chains: normalizedChains,
  }
  const semanticErrors = validateDocumentPolicyObject(policy, rowNo)
  if (semanticErrors.length > 0) {
    return { policy: null, errors: semanticErrors }
  }
  return { policy, errors: [] }
}

const parseDocumentPolicyMetadata = (
  rawPolicyJson: string,
  rowNo: number
): {
  policy: Record<string, unknown> | null
  errors: string[]
} => {
  const errors: string[] = []
  const source = rawPolicyJson.trim()
  if (!source) {
    return { policy: null, errors }
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(source)
  } catch {
    return {
      policy: null,
      errors: [`Edge #${rowNo}: document_policy должен быть валидным JSON.`],
    }
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return {
      policy: null,
      errors: [`Edge #${rowNo}: document_policy должен быть JSON object.`],
    }
  }
  const policy = parsed as Record<string, unknown>
  errors.push(...validateDocumentPolicyObject(policy, rowNo))
  return { policy, errors }
}

const buildEdgeMetadataFromBuilder = (
  fieldsRaw: EdgeMetadataBuilderFieldFormValue[] | undefined,
  rowNo: number
): {
  metadata: Record<string, unknown>
  errors: string[]
} => {
  const fields = Array.isArray(fieldsRaw) ? fieldsRaw : []
  const errors: string[] = []
  const metadata: Record<string, unknown> = {}

  fields.forEach((item, fieldIndex) => {
    const fieldNo = fieldIndex + 1
    const key = String(item?.key ?? '').trim()
    const valueJson = String(item?.value_json ?? '').trim()

    if (!key && !valueJson) return
    if (!key) {
      errors.push(`Edge #${rowNo}: metadata field #${fieldNo} должен содержать key.`)
      return
    }
    if (!valueJson) {
      errors.push(`Edge #${rowNo}: metadata field "${key}" должен содержать JSON value.`)
      return
    }
    if (Object.prototype.hasOwnProperty.call(metadata, key)) {
      errors.push(`Edge #${rowNo}: metadata field "${key}" дублируется.`)
      return
    }
    try {
      metadata[key] = JSON.parse(valueJson)
    } catch {
      errors.push(`Edge #${rowNo}: metadata field "${key}" содержит невалидный JSON value.`)
    }
  })

  return {
    metadata: Object.fromEntries(
      Object.entries(metadata).sort(([left], [right]) => left.localeCompare(right))
    ),
    errors,
  }
}

const buildTopologyPreflight = (
  values: TopologyFormValues,
  selectedTemplateRevision?: PoolTopologyTemplateRevision | null
): {
  payload: {
    effective_from: string
    effective_to?: string | null
    topology_template_revision_id?: string
    slot_assignments?: PoolTopologyTemplateSlotAssignmentInput[]
    edge_selector_overrides?: PoolTopologyTemplateEdgeSelectorOverrideInput[]
    nodes: PoolTopologySnapshotNodeInput[]
    edges: PoolTopologySnapshotEdgeInput[]
  } | null
  errors: string[]
} => {
  const errors: string[] = []
  const effectiveFrom = String(values.effective_from || '').trim()
  const effectiveToRaw = String(values.effective_to || '').trim()
  const authoringMode = String(values.authoring_mode || 'manual').trim().toLowerCase() === 'template'
    ? 'template'
    : 'manual'
  if (!effectiveFrom) {
    errors.push('effective_from обязателен.')
  }
  if (effectiveToRaw && effectiveFrom && effectiveToRaw < effectiveFrom) {
    errors.push('effective_to не может быть раньше effective_from.')
  }

  if (authoringMode === 'template') {
    const topologyTemplateRevisionId = String(values.topology_template_revision_id || '').trim()
    if (!topologyTemplateRevisionId) {
      errors.push('Выберите topology template revision.')
    }
    if (!selectedTemplateRevision) {
      errors.push('Не удалось загрузить выбранную topology template revision.')
    }
    const slotAssignmentsSource = Array.isArray(values.slot_assignments) ? values.slot_assignments : []
    const slotAssignments = slotAssignmentsSource
      .map((assignment) => ({
        slot_key: String(assignment.slot_key || '').trim(),
        organization_id: String(assignment.organization_id || '').trim(),
      }))
      .filter((assignment) => assignment.slot_key)
    if (selectedTemplateRevision) {
      selectedTemplateRevision.nodes.forEach((node, index) => {
        const slotKey = String(node.slot_key || '').trim()
        const assignment = slotAssignments.find((item) => item.slot_key === slotKey)
        if (!assignment?.organization_id) {
          errors.push(`Назначьте организацию для slot ${slotKey || `#${index + 1}`}.`)
        }
      })
    }
    const edgeSelectorOverrides = (Array.isArray(values.edge_selector_overrides) ? values.edge_selector_overrides : [])
      .map((override) => ({
        parent_slot_key: String(override.parent_slot_key || '').trim(),
        child_slot_key: String(override.child_slot_key || '').trim(),
        document_policy_key: String(override.document_policy_key || '').trim(),
      }))
      .filter((override) => (
        override.parent_slot_key
        && override.child_slot_key
        && override.document_policy_key
      ))

    if (errors.length > 0 || !effectiveFrom || !topologyTemplateRevisionId) {
      return { payload: null, errors }
    }

    return {
      payload: {
        effective_from: effectiveFrom,
        effective_to: effectiveToRaw || null,
        topology_template_revision_id: topologyTemplateRevisionId,
        slot_assignments: slotAssignments,
        edge_selector_overrides: edgeSelectorOverrides,
        nodes: [],
        edges: [],
      },
      errors,
    }
  }

  const nodesSource = Array.isArray(values.nodes) ? values.nodes : []
  const nodes: PoolTopologySnapshotNodeInput[] = []
  nodesSource.forEach((item, index) => {
    const organizationId = String(item.organization_id || '').trim()
    if (!organizationId) {
      return
    }
    const metadataParseResult = parseTopologyMetadata(item.metadata_json, `Node #${index + 1}`)
    errors.push(...metadataParseResult.errors)
    if (metadataParseResult.errors.length > 0) {
      return
    }
    nodes.push({
      organization_id: organizationId,
      is_root: Boolean(item.is_root),
      metadata: metadataParseResult.metadata,
    })
  })
  if (nodes.length === 0) {
    errors.push('Добавьте хотя бы один topology node.')
  }
  const rootCount = nodes.filter((item) => item.is_root).length
  if (nodes.length > 0 && rootCount === 0) {
    errors.push('Отметьте хотя бы один root node.')
  }
  const nodeIds = nodes.map((item) => item.organization_id)
  const duplicates = nodeIds.filter((item, index) => nodeIds.indexOf(item) !== index)
  if (duplicates.length > 0) {
    errors.push(`Найдены дубликаты organization_id в nodes: ${Array.from(new Set(duplicates)).join(', ')}`)
  }
  const allowedNodeIds = new Set(nodeIds)

  const edgesSource = Array.isArray(values.edges) ? values.edges : []
  const edges: PoolTopologySnapshotEdgeInput[] = []
  edgesSource.forEach((edge, index) => {
    const rowNo = index + 1
    const parentId = String(edge.parent_organization_id || '').trim()
    const childId = String(edge.child_organization_id || '').trim()
    if (!parentId && !childId) {
      return
    }
    if (!parentId || !childId) {
      errors.push(`Edge #${rowNo}: parent и child обязательны.`)
      return
    }
    if (parentId === childId) {
      errors.push(`Edge #${rowNo}: parent и child не могут совпадать.`)
      return
    }
    if (!allowedNodeIds.has(parentId) || !allowedNodeIds.has(childId)) {
      errors.push(`Edge #${rowNo}: parent/child должны ссылаться на узлы из nodes.`)
      return
    }
    const minAmount = formatOptionalDecimal(edge.min_amount)
    const maxAmount = formatOptionalDecimal(edge.max_amount)
    if (minAmount && maxAmount && Number(maxAmount) < Number(minAmount)) {
      errors.push(`Edge #${rowNo}: max_amount должен быть >= min_amount.`)
      return
    }
    const policyMode = String(edge.document_policy_mode ?? 'raw').trim().toLowerCase() === 'builder'
      ? 'builder'
      : 'raw'
    const policyResult = policyMode === 'builder'
      ? buildDocumentPolicyFromBuilder(edge.document_policy_builder, rowNo)
      : parseDocumentPolicyMetadata(
        String(edge.document_policy_json ?? ''),
        rowNo
      )
    errors.push(...policyResult.errors)
    if (policyResult.errors.length > 0) {
      return
    }
    if (policyResult.policy) {
      errors.push(
        `Edge #${rowNo}: legacy document_policy больше не поддерживается в Topology Editor. Используйте /decisions и workflow bindings remediation flow.`
      )
      return
    }
    const edgeMetadataMode = String(edge.edge_metadata_mode ?? 'raw').trim().toLowerCase() === 'builder'
      ? 'builder'
      : 'raw'
    const metadataParseResult = edgeMetadataMode === 'builder'
      ? buildEdgeMetadataFromBuilder(edge.edge_metadata_builder, rowNo)
      : parseTopologyMetadata(edge.metadata_json, `Edge #${rowNo}`)
    errors.push(...metadataParseResult.errors)
    if (metadataParseResult.errors.length > 0) {
      return
    }
    const metadata: Record<string, unknown> = { ...metadataParseResult.metadata }
    delete metadata.document_policy
    delete metadata.document_policy_key
    const documentPolicyKey = String(edge.document_policy_key || '').trim()
    if (documentPolicyKey) {
      metadata.document_policy_key = documentPolicyKey
    }
    edges.push({
      parent_organization_id: parentId,
      child_organization_id: childId,
      weight: edge.weight == null ? '1' : String(edge.weight),
      min_amount: minAmount,
      max_amount: maxAmount,
      metadata,
    })
  })

  if (errors.length > 0 || !effectiveFrom) {
    return { payload: null, errors }
  }

  return {
    payload: {
      effective_from: effectiveFrom,
      effective_to: effectiveToRaw || null,
      nodes,
      edges,
    },
    errors,
  }
}

export function PoolCatalogPage() {
  const { message } = AntApp.useApp()
  const { isStaff } = useAuthz()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const api = useMemo(() => getV2(), [])
  const activeTenantId = localStorage.getItem('active_tenant_id')
  const hasTenantContext = Boolean(activeTenantId)
  const mutatingDisabled = isStaff && !hasTenantContext
  const databasesQuery = useDatabases({ filters: { limit: 500, offset: 0 } })
  const requestedPoolId = useMemo(() => normalizeRouteParam(searchParams.get('pool_id')), [searchParams])
  const requestedWorkspaceTab = useMemo(
    () => parseWorkspaceTab(searchParams.get('tab')),
    [searchParams],
  )
  const graphDateFromUrl = useMemo(() => normalizeGraphDateParam(searchParams.get('date')), [searchParams])

  const [organizationForm] = Form.useForm<OrganizationFormValues>()
  const [poolForm] = Form.useForm<PoolFormValues>()
  const [poolBindingsForm] = Form.useForm<PoolBindingsFormValues>()
  const [topologyForm] = Form.useForm<TopologyFormValues>()
  const watchedEdges = Form.useWatch('edges', topologyForm)
  const watchedTopologyAuthoringMode = Form.useWatch('authoring_mode', topologyForm)
  const watchedTopologyTemplateRevisionId = Form.useWatch('topology_template_revision_id', topologyForm)
  const watchedTopologyTemplateEdgeSelectorOverrides = Form.useWatch('edge_selector_overrides', topologyForm)

  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null)
  const [organizationDetail, setOrganizationDetail] = useState<{
    organization: Organization
    pool_bindings: OrganizationPoolBinding[]
  } | null>(null)
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null | undefined>(() => requestedPoolId ?? undefined)
  const [graphDate, setGraphDate] = useState<string>(graphDateFromUrl ?? '')
  const [graph, setGraph] = useState<PoolGraph | null>(null)
  const [topologySnapshots, setTopologySnapshots] = useState<PoolTopologySnapshotPeriod[]>([])
  const [topologyTemplates, setTopologyTemplates] = useState<PoolTopologyTemplate[]>([])
  const [loadingOrganizations, setLoadingOrganizations] = useState(false)
  const [loadingOrganizationDetail, setLoadingOrganizationDetail] = useState(false)
  const [loadingPools, setLoadingPools] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [loadingTopologySnapshots, setLoadingTopologySnapshots] = useState(false)
  const [loadingTopologyTemplates, setLoadingTopologyTemplates] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | OrganizationStatus>('all')
  const [databaseLinkFilter, setDatabaseLinkFilter] = useState<'all' | 'linked' | 'unlinked'>('all')
  const [error, setError] = useState<string | null>(null)
  const [isOrganizationDrawerOpen, setIsOrganizationDrawerOpen] = useState(false)
  const [organizationDrawerMode, setOrganizationDrawerMode] = useState<'create' | 'edit'>('create')
  const [editingOrganization, setEditingOrganization] = useState<Organization | null>(null)
  const [organizationSubmitError, setOrganizationSubmitError] = useState<string | null>(null)
  const [isOrganizationSaving, setIsOrganizationSaving] = useState(false)
  const [isPoolDrawerOpen, setIsPoolDrawerOpen] = useState(false)
  const [poolDrawerMode, setPoolDrawerMode] = useState<'create' | 'edit'>('create')
  const [poolSubmitError, setPoolSubmitError] = useState<string | null>(null)
  const [isPoolSaving, setIsPoolSaving] = useState(false)
  const [isPoolBindingsLoading, setIsPoolBindingsLoading] = useState(false)
  const [isPoolBindingsSaving, setIsPoolBindingsSaving] = useState(false)
  const [poolBindingsLoadError, setPoolBindingsLoadError] = useState<string | null>(null)
  const [poolBindingsSubmitError, setPoolBindingsSubmitError] = useState<string | null>(null)
  const [loadedPoolBindings, setLoadedPoolBindings] = useState<PoolWorkflowBinding[]>([])
  const [loadedPoolBindingsCollectionEtag, setLoadedPoolBindingsCollectionEtag] = useState('')
  const [poolBindingsBackendBlockingRemediation, setPoolBindingsBackendBlockingRemediation] = useState<PoolWorkflowBindingBlockingRemediation | null>(null)
  const [topologyPreflightErrors, setTopologyPreflightErrors] = useState<string[]>([])
  const [topologySubmitError, setTopologySubmitError] = useState<string | null>(null)
  const [topologyTemplatesLoadError, setTopologyTemplatesLoadError] = useState<string | null>(null)
  const [isTopologySaving, setIsTopologySaving] = useState(false)
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)
  const [syncInput, setSyncInput] = useState('{\n  "rows": []\n}')
  const [syncErrors, setSyncErrors] = useState<string[]>([])
  const [syncResult, setSyncResult] = useState<{ stats: { created: number; updated: number; skipped: number }; total_rows: number } | null>(null)
  const [isSyncSubmitting, setIsSyncSubmitting] = useState(false)
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<PoolCatalogWorkspaceTab>(requestedWorkspaceTab)
  const [isBindingsWorkspaceOpen, setIsBindingsWorkspaceOpen] = useState(requestedWorkspaceTab === 'bindings')
  const [bindingProfileDetailsById, setBindingProfileDetailsById] = useState<Record<string, BindingProfileDetail>>({})
  const [bindingProfileDetailFallbackIds, setBindingProfileDetailFallbackIds] = useState<Record<string, true>>({})
  const [bindingProfileDetailsLoading, setBindingProfileDetailsLoading] = useState(false)
  const [bindingProfileDetailsError, setBindingProfileDetailsError] = useState<string | null>(null)
  const [topologyCoverageBindingId, setTopologyCoverageBindingId] = useState<string | undefined>(undefined)
  const [metadataCatalogByDatabase, setMetadataCatalogByDatabase] = useState<Record<string, PoolODataMetadataCatalogResponse>>({})
  const [metadataCatalogLoadingByDatabase, setMetadataCatalogLoadingByDatabase] = useState<Record<string, boolean>>({})
  const [metadataCatalogErrorByDatabase, setMetadataCatalogErrorByDatabase] = useState<Record<string, string>>({})
  const [masterDataParties, setMasterDataParties] = useState<PoolMasterParty[]>([])
  const [masterDataItems, setMasterDataItems] = useState<PoolMasterItem[]>([])
  const [masterDataContracts, setMasterDataContracts] = useState<PoolMasterContract[]>([])
  const [masterDataTaxProfiles, setMasterDataTaxProfiles] = useState<PoolMasterTaxProfile[]>([])
  const [loadingMasterDataTokenCatalog, setLoadingMasterDataTokenCatalog] = useState(false)
  const [masterDataTokenCatalogError, setMasterDataTokenCatalogError] = useState<string | null>(null)
  const watchedWorkflowBindings = Form.useWatch('workflow_bindings', poolBindingsForm)

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === selectedOrganizationId) ?? null,
    [organizations, selectedOrganizationId]
  )
  const selectedPool = useMemo(
    () => pools.find((item) => item.id === selectedPoolId) ?? null,
    [pools, selectedPoolId]
  )
  const bindingProfilesQuery = useBindingProfiles({ enabled: activeWorkspaceTab === 'bindings' })
  const organizationById = useMemo(() => (
    Object.fromEntries(organizations.map((item) => [item.id, item]))
  ), [organizations])
  const selectedPoolTopologyInstantiation = useMemo(
    () => readTopologyTemplateInstantiation(selectedPool),
    [selectedPool]
  )
  const isTemplateTopologyAuthoring = String(watchedTopologyAuthoringMode || 'manual').trim().toLowerCase() === 'template'
  const topologyTemplateRevisionOptions = useMemo(() => (
    topologyTemplates.flatMap((template) => (
      template.revisions.map((revision) => ({
        value: revision.topology_template_revision_id,
        label: `${template.name} · r${revision.revision_number}`,
      }))
    ))
  ), [topologyTemplates])
  const selectedTopologyTemplateRevision = useMemo(() => {
    const revisionId = String(watchedTopologyTemplateRevisionId || '').trim()
    if (!revisionId) {
      return null
    }
    for (const template of topologyTemplates) {
      const revision = template.revisions.find((item) => item.topology_template_revision_id === revisionId)
      if (revision) {
        return revision
      }
    }
    return null
  }, [topologyTemplates, watchedTopologyTemplateRevisionId])
  const selectedTopologyTemplate = useMemo(() => {
    if (!selectedTopologyTemplateRevision) {
      return null
    }
    return topologyTemplates.find(
      (template) => template.topology_template_id === selectedTopologyTemplateRevision.topology_template_id
    ) ?? null
  }, [selectedTopologyTemplateRevision, topologyTemplates])
  const topologyCoverageBindingOptions = useMemo(() => (
    loadedPoolBindings
      .filter((binding) => binding.status === 'active')
      .map((binding) => ({
        value: binding.binding_id,
        label: describePoolWorkflowBindingCoverage(binding),
      }))
      .sort((left, right) => left.label.localeCompare(right.label))
  ), [loadedPoolBindings])
  const topologyCoverageContext = useMemo(
    () => resolveTopologyCoverageContext(loadedPoolBindings, topologyCoverageBindingId),
    [loadedPoolBindings, topologyCoverageBindingId]
  )
  const topologySlotOptions = useMemo(
    () => buildTopologySlotOptions(topologyCoverageContext.slotRefs),
    [topologyCoverageContext]
  )
  useEffect(() => {
    setActiveWorkspaceTab((previous) => (previous === requestedWorkspaceTab ? previous : requestedWorkspaceTab))
  }, [requestedWorkspaceTab])

  useEffect(() => {
    if (!requestedPoolId || !pools.some((item) => item.id === requestedPoolId)) {
      return
    }
    setSelectedPoolId((previous) => (previous === requestedPoolId ? previous : requestedPoolId))
  }, [pools, requestedPoolId])

  useEffect(() => {
    const nextGraphDate = graphDateFromUrl ?? ''
    setGraphDate((current) => (current === nextGraphDate ? current : nextGraphDate))
  }, [graphDateFromUrl])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)

    if (selectedPoolId !== undefined) {
      if (selectedPoolId) {
        next.set('pool_id', selectedPoolId)
      } else {
        next.delete('pool_id')
      }
    }

    next.set('tab', activeWorkspaceTab)

    if (graphDate.trim()) {
      next.set('date', graphDate.trim())
    } else {
      next.delete('date')
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined,
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [activeWorkspaceTab, graphDate, searchParams, selectedPoolId, setSearchParams])

  useEffect(() => {
    if (requestedWorkspaceTab === 'bindings') {
      setIsBindingsWorkspaceOpen(true)
      return
    }
    setIsBindingsWorkspaceOpen(false)
  }, [requestedWorkspaceTab])

  const handleSelectWorkspaceTab = useCallback((nextTab: PoolCatalogWorkspaceTab) => {
    routeUpdateModeRef.current = 'push'
    if (nextTab !== 'bindings') {
      setIsBindingsWorkspaceOpen(false)
    }
    setActiveWorkspaceTab((previous) => (previous === nextTab ? previous : nextTab))
  }, [])

  const handleSelectPool = useCallback((nextPoolId: string | null | undefined) => {
    const normalizedPoolId = typeof nextPoolId === 'string' && nextPoolId.trim()
      ? nextPoolId
      : null
    routeUpdateModeRef.current = 'push'
    setSelectedPoolId((previous) => (previous === normalizedPoolId ? previous : normalizedPoolId))
  }, [])

  const handleGraphDateChange = useCallback((nextGraphDate: string) => {
    const normalizedGraphDate = parseGraphDateInput(nextGraphDate)
    routeUpdateModeRef.current = 'push'
    setGraphDate((current) => (current === normalizedGraphDate ? current : normalizedGraphDate))
  }, [])

  const handleOpenBindingsWorkspace = useCallback(() => {
    if (!selectedPool) return
    routeUpdateModeRef.current = 'push'
    setActiveWorkspaceTab('bindings')
    setIsBindingsWorkspaceOpen(true)
  }, [selectedPool])

  useEffect(() => {
    if (activeWorkspaceTab !== 'bindings' || bindingProfilesQuery.isLoading || bindingProfilesQuery.isError) {
      return
    }

    const profiles = bindingProfilesQuery.data?.binding_profiles ?? []
    const profileIds = new Set(profiles.map((profile) => profile.binding_profile_id))
    setBindingProfileDetailFallbackIds((previous) => {
      const nextEntries = Object.entries(previous).filter(([bindingProfileId]) => profileIds.has(bindingProfileId))
      if (
        nextEntries.length === Object.keys(previous).length
        && nextEntries.every(([bindingProfileId, value]) => previous[bindingProfileId] === value)
      ) {
        return previous
      }
      return Object.fromEntries(nextEntries)
    })
    setBindingProfileDetailsById((previous) => {
      const nextEntries = Object.entries(previous).filter(([bindingProfileId]) => profileIds.has(bindingProfileId))
      if (
        nextEntries.length === Object.keys(previous).length
        && nextEntries.every(([bindingProfileId, value]) => previous[bindingProfileId] === value)
      ) {
        return previous
      }
      return Object.fromEntries(nextEntries)
    })
    if (bindingProfileDetailsError && Object.keys(bindingProfileDetailFallbackIds).length === 0) {
      setBindingProfileDetailsError(null)
    }
  }, [
    activeWorkspaceTab,
    bindingProfileDetailFallbackIds,
    bindingProfileDetailsError,
    bindingProfilesQuery.data?.binding_profiles,
    bindingProfilesQuery.isError,
    bindingProfilesQuery.isLoading,
  ])

  const ensureBindingProfileDetailsLoaded = useCallback(async () => {
    if (bindingProfilesQuery.isLoading || bindingProfilesQuery.isError || bindingProfileDetailsLoading) {
      return
    }

    const profiles = bindingProfilesQuery.data?.binding_profiles ?? []
    const missingProfileIds = profiles
      .map((profile) => profile.binding_profile_id)
      .filter((bindingProfileId) => (
        !bindingProfileDetailsById[bindingProfileId]
        && !bindingProfileDetailFallbackIds[bindingProfileId]
      ))
    if (!missingProfileIds.length) {
      if (bindingProfileDetailsError && Object.keys(bindingProfileDetailFallbackIds).length === 0) {
        setBindingProfileDetailsError(null)
      }
      return
    }

    setBindingProfileDetailsLoading(true)
    try {
      const results = await Promise.all(
        missingProfileIds.map(async (bindingProfileId) => {
          try {
            const response = await getBindingProfileDetail(bindingProfileId)
            return {
              bindingProfileId,
              bindingProfile: isValidBindingProfileDetailResponse(bindingProfileId, response.binding_profile)
                ? response.binding_profile
                : null,
            }
          } catch {
            return {
              bindingProfileId,
              bindingProfile: null,
            }
          }
        }),
      )
      const validDetails = results
        .map((item) => item.bindingProfile)
        .filter((detail): detail is BindingProfileDetail => Boolean(detail))
      const fallbackProfileIds = results
        .filter((item) => !item.bindingProfile)
        .map((item) => item.bindingProfileId)
      setBindingProfileDetailsById((previous) => ({
        ...previous,
        ...Object.fromEntries(validDetails.map((detail) => [detail.binding_profile_id, detail])),
      }))
      if (fallbackProfileIds.length > 0) {
        setBindingProfileDetailFallbackIds((previous) => ({
          ...previous,
          ...Object.fromEntries(fallbackProfileIds.map((bindingProfileId) => [bindingProfileId, true])),
        }))
      }
      setBindingProfileDetailsError(
        validDetails.length === results.length
          ? null
          : 'Некоторые binding profiles вернули неконсистентную историю revisions; используется latest revision из summary catalog.',
      )
    } finally {
      setBindingProfileDetailsLoading(false)
    }
  }, [
    bindingProfileDetailFallbackIds,
    bindingProfileDetailsById,
    bindingProfileDetailsError,
    bindingProfileDetailsLoading,
    bindingProfilesQuery.data?.binding_profiles,
    bindingProfilesQuery.isError,
    bindingProfilesQuery.isLoading,
  ])

  const topologyEdgeSelectors = useMemo<TopologyEdgeSelector[]>(() => {
    if (!graph) {
      return []
    }
    const nodeByVersionId = new Map(
      graph.nodes.map((node) => [node.node_version_id, node])
    )
    return graph.edges.map((edge, index) => {
      const metadata = normalizeMetadataObject(edge.metadata)
      const slotKey = String(metadata.document_policy_key || '').trim()
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
  }, [graph])
  const draftTopologyEdgeSelectors = useMemo(
    () => (
      isTemplateTopologyAuthoring
        ? buildTemplateDraftTopologyEdgeSelectors(
          selectedTopologyTemplateRevision,
          watchedTopologyTemplateEdgeSelectorOverrides
        )
        : buildDraftTopologyEdgeSelectors(watchedEdges, organizationById)
    ),
    [
      isTemplateTopologyAuthoring,
      organizationById,
      selectedTopologyTemplateRevision,
      watchedEdges,
      watchedTopologyTemplateEdgeSelectorOverrides,
    ]
  )
  const topologyCoverageSummary = useMemo(
    () => summarizeTopologySlotCoverage(draftTopologyEdgeSelectors, topologyCoverageContext),
    [draftTopologyEdgeSelectors, topologyCoverageContext]
  )
  const legacyTopologyBlockingRemediation = useMemo(
    () => buildLegacyTopologyBlockingRemediation({ graph, pool: selectedPool }),
    [graph, selectedPool]
  )
  const topologyCoverageBlockingRemediation = useMemo(() => {
    if (draftTopologyEdgeSelectors.length === 0) {
      return null
    }
    if (topologyCoverageContext.status !== 'resolved') {
      return buildCoverageBlockingRemediation({
        code: 'TOPOLOGY_SLOT_COVERAGE_INCOMPLETE',
        title: 'Topology remediation required',
        summary: topologyCoverageSummary,
        unresolvedDetail: `${topologyCoverageContext.detail} Resolve coverage before saving topology.`,
      })
    }
    return buildCoverageBlockingRemediation({
      code: 'TOPOLOGY_SLOT_COVERAGE_INCOMPLETE',
      title: 'Topology remediation required',
      summary: topologyCoverageSummary,
      unresolvedDetail: 'Resolve publication slot coverage for all topology edges before saving this snapshot.',
    })
  }, [draftTopologyEdgeSelectors.length, topologyCoverageContext, topologyCoverageSummary])
  const topologyBlockingRemediations = useMemo(
    () => [
      legacyTopologyBlockingRemediation,
      topologyCoverageBlockingRemediation,
    ].filter((item): item is PoolWorkflowBindingBlockingRemediation => Boolean(item)),
    [legacyTopologyBlockingRemediation, topologyCoverageBlockingRemediation]
  )
  const poolBindingsCoverageBlockingRemediation = useMemo(() => {
    if (topologyEdgeSelectors.length === 0) {
      return null
    }
    const draftBindings = (Array.isArray(watchedWorkflowBindings) ? watchedWorkflowBindings : [])
      .filter((binding) => String(binding?.status ?? 'draft').trim() === 'active')
    if (draftBindings.length === 0) {
      return null
    }
    for (let index = 0; index < draftBindings.length; index += 1) {
      const binding = draftBindings[index]
      const bindingLabel = getWorkflowBindingCardTitle(binding, index + 1)
      const coverageSummary = summarizeTopologySlotCoverage(
        topologyEdgeSelectors,
        buildTopologyCoverageContext({
          bindingLabel,
          detail: `Coverage is evaluated against binding draft ${bindingLabel}.`,
          slotRefs: buildBindingSlotRefsFromForm(binding),
          source: 'selected',
        })
      )
      const remediation = buildCoverageBlockingRemediation({
        code: 'POOL_BINDING_SLOT_COVERAGE_INCOMPLETE',
        title: 'Binding remediation required',
        summary: coverageSummary,
        unresolvedDetail: `${bindingLabel} leaves topology slot coverage incomplete. Add or fix named slots before saving bindings.`,
      })
      if (remediation) {
        return remediation
      }
    }
    return null
  }, [topologyEdgeSelectors, watchedWorkflowBindings])
  const poolBindingsBlockingRemediations = useMemo(
    () => [
      poolBindingsBackendBlockingRemediation,
      legacyTopologyBlockingRemediation,
      poolBindingsCoverageBlockingRemediation,
    ].filter((item): item is PoolWorkflowBindingBlockingRemediation => Boolean(item)),
    [
      legacyTopologyBlockingRemediation,
      poolBindingsBackendBlockingRemediation,
      poolBindingsCoverageBlockingRemediation,
    ]
  )
  const isPoolBindingsSaveBlocked = poolBindingsBlockingRemediations.length > 0
  const isTopologySaveBlocked = topologyBlockingRemediations.length > 0

  const databaseOptions = useMemo(() => {
    const databases = databasesQuery.data?.databases ?? []
    return databases
      .map((database) => ({ label: database.name || database.id || 'unknown', value: database.id || '' }))
      .filter((item) => item.value)
      .sort((left, right) => left.label.localeCompare(right.label))
  }, [databasesQuery.data?.databases])

  const organizationOptions = useMemo(
    () => organizations
      .map((item) => ({
        value: item.id,
        label: `${item.name} (${item.inn})`,
      }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    [organizations]
  )

  const masterDataPartyOptions = useMemo(
    () => masterDataParties
      .map((item) => ({
        value: item.canonical_id,
        label: `${item.canonical_id} - ${item.name}`,
      }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    [masterDataParties]
  )
  const masterDataCounterpartyOptions = useMemo(
    () => masterDataParties
      .filter((item) => item.is_counterparty)
      .map((item) => ({
        value: item.canonical_id,
        label: `${item.canonical_id} - ${item.name}`,
      }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    [masterDataParties]
  )
  const masterDataItemOptions = useMemo(
    () => masterDataItems
      .map((item) => ({
        value: item.canonical_id,
        label: `${item.canonical_id} - ${item.name}`,
      }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    [masterDataItems]
  )
  const masterDataContractOptions = useMemo(
    () => masterDataContracts
      .map((item) => ({
        value: item.canonical_id,
        label: `${item.canonical_id} - ${item.name}`,
      }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    [masterDataContracts]
  )
  const masterDataContractByCanonicalId = useMemo(() => (
    Object.fromEntries(masterDataContracts.map((item) => [item.canonical_id, item]))
  ), [masterDataContracts])
  const masterDataTaxProfileOptions = useMemo(
    () => masterDataTaxProfiles
      .map((item) => ({
        value: item.canonical_id,
        label: item.canonical_id,
      }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    [masterDataTaxProfiles]
  )

  const flow = useMemo(() => buildFlowLayout(graph), [graph])

  const loadOrganizations = useCallback(async (options?: { force?: boolean }) => {
    setLoadingOrganizations(true)
    setError(null)
    try {
      const filters = {
        status: statusFilter === 'all' ? undefined : statusFilter,
        query: query.trim() || undefined,
        databaseLinked: databaseLinkFilter === 'all' ? undefined : databaseLinkFilter === 'linked',
        limit: 300,
      }
      const data = await queryClient.fetchQuery(withQueryPolicy('interactive', {
        queryKey: queryKeys.poolCatalog.organizations(filters),
        queryFn: () => listOrganizations(filters),
        ...(options?.force ? { staleTime: 0 } : {}),
      }))
      setOrganizations(data)
      setSelectedOrganizationId((previous) => {
        if (previous && data.some((item) => item.id === previous)) {
          return previous
        }
        return data[0]?.id ?? null
      })
    } catch {
      setError('Не удалось загрузить каталог организаций.')
    } finally {
      setLoadingOrganizations(false)
    }
  }, [databaseLinkFilter, query, queryClient, statusFilter])

  const loadOrganizationDetailById = useCallback(async (
    organizationId: string,
    options?: { force?: boolean },
  ) => {
    const normalizedOrganizationId = String(organizationId || '').trim()
    if (!normalizedOrganizationId) {
      setOrganizationDetail(null)
      return
    }
    setLoadingOrganizationDetail(true)
    try {
      const detail = await queryClient.fetchQuery(withQueryPolicy('interactive', {
        queryKey: queryKeys.poolCatalog.organizationDetail(normalizedOrganizationId),
        queryFn: () => getOrganization(normalizedOrganizationId),
        ...(options?.force ? { staleTime: 0 } : {}),
      }))
      setOrganizationDetail(detail)
    } catch {
      setError('Не удалось загрузить детали организации.')
    } finally {
      setLoadingOrganizationDetail(false)
    }
  }, [queryClient])

  const loadOrganizationDetail = useCallback(async (options?: { force?: boolean }) => {
    if (!selectedOrganizationId) {
      setOrganizationDetail(null)
      return
    }
    await loadOrganizationDetailById(selectedOrganizationId, options)
  }, [loadOrganizationDetailById, selectedOrganizationId])

  const loadPools = useCallback(async (options?: { force?: boolean }) => {
    setLoadingPools(true)
    try {
      const data = await queryClient.fetchQuery(withQueryPolicy('interactive', {
        queryKey: queryKeys.poolCatalog.pools(),
        queryFn: () => listOrganizationPools(),
        ...(options?.force ? { staleTime: 0 } : {}),
      }))
      setPools(data)
      setSelectedPoolId((previous) => {
        if (previous && data.some((item) => item.id === previous)) {
          return previous
        }
        return data[0]?.id ?? null
      })
    } catch {
      setError('Не удалось загрузить каталог пулов.')
    } finally {
      setLoadingPools(false)
    }
  }, [queryClient])

  const loadGraph = useCallback(async (options?: { force?: boolean }) => {
    const resolvedGraphDate = graphDate.trim()
    if (!selectedPoolId || !resolvedGraphDate) {
      setGraph(null)
      return
    }
    setLoadingGraph(true)
    try {
      const payload = await queryClient.fetchQuery(withQueryPolicy('interactive', {
        queryKey: queryKeys.poolCatalog.graph(selectedPoolId, resolvedGraphDate),
        queryFn: () => getPoolGraph(selectedPoolId, resolvedGraphDate),
        ...(options?.force ? { staleTime: 0 } : {}),
      }))
      setGraph(payload)
    } catch {
      setError('Не удалось загрузить граф пула.')
    } finally {
      setLoadingGraph(false)
    }
  }, [graphDate, queryClient, selectedPoolId])

  const loadTopologySnapshots = useCallback(async (options?: { force?: boolean }) => {
    if (!selectedPoolId) {
      setTopologySnapshots([])
      return
    }
    setLoadingTopologySnapshots(true)
    try {
      const payload = await queryClient.fetchQuery(withQueryPolicy('interactive', {
        queryKey: queryKeys.poolCatalog.topologySnapshots(selectedPoolId),
        queryFn: () => listPoolTopologySnapshots(selectedPoolId),
        ...(options?.force ? { staleTime: 0 } : {}),
      }))
      const snapshots = Array.isArray(payload.snapshots) ? payload.snapshots : []
      setTopologySnapshots(snapshots)

      const activeSnapshot = snapshots.find((item) => !String(item.effective_to || '').trim())
      const defaultSnapshot = activeSnapshot ?? snapshots[0]
      if (defaultSnapshot) {
        setGraphDate((previous) => {
          if (previous && snapshots.some((item) => item.effective_from === previous)) {
            return previous
          }
          return defaultSnapshot.effective_from
        })
      }
    } catch {
      setTopologySnapshots([])
    } finally {
      setLoadingTopologySnapshots(false)
    }
  }, [queryClient, selectedPoolId])

  const loadTopologyTemplates = useCallback(async (options?: { force?: boolean }) => {
    setLoadingTopologyTemplates(true)
    try {
      const data = await queryClient.fetchQuery(withQueryPolicy('interactive', {
        queryKey: queryKeys.poolCatalog.topologyTemplates(),
        queryFn: () => listPoolTopologyTemplates(),
        ...(options?.force ? { staleTime: 0 } : {}),
      }))
      setTopologyTemplates(data)
      setTopologyTemplatesLoadError(null)
    } catch {
      setTopologyTemplates([])
      setTopologyTemplatesLoadError('Не удалось загрузить topology templates catalog.')
    } finally {
      setLoadingTopologyTemplates(false)
    }
  }, [queryClient])

  const loadMetadataCatalog = useCallback(async (
    databaseId: string,
    forceRefresh: boolean
  ) => {
    const normalizedDatabaseId = String(databaseId || '').trim()
    if (!normalizedDatabaseId) return
    setMetadataCatalogLoadingByDatabase((previous) => ({
      ...previous,
      [normalizedDatabaseId]: true,
    }))
    try {
      const payload = forceRefresh
        ? await api.postPoolsOdataMetadataCatalogRefresh(
          { database_id: normalizedDatabaseId },
          { skipGlobalError: true }
        )
        : await api.getPoolsOdataMetadataCatalogGet(
          { database_id: normalizedDatabaseId },
          { skipGlobalError: true }
        )
      setMetadataCatalogByDatabase((previous) => ({
        ...previous,
        [normalizedDatabaseId]: payload,
      }))
      setMetadataCatalogErrorByDatabase((previous) => {
        const next = { ...previous }
        delete next[normalizedDatabaseId]
        return next
      })
    } catch (err) {
      const resolved = resolveApiError(
        err,
        'Не удалось загрузить metadata catalog.',
        { includeProblemDetail: true, includeProblemItems: true }
      )
      setMetadataCatalogErrorByDatabase((previous) => ({
        ...previous,
        [normalizedDatabaseId]: resolved.message,
      }))
    } finally {
      setMetadataCatalogLoadingByDatabase((previous) => ({
        ...previous,
        [normalizedDatabaseId]: false,
      }))
    }
  }, [api])

  const loadMasterDataTokenCatalog = useCallback(async () => {
    if (!hasTenantContext) {
      setMasterDataParties([])
      setMasterDataItems([])
      setMasterDataContracts([])
      setMasterDataTaxProfiles([])
      return
    }
    setLoadingMasterDataTokenCatalog(true)
    setMasterDataTokenCatalogError(null)
    try {
      const [
        partiesPayload,
        itemsPayload,
        contractsPayload,
        taxProfilesPayload,
      ] = await Promise.all([
        listMasterDataParties({ limit: MASTER_DATA_TOKEN_CATALOG_LIMIT, offset: 0 }),
        listMasterDataItems({ limit: MASTER_DATA_TOKEN_CATALOG_LIMIT, offset: 0 }),
        listMasterDataContracts({ limit: MASTER_DATA_TOKEN_CATALOG_LIMIT, offset: 0 }),
        listMasterDataTaxProfiles({ limit: MASTER_DATA_TOKEN_CATALOG_LIMIT, offset: 0 }),
      ])
      setMasterDataParties(Array.isArray(partiesPayload.parties) ? partiesPayload.parties : [])
      setMasterDataItems(Array.isArray(itemsPayload.items) ? itemsPayload.items : [])
      setMasterDataContracts(Array.isArray(contractsPayload.contracts) ? contractsPayload.contracts : [])
      setMasterDataTaxProfiles(
        Array.isArray(taxProfilesPayload.tax_profiles) ? taxProfilesPayload.tax_profiles : []
      )
    } catch {
      setMasterDataTokenCatalogError('Не удалось загрузить master-data каталог для token picker.')
    } finally {
      setLoadingMasterDataTokenCatalog(false)
    }
  }, [hasTenantContext])

  const switchEdgeMetadataMode = useCallback((edgeIndex: number, nextMode: 'builder' | 'raw') => {
    const currentMode = (
      String(topologyForm.getFieldValue(['edges', edgeIndex, 'edge_metadata_mode']) || 'raw')
        .trim()
        .toLowerCase() === 'builder'
        ? 'builder'
        : 'raw'
    )
    if (nextMode === currentMode) return

    if (nextMode === 'builder') {
      const parsed = parseTopologyMetadata(
        topologyForm.getFieldValue(['edges', edgeIndex, 'metadata_json']),
        `Edge #${edgeIndex + 1}`
      )
      if (parsed.errors.length > 0) {
        message.error(parsed.errors[0] || `Edge #${edgeIndex + 1}: не удалось переключить metadata в builder.`)
        return
      }
      topologyForm.setFieldValue(
        ['edges', edgeIndex, 'edge_metadata_builder'],
        metadataObjectToBuilderRows(parsed.metadata)
      )
      topologyForm.setFieldValue(['edges', edgeIndex, 'edge_metadata_mode'], 'builder')
      return
    }

    const built = buildEdgeMetadataFromBuilder(
      topologyForm.getFieldValue(['edges', edgeIndex, 'edge_metadata_builder']),
      edgeIndex + 1
    )
    if (built.errors.length > 0) {
      message.error(built.errors[0] || `Edge #${edgeIndex + 1}: исправьте metadata builder перед переключением.`)
      return
    }
    topologyForm.setFieldValue(
      ['edges', edgeIndex, 'metadata_json'],
      Object.keys(built.metadata).length > 0 ? JSON.stringify(built.metadata, null, 2) : ''
    )
    topologyForm.setFieldValue(['edges', edgeIndex, 'edge_metadata_mode'], 'raw')
  }, [message, topologyForm])

  useEffect(() => {
    void loadOrganizations()
  }, [loadOrganizations])

  useEffect(() => {
    void loadOrganizationDetail()
  }, [loadOrganizationDetail])

  useEffect(() => {
    void loadPools()
  }, [loadPools])

  useEffect(() => {
    void loadGraph()
  }, [loadGraph])

  useEffect(() => {
    void loadTopologySnapshots()
  }, [loadTopologySnapshots])

  useEffect(() => {
    if (activeWorkspaceTab !== 'topology') return
    const edges = Array.isArray(watchedEdges) ? watchedEdges : []
    edges.forEach((edge) => {
      const mode = (
        String(edge?.document_policy_mode || 'raw').trim().toLowerCase() === 'builder'
          ? 'builder'
          : 'raw'
      )
      if (mode !== 'builder') return
      const childOrgId = String(edge?.child_organization_id || '').trim()
      if (!childOrgId) return
      const childOrganization = organizationById[childOrgId]
      const databaseId = String(childOrganization?.database_id || '').trim()
      if (!databaseId) return
      if (metadataCatalogByDatabase[databaseId]) return
      if (metadataCatalogLoadingByDatabase[databaseId]) return
      if (metadataCatalogErrorByDatabase[databaseId]) return
      void loadMetadataCatalog(databaseId, false)
    })
  }, [
    activeWorkspaceTab,
    loadMetadataCatalog,
    metadataCatalogByDatabase,
    metadataCatalogErrorByDatabase,
    metadataCatalogLoadingByDatabase,
    organizationById,
    watchedEdges,
  ])

  useEffect(() => {
    if (activeWorkspaceTab !== 'topology') return
    if (!hasTenantContext) return
    if (topologyTemplates.length > 0 || loadingTopologyTemplates) {
      return
    }
    void loadTopologyTemplates()
  }, [
    activeWorkspaceTab,
    hasTenantContext,
    loadTopologyTemplates,
    loadingTopologyTemplates,
    topologyTemplates.length,
  ])

  useEffect(() => {
    if (activeWorkspaceTab !== 'topology') return
    if (!hasTenantContext) return
    if (
      masterDataParties.length > 0
      || masterDataItems.length > 0
      || masterDataContracts.length > 0
      || masterDataTaxProfiles.length > 0
    ) {
      return
    }
    void loadMasterDataTokenCatalog()
  }, [
    activeWorkspaceTab,
    hasTenantContext,
    loadMasterDataTokenCatalog,
    masterDataContracts.length,
    masterDataItems.length,
    masterDataParties.length,
    masterDataTaxProfiles.length,
  ])

  useEffect(() => {
    setTopologyPreflightErrors([])
    setTopologySubmitError(null)
    if (activeWorkspaceTab !== 'topology' || !selectedPool) return
    const topologyInstantiation = selectedPoolTopologyInstantiation
    const selectedPoolGraph = graph && graph.pool_id === selectedPoolId ? graph : null
    topologyForm.setFieldsValue({
      authoring_mode: resolveInitialTopologyAuthoringMode({
        graph: selectedPoolGraph,
        topologyInstantiation,
      }),
      effective_from: new Date().toISOString().slice(0, 10),
      effective_to: '',
      topology_template_revision_id: undefined,
      slot_assignments: [],
      edge_selector_overrides: [],
      nodes: [],
      edges: [],
    })
  }, [activeWorkspaceTab, graph, selectedPool, selectedPoolId, selectedPoolTopologyInstantiation, topologyForm])

  useEffect(() => {
    if (
      activeWorkspaceTab !== 'topology'
      || !selectedPool
      || !selectedPoolId
      || !graph
      || graph.pool_id !== selectedPoolId
    ) return
    const topologyInstantiation = selectedPoolTopologyInstantiation
    const organizationByNodeVersion = new Map(
      graph.nodes.map((node) => [node.node_version_id, node.organization_id])
    )
    const nodes = graph.nodes.map<TopologyNodeFormValue>((node) => ({
      organization_id: node.organization_id,
      is_root: Boolean(node.is_root),
      metadata_json: stringifyMetadataForForm(node.metadata),
    }))
    const edges = graph.edges.map<TopologyEdgeFormValue>((edge) => {
      const metadata = normalizeMetadataObject(edge.metadata)
      const rawPolicy = metadata.document_policy
      const policy =
        rawPolicy && typeof rawPolicy === 'object' && !Array.isArray(rawPolicy)
          ? rawPolicy as Record<string, unknown>
          : null
      const weight = Number(edge.weight)
      const minAmount = edge.min_amount == null ? null : Number(edge.min_amount)
      const maxAmount = edge.max_amount == null ? null : Number(edge.max_amount)
      const metadataWithoutPolicy = { ...metadata }
      delete metadataWithoutPolicy.document_policy
      const documentPolicyKey = String(metadata.document_policy_key || '').trim()
      delete metadataWithoutPolicy.document_policy_key
      return {
        edge_version_id: edge.edge_version_id,
        parent_organization_id: organizationByNodeVersion.get(edge.parent_node_version_id),
        child_organization_id: organizationByNodeVersion.get(edge.child_node_version_id),
        weight: Number.isFinite(weight) ? weight : undefined,
        min_amount: minAmount == null || Number.isNaN(minAmount) ? null : minAmount,
        max_amount: maxAmount == null || Number.isNaN(maxAmount) ? null : maxAmount,
        document_policy_key: documentPolicyKey,
        document_policy_mode: 'raw',
        document_policy_json: policy ? JSON.stringify(policy, null, 2) : '',
        document_policy_builder: documentPolicyToBuilderChains(policy),
        edge_metadata_mode: 'raw',
        edge_metadata_builder: metadataObjectToBuilderRows(metadataWithoutPolicy),
        metadata_json: stringifyMetadataForForm(metadataWithoutPolicy),
      }
    })
    topologyForm.setFieldsValue({
      authoring_mode: resolveInitialTopologyAuthoringMode({
        graph,
        topologyInstantiation,
      }),
      effective_from: String(graph.date || '').trim() || new Date().toISOString().slice(0, 10),
      effective_to: '',
      topology_template_revision_id: topologyInstantiation?.topology_template_revision_id || undefined,
      slot_assignments: Array.isArray(topologyInstantiation?.slot_assignments)
        ? topologyInstantiation?.slot_assignments
        : [],
      edge_selector_overrides: Array.isArray(topologyInstantiation?.edge_selector_overrides)
        ? topologyInstantiation?.edge_selector_overrides
        : [],
      nodes,
      edges,
    })
  }, [activeWorkspaceTab, graph, selectedPool, selectedPoolId, selectedPoolTopologyInstantiation, topologyForm])

  useEffect(() => {
    if (!isTemplateTopologyAuthoring) {
      return
    }
    const revisionId = String(watchedTopologyTemplateRevisionId || '').trim()
    if (!revisionId) {
      topologyForm.setFieldsValue({
        slot_assignments: [],
        edge_selector_overrides: [],
      })
      return
    }
    if (!selectedTopologyTemplateRevision) {
      return
    }

    const assignmentBySlotKey = new Map<string, string>()
    const currentAssignments = topologyForm.getFieldValue('slot_assignments')
    ;(Array.isArray(currentAssignments) ? currentAssignments : []).forEach((assignment) => {
      const slotKey = String(assignment?.slot_key || '').trim()
      const organizationId = String(assignment?.organization_id || '').trim()
      if (slotKey) {
        assignmentBySlotKey.set(slotKey, organizationId)
      }
    })

    const overrideByEdge = new Map<string, string>()
    const currentOverrides = topologyForm.getFieldValue('edge_selector_overrides')
    ;(Array.isArray(currentOverrides) ? currentOverrides : []).forEach((override) => {
      const parentSlotKey = String(override?.parent_slot_key || '').trim()
      const childSlotKey = String(override?.child_slot_key || '').trim()
      const documentPolicyKey = String(override?.document_policy_key || '').trim()
      if (parentSlotKey && childSlotKey) {
        overrideByEdge.set(`${parentSlotKey}:${childSlotKey}`, documentPolicyKey)
      }
    })

    topologyForm.setFieldsValue({
      slot_assignments: selectedTopologyTemplateRevision.nodes.map((node) => {
        const slotKey = String(node.slot_key || '').trim()
        return {
          slot_key: slotKey,
          organization_id: assignmentBySlotKey.get(slotKey) || '',
        }
      }),
      edge_selector_overrides: selectedTopologyTemplateRevision.edges.map((edge) => {
        const parentSlotKey = String(edge.parent_slot_key || '').trim()
        const childSlotKey = String(edge.child_slot_key || '').trim()
        return {
          parent_slot_key: parentSlotKey,
          child_slot_key: childSlotKey,
          document_policy_key: overrideByEdge.get(`${parentSlotKey}:${childSlotKey}`) || '',
        }
      }),
    })
  }, [
    isTemplateTopologyAuthoring,
    selectedTopologyTemplateRevision,
    topologyForm,
    watchedTopologyTemplateRevisionId,
  ])

  const openCreateOrganizationDrawer = useCallback(() => {
    if (mutatingDisabled) return
    setOrganizationDrawerMode('create')
    setEditingOrganization(null)
    setOrganizationSubmitError(null)
    setIsOrganizationDrawerOpen(true)
  }, [mutatingDisabled])

  const openEditOrganizationDrawer = useCallback((organization: Organization | null) => {
    if (mutatingDisabled || !organization) return
    setOrganizationDrawerMode('edit')
    setEditingOrganization(organization)
    setOrganizationSubmitError(null)
    setIsOrganizationDrawerOpen(true)
  }, [mutatingDisabled])

  const closeOrganizationDrawer = useCallback(() => {
    if (isOrganizationSaving) return
    setIsOrganizationDrawerOpen(false)
    setOrganizationSubmitError(null)
  }, [isOrganizationSaving])

  useEffect(() => {
    if (!isOrganizationDrawerOpen) return
    organizationForm.resetFields()
    if (organizationDrawerMode === 'edit' && editingOrganization) {
      organizationForm.setFieldsValue({
        inn: editingOrganization.inn,
        name: editingOrganization.name,
        full_name: editingOrganization.full_name || '',
        kpp: editingOrganization.kpp || '',
        status: editingOrganization.status,
        database_id: editingOrganization.database_id || undefined,
        external_ref: editingOrganization.external_ref || '',
      })
      return
    }
    organizationForm.setFieldsValue({
      inn: '',
      name: '',
      full_name: '',
      kpp: '',
      status: 'active',
      database_id: undefined,
      external_ref: '',
    })
  }, [editingOrganization, isOrganizationDrawerOpen, organizationDrawerMode, organizationForm])

  const submitOrganization = useCallback(async () => {
    if (mutatingDisabled) return

    setOrganizationSubmitError(null)
    try {
      const values = await organizationForm.validateFields()
      const payload = {
        organization_id: organizationDrawerMode === 'edit' ? editingOrganization?.id : undefined,
        inn: values.inn.trim(),
        name: values.name.trim(),
        full_name: values.full_name.trim(),
        kpp: values.kpp.trim(),
        status: values.status,
        database_id: values.database_id ? values.database_id : null,
        external_ref: values.external_ref.trim(),
      }

      setIsOrganizationSaving(true)
      const response = await upsertOrganization(payload)
      const organizationId = response.organization.id
      setSelectedOrganizationId(organizationId)
      message.success(response.created ? 'Организация создана.' : 'Организация обновлена.')
      setIsOrganizationDrawerOpen(false)
      await Promise.all([
        loadOrganizations({ force: true }),
        loadOrganizationDetailById(organizationId, { force: true }),
      ])
    } catch (err) {
      if (
        err
        && typeof err === 'object'
        && Array.isArray((err as { errorFields?: unknown }).errorFields)
      ) {
        return
      }
      const resolved = resolveApiError(
        err,
        organizationDrawerMode === 'create'
          ? 'Не удалось создать организацию.'
          : 'Не удалось обновить организацию.'
      )
      if (Object.keys(resolved.fieldErrors).length > 0) {
        const fields = Object.entries(resolved.fieldErrors)
          .filter(([fieldName]) => ORGANIZATION_FORM_FIELDS.includes(fieldName as keyof OrganizationFormValues))
          .map(([fieldName, fieldErrors]) => ({
            name: fieldName as keyof OrganizationFormValues,
            errors: fieldErrors,
          }))
        if (fields.length > 0) {
          organizationForm.setFields(fields)
        }
      }
      setOrganizationSubmitError(resolved.message)
    } finally {
      setIsOrganizationSaving(false)
    }
  }, [
    editingOrganization?.id,
    loadOrganizationDetailById,
    loadOrganizations,
    message,
    mutatingDisabled,
    organizationDrawerMode,
    organizationForm,
  ])

  const openCreatePoolDrawer = useCallback(() => {
    if (mutatingDisabled) return
    setPoolDrawerMode('create')
    setPoolSubmitError(null)
    setIsPoolDrawerOpen(true)
  }, [mutatingDisabled])

  const openEditPoolDrawer = useCallback(() => {
    if (mutatingDisabled || !selectedPool) return
    setPoolDrawerMode('edit')
    setPoolSubmitError(null)
    setIsPoolDrawerOpen(true)
  }, [mutatingDisabled, selectedPool])

  const closePoolDrawer = useCallback(() => {
    if (isPoolSaving) return
    setIsPoolDrawerOpen(false)
    setPoolSubmitError(null)
  }, [isPoolSaving])

  const reloadBindingsWorkspace = useCallback(async (pool: OrganizationPool) => {
    setIsPoolBindingsLoading(true)
    setPoolBindingsLoadError(null)
    setPoolBindingsSubmitError(null)
    try {
      const collection = await listPoolWorkflowBindings(pool.id)
      setLoadedPoolBindings(collection.workflow_bindings)
      setLoadedPoolBindingsCollectionEtag(collection.collection_etag)
      setPoolBindingsBackendBlockingRemediation(collection.blocking_remediation ?? null)
      poolBindingsForm.setFieldsValue({
        workflow_bindings: workflowBindingsToFormValues(collection.workflow_bindings),
      } as unknown as Parameters<typeof poolBindingsForm.setFieldsValue>[0])
    } catch (err) {
      const resolved = resolveApiError(err, 'Не удалось загрузить workflow bindings.')
      setLoadedPoolBindings([])
      setLoadedPoolBindingsCollectionEtag('')
      setPoolBindingsBackendBlockingRemediation(null)
      setPoolBindingsLoadError(resolved.message)
      poolBindingsForm.setFieldsValue({ workflow_bindings: [] })
    } finally {
      setIsPoolBindingsLoading(false)
    }
  }, [poolBindingsForm])

  useEffect(() => {
    if (!isPoolDrawerOpen) return () => {
    }
    poolForm.resetFields()
    if (poolDrawerMode === 'edit' && selectedPool) {
      poolForm.setFieldsValue({
        code: selectedPool.code,
        name: selectedPool.name,
        description: selectedPool.description || '',
        is_active: selectedPool.is_active,
      })
      return
    }
    poolForm.setFieldsValue({
      code: '',
      name: '',
      description: '',
      is_active: true,
    })
  }, [isPoolDrawerOpen, poolDrawerMode, poolForm, selectedPool])

  useEffect(() => {
    if ((activeWorkspaceTab !== 'bindings' && activeWorkspaceTab !== 'topology') || !selectedPool) {
      setLoadedPoolBindings([])
      setLoadedPoolBindingsCollectionEtag('')
      setPoolBindingsBackendBlockingRemediation(null)
      setIsPoolBindingsLoading(false)
      setPoolBindingsLoadError(null)
      setPoolBindingsSubmitError(null)
      poolBindingsForm.setFieldsValue({ workflow_bindings: [] })
      return
    }

    void reloadBindingsWorkspace(selectedPool)
  }, [activeWorkspaceTab, poolBindingsForm, reloadBindingsWorkspace, selectedPool])

  useEffect(() => {
    setTopologyCoverageBindingId((current) => {
      const normalizedCurrent = String(current || '').trim()
      if (!normalizedCurrent) {
        return undefined
      }
      return loadedPoolBindings.some((binding) => binding.binding_id === normalizedCurrent)
        ? normalizedCurrent
        : undefined
    })
  }, [loadedPoolBindings, selectedPoolId])

  const submitPool = useCallback(async () => {
    if (mutatingDisabled) return
    if (poolDrawerMode === 'edit' && !selectedPool) return
    setPoolSubmitError(null)
    try {
      const values = await poolForm.validateFields()
      setIsPoolSaving(true)
      const response = await upsertOrganizationPool({
        pool_id: poolDrawerMode === 'edit' ? selectedPool?.id : undefined,
        code: values.code.trim(),
        name: values.name.trim(),
        description: values.description.trim(),
        is_active: Boolean(values.is_active),
        metadata: poolDrawerMode === 'edit' ? selectedPool?.metadata ?? {} : {},
      })
      const defaultGraphDate = graphDate.trim() || new Date().toISOString().slice(0, 10)
      if (response.created) {
        setGraphDate(defaultGraphDate)
        setGraph({
          pool_id: response.pool.id,
          date: defaultGraphDate,
          version: '',
          nodes: [],
          edges: [],
        })
        setTopologySnapshots([
          {
            effective_from: defaultGraphDate,
            effective_to: null,
            nodes_count: 0,
            edges_count: 0,
          },
        ])
      }
      setSelectedPoolId(response.pool.id)
      message.success(response.created ? 'Пул создан.' : 'Пул обновлён.')
      setIsPoolDrawerOpen(false)
      await loadPools({ force: true })
      await loadGraph({ force: true })
    } catch (err) {
      if (
        err
        && typeof err === 'object'
        && Array.isArray((err as { errorFields?: unknown }).errorFields)
      ) {
        return
      }
      const resolved = resolveApiError(
        err,
        poolDrawerMode === 'create'
          ? 'Не удалось создать пул.'
          : 'Не удалось обновить пул.'
      )
      setPoolSubmitError(resolved.message)
    } finally {
      setIsPoolSaving(false)
    }
  }, [graphDate, loadGraph, loadPools, message, mutatingDisabled, poolDrawerMode, poolForm, selectedPool])

  const submitPoolBindings = useCallback(async () => {
    if (mutatingDisabled || isPoolBindingsLoading || isPoolBindingsSaving || !selectedPool) return
    if (isPoolBindingsSaveBlocked) {
      setPoolBindingsSubmitError(
        poolBindingsBlockingRemediations[0]?.detail || 'Bindings remediation is required before save.'
      )
      return
    }
    setPoolBindingsSubmitError(null)
    try {
      const values = await poolBindingsForm.validateFields()
      const preparedBindings = buildWorkflowBindingsFromForm(values.workflow_bindings)
      if (preparedBindings.errors.length > 0) {
        setPoolBindingsSubmitError(preparedBindings.errors[0] ?? 'Workflow bindings form is invalid.')
        return
      }
      setIsPoolBindingsSaving(true)
      await syncPoolWorkflowBindings({
        poolId: selectedPool.id,
        collectionEtag: loadedPoolBindingsCollectionEtag,
        nextBindings: preparedBindings.bindings,
      })
      await reloadBindingsWorkspace(selectedPool)
      message.success('Workflow bindings updated.')
      await loadPools({ force: true })
      await loadOrganizationDetail({ force: true })
    } catch (err) {
      if (
        err
        && typeof err === 'object'
        && Array.isArray((err as { errorFields?: unknown }).errorFields)
      ) {
        return
      }
      const resolved = resolveApiError(err, 'Не удалось сохранить workflow bindings.')
      setPoolBindingsSubmitError(resolved.message)
    } finally {
      setIsPoolBindingsSaving(false)
    }
  }, [
    isPoolBindingsLoading,
    isPoolBindingsSaving,
    loadOrganizationDetail,
    loadPools,
    loadedPoolBindingsCollectionEtag,
    message,
    mutatingDisabled,
    poolBindingsForm,
    isPoolBindingsSaveBlocked,
    poolBindingsBlockingRemediations,
    reloadBindingsWorkspace,
    selectedPool,
  ])

  const toggleSelectedPoolActive = useCallback(async () => {
    if (mutatingDisabled || !selectedPool) return
    setPoolSubmitError(null)
    setIsPoolSaving(true)
    try {
      await upsertOrganizationPool({
        pool_id: selectedPool.id,
        code: selectedPool.code,
        name: selectedPool.name,
        description: selectedPool.description || '',
        is_active: !selectedPool.is_active,
        metadata: selectedPool.metadata,
      })
      message.success(selectedPool.is_active ? 'Пул деактивирован.' : 'Пул активирован.')
      await loadPools({ force: true })
      await loadGraph({ force: true })
    } catch (err) {
      const resolved = resolveApiError(err, 'Не удалось изменить статус пула.')
      setPoolSubmitError(resolved.message)
    } finally {
      setIsPoolSaving(false)
    }
  }, [loadGraph, loadPools, message, mutatingDisabled, selectedPool])

  const submitTopologySnapshot = useCallback(async () => {
    if (mutatingDisabled || !selectedPoolId) return
    if (isTopologySaveBlocked) {
      setTopologySubmitError(
        topologyBlockingRemediations[0]?.detail || 'Topology remediation is required before save.'
      )
      return
    }
    setTopologySubmitError(null)
    setTopologyPreflightErrors([])
    try {
      const values = await topologyForm.validateFields()
      const preflight = buildTopologyPreflight(values, selectedTopologyTemplateRevision)
      if (!preflight.payload) {
        setTopologyPreflightErrors(preflight.errors)
        return
      }
      setIsTopologySaving(true)
      const effectiveFrom = preflight.payload.effective_from
      let versionToken = String(graph?.version || '').trim()
      if (!versionToken || graphDate !== effectiveFrom) {
        const versionSnapshot = await getPoolGraph(selectedPoolId, effectiveFrom)
        versionToken = String(versionSnapshot.version || '').trim()
        if (graphDate === effectiveFrom) {
          setGraph(versionSnapshot)
        }
      }
      if (!versionToken) {
        setTopologySubmitError('Не удалось определить актуальную версию topology snapshot. Обновите граф и повторите.')
        return
      }
      await upsertPoolTopologySnapshot(selectedPoolId, { ...preflight.payload, version: versionToken })
      message.success('Topology snapshot сохранён.')
      await Promise.all([
        loadGraph({ force: true }),
        loadTopologySnapshots({ force: true }),
        loadPools({ force: true }),
      ])
    } catch (err) {
      if (
        err
        && typeof err === 'object'
        && Array.isArray((err as { errorFields?: unknown }).errorFields)
      ) {
        return
      }
      const resolved = resolveApiError(
        err,
        'Не удалось сохранить topology snapshot.',
        { includeProblemItems: true }
      )
      const errorCode = getApiErrorCode(err)
      setTopologySubmitError(
        METADATA_HANDOFF_ERROR_CODES.has(errorCode)
          ? appendMetadataManagementHandoff(resolved.message)
          : resolved.message
      )
    } finally {
      setIsTopologySaving(false)
    }
  }, [
    graph,
    graphDate,
    isTopologySaveBlocked,
    loadGraph,
    loadPools,
    loadTopologySnapshots,
    message,
    mutatingDisabled,
    selectedPoolId,
    selectedTopologyTemplateRevision,
    topologyBlockingRemediations,
    topologyForm,
  ])

  const openSyncModal = useCallback(() => {
    if (mutatingDisabled) return
    setSyncErrors([])
    setSyncResult(null)
    setSyncInput('{\n  "rows": []\n}')
    setIsSyncModalOpen(true)
  }, [mutatingDisabled])

  const closeSyncModal = useCallback(() => {
    if (isSyncSubmitting) return
    setIsSyncModalOpen(false)
    setSyncErrors([])
  }, [isSyncSubmitting])

  const submitSync = useCallback(async () => {
    if (mutatingDisabled) return
    const parsed = parseSyncPayload(syncInput)
    if (parsed.errors.length > 0) {
      setSyncErrors(parsed.errors)
      setSyncResult(null)
      return
    }

    setSyncErrors([])
    setSyncResult(null)
    setIsSyncSubmitting(true)
    try {
      const response = await syncOrganizationsCatalog({ rows: parsed.rows })
      setSyncResult(response)
      message.success('Синхронизация каталога завершена.')
      await loadOrganizations({ force: true })
    } catch (err) {
      const resolved = resolveApiError(err, 'Не удалось выполнить синхронизацию каталога.')
      const fieldErrors = buildFieldErrorLines(resolved.fieldErrors)
      setSyncErrors(fieldErrors.length > 0 ? [resolved.message, ...fieldErrors] : [resolved.message])
    } finally {
      setIsSyncSubmitting(false)
    }
  }, [loadOrganizations, message, mutatingDisabled, syncInput])

  const organizationColumns: ColumnsType<Organization> = useMemo(
    () => [
      {
        title: 'Name',
        dataIndex: 'name',
        key: 'name',
        render: (value: string, record) => (
          <Space direction="vertical" size={0}>
            <Text strong>{value}</Text>
            <Text type="secondary">INN: {record.inn}</Text>
          </Space>
        ),
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        width: 120,
        render: (value: OrganizationStatus) => <Tag color={statusColor[value]}>{value}</Tag>,
      },
      {
        title: 'Database',
        key: 'database_id',
        width: 220,
        render: (_value, record) => (
          record.database_id
            ? <Text code>{record.database_id.slice(0, 8)}</Text>
            : <Text type="secondary">not linked</Text>
        ),
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 180,
        render: (value: string) => formatDate(value),
      },
      {
        title: 'Actions',
        key: 'actions',
        width: 100,
        render: (_value, record) => (
          <Button
            size="small"
            onClick={() => openEditOrganizationDrawer(record)}
            disabled={mutatingDisabled}
          >
            Edit
          </Button>
        ),
      },
    ],
    [mutatingDisabled, openEditOrganizationDrawer]
  )

  const bindingColumns: ColumnsType<OrganizationPoolBinding> = useMemo(
    () => [
      {
        title: 'Pool',
        key: 'pool',
        render: (_value, record) => `${record.pool_code} - ${record.pool_name}`,
      },
      {
        title: 'Root',
        dataIndex: 'is_root',
        key: 'is_root',
        width: 90,
        render: (value: boolean) => (value ? <Tag color="blue">yes</Tag> : <Tag>no</Tag>),
      },
      {
        title: 'From',
        dataIndex: 'effective_from',
        key: 'effective_from',
        width: 120,
      },
      {
        title: 'To',
        dataIndex: 'effective_to',
        key: 'effective_to',
        width: 120,
        render: (value: string | null) => value || 'open',
      },
    ],
    []
  )

  const poolColumns: ColumnsType<OrganizationPool> = useMemo(
    () => [
      {
        title: 'Code',
        dataIndex: 'code',
        key: 'code',
        width: 180,
        render: (value: string, record) => (
          <Space direction="vertical" size={0}>
            <Text code>{value}</Text>
            <Text type="secondary">{record.name}</Text>
          </Space>
        ),
      },
      {
        title: 'Description',
        dataIndex: 'description',
        key: 'description',
        render: (value: string) => value || <Text type="secondary">-</Text>,
      },
      {
        title: 'Status',
        dataIndex: 'is_active',
        key: 'is_active',
        width: 120,
        render: (value: boolean) => (
          value ? <Tag color="success">active</Tag> : <Tag color="default">inactive</Tag>
        ),
      },
      {
        title: 'Workflow bindings',
        key: 'workflow_bindings',
        width: 220,
        render: (_value, record) => {
          const summary = summarizeWorkflowBindings(record)
          return (
            <Space direction="vertical" size={0}>
              <Text>{summary.primary}</Text>
              {summary.secondary ? <Text type="secondary">{summary.secondary}</Text> : null}
            </Space>
          )
        },
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 180,
        render: (value: string) => formatDate(value),
      },
    ],
    []
  )

  return (
    <>
      <WorkspacePage
        header={(
          <PageHeader
            title="Pool Catalog"
            subtitle={(
              <>
                Task-first operator workspace on
                {' '}
                <Text code>{POOL_CATALOG_ROUTE}</Text>
                {' '}
                for pool basics, workflow attachments, topology authoring, and graph inspection.
              </>
            )}
            actions={(
              <Space wrap size={16} align="start">
                <Space direction="vertical" size={4}>
                  <Text strong>Pool</Text>
                  <Select
                    aria-label="Catalog pool"
                    data-testid="pool-catalog-context-pool"
                    style={{ width: 320 }}
                    placeholder="Select pool"
                    value={selectedPoolId ?? undefined}
                    options={pools.map((pool) => ({
                      value: pool.id,
                      label: `${pool.code} - ${pool.name}`,
                    }))}
                    onChange={(value) => handleSelectPool(value ?? null)}
                  />
                </Space>
                <Space direction="vertical" size={4}>
                  <Text strong>Graph date</Text>
                  <Input
                    aria-label="Pool graph date"
                    type="date"
                    value={graphDate}
                    onChange={(event) => handleGraphDateChange(event.target.value)}
                    style={{ width: 180 }}
                  />
                </Space>
                <Button
                  onClick={() => {
                    if (activeWorkspaceTab === 'bindings' && selectedPool) {
                      void reloadBindingsWorkspace(selectedPool)
                      return
                    }
                    if (activeWorkspaceTab === 'graph' || activeWorkspaceTab === 'topology') {
                      void loadGraph({ force: true })
                      return
                    }
                    void loadPools({ force: true })
                  }}
                  loading={loadingPools || loadingGraph || isPoolBindingsLoading}
                  style={{ marginTop: 28 }}
                >
                  Refresh data
                </Button>
              </Space>
            )}
          />
        )}
      >
        <Alert
          type="info"
          showIcon
          message="Task-first pool workspace"
          description={(
            <Space direction="vertical" size={8}>
              <Text>
                Keep pool fields, reusable attachment logic, and topology remediation on separate task surfaces. Open
                reusable logic in the binding profile catalog and concrete policy authoring in /decisions.
              </Text>
              {selectedOrganization ? (
                <Space size={4} wrap>
                  <Text type="secondary">Organization catalog ready:</Text>
                  <Text>{selectedOrganization.name}</Text>
                </Space>
              ) : null}
              <Space wrap>
                <RouteButton to={POOL_BINDING_PROFILES_ROUTE}>Open binding profiles</RouteButton>
                <RouteButton to="/decisions">Open /decisions</RouteButton>
              </Space>
            </Space>
          )}
        />

        {error && <Alert type="error" message={error} showIcon />}

        <Tabs
          activeKey={activeWorkspaceTab}
          onChange={(key) => handleSelectWorkspaceTab(key as PoolCatalogWorkspaceTab)}
          data-testid="pool-catalog-workspace-tabs"
          items={[
            {
              key: 'organizations',
              label: 'Organizations',
              children: (
                <Card title="Organizations" loading={loadingOrganizations}>
                  {mutatingDisabled && (
                    <Alert
                      type="warning"
                      showIcon
                      style={{ marginBottom: 12 }}
                      message="Mutating actions are disabled"
                      description="Staff users must select a tenant (X-CC1C-Tenant-ID) to run mutating actions."
                    />
                  )}

                  <Space size="small" wrap style={{ marginBottom: 12 }}>
                    <Input
                      value={query}
                      placeholder="Search by INN/name"
                      style={{ width: 280 }}
                      onChange={(event) => setQuery(event.target.value)}
                      onPressEnter={() => { void loadOrganizations({ force: true }) }}
                      allowClear
                    />
                    <Select
                      value={statusFilter}
                      style={{ width: 160 }}
                      options={[
                        { value: 'all', label: 'All statuses' },
                        { value: 'active', label: 'Active' },
                        { value: 'inactive', label: 'Inactive' },
                        { value: 'archived', label: 'Archived' },
                      ]}
                      onChange={setStatusFilter}
                    />
                    <Select
                      value={databaseLinkFilter}
                      style={{ width: 180 }}
                      options={[
                        { value: 'all', label: 'All databases' },
                        { value: 'linked', label: 'Linked only' },
                        { value: 'unlinked', label: 'Unlinked only' },
                      ]}
                      onChange={setDatabaseLinkFilter}
                    />
                    <Button onClick={() => { void loadOrganizations({ force: true }) }} loading={loadingOrganizations}>
                      Refresh
                    </Button>
                    <Button
                      type="primary"
                      onClick={openCreateOrganizationDrawer}
                      disabled={mutatingDisabled}
                      data-testid="pool-catalog-add-org"
                    >
                      Add organization
                    </Button>
                    <Button
                      onClick={() => openEditOrganizationDrawer(selectedOrganization)}
                      disabled={mutatingDisabled || !selectedOrganization}
                      data-testid="pool-catalog-edit-org"
                    >
                      Edit
                    </Button>
                    <Button
                      onClick={openSyncModal}
                      disabled={mutatingDisabled}
                      data-testid="pool-catalog-sync-orgs"
                    >
                      Sync catalog
                    </Button>
                  </Space>

                  <Row gutter={16}>
                    <Col span={14}>
                      <Table
                        rowKey="id"
                        size="small"
                        columns={organizationColumns}
                        dataSource={organizations}
                        loading={loadingOrganizations}
                        pagination={{ pageSize: 10 }}
                        rowSelection={{
                          type: 'radio',
                          selectedRowKeys: selectedOrganizationId ? [selectedOrganizationId] : [],
                          onChange: (keys) => setSelectedOrganizationId(keys[0] ? String(keys[0]) : null),
                        }}
                        onRow={(record) => ({
                          onClick: () => setSelectedOrganizationId(record.id),
                        })}
                      />
                    </Col>
                    <Col span={10}>
                      <Card title="Organization details" loading={loadingOrganizationDetail}>
                        {!organizationDetail && (
                          <Text type="secondary">Выберите организацию из каталога.</Text>
                        )}
                        {organizationDetail && (
                          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                            <Descriptions size="small" column={1}>
                              <Descriptions.Item label="Name">{organizationDetail.organization.name}</Descriptions.Item>
                              <Descriptions.Item label="INN">{organizationDetail.organization.inn}</Descriptions.Item>
                              <Descriptions.Item label="KPP">{organizationDetail.organization.kpp || '-'}</Descriptions.Item>
                              <Descriptions.Item label="Status">
                                <Tag color={statusColor[organizationDetail.organization.status]}>
                                  {organizationDetail.organization.status}
                                </Tag>
                              </Descriptions.Item>
                              <Descriptions.Item label="Database ID">
                                {organizationDetail.organization.database_id
                                  ? <Text code>{organizationDetail.organization.database_id}</Text>
                                  : <Text type="secondary">not linked</Text>}
                              </Descriptions.Item>
                            </Descriptions>
                            <Text strong>Pool bindings</Text>
                            <Table
                              rowKey={(record) => `${record.pool_id}:${record.effective_from}`}
                              size="small"
                              columns={bindingColumns}
                              dataSource={organizationDetail.pool_bindings}
                              pagination={false}
                              locale={{ emptyText: 'No bindings' }}
                            />
                          </Space>
                        )}
                      </Card>
                    </Col>
                  </Row>
                </Card>
              ),
            },
            {
              key: 'pools',
              label: 'Pools',
              children: (
                <Card title="Pools management" loading={loadingPools}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    {mutatingDisabled && (
                      <Alert
                        type="warning"
                        showIcon
                        message="Mutating actions are disabled"
                        description="Staff users must select a tenant (X-CC1C-Tenant-ID) to run mutating actions."
                      />
                    )}
                    {poolSubmitError && <Alert type="error" message={poolSubmitError} showIcon />}
                    <Space size="small" wrap>
                      <Select
                        value={selectedPoolId ?? undefined}
                        style={{ width: 320 }}
                        placeholder="Select pool"
                        options={pools.map((pool) => ({
                          value: pool.id,
                          label: `${pool.code} - ${pool.name}`,
                        }))}
                        onChange={(value) => handleSelectPool(value ?? null)}
                      />
                      <Button
                        type="primary"
                        onClick={openCreatePoolDrawer}
                        disabled={mutatingDisabled}
                        data-testid="pool-catalog-add-pool"
                      >
                        Add pool
                      </Button>
                      <Button
                        onClick={openEditPoolDrawer}
                        disabled={mutatingDisabled || !selectedPool}
                        data-testid="pool-catalog-edit-pool"
                      >
                        Edit pool
                      </Button>
                      <Button
                        onClick={() => { void toggleSelectedPoolActive() }}
                        disabled={mutatingDisabled || !selectedPool}
                        loading={isPoolSaving}
                        data-testid="pool-catalog-toggle-pool-active"
                      >
                        {selectedPool?.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                    </Space>

                    <Table
                      rowKey="id"
                      size="small"
                      columns={poolColumns}
                      dataSource={pools}
                      loading={loadingPools}
                      pagination={{ pageSize: 8 }}
                      rowSelection={{
                        type: 'radio',
                        selectedRowKeys: selectedPoolId ? [selectedPoolId] : [],
                        onChange: (keys) => handleSelectPool(keys[0] ? String(keys[0]) : null),
                      }}
                      onRow={(record) => ({
                        onClick: () => handleSelectPool(record.id),
                      })}
                    />
                  </Space>
                </Card>
              ),
            },
            {
              key: 'bindings',
              label: 'Bindings',
              forceRender: true,
              children: (
                <Card title="Workflow attachment workspace" loading={loadingPools}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    {mutatingDisabled && (
                      <Alert
                        type="warning"
                        showIcon
                        message="Mutating actions are disabled"
                        description="Staff users must select a tenant (X-CC1C-Tenant-ID) to run mutating actions."
                      />
                    )}
                    <Alert
                      type="info"
                      showIcon
                      message="Workflow attachments are managed separately from pool fields"
                      description="Use the Pools tab to create or edit pool code/name/status. Save attachments here through the canonical collection-level CRUD only."
                    />
                    <Space size="small" wrap>
                      <Select
                        value={selectedPoolId ?? undefined}
                        style={{ width: 320 }}
                        placeholder="Select pool"
                        options={pools.map((pool) => ({
                          value: pool.id,
                          label: `${pool.code} - ${pool.name}`,
                        }))}
                        onChange={(value) => handleSelectPool(value ?? null)}
                      />
                      <Button
                        onClick={() => {
                          if (selectedPool) {
                            handleSelectWorkspaceTab('pools')
                            openEditPoolDrawer()
                          }
                        }}
                        disabled={mutatingDisabled || !selectedPool}
                      >
                        Edit pool fields
                      </Button>
                      <Button
                        onClick={() => {
                          if (selectedPool) {
                            void loadPools({ force: true })
                            void loadOrganizationDetail({ force: true })
                          }
                        }}
                        disabled={!selectedPool || isPoolBindingsSaving}
                        loading={loadingPools}
                      >
                        Refresh pools
                      </Button>
                      <Button
                        onClick={() => {
                          if (selectedPool) {
                            void reloadBindingsWorkspace(selectedPool)
                          }
                        }}
                        disabled={!selectedPool || isPoolBindingsSaving}
                        loading={isPoolBindingsLoading}
                      >
                        Refresh bindings
                      </Button>
                      <Button
                        type="primary"
                        onClick={() => { handleOpenBindingsWorkspace() }}
                        disabled={!selectedPool}
                        data-testid="pool-catalog-open-bindings-workspace"
                      >
                        Open attachment workspace
                      </Button>
                      <RouteButton to={POOL_BINDING_PROFILES_ROUTE}>Open binding profiles</RouteButton>
                    </Space>

                    {poolBindingsSubmitError && <Alert type="error" message={poolBindingsSubmitError} showIcon />}
                    {poolBindingsLoadError && <Alert type="error" message={poolBindingsLoadError} showIcon />}
                    {poolBindingsBlockingRemediations.map((remediation) => (
                      <Alert
                        key={remediation.code}
                        type="warning"
                        message={remediation.title}
                        description={remediation.detail}
                        showIcon
                        action={(
                          <Space size={8}>
                            <Button size="small" onClick={() => { handleSelectWorkspaceTab('topology') }}>
                              Open Topology Editor
                            </Button>
                            <Button size="small" onClick={() => { navigate('/decisions') }}>
                              Open /decisions
                            </Button>
                          </Space>
                        )}
                      />
                    ))}
                    {isPoolBindingsLoading && (
                      <Alert type="info" message="Loading workflow attachments..." showIcon />
                    )}

                    {!selectedPool ? (
                      <Text type="secondary">Выберите пул, чтобы управлять workflow attachments.</Text>
                    ) : (
                      <>
                        <Descriptions size="small" column={1} bordered style={{ marginBottom: 16 }}>
                          <Descriptions.Item label="Pool">{`${selectedPool.code} - ${selectedPool.name}`}</Descriptions.Item>
                          <Descriptions.Item label="Status">
                            <StatusBadge status={selectedPool.is_active ? 'active' : 'inactive'} />
                          </Descriptions.Item>
                          <Descriptions.Item label="Attachment state">
                            {loadedPoolBindings.length > 0
                              ? `${loadedPoolBindings.length} configured attachment${loadedPoolBindings.length === 1 ? '' : 's'}`
                              : 'No attachments configured yet'}
                          </Descriptions.Item>
                        </Descriptions>
                        <Alert
                          type="info"
                          showIcon
                          message="Attachment editing moved to a dedicated secondary surface"
                          description="The canonical attachment workspace now opens in a drawer so pool basics, topology authoring, and reusable profile logic do not compete on one default canvas."
                        />
                        <DrawerFormShell
                          open={isBindingsWorkspaceOpen}
                          onClose={() => setIsBindingsWorkspaceOpen(false)}
                          title="Attachment workspace"
                          subtitle={`${selectedPool.code} - ${selectedPool.name}`}
                          width={960}
                          drawerTestId="pool-catalog-bindings-drawer"
                        >
                          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                            <Space size="small" wrap>
                              <Button
                                onClick={() => {
                                  if (selectedPool) {
                                    void reloadBindingsWorkspace(selectedPool)
                                  }
                                }}
                                disabled={!selectedPool || isPoolBindingsSaving}
                                loading={isPoolBindingsLoading}
                                data-testid="pool-catalog-refresh-bindings"
                              >
                                Refresh bindings
                              </Button>
                              <Button
                                type="primary"
                                onClick={() => { void submitPoolBindings() }}
                                loading={isPoolBindingsSaving}
                                disabled={(
                                  mutatingDisabled
                                  || !selectedPool
                                  || isPoolBindingsLoading
                                  || isPoolBindingsSaving
                                  || Boolean(poolBindingsLoadError)
                                  || isPoolBindingsSaveBlocked
                                  || !loadedPoolBindingsCollectionEtag
                                )}
                                data-testid="pool-catalog-save-bindings"
                              >
                                Save bindings
                              </Button>
                            </Space>
                            <Form form={poolBindingsForm} layout="vertical">
                              <PoolWorkflowBindingsEditor
                                availableBindingProfiles={bindingProfilesQuery.data?.binding_profiles ?? []}
                                availableBindingProfileDetails={bindingProfileDetailsById}
                                bindingProfilesLoading={bindingProfilesQuery.isLoading}
                                bindingProfileDetailsLoading={bindingProfileDetailsLoading}
                                bindingProfilesLoadError={
                                  bindingProfilesQuery.isError
                                    ? resolveApiError(bindingProfilesQuery.error, 'Не удалось загрузить binding profiles catalog.').message
                                    : bindingProfileDetailsError
                                }
                                onBindingProfileRevisionSelectOpen={() => {
                                  void ensureBindingProfileDetailsLoaded()
                                }}
                                topologyEdgeSelectors={topologyEdgeSelectors}
                                disabled={
                                  mutatingDisabled
                                  || isPoolBindingsSaving
                                  || isPoolBindingsLoading
                                  || Boolean(poolBindingsBackendBlockingRemediation)
                                }
                              />
                            </Form>
                          </Space>
                        </DrawerFormShell>
                      </>
                    )}
                  </Space>
                </Card>
              ),
            },
            {
              key: 'topology',
              label: 'Topology Editor',
              children: (
                <Card title="Topology snapshot editor">
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    {mutatingDisabled && (
                      <Alert
                        type="warning"
                        showIcon
                        message="Mutating actions are disabled"
                        description="Staff users must select a tenant (X-CC1C-Tenant-ID) to run mutating actions."
                      />
                    )}
                    {!selectedPool && (
                      <Text type="secondary">Выберите пул, чтобы редактировать topology snapshot.</Text>
                    )}
                    {selectedPool && (
                      <Form form={topologyForm} layout="vertical">
                        <Row gutter={12}>
                          <Col span={8}>
                            <Form.Item name="effective_from" label="effective_from" rules={[{ required: true }]}>
                              <Input type="date" />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name="effective_to" label="effective_to">
                              <Input type="date" />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item label="Pool">
                              <Input value={`${selectedPool.code} - ${selectedPool.name}`} disabled />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Alert
                          type="info"
                          showIcon
                          style={{ marginBottom: 12 }}
                          message="Workflow-centric authoring is the default path"
                          description="Topology editor remains for structural metadata and publication slot assignment. Author concrete document policies in /decisions and pin them in workflow bindings."
                        />
                        {topologyBlockingRemediations.map((remediation) => (
                          <Alert
                            key={remediation.code}
                            type="warning"
                            showIcon
                            style={{ marginBottom: 12 }}
                            message={remediation.title}
                            description={remediation.detail}
                            action={(
                              <Space size={8}>
                                <Button size="small" onClick={() => { navigate('/decisions') }}>
                                  Open /decisions
                                </Button>
                                <Button size="small" onClick={() => { handleOpenBindingsWorkspace() }}>
                                  Open Bindings
                                </Button>
                              </Space>
                            )}
                          />
                        ))}
                        <Row gutter={12} style={{ marginBottom: 12 }}>
                          <Col span={12}>
                            <Form.Item label="Coverage binding context" style={{ marginBottom: 0 }}>
                              <Select
                                allowClear
                                showSearch
                                optionFilterProp="label"
                                placeholder="Select active binding for slot coverage"
                                options={topologyCoverageBindingOptions}
                                value={topologyCoverageBindingId}
                                onChange={(value) => {
                                  setTopologyCoverageBindingId(
                                    typeof value === 'string' && value.trim() ? value : undefined
                                  )
                                }}
                                disabled={!selectedPool || isPoolBindingsLoading || topologyCoverageBindingOptions.length === 0}
                                notFoundContent={(
                                  isPoolBindingsLoading
                                    ? 'Loading bindings...'
                                    : 'No active bindings'
                                )}
                                data-testid="pool-catalog-topology-coverage-binding"
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Space direction="vertical" size={4} style={{ width: '100%' }}>
                              <Text strong>Coverage status</Text>
                              <Space wrap>
                                <Tag
                                  color={(
                                    topologyCoverageContext.status === 'resolved'
                                      ? 'success'
                                      : topologyCoverageContext.status === 'ambiguous'
                                        ? 'warning'
                                        : 'default'
                                  )}
                                  data-testid="pool-catalog-topology-coverage-status"
                                >
                                  {(
                                    topologyCoverageContext.status === 'resolved'
                                      ? topologyCoverageContext.source === 'auto'
                                        ? 'Auto-resolved binding'
                                        : 'Selected binding'
                                      : topologyCoverageContext.status === 'ambiguous'
                                        ? 'Ambiguous context'
                                        : 'Coverage unavailable'
                                  )}
                                </Tag>
                                <Text type="secondary">{topologyCoverageContext.detail}</Text>
                              </Space>
                            </Space>
                          </Col>
                        </Row>
                        {poolBindingsLoadError && (
                          <Alert
                            type="warning"
                            showIcon
                            style={{ marginBottom: 12 }}
                            message="Coverage bindings could not be loaded"
                            description={poolBindingsLoadError}
                          />
                        )}

                        <Row gutter={12} style={{ marginBottom: 12 }}>
                          <Col span={12}>
                            <Form.Item label="Authoring path" name="authoring_mode" style={{ marginBottom: 0 }}>
                              <Select
                                options={[
                                  { value: 'template', label: 'Template-based instantiation' },
                                  { value: 'manual', label: 'Manual snapshot editor' },
                                ]}
                                data-testid="pool-catalog-topology-authoring-mode"
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Space direction="vertical" size={4} style={{ width: '100%' }}>
                              <Text strong>Current mode</Text>
                              <Text type="secondary">
                                {isTemplateTopologyAuthoring
                                  ? 'Topology template revision + slot assignment'
                                  : 'Concrete nodes/edges authoring'}
                              </Text>
                            </Space>
                          </Col>
                        </Row>

                        {isTemplateTopologyAuthoring ? (
                          <Space direction="vertical" size={12} style={{ width: '100%', marginBottom: 12 }}>
                            <Alert
                              type="info"
                              showIcon
                              message="Template-based path is the preferred reuse flow"
                              description="Выберите published topology template revision, назначьте организации в slot-ы и при необходимости задайте explicit selector override для edge. Concrete graph materialize'ится в текущий pool snapshot при сохранении."
                            />
                            {topologyTemplatesLoadError && (
                              <Alert
                                type="warning"
                                showIcon
                                message={topologyTemplatesLoadError}
                                action={(
                                  <Button
                                    size="small"
                                    onClick={() => { void loadTopologyTemplates({ force: true }) }}
                                    loading={loadingTopologyTemplates}
                                  >
                                    Retry templates
                                  </Button>
                                )}
                              />
                            )}
                            <Row gutter={12}>
                              <Col span={12}>
                                <Form.Item
                                  label="Topology template revision"
                                  name="topology_template_revision_id"
                                  style={{ marginBottom: 0 }}
                                >
                                  <Select
                                    showSearch
                                    optionFilterProp="label"
                                    placeholder="Select topology template revision"
                                    options={topologyTemplateRevisionOptions}
                                    loading={loadingTopologyTemplates}
                                    data-testid="pool-catalog-topology-template-revision"
                                  />
                                </Form.Item>
                              </Col>
                              <Col span={12}>
                                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                  <Text strong>Template summary</Text>
                                  {selectedTopologyTemplate && selectedTopologyTemplateRevision ? (
                                    <Descriptions size="small" column={1} bordered>
                                      <Descriptions.Item label="Template">
                                        {selectedTopologyTemplate.name}
                                      </Descriptions.Item>
                                      <Descriptions.Item label="Revision">
                                        {`r${selectedTopologyTemplateRevision.revision_number}`}
                                      </Descriptions.Item>
                                      <Descriptions.Item label="Edges">
                                        {selectedTopologyTemplateRevision.edges.length}
                                      </Descriptions.Item>
                                    </Descriptions>
                                  ) : (
                                    <Text type="secondary">Выберите revision из topology template catalog.</Text>
                                  )}
                                </Space>
                              </Col>
                            </Row>

                            <Text strong>Slot assignments</Text>
                            <Form.List name="slot_assignments">
                              {(fields) => (
                                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                  {fields.length === 0 && (
                                    <Text type="secondary">
                                      Сначала выберите topology template revision.
                                    </Text>
                                  )}
                                  {fields.map((field) => (
                                    <Row key={field.key} gutter={12} align="middle">
                                      <Col span={8}>
                                        <Form.Item
                                          name={[field.name, 'slot_key']}
                                          label={field.name === 0 ? 'Slot key' : ''}
                                          style={{ marginBottom: 0 }}
                                        >
                                          <Input
                                            disabled
                                            data-testid={`pool-catalog-topology-template-slot-key-${field.name}`}
                                          />
                                        </Form.Item>
                                      </Col>
                                      <Col span={16}>
                                        <Form.Item
                                          name={[field.name, 'organization_id']}
                                          label={field.name === 0 ? 'Organization' : ''}
                                          style={{ marginBottom: 0 }}
                                        >
                                          <Select
                                            showSearch
                                            optionFilterProp="label"
                                            placeholder="Assign organization to slot"
                                            options={organizationOptions}
                                            data-testid={`pool-catalog-topology-template-slot-org-${field.name}`}
                                          />
                                        </Form.Item>
                                      </Col>
                                    </Row>
                                  ))}
                                </Space>
                              )}
                            </Form.List>

                            <Text strong>Template edge selector overrides</Text>
                            <Form.List name="edge_selector_overrides">
                              {(fields) => (
                                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                  {fields.length === 0 && (
                                    <Text type="secondary">
                                      После выбора revision здесь появятся materialized template edge selectors.
                                    </Text>
                                  )}
                                  {fields.map((field) => {
                                    const templateEdge = selectedTopologyTemplateRevision?.edges[field.name]
                                    const parentSlotKey = String(templateEdge?.parent_slot_key || '').trim()
                                    const childSlotKey = String(templateEdge?.child_slot_key || '').trim()
                                    const defaultSelector = String(templateEdge?.document_policy_key || '').trim()

                                    return (
                                      <Space
                                        key={field.key}
                                        direction="vertical"
                                        size={6}
                                        style={{ width: '100%' }}
                                      >
                                        <Row gutter={12} align="middle">
                                          <Col span={8}>
                                            <Form.Item
                                              name={[field.name, 'parent_slot_key']}
                                              label={field.name === 0 ? 'Parent slot' : ''}
                                              style={{ marginBottom: 0 }}
                                            >
                                              <Input
                                                disabled
                                                data-testid={`pool-catalog-topology-template-edge-parent-${field.name}`}
                                              />
                                            </Form.Item>
                                          </Col>
                                          <Col span={8}>
                                            <Form.Item
                                              name={[field.name, 'child_slot_key']}
                                              label={field.name === 0 ? 'Child slot' : ''}
                                              style={{ marginBottom: 0 }}
                                            >
                                              <Input
                                                disabled
                                                data-testid={`pool-catalog-topology-template-edge-child-${field.name}`}
                                              />
                                            </Form.Item>
                                          </Col>
                                          <Col span={8}>
                                            <Form.Item noStyle shouldUpdate>
                                              {({ getFieldValue }) => {
                                                const currentSlotKey = String(
                                                  getFieldValue(['edge_selector_overrides', field.name, 'document_policy_key']) || ''
                                                ).trim()
                                                const effectiveSlotKey = currentSlotKey || defaultSelector
                                                const slotCoverage = resolveTopologySlotCoverage(
                                                  effectiveSlotKey,
                                                  topologyCoverageContext
                                                )
                                                const currentSlotOptions = (
                                                  currentSlotKey
                                                  && !topologySlotOptions.some((option) => option.value === currentSlotKey)
                                                )
                                                  ? [
                                                      {
                                                        value: currentSlotKey,
                                                        label: `${currentSlotKey} · current override`,
                                                      },
                                                      ...topologySlotOptions,
                                                    ]
                                                  : topologySlotOptions

                                                return (
                                                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                                                    <Form.Item
                                                      name={[field.name, 'document_policy_key']}
                                                      label={field.name === 0 ? 'Override selector' : ''}
                                                      style={{ marginBottom: 0 }}
                                                    >
                                                      {currentSlotOptions.length > 0 ? (
                                                        <Select
                                                          allowClear
                                                          showSearch
                                                          optionFilterProp="label"
                                                          placeholder={defaultSelector || 'Override template selector'}
                                                          options={currentSlotOptions}
                                                          data-testid={`pool-catalog-topology-template-edge-slot-${field.name}`}
                                                        />
                                                      ) : (
                                                        <Input
                                                          placeholder={defaultSelector || 'sale'}
                                                          data-testid={`pool-catalog-topology-template-edge-slot-${field.name}`}
                                                        />
                                                      )}
                                                    </Form.Item>
                                                    <Space wrap size={8}>
                                                      <Tag color={defaultSelector ? 'blue' : 'default'}>
                                                        {defaultSelector
                                                          ? `Template default: ${defaultSelector}`
                                                          : 'Template default missing'}
                                                      </Tag>
                                                      <Tag
                                                        color={(
                                                          slotCoverage.status === 'resolved'
                                                            ? 'success'
                                                            : slotCoverage.status === 'missing_selector'
                                                              ? 'default'
                                                              : slotCoverage.status === 'ambiguous_context'
                                                                || slotCoverage.status === 'ambiguous_slot'
                                                                ? 'warning'
                                                                : 'error'
                                                        )}
                                                        data-testid={`pool-catalog-topology-template-edge-slot-status-${field.name}`}
                                                      >
                                                        {slotCoverage.label}
                                                      </Tag>
                                                      <Text type="secondary">
                                                        {slotCoverage.detail || `${parentSlotKey} -> ${childSlotKey}`}
                                                      </Text>
                                                    </Space>
                                                  </Space>
                                                )
                                              }}
                                            </Form.Item>
                                          </Col>
                                        </Row>
                                      </Space>
                                    )
                                  })}
                                </Space>
                              )}
                            </Form.List>
                          </Space>
                        ) : (
                          <Alert
                            type="info"
                            showIcon
                            style={{ marginBottom: 12 }}
                            message="Manual topology editor remains a fallback path"
                            description="Используйте его для нестандартных схем или remediation cases, когда reusable topology template ещё не опубликован."
                          />
                        )}

                        <Space direction="vertical" size={8} style={{ width: '100%', marginBottom: 12 }}>
                          <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
                            <Text strong>Topology snapshots by date</Text>
                            <Button
                              size="small"
                              onClick={() => { void loadTopologySnapshots({ force: true }) }}
                              loading={loadingTopologySnapshots}
                            >
                              Refresh snapshots
                            </Button>
                          </Space>
                          <Table<PoolTopologySnapshotPeriod>
                            size="small"
                            pagination={false}
                            loading={loadingTopologySnapshots}
                            rowKey={(item) => `${item.effective_from}:${item.effective_to || 'open'}`}
                            dataSource={topologySnapshots}
                            columns={[
                              {
                                title: 'From',
                                dataIndex: 'effective_from',
                                key: 'effective_from',
                                width: 140,
                              },
                              {
                                title: 'To',
                                key: 'effective_to',
                                width: 140,
                                render: (_value: unknown, record) => record.effective_to || 'open',
                              },
                              {
                                title: 'Nodes',
                                dataIndex: 'nodes_count',
                                key: 'nodes_count',
                                width: 80,
                              },
                              {
                                title: 'Edges',
                                dataIndex: 'edges_count',
                                key: 'edges_count',
                                width: 80,
                              },
                              {
                                title: '',
                                key: 'action',
                                width: 120,
                                render: (_value: unknown, record) => (
                                  <Button
                                    size="small"
                                    type={graphDate === record.effective_from ? 'primary' : 'default'}
                                    onClick={() => handleGraphDateChange(record.effective_from)}
                                    data-testid={`pool-catalog-topology-snapshot-open-${record.effective_from}`}
                                  >
                                    Open
                                  </Button>
                                ),
                              },
                            ]}
                          />
                        </Space>

                        {!isTemplateTopologyAuthoring && (
                          <>
                            <Text strong>Nodes</Text>
                            <Form.List name="nodes">
                          {(fields, { add, remove, move }) => (
                            <Space direction="vertical" size="small" style={{ width: '100%' }}>
                              {fields.map((field) => (
                                <Space key={field.key} direction="vertical" size={8} style={{ width: '100%' }}>
                                  <Row gutter={12} align="middle">
                                    <Col span={16}>
                                      <Form.Item
                                        name={[field.name, 'organization_id']}
                                        label={field.name === 0 ? 'Organization' : ''}
                                        style={{ marginBottom: 0 }}
                                      >
                                        <Select
                                          showSearch
                                          optionFilterProp="label"
                                          placeholder="Select organization"
                                          options={organizationOptions}
                                        />
                                      </Form.Item>
                                    </Col>
                                    <Col span={4}>
                                      <Form.Item
                                        name={[field.name, 'is_root']}
                                        valuePropName="checked"
                                        label={field.name === 0 ? 'Root' : ''}
                                        style={{ marginBottom: 0 }}
                                      >
                                        <Switch />
                                      </Form.Item>
                                    </Col>
                                    <Col span={4}>
                                      <Space size={4}>
                                        <Button
                                          aria-label="Move node up"
                                          icon={<ArrowUpOutlined />}
                                          onClick={() => move(field.name, field.name - 1)}
                                          disabled={field.name === 0}
                                          data-testid={`pool-catalog-topology-node-move-up-${field.name}`}
                                        />
                                        <Button
                                          aria-label="Move node down"
                                          icon={<ArrowDownOutlined />}
                                          onClick={() => move(field.name, field.name + 1)}
                                          disabled={field.name === fields.length - 1}
                                          data-testid={`pool-catalog-topology-node-move-down-${field.name}`}
                                        />
                                        <Button danger onClick={() => remove(field.name)}>
                                          Remove
                                        </Button>
                                      </Space>
                                    </Col>
                                  </Row>
                                  <Collapse
                                    size="small"
                                    items={[
                                      {
                                        key: `node-advanced-${field.key}`,
                                        label: 'Advanced node JSON',
                                        children: (
                                          <Form.Item
                                            name={[field.name, 'metadata_json']}
                                            label="Node metadata (JSON)"
                                            style={{ marginBottom: 0 }}
                                          >
                                            <TextArea
                                              autoSize={{ minRows: 2, maxRows: 6 }}
                                              placeholder='{"priority":1}'
                                              data-testid={`pool-catalog-topology-node-metadata-${field.name}`}
                                            />
                                          </Form.Item>
                                        ),
                                      },
                                    ]}
                                  />
                                </Space>
                              ))}
                              <Button
                                onClick={() => add({ organization_id: undefined, is_root: false, metadata_json: '' })}
                                data-testid="pool-catalog-topology-add-node"
                              >
                                Add node
                              </Button>
                            </Space>
                          )}
                            </Form.List>

                            <Text strong style={{ marginTop: 12 }}>Edges</Text>
                            <Form.List name="edges">
                          {(fields, { add, remove, move }) => (
                            <Space direction="vertical" size="small" style={{ width: '100%' }}>
                              {fields.map((field) => (
                                <Space
                                  key={field.key}
                                  direction="vertical"
                                  size={6}
                                  style={{ width: '100%' }}
                                >
                                  <Row gutter={8} align="middle">
                                    <Col span={7}>
                                      <Form.Item
                                        name={[field.name, 'parent_organization_id']}
                                        label={field.name === 0 ? 'Parent' : ''}
                                        style={{ marginBottom: 0 }}
                                      >
                                        <Select options={organizationOptions} placeholder="Parent" />
                                      </Form.Item>
                                    </Col>
                                    <Col span={7}>
                                      <Form.Item
                                        name={[field.name, 'child_organization_id']}
                                        label={field.name === 0 ? 'Child' : ''}
                                        style={{ marginBottom: 0 }}
                                      >
                                        <Select options={organizationOptions} placeholder="Child" />
                                      </Form.Item>
                                    </Col>
                                    <Col span={8}>
                                      <Form.Item noStyle shouldUpdate>
                                        {({ getFieldValue }) => {
                                          const currentSlotKey = String(
                                            getFieldValue(['edges', field.name, 'document_policy_key']) || ''
                                          ).trim()
                                          const currentSlotOptions = (
                                            currentSlotKey
                                            && !topologySlotOptions.some((option) => option.value === currentSlotKey)
                                          )
                                            ? [
                                                {
                                                  value: currentSlotKey,
                                                  label: `${currentSlotKey} · current edge value`,
                                                },
                                                ...topologySlotOptions,
                                              ]
                                            : topologySlotOptions

                                          return (
                                            <Form.Item
                                              name={[field.name, 'document_policy_key']}
                                              label={field.name === 0 ? 'Publication slot' : ''}
                                              style={{ marginBottom: 0 }}
                                            >
                                              {currentSlotOptions.length > 0 ? (
                                                <Select
                                                  showSearch
                                                  optionFilterProp="label"
                                                  placeholder="Select publication slot from bindings"
                                                  options={currentSlotOptions}
                                                  data-testid={`pool-catalog-topology-edge-slot-${field.name}`}
                                                />
                                              ) : (
                                                <Input
                                                  placeholder="sale"
                                                  data-testid={`pool-catalog-topology-edge-slot-${field.name}`}
                                                />
                                              )}
                                            </Form.Item>
                                          )
                                        }}
                                      </Form.Item>
                                    </Col>
                                    <Col span={2}>
                                      <Space size={4}>
                                        <Button
                                          aria-label="Move edge up"
                                          icon={<ArrowUpOutlined />}
                                          onClick={() => move(field.name, field.name - 1)}
                                          disabled={field.name === 0}
                                          data-testid={`pool-catalog-topology-edge-move-up-${field.name}`}
                                        />
                                        <Button
                                          aria-label="Move edge down"
                                          icon={<ArrowDownOutlined />}
                                          onClick={() => move(field.name, field.name + 1)}
                                          disabled={field.name === fields.length - 1}
                                          data-testid={`pool-catalog-topology-edge-move-down-${field.name}`}
                                        />
                                        <Button danger onClick={() => remove(field.name)}>x</Button>
                                      </Space>
                                    </Col>
                                  </Row>
                                  <Row gutter={8} align="middle">
                                    <Col span={4}>
                                      <Form.Item
                                        name={[field.name, 'weight']}
                                        label={field.name === 0 ? 'Weight' : ''}
                                        style={{ marginBottom: 0 }}
                                      >
                                        <InputNumber min={0.000001} step={0.1} style={{ width: '100%' }} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={4}>
                                      <Form.Item
                                        name={[field.name, 'min_amount']}
                                        label={field.name === 0 ? 'Min' : ''}
                                        style={{ marginBottom: 0 }}
                                      >
                                        <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={4}>
                                      <Form.Item
                                        name={[field.name, 'max_amount']}
                                        label={field.name === 0 ? 'Max' : ''}
                                        style={{ marginBottom: 0 }}
                                      >
                                        <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                  <Form.Item noStyle shouldUpdate>
                                    {({ getFieldValue }) => {
                                      const slotCoverage = resolveTopologySlotCoverage(
                                        getFieldValue(['edges', field.name, 'document_policy_key']),
                                        topologyCoverageContext
                                      )
                                      return (
                                        <Space wrap size={8}>
                                          <Tag
                                            color={(
                                              slotCoverage.status === 'resolved'
                                                ? 'success'
                                                : slotCoverage.status === 'missing_selector'
                                                  ? 'default'
                                                  : slotCoverage.status === 'ambiguous_context'
                                                    || slotCoverage.status === 'ambiguous_slot'
                                                    ? 'warning'
                                                    : 'error'
                                            )}
                                            data-testid={`pool-catalog-topology-edge-slot-status-${field.name}`}
                                          >
                                            {slotCoverage.label}
                                          </Tag>
                                          <Text type="secondary">{slotCoverage.detail}</Text>
                                        </Space>
                                      )
                                    }}
                                  </Form.Item>
                                  <Collapse
                                    size="small"
                                    items={[
                                      {
                                        key: `edge-advanced-${field.key}`,
                                        label: 'Advanced edge metadata',
                                        children: (
                                          <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                            <Form.Item noStyle shouldUpdate>
                                              {({ getFieldValue }) => {
                                                const policyMode = (
                                                  String(getFieldValue(['edges', field.name, 'document_policy_mode']) || 'raw')
                                                    .trim()
                                                    .toLowerCase() === 'builder'
                                                    ? 'builder'
                                                    : 'raw'
                                                )
                                                const edgeMetadataMode = (
                                                  String(getFieldValue(['edges', field.name, 'edge_metadata_mode']) || 'raw')
                                                    .trim()
                                                    .toLowerCase() === 'builder'
                                                    ? 'builder'
                                                    : 'raw'
                                                )
                                                const childOrgId = String(
                                                  getFieldValue(['edges', field.name, 'child_organization_id']) || ''
                                                ).trim()
                                                const childOrganization = organizationById[childOrgId]
                                                const databaseId = String(childOrganization?.database_id || '').trim()
                                                const metadataCatalog = (
                                                  databaseId
                                                    ? metadataCatalogByDatabase[databaseId]
                                                    : undefined
                                                )
                                                const metadataDocuments = Array.isArray(metadataCatalog?.documents)
                                                  ? metadataCatalog.documents
                                                  : []
                                                const metadataLoading = databaseId
                                                  ? Boolean(metadataCatalogLoadingByDatabase[databaseId])
                                                  : false
                                                const metadataError = databaseId
                                                  ? metadataCatalogErrorByDatabase[databaseId]
                                                  : ''

                                                return (
                                                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                                    {policyMode === 'builder' && TOPOLOGY_DOCUMENT_POLICY_BUILDER_ENABLED ? (
                                                      <>
                                                        {!databaseId && (
                                                          <Alert
                                                            type="warning"
                                                            showIcon
                                                            message="Builder требует child organization с привязанной базой."
                                                          />
                                                        )}
                                                        {databaseId && (
                                                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                            <Space size="small" wrap>
                                                              <Tag color={metadataCatalog ? 'blue' : metadataLoading ? 'processing' : 'default'}>
                                                                {metadataCatalog
                                                                  ? `каталог ${metadataCatalog?.catalog_version} • документов ${metadataDocuments.length}`
                                                                  : metadataLoading
                                                                    ? 'metadata context загружается'
                                                                    : 'metadata context недоступен'}
                                                              </Tag>
                                                              <Button
                                                                size="small"
                                                                onClick={() => { navigate('/databases') }}
                                                                data-testid={`pool-catalog-topology-edge-policy-open-databases-${field.name}`}
                                                              >
                                                                Открыть /databases
                                                              </Button>
                                                            </Space>
                                                            <Text type="secondary">
                                                              Configuration profile и metadata snapshot управляются на странице /databases. В topology editor используется только текущий metadata context.
                                                            </Text>
                                                          </Space>
                                                        )}
                                                        {metadataError && (
                                                          <Alert
                                                            type="error"
                                                            showIcon
                                                            message={metadataError}
                                                            action={(
                                                              <Button
                                                                size="small"
                                                                onClick={() => { navigate('/databases') }}
                                                                data-testid={`pool-catalog-topology-edge-policy-error-open-databases-${field.name}`}
                                                              >
                                                                Открыть /databases
                                                              </Button>
                                                            )}
                                                          />
                                                        )}
                                                        {masterDataTokenCatalogError && (
                                                          <Alert
                                                            type="warning"
                                                            showIcon
                                                            message={masterDataTokenCatalogError}
                                                            action={(
                                                              <Button
                                                                size="small"
                                                                onClick={() => { void loadMasterDataTokenCatalog() }}
                                                                loading={loadingMasterDataTokenCatalog}
                                                              >
                                                                Retry token catalog
                                                              </Button>
                                                            )}
                                                          />
                                                        )}
                                                        <Form.List name={[field.name, 'document_policy_builder']}>
                                                          {(chainFields, { add: addChain, remove: removeChain, move: moveChain }) => (
                                                            <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                                              {chainFields.map((chainField) => (
                                                                <Card
                                                                  key={chainField.key}
                                                                  size="small"
                                                                  title={`Chain #${chainField.name + 1}`}
                                                                  extra={(
                                                                    <Space size={4}>
                                                                      <Button
                                                                        size="small"
                                                                        icon={<ArrowUpOutlined />}
                                                                        onClick={() => moveChain(chainField.name, chainField.name - 1)}
                                                                        disabled={chainField.name === 0}
                                                                      />
                                                                      <Button
                                                                        size="small"
                                                                        icon={<ArrowDownOutlined />}
                                                                        onClick={() => moveChain(chainField.name, chainField.name + 1)}
                                                                        disabled={chainField.name === chainFields.length - 1}
                                                                      />
                                                                      <Button
                                                                        size="small"
                                                                        danger
                                                                        onClick={() => removeChain(chainField.name)}
                                                                      >
                                                                        Remove
                                                                      </Button>
                                                                    </Space>
                                                                  )}
                                                                >
                                                                  <Form.Item
                                                                    name={[chainField.name, 'chain_id']}
                                                                    label="chain_id"
                                                                    style={{ marginBottom: 8 }}
                                                                  >
                                                                    <Input placeholder="sale_chain" />
                                                                  </Form.Item>

                                                                  <Form.List name={[chainField.name, 'documents']}>
                                                                    {(documentFields, { add: addDocument, remove: removeDocument, move: moveDocument }) => (
                                                                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                                                        {documentFields.map((documentField) => {
                                                                          const selectedEntityName = String(
                                                                            getFieldValue([
                                                                              'edges',
                                                                              field.name,
                                                                              'document_policy_builder',
                                                                              chainField.name,
                                                                              'documents',
                                                                              documentField.name,
                                                                              'entity_name',
                                                                            ]) || ''
                                                                          ).trim()
                                                                          const selectedDocument = metadataDocuments.find(
                                                                            (item) => item.entity_name === selectedEntityName
                                                                          )
                                                                          const fieldOptions = (
                                                                            selectedDocument?.fields || []
                                                                          ).map((item) => ({
                                                                            value: item.name,
                                                                            label: item.name,
                                                                          }))
                                                                          const tablePartOptions = (
                                                                            selectedDocument?.table_parts || []
                                                                          ).map((item) => ({
                                                                            value: item.name,
                                                                            label: item.name,
                                                                          }))
                                                                          const chainDocuments = (
                                                                            getFieldValue([
                                                                              'edges',
                                                                              field.name,
                                                                              'document_policy_builder',
                                                                              chainField.name,
                                                                              'documents',
                                                                            ]) || []
                                                                          ) as DocumentPolicyBuilderDocumentFormValue[]
                                                                          const linkToOptions = chainDocuments
                                                                            .map((item) => String(item?.document_id || '').trim())
                                                                            .filter((item) => item)
                                                                          const uniqueLinkToOptions = Array.from(new Set(linkToOptions))
                                                                            .map((item) => ({ value: item, label: item }))

                                                                          return (
                                                                            <Card
                                                                              key={documentField.key}
                                                                              size="small"
                                                                              title={`Document #${documentField.name + 1}`}
                                                                              extra={(
                                                                                <Space size={4}>
                                                                                  <Button
                                                                                    size="small"
                                                                                    icon={<ArrowUpOutlined />}
                                                                                    onClick={() => moveDocument(documentField.name, documentField.name - 1)}
                                                                                    disabled={documentField.name === 0}
                                                                                  />
                                                                                  <Button
                                                                                    size="small"
                                                                                    icon={<ArrowDownOutlined />}
                                                                                    onClick={() => moveDocument(documentField.name, documentField.name + 1)}
                                                                                    disabled={documentField.name === documentFields.length - 1}
                                                                                  />
                                                                                  <Button
                                                                                    size="small"
                                                                                    danger
                                                                                    onClick={() => removeDocument(documentField.name)}
                                                                                  >
                                                                                    Remove
                                                                                  </Button>
                                                                                </Space>
                                                                              )}
                                                                            >
                                                                              <Row gutter={8}>
                                                                                <Col span={8}>
                                                                                  <Form.Item
                                                                                    name={[documentField.name, 'document_id']}
                                                                                    label="document_id"
                                                                                    style={{ marginBottom: 8 }}
                                                                                  >
                                                                                    <Input placeholder="sale" />
                                                                                  </Form.Item>
                                                                                </Col>
                                                                                <Col span={8}>
                                                                                  <Form.Item
                                                                                    name={[documentField.name, 'entity_name']}
                                                                                    label="entity_name"
                                                                                    style={{ marginBottom: 8 }}
                                                                                  >
                                                                                    <Select
                                                                                      showSearch
                                                                                      optionFilterProp="label"
                                                                                      options={metadataDocuments.map((item: PoolODataMetadataCatalogDocument) => ({
                                                                                        value: item.entity_name,
                                                                                        label: `${item.entity_name} (${item.display_name})`,
                                                                                      }))}
                                                                                    />
                                                                                  </Form.Item>
                                                                                </Col>
                                                                                <Col span={8}>
                                                                                  <Form.Item
                                                                                    name={[documentField.name, 'document_role']}
                                                                                    label="document_role"
                                                                                    style={{ marginBottom: 8 }}
                                                                                  >
                                                                                    <Input placeholder="sale|invoice" />
                                                                                  </Form.Item>
                                                                                </Col>
                                                                              </Row>
                                                                              <Row gutter={8}>
                                                                                <Col span={8}>
                                                                                  <Form.Item
                                                                                    name={[documentField.name, 'invoice_mode']}
                                                                                    label="invoice_mode"
                                                                                    style={{ marginBottom: 8 }}
                                                                                  >
                                                                                    <Select
                                                                                      options={[
                                                                                        { value: 'optional', label: 'optional' },
                                                                                        { value: 'required', label: 'required' },
                                                                                      ]}
                                                                                    />
                                                                                  </Form.Item>
                                                                                </Col>
                                                                                <Col span={16}>
                                                                                  <Form.Item
                                                                                    name={[documentField.name, 'link_to']}
                                                                                    label="link_to"
                                                                                    style={{ marginBottom: 8 }}
                                                                                  >
                                                                                    <Select
                                                                                      allowClear
                                                                                      showSearch
                                                                                      optionFilterProp="label"
                                                                                      options={uniqueLinkToOptions}
                                                                                      placeholder="document_id from this chain"
                                                                                      notFoundContent="Сначала задайте document_id для документов в этой цепочке."
                                                                                    />
                                                                                  </Form.Item>
                                                                                </Col>
                                                                              </Row>
                                                                              {uniqueLinkToOptions.length === 0 && (
                                                                                <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                                                                                  link_to доступен после добавления в цепочку второго документа с `document_id`.
                                                                                </Text>
                                                                              )}
                                                                              {selectedEntityName && !selectedDocument && (
                                                                                <Alert
                                                                                  type="warning"
                                                                                  showIcon
                                                                                  style={{ marginBottom: 8 }}
                                                                                  message={(
                                                                                    `Entity "${selectedEntityName}" не найден в загруженном metadata catalog.`
                                                                                  )}
                                                                                  description="Проверьте metadata snapshot через /databases или выберите другой entity_name."
                                                                                />
                                                                              )}
                                                                              {selectedDocument && fieldOptions.length === 0 && (
                                                                                <Alert
                                                                                  type="warning"
                                                                                  showIcon
                                                                                  style={{ marginBottom: 8 }}
                                                                                  message={(
                                                                                    `Для "${selectedEntityName}" в metadata catalog нет fields.`
                                                                                  )}
                                                                                  description={(
                                                                                    'Проверьте metadata snapshot через /databases, включая BaseType-наследование и publication drift.'
                                                                                  )}
                                                                                />
                                                                              )}

                                                                              <Form.List name={[documentField.name, 'link_rule_mappings']}>
                                                                                {(linkRuleFields, { add: addLinkRule, remove: removeLinkRule }) => (
                                                                                  <Space direction="vertical" size={4} style={{ width: '100%', marginBottom: 8 }}>
                                                                                    <Text type="secondary">link_rules</Text>
                                                                                    {linkRuleFields.map((linkRuleField) => (
                                                                                      <Row key={linkRuleField.key} gutter={8} align="middle">
                                                                                        <Col span={9}>
                                                                                          <Form.Item
                                                                                            name={[linkRuleField.name, 'target_field']}
                                                                                            style={{ marginBottom: 0 }}
                                                                                          >
                                                                                            <Input placeholder="rule key" />
                                                                                          </Form.Item>
                                                                                        </Col>
                                                                                        <Col span={12}>
                                                                                          <Form.Item
                                                                                            name={[linkRuleField.name, 'source']}
                                                                                            style={{ marginBottom: 0 }}
                                                                                          >
                                                                                            <Input placeholder="sale.document_id" />
                                                                                          </Form.Item>
                                                                                        </Col>
                                                                                        <Col span={3}>
                                                                                          <Button danger onClick={() => removeLinkRule(linkRuleField.name)}>
                                                                                            x
                                                                                          </Button>
                                                                                        </Col>
                                                                                      </Row>
                                                                                    ))}
                                                                                    <Button
                                                                                      size="small"
                                                                                      onClick={() => addLinkRule({ target_field: '', source: '' })}
                                                                                    >
                                                                                      Add link rule
                                                                                    </Button>
                                                                                  </Space>
                                                                                )}
                                                                              </Form.List>

                                                                              <Form.List name={[documentField.name, 'field_mappings']}>
                                                                                {(fieldMappingFields, { add: addFieldMapping, remove: removeFieldMapping }) => (
                                                                                  <Space direction="vertical" size={4} style={{ width: '100%', marginBottom: 8 }}>
                                                                                    <Text type="secondary">field_mapping</Text>
                                                                                    {fieldMappingFields.map((mappingField) => {
                                                                                      const sourceType = (
                                                                                        String(
                                                                                          getFieldValue([
                                                                                            'edges',
                                                                                            field.name,
                                                                                            'document_policy_builder',
                                                                                            chainField.name,
                                                                                            'documents',
                                                                                            documentField.name,
                                                                                            'field_mappings',
                                                                                            mappingField.name,
                                                                                            'source_type',
                                                                                          ]) || 'expression'
                                                                                        )
                                                                                          .trim()
                                                                                          .toLowerCase() === 'master_data_token'
                                                                                          ? 'master_data_token'
                                                                                          : 'expression'
                                                                                      )
                                                                                      const tokenEntityType = String(
                                                                                        getFieldValue([
                                                                                          'edges',
                                                                                          field.name,
                                                                                          'document_policy_builder',
                                                                                          chainField.name,
                                                                                          'documents',
                                                                                          documentField.name,
                                                                                          'field_mappings',
                                                                                          mappingField.name,
                                                                                          'token_entity_type',
                                                                                        ]) || ''
                                                                                      ).trim()
                                                                                      const tokenCanonicalId = String(
                                                                                        getFieldValue([
                                                                                          'edges',
                                                                                          field.name,
                                                                                          'document_policy_builder',
                                                                                          chainField.name,
                                                                                          'documents',
                                                                                          documentField.name,
                                                                                          'field_mappings',
                                                                                          mappingField.name,
                                                                                          'token_canonical_id',
                                                                                        ]) || ''
                                                                                      ).trim()
                                                                                      const tokenPartyRole = String(
                                                                                        getFieldValue([
                                                                                          'edges',
                                                                                          field.name,
                                                                                          'document_policy_builder',
                                                                                          chainField.name,
                                                                                          'documents',
                                                                                          documentField.name,
                                                                                          'field_mappings',
                                                                                          mappingField.name,
                                                                                          'token_party_role',
                                                                                        ]) || ''
                                                                                      ).trim()
                                                                                      const tokenOwnerCounterpartyCanonicalId = String(
                                                                                        getFieldValue([
                                                                                          'edges',
                                                                                          field.name,
                                                                                          'document_policy_builder',
                                                                                          chainField.name,
                                                                                          'documents',
                                                                                          documentField.name,
                                                                                          'field_mappings',
                                                                                          mappingField.name,
                                                                                          'token_owner_counterparty_canonical_id',
                                                                                        ]) || ''
                                                                                      ).trim()
                                                                                      const contractOwnerDefault = (
                                                                                        tokenEntityType === 'contract' && tokenCanonicalId
                                                                                          ? String(
                                                                                            masterDataContractByCanonicalId[tokenCanonicalId]?.owner_counterparty_canonical_id
                                                                                            || ''
                                                                                          ).trim()
                                                                                          : ''
                                                                                      )
                                                                                      const tokenCanonicalOptions = (
                                                                                        tokenEntityType === 'party'
                                                                                          ? masterDataPartyOptions
                                                                                          : tokenEntityType === 'item'
                                                                                            ? masterDataItemOptions
                                                                                            : tokenEntityType === 'contract'
                                                                                              ? masterDataContractOptions
                                                                                              : tokenEntityType === 'tax_profile'
                                                                                                ? masterDataTaxProfileOptions
                                                                                                : []
                                                                                      )
                                                                                      const ownerCounterpartyOptions = (
                                                                                        contractOwnerDefault
                                                                                        && !masterDataCounterpartyOptions.some(
                                                                                          (item) => item.value === contractOwnerDefault
                                                                                        )
                                                                                          ? [
                                                                                            ...masterDataCounterpartyOptions,
                                                                                            {
                                                                                              value: contractOwnerDefault,
                                                                                              label: contractOwnerDefault,
                                                                                            },
                                                                                          ]
                                                                                          : masterDataCounterpartyOptions
                                                                                      )
                                                                                      const tokenPreview = sourceType === 'master_data_token'
                                                                                        ? buildMasterDataToken({
                                                                                          token_entity_type: tokenEntityType as MasterDataTokenEntityType,
                                                                                          token_canonical_id: tokenCanonicalId,
                                                                                          token_party_role: tokenPartyRole as MasterDataTokenPartyRole,
                                                                                          token_owner_counterparty_canonical_id: (
                                                                                            tokenOwnerCounterpartyCanonicalId || contractOwnerDefault
                                                                                          ),
                                                                                        })
                                                                                        : null

                                                                                      return (
                                                                                        <Row key={mappingField.key} gutter={8} align="top">
                                                                                          <Col span={6}>
                                                                                            <Form.Item
                                                                                              name={[mappingField.name, 'target_field']}
                                                                                              style={{ marginBottom: 0 }}
                                                                                            >
                                                                                              <Select
                                                                                                showSearch
                                                                                                optionFilterProp="label"
                                                                                                options={fieldOptions}
                                                                                                placeholder="target field"
                                                                                                notFoundContent={(
                                                                                                  selectedEntityName
                                                                                                    ? 'Для выбранного entity_name нет fields в metadata catalog.'
                                                                                                    : 'Сначала выберите entity_name.'
                                                                                                )}
                                                                                              />
                                                                                            </Form.Item>
                                                                                          </Col>
                                                                                          <Col span={6}>
                                                                                            <Form.Item
                                                                                              name={[mappingField.name, 'source_type']}
                                                                                              style={{ marginBottom: 0 }}
                                                                                              initialValue="expression"
                                                                                            >
                                                                                              <Select
                                                                                                options={TOKEN_SOURCE_TYPE_OPTIONS}
                                                                                                data-testid={(
                                                                                                  `pool-catalog-topology-field-mapping-source-type-${field.name}-${chainField.name}-${documentField.name}-${mappingField.name}`
                                                                                                )}
                                                                                              />
                                                                                            </Form.Item>
                                                                                          </Col>
                                                                                          <Col span={9}>
                                                                                            {sourceType === 'master_data_token' ? (
                                                                                              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                                                                <Row gutter={8}>
                                                                                                  <Col span={8}>
                                                                                                    <Form.Item
                                                                                                      name={[mappingField.name, 'token_entity_type']}
                                                                                                      style={{ marginBottom: 0 }}
                                                                                                    >
                                                                                                      <Select
                                                                                                        placeholder="entity"
                                                                                                        options={TOKEN_ENTITY_TYPE_OPTIONS}
                                                                                                        loading={loadingMasterDataTokenCatalog}
                                                                                                        data-testid={(
                                                                                                          `pool-catalog-topology-field-mapping-token-entity-${field.name}-${chainField.name}-${documentField.name}-${mappingField.name}`
                                                                                                        )}
                                                                                                      />
                                                                                                    </Form.Item>
                                                                                                  </Col>
                                                                                                  <Col span={16}>
                                                                                                    <Form.Item
                                                                                                      name={[mappingField.name, 'token_canonical_id']}
                                                                                                      style={{ marginBottom: 0 }}
                                                                                                    >
                                                                                                      <Select
                                                                                                        showSearch
                                                                                                        optionFilterProp="label"
                                                                                                        allowClear
                                                                                                        placeholder="canonical_id"
                                                                                                        options={tokenCanonicalOptions}
                                                                                                        loading={loadingMasterDataTokenCatalog}
                                                                                                        data-testid={(
                                                                                                          `pool-catalog-topology-field-mapping-token-canonical-${field.name}-${chainField.name}-${documentField.name}-${mappingField.name}`
                                                                                                        )}
                                                                                                      />
                                                                                                    </Form.Item>
                                                                                                  </Col>
                                                                                                </Row>
                                                                                                {tokenEntityType === 'party' && (
                                                                                                  <Form.Item
                                                                                                    name={[mappingField.name, 'token_party_role']}
                                                                                                    style={{ marginBottom: 0 }}
                                                                                                  >
                                                                                                    <Select
                                                                                                      allowClear
                                                                                                      placeholder="party role"
                                                                                                      options={TOKEN_PARTY_ROLE_OPTIONS}
                                                                                                      data-testid={(
                                                                                                        `pool-catalog-topology-field-mapping-token-party-role-${field.name}-${chainField.name}-${documentField.name}-${mappingField.name}`
                                                                                                      )}
                                                                                                    />
                                                                                                  </Form.Item>
                                                                                                )}
                                                                                                {tokenEntityType === 'contract' && (
                                                                                                  <Form.Item
                                                                                                    name={[mappingField.name, 'token_owner_counterparty_canonical_id']}
                                                                                                    style={{ marginBottom: 0 }}
                                                                                                    initialValue={contractOwnerDefault || undefined}
                                                                                                  >
                                                                                                    <Select
                                                                                                      showSearch
                                                                                                      optionFilterProp="label"
                                                                                                      allowClear
                                                                                                      placeholder="owner_counterparty_canonical_id"
                                                                                                      options={ownerCounterpartyOptions}
                                                                                                      loading={loadingMasterDataTokenCatalog}
                                                                                                      data-testid={(
                                                                                                        `pool-catalog-topology-field-mapping-token-owner-${field.name}-${chainField.name}-${documentField.name}-${mappingField.name}`
                                                                                                      )}
                                                                                                    />
                                                                                                  </Form.Item>
                                                                                                )}
                                                                                                {tokenPreview ? (
                                                                                                  <Text code>{tokenPreview}</Text>
                                                                                                ) : (
                                                                                                  <Text type="secondary">
                                                                                                    Configure token fields.
                                                                                                  </Text>
                                                                                                )}
                                                                                              </Space>
                                                                                            ) : (
                                                                                              <Form.Item
                                                                                                name={[mappingField.name, 'expression_source']}
                                                                                                style={{ marginBottom: 0 }}
                                                                                              >
                                                                                                <Input placeholder="allocation.amount" />
                                                                                              </Form.Item>
                                                                                            )}
                                                                                          </Col>
                                                                                          <Col span={3}>
                                                                                            <Button danger onClick={() => removeFieldMapping(mappingField.name)}>
                                                                                              x
                                                                                            </Button>
                                                                                          </Col>
                                                                                        </Row>
                                                                                      )
                                                                                    })}
                                                                                    <Button
                                                                                      size="small"
                                                                                      onClick={() => addFieldMapping({
                                                                                        target_field: '',
                                                                                        source_type: 'expression',
                                                                                        expression_source: '',
                                                                                      })}
                                                                                    >
                                                                                      Add field mapping
                                                                                    </Button>
                                                                                  </Space>
                                                                                )}
                                                                              </Form.List>

                                                                              <Form.List name={[documentField.name, 'table_part_mappings']}>
                                                                                {(tablePartFields, { add: addTablePart, remove: removeTablePart }) => (
                                                                                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                                                    <Text type="secondary">table_parts_mapping</Text>
                                                                                    {tablePartFields.map((tablePartField) => {
                                                                                      const selectedTablePart = String(
                                                                                        getFieldValue([
                                                                                          'edges',
                                                                                          field.name,
                                                                                          'document_policy_builder',
                                                                                          chainField.name,
                                                                                          'documents',
                                                                                          documentField.name,
                                                                                          'table_part_mappings',
                                                                                          tablePartField.name,
                                                                                          'table_part',
                                                                                        ]) || ''
                                                                                      ).trim()
                                                                                      const tablePart = (selectedDocument?.table_parts || []).find(
                                                                                        (item) => item.name === selectedTablePart
                                                                                      )
                                                                                      const tablePartEntity = (
                                                                                        selectedTablePart
                                                                                          ? metadataDocuments.find(
                                                                                            (item) => (
                                                                                              item.entity_name
                                                                                                === `${selectedEntityName}_${selectedTablePart}`
                                                                                            )
                                                                                          )
                                                                                          : undefined
                                                                                      )
                                                                                      const rowFieldOptions = (
                                                                                        (
                                                                                          (tablePart?.row_fields || []).length > 0
                                                                                            ? tablePart?.row_fields
                                                                                            : (tablePartEntity?.fields || [])
                                                                                        ) || []
                                                                                      ).map((item) => ({
                                                                                        value: item.name,
                                                                                        label: item.name,
                                                                                      }))
                                                                                      return (
                                                                                        <Card
                                                                                          key={tablePartField.key}
                                                                                          size="small"
                                                                                          title={`Table part #${tablePartField.name + 1}`}
                                                                                          extra={(
                                                                                            <Button
                                                                                              size="small"
                                                                                              danger
                                                                                              onClick={() => removeTablePart(tablePartField.name)}
                                                                                            >
                                                                                              Remove
                                                                                            </Button>
                                                                                          )}
                                                                                        >
                                                                                          <Form.Item
                                                                                            name={[tablePartField.name, 'table_part']}
                                                                                            label="table_part"
                                                                                            style={{ marginBottom: 8 }}
                                                                                          >
                                                                                            <Select
                                                                                              showSearch
                                                                                              optionFilterProp="label"
                                                                                              options={tablePartOptions}
                                                                                              notFoundContent={(
                                                                                                selectedEntityName
                                                                                                  ? 'Для выбранного entity_name нет table_parts в metadata catalog.'
                                                                                                  : 'Сначала выберите entity_name.'
                                                                                              )}
                                                                                            />
                                                                                          </Form.Item>
                                                                                          <Form.List name={[tablePartField.name, 'row_mappings']}>
                                                                                            {(rowMappingFields, { add: addRowMapping, remove: removeRowMapping }) => (
                                                                                              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                                                                {rowMappingFields.map((rowMappingField) => {
                                                                                                  const sourceType = (
                                                                                                    String(
                                                                                                      getFieldValue([
                                                                                                        'edges',
                                                                                                        field.name,
                                                                                                        'document_policy_builder',
                                                                                                        chainField.name,
                                                                                                        'documents',
                                                                                                        documentField.name,
                                                                                                        'table_part_mappings',
                                                                                                        tablePartField.name,
                                                                                                        'row_mappings',
                                                                                                        rowMappingField.name,
                                                                                                        'source_type',
                                                                                                      ]) || 'expression'
                                                                                                    )
                                                                                                      .trim()
                                                                                                      .toLowerCase() === 'master_data_token'
                                                                                                      ? 'master_data_token'
                                                                                                      : 'expression'
                                                                                                  )
                                                                                                  const tokenEntityType = String(
                                                                                                    getFieldValue([
                                                                                                      'edges',
                                                                                                      field.name,
                                                                                                      'document_policy_builder',
                                                                                                      chainField.name,
                                                                                                      'documents',
                                                                                                      documentField.name,
                                                                                                      'table_part_mappings',
                                                                                                      tablePartField.name,
                                                                                                      'row_mappings',
                                                                                                      rowMappingField.name,
                                                                                                      'token_entity_type',
                                                                                                    ]) || ''
                                                                                                  ).trim()
                                                                                                  const tokenCanonicalId = String(
                                                                                                    getFieldValue([
                                                                                                      'edges',
                                                                                                      field.name,
                                                                                                      'document_policy_builder',
                                                                                                      chainField.name,
                                                                                                      'documents',
                                                                                                      documentField.name,
                                                                                                      'table_part_mappings',
                                                                                                      tablePartField.name,
                                                                                                      'row_mappings',
                                                                                                      rowMappingField.name,
                                                                                                      'token_canonical_id',
                                                                                                    ]) || ''
                                                                                                  ).trim()
                                                                                                  const tokenPartyRole = String(
                                                                                                    getFieldValue([
                                                                                                      'edges',
                                                                                                      field.name,
                                                                                                      'document_policy_builder',
                                                                                                      chainField.name,
                                                                                                      'documents',
                                                                                                      documentField.name,
                                                                                                      'table_part_mappings',
                                                                                                      tablePartField.name,
                                                                                                      'row_mappings',
                                                                                                      rowMappingField.name,
                                                                                                      'token_party_role',
                                                                                                    ]) || ''
                                                                                                  ).trim()
                                                                                                  const tokenOwnerCounterpartyCanonicalId = String(
                                                                                                    getFieldValue([
                                                                                                      'edges',
                                                                                                      field.name,
                                                                                                      'document_policy_builder',
                                                                                                      chainField.name,
                                                                                                      'documents',
                                                                                                      documentField.name,
                                                                                                      'table_part_mappings',
                                                                                                      tablePartField.name,
                                                                                                      'row_mappings',
                                                                                                      rowMappingField.name,
                                                                                                      'token_owner_counterparty_canonical_id',
                                                                                                    ]) || ''
                                                                                                  ).trim()
                                                                                                  const contractOwnerDefault = (
                                                                                                    tokenEntityType === 'contract' && tokenCanonicalId
                                                                                                      ? String(
                                                                                                        masterDataContractByCanonicalId[tokenCanonicalId]?.owner_counterparty_canonical_id
                                                                                                        || ''
                                                                                                      ).trim()
                                                                                                      : ''
                                                                                                  )
                                                                                                  const tokenCanonicalOptions = (
                                                                                                    tokenEntityType === 'party'
                                                                                                      ? masterDataPartyOptions
                                                                                                      : tokenEntityType === 'item'
                                                                                                        ? masterDataItemOptions
                                                                                                        : tokenEntityType === 'contract'
                                                                                                          ? masterDataContractOptions
                                                                                                          : tokenEntityType === 'tax_profile'
                                                                                                            ? masterDataTaxProfileOptions
                                                                                                            : []
                                                                                                  )
                                                                                                  const ownerCounterpartyOptions = (
                                                                                                    contractOwnerDefault
                                                                                                    && !masterDataCounterpartyOptions.some(
                                                                                                      (item) => item.value === contractOwnerDefault
                                                                                                    )
                                                                                                      ? [
                                                                                                        ...masterDataCounterpartyOptions,
                                                                                                        {
                                                                                                          value: contractOwnerDefault,
                                                                                                          label: contractOwnerDefault,
                                                                                                        },
                                                                                                      ]
                                                                                                      : masterDataCounterpartyOptions
                                                                                                  )
                                                                                                  const tokenPreview = sourceType === 'master_data_token'
                                                                                                    ? buildMasterDataToken({
                                                                                                      token_entity_type: tokenEntityType as MasterDataTokenEntityType,
                                                                                                      token_canonical_id: tokenCanonicalId,
                                                                                                      token_party_role: tokenPartyRole as MasterDataTokenPartyRole,
                                                                                                      token_owner_counterparty_canonical_id: (
                                                                                                        tokenOwnerCounterpartyCanonicalId || contractOwnerDefault
                                                                                                      ),
                                                                                                    })
                                                                                                    : null

                                                                                                  return (
                                                                                                    <Row key={rowMappingField.key} gutter={8} align="top">
                                                                                                      <Col span={6}>
                                                                                                        <Form.Item
                                                                                                          name={[rowMappingField.name, 'target_row_field']}
                                                                                                          style={{ marginBottom: 0 }}
                                                                                                        >
                                                                                                          <Select
                                                                                                            showSearch
                                                                                                            optionFilterProp="label"
                                                                                                            options={rowFieldOptions}
                                                                                                            placeholder="target row field"
                                                                                                            notFoundContent={(
                                                                                                              selectedTablePart
                                                                                                                ? 'Для выбранной табличной части нет row_fields.'
                                                                                                                : 'Сначала выберите table_part.'
                                                                                                            )}
                                                                                                          />
                                                                                                        </Form.Item>
                                                                                                      </Col>
                                                                                                      <Col span={6}>
                                                                                                        <Form.Item
                                                                                                          name={[rowMappingField.name, 'source_type']}
                                                                                                          style={{ marginBottom: 0 }}
                                                                                                          initialValue="expression"
                                                                                                        >
                                                                                                          <Select options={TOKEN_SOURCE_TYPE_OPTIONS} />
                                                                                                        </Form.Item>
                                                                                                      </Col>
                                                                                                      <Col span={9}>
                                                                                                        {sourceType === 'master_data_token' ? (
                                                                                                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                                                                            <Row gutter={8}>
                                                                                                              <Col span={8}>
                                                                                                                <Form.Item
                                                                                                                  name={[rowMappingField.name, 'token_entity_type']}
                                                                                                                  style={{ marginBottom: 0 }}
                                                                                                                >
                                                                                                                  <Select
                                                                                                                    placeholder="entity"
                                                                                                                    options={TOKEN_ENTITY_TYPE_OPTIONS}
                                                                                                                    loading={loadingMasterDataTokenCatalog}
                                                                                                                  />
                                                                                                                </Form.Item>
                                                                                                              </Col>
                                                                                                              <Col span={16}>
                                                                                                                <Form.Item
                                                                                                                  name={[rowMappingField.name, 'token_canonical_id']}
                                                                                                                  style={{ marginBottom: 0 }}
                                                                                                                >
                                                                                                                  <Select
                                                                                                                    showSearch
                                                                                                                    optionFilterProp="label"
                                                                                                                    allowClear
                                                                                                                    placeholder="canonical_id"
                                                                                                                    options={tokenCanonicalOptions}
                                                                                                                    loading={loadingMasterDataTokenCatalog}
                                                                                                                  />
                                                                                                                </Form.Item>
                                                                                                              </Col>
                                                                                                            </Row>
                                                                                                            {tokenEntityType === 'party' && (
                                                                                                              <Form.Item
                                                                                                                name={[rowMappingField.name, 'token_party_role']}
                                                                                                                style={{ marginBottom: 0 }}
                                                                                                              >
                                                                                                                <Select
                                                                                                                  allowClear
                                                                                                                  placeholder="party role"
                                                                                                                  options={TOKEN_PARTY_ROLE_OPTIONS}
                                                                                                                />
                                                                                                              </Form.Item>
                                                                                                            )}
                                                                                                            {tokenEntityType === 'contract' && (
                                                                                                              <Form.Item
                                                                                                                name={[rowMappingField.name, 'token_owner_counterparty_canonical_id']}
                                                                                                                style={{ marginBottom: 0 }}
                                                                                                                initialValue={contractOwnerDefault || undefined}
                                                                                                              >
                                                                                                                <Select
                                                                                                                  showSearch
                                                                                                                  optionFilterProp="label"
                                                                                                                  allowClear
                                                                                                                  placeholder="owner_counterparty_canonical_id"
                                                                                                                  options={ownerCounterpartyOptions}
                                                                                                                  loading={loadingMasterDataTokenCatalog}
                                                                                                                />
                                                                                                              </Form.Item>
                                                                                                            )}
                                                                                                            {tokenPreview ? (
                                                                                                              <Text code>{tokenPreview}</Text>
                                                                                                            ) : (
                                                                                                              <Text type="secondary">
                                                                                                                Configure token fields.
                                                                                                              </Text>
                                                                                                            )}
                                                                                                          </Space>
                                                                                                        ) : (
                                                                                                          <Form.Item
                                                                                                            name={[rowMappingField.name, 'expression_source']}
                                                                                                            style={{ marginBottom: 0 }}
                                                                                                          >
                                                                                                            <Input placeholder="allocation.lines.amount" />
                                                                                                          </Form.Item>
                                                                                                        )}
                                                                                                      </Col>
                                                                                                      <Col span={3}>
                                                                                                        <Button danger onClick={() => removeRowMapping(rowMappingField.name)}>
                                                                                                          x
                                                                                                        </Button>
                                                                                                      </Col>
                                                                                                    </Row>
                                                                                                  )
                                                                                                })}
                                                                                                <Button
                                                                                                  size="small"
                                                                                                  onClick={() => addRowMapping({
                                                                                                    target_row_field: '',
                                                                                                    source_type: 'expression',
                                                                                                    expression_source: '',
                                                                                                  })}
                                                                                                >
                                                                                                  Add row mapping
                                                                                                </Button>
                                                                                              </Space>
                                                                                            )}
                                                                                          </Form.List>
                                                                                        </Card>
                                                                                      )
                                                                                    })}
                                                                                    <Button
                                                                                      size="small"
                                                                                      onClick={() => addTablePart({ table_part: '', row_mappings: [] })}
                                                                                    >
                                                                                      Add table part mapping
                                                                                    </Button>
                                                                                  </Space>
                                                                                )}
                                                                              </Form.List>
                                                                            </Card>
                                                                          )
                                                                        })}
                                                                        <Button
                                                                          size="small"
                                                                          onClick={() => addDocument({
                                                                            document_id: '',
                                                                            entity_name: '',
                                                                            document_role: '',
                                                                            invoice_mode: 'optional',
                                                                            link_to: '',
                                                                            link_rule_mappings: [],
                                                                            field_mappings: [],
                                                                            table_part_mappings: [],
                                                                          })}
                                                                        >
                                                                          Add document
                                                                        </Button>
                                                                      </Space>
                                                                    )}
                                                                  </Form.List>
                                                                </Card>
                                                              ))}
                                                              <Button
                                                                size="small"
                                                                onClick={() => addChain({ chain_id: '', documents: [] })}
                                                                data-testid={`pool-catalog-topology-edge-policy-add-chain-${field.name}`}
                                                              >
                                                                Add chain
                                                              </Button>
                                                            </Space>
                                                          )}
                                                        </Form.List>
                                                      </>
                                                    ) : null}

                                                    <Form.Item
                                                      name={[field.name, 'edge_metadata_mode']}
                                                      label="Edge metadata mode"
                                                      style={{ marginBottom: 0 }}
                                                    >
                                                      <Select
                                                        options={[
                                                          { value: 'builder', label: 'Builder' },
                                                          { value: 'raw', label: 'Raw JSON' },
                                                        ]}
                                                        onChange={(value) => {
                                                          switchEdgeMetadataMode(
                                                            field.name,
                                                            value === 'builder' ? 'builder' : 'raw'
                                                          )
                                                        }}
                                                        data-testid={`pool-catalog-topology-edge-metadata-mode-${field.name}`}
                                                      />
                                                    </Form.Item>
                                                    {edgeMetadataMode === 'builder' ? (
                                                      <Form.List name={[field.name, 'edge_metadata_builder']}>
                                                        {(metadataFields, { add: addMetadataField, remove: removeMetadataField }) => (
                                                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                            {metadataFields.map((metadataField) => (
                                                              <Row key={metadataField.key} gutter={8} align="middle">
                                                                <Col span={8}>
                                                                  <Form.Item
                                                                    name={[metadataField.name, 'key']}
                                                                    style={{ marginBottom: 0 }}
                                                                  >
                                                                    <Input placeholder="metadata key" />
                                                                  </Form.Item>
                                                                </Col>
                                                                <Col span={13}>
                                                                  <Form.Item
                                                                    name={[metadataField.name, 'value_json']}
                                                                    style={{ marginBottom: 0 }}
                                                                  >
                                                                    <TextArea
                                                                      autoSize={{ minRows: 1, maxRows: 4 }}
                                                                      placeholder='"value" или {"nested":true}'
                                                                    />
                                                                  </Form.Item>
                                                                </Col>
                                                                <Col span={3}>
                                                                  <Button danger onClick={() => removeMetadataField(metadataField.name)}>
                                                                    x
                                                                  </Button>
                                                                </Col>
                                                              </Row>
                                                            ))}
                                                            <Button
                                                              size="small"
                                                              onClick={() => addMetadataField({ key: '', value_json: '' })}
                                                              data-testid={`pool-catalog-topology-edge-metadata-add-field-${field.name}`}
                                                            >
                                                              Add metadata field
                                                            </Button>
                                                          </Space>
                                                        )}
                                                      </Form.List>
                                                    ) : (
                                                      <Form.Item
                                                        name={[field.name, 'metadata_json']}
                                                        label="Edge metadata (JSON)"
                                                        style={{ marginBottom: 0 }}
                                                      >
                                                        <TextArea
                                                          autoSize={{ minRows: 2, maxRows: 6 }}
                                                          placeholder='{"custom_key":"value"}'
                                                          data-testid={`pool-catalog-topology-edge-metadata-${field.name}`}
                                                        />
                                                      </Form.Item>
                                                    )}
                                                  </Space>
                                                )
                                              }}
                                            </Form.Item>
                                          </Space>
                                        ),
                                      },
                                    ]}
                                  />
                                </Space>
                              ))}
                              <Button
                                onClick={() => add({
                                  edge_version_id: undefined,
                                  weight: 1,
                                  min_amount: null,
                                  max_amount: null,
                                  document_policy_key: '',
                                  document_policy_mode: 'raw',
                                  document_policy_json: '',
                                  document_policy_builder: [],
                                  edge_metadata_mode: 'raw',
                                  edge_metadata_builder: [],
                                  metadata_json: '',
                                })}
                                data-testid="pool-catalog-topology-add-edge"
                              >
                                Add edge
                              </Button>
                            </Space>
                          )}
                            </Form.List>
                          </>
                        )}

                        {topologyPreflightErrors.length > 0 && (
                          <Alert
                            type="error"
                            showIcon
                            message="Preflight validation failed"
                            description={(
                              <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                                {topologyPreflightErrors.map((item, index) => (
                                  <li key={`${index}-${item}`}>{item}</li>
                                ))}
                              </ul>
                            )}
                          />
                        )}
                        {topologySubmitError && <Alert type="error" message={topologySubmitError} showIcon />}

                        <Button
                          type="primary"
                          onClick={() => { void submitTopologySnapshot() }}
                          loading={isTopologySaving}
                          disabled={mutatingDisabled || isTopologySaveBlocked}
                          data-testid="pool-catalog-topology-save"
                        >
                          Save topology snapshot
                        </Button>
                      </Form>
                    )}
                  </Space>
                </Card>
              ),
            },
            {
              key: 'graph',
              label: 'Graph Preview',
              children: (
                <Card title="Pools graph (read-only)" loading={loadingPools || loadingGraph}>
                  <Space size="small" wrap style={{ marginBottom: 12 }}>
                    <Select
                      value={selectedPoolId ?? undefined}
                      style={{ width: 320 }}
                      placeholder="Select pool"
                      options={pools.map((pool) => ({
                        value: pool.id,
                        label: `${pool.code} - ${pool.name}`,
                      }))}
                      onChange={(value) => handleSelectPool(value ?? null)}
                    />
                    <Input
                      type="date"
                      value={graphDate}
                      style={{ width: 170 }}
                      onChange={(event) => handleGraphDateChange(event.target.value)}
                    />
                    <Button onClick={() => { void loadGraph({ force: true }) }} loading={loadingGraph}>
                      Refresh graph
                    </Button>
                  </Space>
                  <div style={{ height: 520 }}>
                    <ReactFlow
                      nodes={flow.nodes}
                      edges={flow.edges}
                      fitView
                      nodesDraggable={false}
                      nodesConnectable={false}
                      elementsSelectable={false}
                      zoomOnDoubleClick={false}
                      proOptions={{ hideAttribution: true }}
                    >
                      <MiniMap />
                      <Controls />
                      <Background />
                    </ReactFlow>
                  </div>
                </Card>
              ),
            },
          ]}
        />
      </WorkspacePage>

      <Drawer
        data-testid="pool-catalog-organization-drawer"
        title={organizationDrawerMode === 'create' ? 'Add organization' : 'Edit organization'}
        width={520}
        open={isOrganizationDrawerOpen}
        onClose={closeOrganizationDrawer}
        forceRender
        destroyOnHidden
        extra={(
          <Space>
            <Button onClick={closeOrganizationDrawer} disabled={isOrganizationSaving}>
              Cancel
            </Button>
            <Button type="primary" onClick={() => { void submitOrganization() }} loading={isOrganizationSaving}>
              Save
            </Button>
          </Space>
        )}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {organizationSubmitError && <Alert type="error" message={organizationSubmitError} showIcon />}
          <Form form={organizationForm} layout="vertical">
            <Form.Item
              name="inn"
              label="INN"
              rules={[
                { required: true, message: 'INN обязателен' },
                { max: 12, message: 'INN должен быть не длиннее 12 символов' },
              ]}
            >
              <Input placeholder="730000000001" maxLength={12} />
            </Form.Item>
            <Form.Item
              name="name"
              label="Name"
              rules={[
                { required: true, message: 'Name обязателен' },
                { max: 255, message: 'Name должен быть не длиннее 255 символов' },
              ]}
            >
              <Input placeholder="Organization name" />
            </Form.Item>
            <Form.Item name="status" label="Status" rules={[{ required: true, message: 'Status обязателен' }]}>
              <Select
                options={[
                  { value: 'active', label: 'active' },
                  { value: 'inactive', label: 'inactive' },
                  { value: 'archived', label: 'archived' },
                ]}
              />
            </Form.Item>
            <Form.Item name="database_id" label="Database">
              <Select
                allowClear
                showSearch
                optionFilterProp="label"
                placeholder="Select database"
                options={databaseOptions}
                loading={databasesQuery.isLoading}
              />
            </Form.Item>
            <Form.Item name="full_name" label="Full name">
              <Input placeholder="Optional" />
            </Form.Item>
            <Form.Item name="kpp" label="KPP">
              <Input placeholder="Optional" />
            </Form.Item>
            <Form.Item name="external_ref" label="External ref">
              <Input placeholder="Optional" />
            </Form.Item>
          </Form>
        </Space>
      </Drawer>

      <Drawer
        data-testid="pool-catalog-pool-drawer"
        title={poolDrawerMode === 'create' ? 'Add pool' : 'Edit pool'}
        width={520}
        open={isPoolDrawerOpen}
        onClose={closePoolDrawer}
        forceRender
        destroyOnHidden
        extra={(
          <Space>
            <Button onClick={closePoolDrawer} disabled={isPoolSaving}>
              Cancel
            </Button>
            <Button
              type="primary"
              onClick={() => { void submitPool() }}
              loading={isPoolSaving}
              data-testid="pool-catalog-save-pool"
            >
              Save
            </Button>
          </Space>
        )}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {poolSubmitError && <Alert type="error" message={poolSubmitError} showIcon />}
          <Alert
            type="info"
            showIcon
            message="Pool fields only"
            description="Workflow bindings moved to the Bindings workspace and are saved there through first-class binding CRUD."
          />
          <Form form={poolForm} layout="vertical">
            <Form.Item
              name="code"
              label="Code"
              rules={[
                { required: true, message: 'Code обязателен' },
                { max: 64, message: 'Code должен быть не длиннее 64 символов' },
              ]}
            >
              <Input placeholder="pool-main" />
            </Form.Item>
            <Form.Item
              name="name"
              label="Name"
              rules={[
                { required: true, message: 'Name обязателен' },
                { max: 255, message: 'Name должен быть не длиннее 255 символов' },
              ]}
            >
              <Input placeholder="Main intercompany pool" />
            </Form.Item>
            <Form.Item name="description" label="Description">
              <Input.TextArea autoSize={{ minRows: 2, maxRows: 5 }} placeholder="Optional" />
            </Form.Item>
            <Form.Item name="is_active" label="Active" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Form>
        </Space>
      </Drawer>

      <Modal
        title="Sync organizations catalog (JSON)"
        open={isSyncModalOpen}
        onCancel={closeSyncModal}
        onOk={() => { void submitSync() }}
        okText="Run sync"
        confirmLoading={isSyncSubmitting}
        width={760}
        destroyOnHidden
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Text type="secondary">
            Input JSON payload in format <Text code>{'{"rows":[{"inn":"...","name":"..."}]}'}</Text>. Limit: {SYNC_MAX_ROWS} rows.
          </Text>
          <TextArea
            data-testid="pool-catalog-sync-input"
            value={syncInput}
            onChange={(event) => setSyncInput(event.target.value)}
            autoSize={{ minRows: 12, maxRows: 20 }}
            spellCheck={false}
          />
          {syncErrors.length > 0 && (
            <Alert
              type="error"
              showIcon
              message="Sync blocked"
              description={(
                <ul style={{ paddingInlineStart: 18, margin: 0 }}>
                  {syncErrors.map((item, index) => (
                    <li key={`${index}-${item}`}>{item}</li>
                  ))}
                </ul>
              )}
            />
          )}
          {syncResult && (
            <Alert
              type="success"
              showIcon
              message="Sync completed"
              description={(
                <Space size="large">
                  <Text>created: <Text code>{syncResult.stats.created}</Text></Text>
                  <Text>updated: <Text code>{syncResult.stats.updated}</Text></Text>
                  <Text>skipped: <Text code>{syncResult.stats.skipped}</Text></Text>
                  <Text>total_rows: <Text code>{syncResult.total_rows}</Text></Text>
                </Space>
              )}
            />
          )}
        </Space>
      </Modal>
    </>
  )
}
