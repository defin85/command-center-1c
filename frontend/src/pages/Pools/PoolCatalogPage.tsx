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
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'

import { useDatabases } from '../../api/queries/databases'
import { useMe } from '../../api/queries/me'
import {
  getOrganization,
  getPoolGraph,
  listOrganizationPools,
  listOrganizations,
  syncOrganizationsCatalog,
  upsertOrganization,
  type Organization,
  type OrganizationPool,
  type OrganizationPoolBinding,
  type OrganizationStatus,
  type PoolGraph,
} from '../../api/intercompanyPools'

const { Title, Text } = Typography
const { TextArea } = Input

const SYNC_MAX_ROWS = 1000
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const STATUS_OPTIONS: OrganizationStatus[] = ['active', 'inactive', 'archived']

const API_ERROR_MESSAGE_MAP: Record<string, string> = {
  DATABASE_ALREADY_LINKED: 'Выбранная база уже привязана к другой организации.',
  DUPLICATE_ORGANIZATION_INN: 'Организация с таким ИНН уже существует в текущем tenant.',
  DATABASE_NOT_FOUND: 'База данных не найдена в текущем tenant context.',
  ORGANIZATION_NOT_FOUND: 'Организация не найдена в текущем tenant context.',
  TENANT_NOT_FOUND: 'Текущий tenant context невалиден.',
  TENANT_CONTEXT_REQUIRED: 'Для изменения каталога выберите активный tenant.',
  VALIDATION_ERROR: 'Ошибка валидации данных синхронизации.',
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
      }
    }
  } | null

  const errorNode = err?.response?.data?.error
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

export function PoolCatalogPage() {
  const { message } = AntApp.useApp()
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)
  const hasTenantContext = Boolean(localStorage.getItem('active_tenant_id'))
  const mutatingDisabled = isStaff && !hasTenantContext
  const databasesQuery = useDatabases({ filters: { limit: 500, offset: 0 } })

  const [organizationForm] = Form.useForm<OrganizationFormValues>()

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
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)
  const [syncInput, setSyncInput] = useState('{\n  "rows": []\n}')
  const [syncErrors, setSyncErrors] = useState<string[]>([])
  const [syncResult, setSyncResult] = useState<{ stats: { created: number; updated: number; skipped: number }; total_rows: number } | null>(null)
  const [isSyncSubmitting, setIsSyncSubmitting] = useState(false)

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === selectedOrganizationId) ?? null,
    [organizations, selectedOrganizationId]
  )

  const databaseOptions = useMemo(() => {
    const databases = databasesQuery.data?.databases ?? []
    return databases
      .map((database) => ({ label: database.name || database.id || 'unknown', value: database.id || '' }))
      .filter((item) => item.value)
      .sort((left, right) => left.label.localeCompare(right.label))
  }, [databasesQuery.data?.databases])

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
