import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
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
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'

import { useDatabases } from '../../api/queries/databases'
import { useMe } from '../../api/queries/me'
import { useMyTenants } from '../../api/queries/tenants'
import {
  getOrganization,
  getPoolGraph,
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
  type PoolTopologySnapshotEdgeInput,
  type PoolTopologySnapshotNodeInput,
} from '../../api/intercompanyPools'

const { Title, Text } = Typography
const { TextArea } = Input

const SYNC_MAX_ROWS = 1000
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const STATUS_OPTIONS: OrganizationStatus[] = ['active', 'inactive', 'archived']

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
}

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

type TopologyNodeFormValue = {
  organization_id?: string
  is_root?: boolean
}

type TopologyEdgeFormValue = {
  parent_organization_id?: string
  child_organization_id?: string
  weight?: number
  min_amount?: number | null
  max_amount?: number | null
}

type TopologyFormValues = {
  effective_from: string
  effective_to?: string
  nodes: TopologyNodeFormValue[]
  edges: TopologyEdgeFormValue[]
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

const buildFieldErrorLines = (fieldErrors: Record<string, string[]>): string[] => (
  Object.entries(fieldErrors).flatMap(([field, messages]) => (
    messages.map((message) => `${field}: ${message}`)
  ))
)

const resolveApiError = (
  error: unknown,
  fallbackMessage: string
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
    const problemCode = typeof maybeProblem.code === 'string' ? maybeProblem.code : ''
    const problemDetail = typeof maybeProblem.detail === 'string' ? maybeProblem.detail.trim() : ''
    const problemFieldErrors = normalizeFieldErrors(maybeProblem.errors)
    if (problemCode || problemDetail || Object.keys(problemFieldErrors).length > 0) {
      const mappedMessage = API_ERROR_MESSAGE_MAP[problemCode] ?? problemDetail
      return {
        message: mappedMessage || (Object.keys(problemFieldErrors).length > 0
          ? 'Проверьте корректность заполнения полей.'
          : fallbackMessage),
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
      return {
        message: API_ERROR_MESSAGE_MAP[code] ?? (backendMessage || fallbackMessage),
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

const buildTopologyPreflight = (values: TopologyFormValues): {
  payload: {
    effective_from: string
    effective_to?: string | null
    nodes: PoolTopologySnapshotNodeInput[]
    edges: PoolTopologySnapshotEdgeInput[]
  } | null
  errors: string[]
} => {
  const errors: string[] = []
  const effectiveFrom = String(values.effective_from || '').trim()
  const effectiveToRaw = String(values.effective_to || '').trim()
  if (!effectiveFrom) {
    errors.push('effective_from обязателен.')
  }
  if (effectiveToRaw && effectiveFrom && effectiveToRaw < effectiveFrom) {
    errors.push('effective_to не может быть раньше effective_from.')
  }

  const nodesSource = Array.isArray(values.nodes) ? values.nodes : []
  const nodes = nodesSource
    .filter((item) => String(item.organization_id || '').trim().length > 0)
    .map((item) => ({
      organization_id: String(item.organization_id || '').trim(),
      is_root: Boolean(item.is_root),
      metadata: {},
    }))
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
    edges.push({
      parent_organization_id: parentId,
      child_organization_id: childId,
      weight: edge.weight == null ? '1' : String(edge.weight),
      min_amount: minAmount,
      max_amount: maxAmount,
      metadata: {},
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
  const meQuery = useMe()
  const hasAuthToken = Boolean(localStorage.getItem('auth_token'))
  const myTenantsQuery = useMyTenants({ enabled: hasAuthToken })
  const isStaff = Boolean(meQuery.data?.is_staff)
  const activeTenantId = localStorage.getItem('active_tenant_id') || myTenantsQuery.data?.active_tenant_id || null
  const hasTenantContext = Boolean(activeTenantId)
  const mutatingDisabled = isStaff && !hasTenantContext
  const databasesQuery = useDatabases({ filters: { limit: 500, offset: 0 } })

  const [organizationForm] = Form.useForm<OrganizationFormValues>()
  const [poolForm] = Form.useForm<PoolFormValues>()
  const [topologyForm] = Form.useForm<TopologyFormValues>()

  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null)
  const [organizationDetail, setOrganizationDetail] = useState<{
    organization: Organization
    pool_bindings: OrganizationPoolBinding[]
  } | null>(null)
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null)
  const [graphDate, setGraphDate] = useState<string>(new Date().toISOString().slice(0, 10))
  const [graph, setGraph] = useState<PoolGraph | null>(null)
  const [loadingOrganizations, setLoadingOrganizations] = useState(false)
  const [loadingOrganizationDetail, setLoadingOrganizationDetail] = useState(false)
  const [loadingPools, setLoadingPools] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)
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
  const [topologyPreflightErrors, setTopologyPreflightErrors] = useState<string[]>([])
  const [topologySubmitError, setTopologySubmitError] = useState<string | null>(null)
  const [isTopologySaving, setIsTopologySaving] = useState(false)
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)
  const [syncInput, setSyncInput] = useState('{\n  "rows": []\n}')
  const [syncErrors, setSyncErrors] = useState<string[]>([])
  const [syncResult, setSyncResult] = useState<{ stats: { created: number; updated: number; skipped: number }; total_rows: number } | null>(null)
  const [isSyncSubmitting, setIsSyncSubmitting] = useState(false)

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === selectedOrganizationId) ?? null,
    [organizations, selectedOrganizationId]
  )
  const selectedPool = useMemo(
    () => pools.find((item) => item.id === selectedPoolId) ?? null,
    [pools, selectedPoolId]
  )

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

  const flow = useMemo(() => buildFlowLayout(graph), [graph])

  const loadOrganizations = useCallback(async () => {
    setLoadingOrganizations(true)
    setError(null)
    try {
      const data = await listOrganizations({
        status: statusFilter === 'all' ? undefined : statusFilter,
        query: query.trim() || undefined,
        databaseLinked: databaseLinkFilter === 'all' ? undefined : databaseLinkFilter === 'linked',
        limit: 300,
      })
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
  }, [databaseLinkFilter, query, statusFilter])

  const loadOrganizationDetail = useCallback(async () => {
    if (!selectedOrganizationId) {
      setOrganizationDetail(null)
      return
    }
    setLoadingOrganizationDetail(true)
    try {
      const detail = await getOrganization(selectedOrganizationId)
      setOrganizationDetail(detail)
    } catch {
      setError('Не удалось загрузить детали организации.')
    } finally {
      setLoadingOrganizationDetail(false)
    }
  }, [selectedOrganizationId])

  const loadPools = useCallback(async () => {
    setLoadingPools(true)
    try {
      const data = await listOrganizationPools()
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
  }, [])

  const loadGraph = useCallback(async () => {
    if (!selectedPoolId) {
      setGraph(null)
      return
    }
    setLoadingGraph(true)
    try {
      const payload = await getPoolGraph(selectedPoolId, graphDate || undefined)
      setGraph(payload)
    } catch {
      setError('Не удалось загрузить граф пула.')
    } finally {
      setLoadingGraph(false)
    }
  }, [graphDate, selectedPoolId])

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
    topologyForm.setFieldsValue({
      effective_from: new Date().toISOString().slice(0, 10),
      effective_to: '',
      nodes: [],
      edges: [],
    })
    setTopologyPreflightErrors([])
    setTopologySubmitError(null)
  }, [selectedPoolId, topologyForm])

  const openCreateOrganizationDrawer = useCallback(() => {
    if (mutatingDisabled) return
    setOrganizationDrawerMode('create')
    setEditingOrganization(null)
    setOrganizationSubmitError(null)
    organizationForm.resetFields()
    organizationForm.setFieldsValue({
      inn: '',
      name: '',
      full_name: '',
      kpp: '',
      status: 'active',
      database_id: undefined,
      external_ref: '',
    })
    setIsOrganizationDrawerOpen(true)
  }, [mutatingDisabled, organizationForm])

  const openEditOrganizationDrawer = useCallback((organization: Organization | null) => {
    if (mutatingDisabled || !organization) return
    setOrganizationDrawerMode('edit')
    setEditingOrganization(organization)
    setOrganizationSubmitError(null)
    organizationForm.resetFields()
    organizationForm.setFieldsValue({
      inn: organization.inn,
      name: organization.name,
      full_name: organization.full_name || '',
      kpp: organization.kpp || '',
      status: organization.status,
      database_id: organization.database_id || undefined,
      external_ref: organization.external_ref || '',
    })
    setIsOrganizationDrawerOpen(true)
  }, [mutatingDisabled, organizationForm])

  const closeOrganizationDrawer = useCallback(() => {
    if (isOrganizationSaving) return
    setIsOrganizationDrawerOpen(false)
    setOrganizationSubmitError(null)
  }, [isOrganizationSaving])

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
      setSelectedOrganizationId(response.organization.id)
      message.success(response.created ? 'Организация создана.' : 'Организация обновлена.')
      setIsOrganizationDrawerOpen(false)
      await loadOrganizations()
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
    poolForm.resetFields()
    poolForm.setFieldsValue({
      code: '',
      name: '',
      description: '',
      is_active: true,
    })
    setIsPoolDrawerOpen(true)
  }, [mutatingDisabled, poolForm])

  const openEditPoolDrawer = useCallback(() => {
    if (mutatingDisabled || !selectedPool) return
    setPoolDrawerMode('edit')
    setPoolSubmitError(null)
    poolForm.resetFields()
    poolForm.setFieldsValue({
      code: selectedPool.code,
      name: selectedPool.name,
      description: selectedPool.description || '',
      is_active: selectedPool.is_active,
    })
    setIsPoolDrawerOpen(true)
  }, [mutatingDisabled, poolForm, selectedPool])

  const closePoolDrawer = useCallback(() => {
    if (isPoolSaving) return
    setIsPoolDrawerOpen(false)
    setPoolSubmitError(null)
  }, [isPoolSaving])

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
        metadata: selectedPool?.metadata ?? {},
      })
      setSelectedPoolId(response.pool.id)
      message.success(response.created ? 'Пул создан.' : 'Пул обновлён.')
      setIsPoolDrawerOpen(false)
      await loadPools()
      await loadGraph()
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
  }, [loadGraph, loadPools, message, mutatingDisabled, poolDrawerMode, poolForm, selectedPool])

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
      await loadPools()
      await loadGraph()
    } catch (err) {
      const resolved = resolveApiError(err, 'Не удалось изменить статус пула.')
      setPoolSubmitError(resolved.message)
    } finally {
      setIsPoolSaving(false)
    }
  }, [loadGraph, loadPools, message, mutatingDisabled, selectedPool])

  const submitTopologySnapshot = useCallback(async () => {
    if (mutatingDisabled || !selectedPoolId) return
    setTopologySubmitError(null)
    setTopologyPreflightErrors([])
    try {
      const values = await topologyForm.validateFields()
      const preflight = buildTopologyPreflight(values)
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
      await loadGraph()
    } catch (err) {
      if (
        err
        && typeof err === 'object'
        && Array.isArray((err as { errorFields?: unknown }).errorFields)
      ) {
        return
      }
      const resolved = resolveApiError(err, 'Не удалось сохранить topology snapshot.')
      setTopologySubmitError(resolved.message)
    } finally {
      setIsTopologySaving(false)
    }
  }, [graph, graphDate, loadGraph, message, mutatingDisabled, selectedPoolId, topologyForm])

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
      await loadOrganizations()
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
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ marginBottom: 0 }}>
            Pool Catalog
          </Title>
          <Text type="secondary">
            Tenant-aware каталог организаций и read-only граф структуры пула по дате.
          </Text>
        </div>

        {error && <Alert type="error" message={error} showIcon />}

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
              onPressEnter={() => { void loadOrganizations() }}
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
            <Button onClick={() => { void loadOrganizations() }} loading={loadingOrganizations}>
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

        <Card title="Pools management" loading={loadingPools}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
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
                onChange={(value) => setSelectedPoolId(value)}
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
                onChange: (keys) => setSelectedPoolId(keys[0] ? String(keys[0]) : null),
              }}
              onRow={(record) => ({
                onClick: () => setSelectedPoolId(record.id),
              })}
            />
          </Space>
        </Card>

        <Card title="Topology snapshot editor">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
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

                <Text strong>Nodes</Text>
                <Form.List name="nodes">
                  {(fields, { add, remove }) => (
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      {fields.map((field) => (
                        <Row key={field.key} gutter={12} align="middle">
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
                            <Button danger onClick={() => remove(field.name)}>
                              Remove
                            </Button>
                          </Col>
                        </Row>
                      ))}
                      <Button
                        onClick={() => add({ organization_id: undefined, is_root: false })}
                        data-testid="pool-catalog-topology-add-node"
                      >
                        Add node
                      </Button>
                    </Space>
                  )}
                </Form.List>

                <Text strong style={{ marginTop: 12 }}>Edges</Text>
                <Form.List name="edges">
                  {(fields, { add, remove }) => (
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      {fields.map((field) => (
                        <Row key={field.key} gutter={8} align="middle">
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
                          <Col span={3}>
                            <Form.Item
                              name={[field.name, 'weight']}
                              label={field.name === 0 ? 'Weight' : ''}
                              style={{ marginBottom: 0 }}
                            >
                              <InputNumber min={0.000001} step={0.1} style={{ width: '100%' }} />
                            </Form.Item>
                          </Col>
                          <Col span={3}>
                            <Form.Item
                              name={[field.name, 'min_amount']}
                              label={field.name === 0 ? 'Min' : ''}
                              style={{ marginBottom: 0 }}
                            >
                              <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
                            </Form.Item>
                          </Col>
                          <Col span={3}>
                            <Form.Item
                              name={[field.name, 'max_amount']}
                              label={field.name === 0 ? 'Max' : ''}
                              style={{ marginBottom: 0 }}
                            >
                              <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
                            </Form.Item>
                          </Col>
                          <Col span={1}>
                            <Button danger onClick={() => remove(field.name)}>x</Button>
                          </Col>
                        </Row>
                      ))}
                      <Button
                        onClick={() => add({ weight: 1, min_amount: null, max_amount: null })}
                        data-testid="pool-catalog-topology-add-edge"
                      >
                        Add edge
                      </Button>
                    </Space>
                  )}
                </Form.List>

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
                  disabled={mutatingDisabled}
                  data-testid="pool-catalog-topology-save"
                >
                  Save topology snapshot
                </Button>
              </Form>
            )}
          </Space>
        </Card>

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
              onChange={(value) => setSelectedPoolId(value)}
            />
            <Input
              type="date"
              value={graphDate}
              style={{ width: 170 }}
              onChange={(event) => setGraphDate(event.target.value)}
            />
            <Button onClick={() => { void loadGraph() }} loading={loadingGraph}>
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
      </Space>

      <Drawer
        title={organizationDrawerMode === 'create' ? 'Add organization' : 'Edit organization'}
        width={520}
        open={isOrganizationDrawerOpen}
        onClose={closeOrganizationDrawer}
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
        title={poolDrawerMode === 'create' ? 'Add pool' : 'Edit pool'}
        width={520}
        open={isPoolDrawerOpen}
        onClose={closePoolDrawer}
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
