import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Alert, App, Button, Form, Popconfirm, Segmented, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  deleteOperationCatalogExposure,
  listOperationCatalogDefinitions,
  listOperationCatalogExposures,
  publishOperationCatalogExposure,
  type OperationCatalogDefinition,
  type OperationCatalogExposure,
  upsertOperationCatalogExposure,
} from '../../api/operationCatalog'
import {
  type OperationTemplate,
  useCreateTemplate,
  useDeleteTemplate,
  useSyncTemplatesFromRegistry,
  useUpdateTemplate,
} from '../../api/queries/templates'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { useMe } from '../../api/queries/me'
import type { ActionFormValues } from '../Settings/actionCatalogTypes'
import type { PlainObject } from '../Settings/actionCatalogTypes'
import { buildActionFromForm, deriveActionFormValues, isPlainObject } from '../Settings/actionCatalogUtils'
import {
  buildActionFromOperationCatalogRecord,
  buildOperationCatalogUpsertFromAction,
  type OperationCatalogActionRecord,
} from '../Settings/actionCatalog/operationCatalogAdapter'
import { OperationExposureEditorModal } from '../Settings/actionCatalog/OperationExposureEditorModal'
import { buildTemplateEditorValues, buildTemplateWritePayloadFromEditor } from './templateEditorAdapter'

const { Title, Text } = Typography

type SurfaceTabKey = 'all' | 'template' | 'action_catalog'
type EditorSurfaceKey = 'template' | 'action_catalog'

type TemplateRow = OperationTemplate & {
  surface: 'template'
  status: string
}

type ActionRow = {
  id: string
  surface: 'action_catalog'
  alias: string
  name: string
  description: string
  capability: string
  contexts: string[]
  status: string
  is_active: boolean
  updated_at: string
  exposure: OperationCatalogExposure
  definition: OperationCatalogDefinition | null
}

type UnifiedRow = TemplateRow | ActionRow

const parseBooleanFilter = (value: unknown): boolean | null => {
  if (typeof value === 'boolean') return value
  const text = String(value ?? '').trim().toLowerCase()
  if (!text) return null
  if (text === 'true' || text === '1' || text === 'yes') return true
  if (text === 'false' || text === '0' || text === 'no') return false
  return null
}

const toErrorMessage = (error: unknown, fallback: string): string => {
  const err = error as {
    message?: string
    response?: {
      data?: {
        error?: { message?: string }
        validation_errors?: Array<{ message?: string }>
      }
    }
  } | null
  const validationMessage = err?.response?.data?.validation_errors?.[0]?.message
  if (typeof validationMessage === 'string' && validationMessage.trim()) return validationMessage
  const apiMessage = err?.response?.data?.error?.message
  if (typeof apiMessage === 'string' && apiMessage.trim()) return apiMessage
  if (typeof err?.message === 'string' && err.message.trim()) return err.message
  return fallback
}

const surfaceLabel = (surface: UnifiedRow['surface']): string => (
  surface === 'template' ? 'Template' : 'Action Catalog'
)

function OperationExposureListShell({
  activeSurface,
  isStaff,
}: {
  activeSurface: SurfaceTabKey
  isStaff: boolean
}) {
  const { message } = App.useApp()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editorSurface, setEditorSurface] = useState<EditorSurfaceKey>('template')
  const [editingTemplate, setEditingTemplate] = useState<TemplateRow | null>(null)
  const [editingAction, setEditingAction] = useState<ActionRow | null>(null)
  const [editingActionBase, setEditingActionBase] = useState<PlainObject | null>(null)
  const [templateReloadTick, setTemplateReloadTick] = useState(0)
  const [actionReloadTick, setActionReloadTick] = useState(0)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)
  const [form] = Form.useForm<ActionFormValues>()

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'surface', label: 'Surface', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'operation_type', label: 'Operation Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'target_entity', label: 'Target', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'capability', label: 'Capability', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Active', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'updated_at', label: 'Updated', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', sortable: false, groupKey: 'meta', groupLabel: 'Meta' },
  ], [])

  const syncMutation = useSyncTemplatesFromRegistry()
  const createMutation = useCreateTemplate()
  const updateMutation = useUpdateTemplate()
  const deleteMutation = useDeleteTemplate()

  const closeModal = useCallback(() => {
    setModalOpen(false)
    setEditingTemplate(null)
    setEditingAction(null)
    setEditingActionBase(null)
    setEditorValues(null)
    form.resetFields()
  }, [form])

  const openCreateModal = useCallback((nextSurface?: EditorSurfaceKey) => {
    const resolvedSurface: EditorSurfaceKey = nextSurface
      ?? (activeSurface === 'action_catalog' ? 'action_catalog' : 'template')
    setEditingTemplate(null)
    setEditingAction(null)
    setEditingActionBase(null)
    setEditorSurface(resolvedSurface)
    const nextValues = resolvedSurface === 'template'
      ? buildTemplateEditorValues(null)
      : deriveActionFormValues(null)
    setEditorValues(nextValues)
    form.resetFields()
    form.setFieldsValue(nextValues)
    setModalOpen(true)
  }, [activeSurface, form])

  const openEditTemplateModal = useCallback((template: TemplateRow) => {
    setEditingTemplate(template)
    setEditingAction(null)
    setEditingActionBase(null)
    setEditorSurface('template')
    const nextValues = buildTemplateEditorValues(template)
    setEditorValues(nextValues)
    form.resetFields()
    form.setFieldsValue(nextValues)
    setModalOpen(true)
  }, [form])

  const openEditActionModal = useCallback((row: ActionRow) => {
    if (!row.definition) {
      message.error('Action definition is missing. Please reload and try again.')
      return
    }
    const record: OperationCatalogActionRecord = {
      exposure: row.exposure,
      definition: row.definition,
    }
    const baseAction = buildActionFromOperationCatalogRecord(record)
    const nextValues = deriveActionFormValues(baseAction)
    setEditingTemplate(null)
    setEditingAction(row)
    setEditingActionBase(baseAction)
    setEditorSurface('action_catalog')
    setEditorValues(nextValues)
    form.resetFields()
    form.setFieldsValue(nextValues)
    setModalOpen(true)
  }, [form, message])

  const handleDeleteTemplate = useCallback(async (template: TemplateRow) => {
    try {
      await deleteMutation.mutateAsync({ template_id: template.id })
      setTemplateReloadTick((value) => value + 1)
      message.success('Template deleted')
    } catch (err) {
      message.error(toErrorMessage(err, 'Failed to delete template'))
    }
  }, [deleteMutation, message])

  const handleDeleteAction = useCallback(async (row: ActionRow) => {
    try {
      await deleteOperationCatalogExposure(row.id)
      setActionReloadTick((value) => value + 1)
      message.success('Action deleted')
    } catch (err) {
      message.error(toErrorMessage(err, 'Failed to delete action'))
    }
  }, [message])

  const columns: ColumnsType<UnifiedRow> = useMemo(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (value: string, record) => (
        <div>
          <div style={{ fontWeight: 600 }}>{value}</div>
          <Text type="secondary">{record.surface === 'template' ? record.id : record.alias}</Text>
        </div>
      ),
    },
    {
      title: 'Surface',
      dataIndex: 'surface',
      key: 'surface',
      width: 140,
      render: (value: UnifiedRow['surface']) => surfaceLabel(value),
    },
    {
      title: 'Operation Type',
      dataIndex: 'operation_type' as const,
      key: 'operation_type',
      width: 180,
      render: (_value, record) => (record.surface === 'template' ? record.operation_type : ''),
    },
    {
      title: 'Target',
      dataIndex: 'target_entity' as const,
      key: 'target_entity',
      width: 120,
      render: (_value, record) => (record.surface === 'template' ? record.target_entity : ''),
    },
    {
      title: 'Capability',
      dataIndex: 'capability' as const,
      key: 'capability',
      width: 220,
      render: (_value, record) => (record.surface === 'action_catalog' ? record.capability : ''),
    },
    {
      title: 'Status',
      dataIndex: 'status' as const,
      key: 'status',
      width: 130,
      render: (_value, record) => (record.surface === 'template' ? record.status : record.status),
    },
    {
      title: 'Active',
      dataIndex: 'is_active' as const,
      key: 'is_active',
      width: 90,
      render: (v: boolean) => (v ? 'yes' : 'no'),
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (v: string) => (v ? new Date(v).toLocaleString() : ''),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_value, record) => (
        <Space>
          <Button
            size="small"
            disabled={
              record.surface === 'template'
                ? (!isStaff || record.operation_type !== 'designer_cli')
                : !isStaff
            }
            onClick={() => {
              if (record.surface === 'template') {
                openEditTemplateModal(record)
                return
              }
              openEditActionModal(record)
            }}
          >
            Edit
          </Button>
          <Popconfirm
            title={record.surface === 'template' ? 'Delete template?' : 'Delete action?'}
            okText="Delete"
            cancelText="Cancel"
            onConfirm={() => {
              if (record.surface === 'template') {
                void handleDeleteTemplate(record)
                return
              }
              void handleDeleteAction(record)
            }}
            disabled={!isStaff}
          >
            <Button size="small" danger disabled={!isStaff}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [handleDeleteAction, handleDeleteTemplate, isStaff, openEditActionModal, openEditTemplateModal])

  const table = useTableToolkit<UnifiedRow>({
    tableId: `operation-exposures-${activeSurface}`,
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })
  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

  const templateExposuresQuery = useQuery({
    queryKey: ['templates', 'template-exposures', templateReloadTick],
    enabled: activeSurface !== 'action_catalog',
    queryFn: async () => listOperationCatalogExposures({
      surface: 'template',
      limit: 1000,
      offset: 0,
    }),
  })

  const actionExposuresQuery = useQuery({
    queryKey: ['templates', 'action-catalog-exposures', actionReloadTick],
    enabled: isStaff && activeSurface !== 'template',
    queryFn: async () => listOperationCatalogExposures({
      surface: 'action_catalog',
      limit: 1000,
      offset: 0,
    }),
  })

  const actionDefinitionsQuery = useQuery({
    queryKey: ['templates', 'action-catalog-definitions', actionReloadTick],
    enabled: isStaff && activeSurface !== 'template',
    queryFn: async () => listOperationCatalogDefinitions({
      limit: 1000,
      offset: 0,
    }),
  })

  const templateRowsAll = useMemo<TemplateRow[]>(() => (
    (templateExposuresQuery.data?.exposures ?? [])
      .filter((exposure) => exposure.surface === 'template')
      .map((exposure) => ({
        id: String(exposure.alias || ''),
        surface: 'template',
        status: String(exposure.status || (exposure.is_active !== false ? 'published' : 'draft')),
        name: String(exposure.name || ''),
        description: String(exposure.description || ''),
        operation_type: String(exposure.operation_type || 'designer_cli'),
        target_entity: String(exposure.target_entity || 'infobase'),
        template_data: isPlainObject(exposure.template_data) ? exposure.template_data : {},
        is_active: exposure.is_active !== false,
        created_at: String(exposure.created_at || ''),
        updated_at: String(exposure.updated_at || ''),
        exposure_id: String(exposure.id || ''),
        definition_id: String(exposure.definition_id || ''),
      }))
  ), [templateExposuresQuery.data?.exposures])

  const actionDefinitionsById = useMemo(() => {
    const map = new Map<string, OperationCatalogDefinition>()
    for (const definition of actionDefinitionsQuery.data?.definitions ?? []) {
      if (typeof definition.id === 'string') {
        map.set(definition.id, definition)
      }
    }
    return map
  }, [actionDefinitionsQuery.data?.definitions])

  const actionRowsAll = useMemo<ActionRow[]>(() => (
    (actionExposuresQuery.data?.exposures ?? [])
      .filter((exposure) => exposure.surface === 'action_catalog')
      .map((exposure) => ({
        id: exposure.id,
        surface: 'action_catalog',
        alias: String(exposure.alias || ''),
        name: String(exposure.name || ''),
        description: String(exposure.description || ''),
        capability: String(exposure.capability || ''),
        contexts: Array.isArray(exposure.contexts)
          ? exposure.contexts.filter((item): item is string => typeof item === 'string')
          : [],
        status: String(exposure.status || ''),
        is_active: exposure.is_active !== false,
        updated_at: String(exposure.updated_at || ''),
        exposure,
        definition: actionDefinitionsById.get(String(exposure.definition_id || '')) ?? null,
      }))
  ), [actionDefinitionsById, actionExposuresQuery.data?.exposures])

  const sourceRows = useMemo<UnifiedRow[]>(() => {
    if (activeSurface === 'template') return templateRowsAll
    if (activeSurface === 'action_catalog') return actionRowsAll
    return [...templateRowsAll, ...actionRowsAll]
  }, [activeSurface, actionRowsAll, templateRowsAll])

  const pagedRows = useMemo(() => {
    let rows = sourceRows.slice()

    const q = table.search.trim().toLowerCase()
    if (q) {
      rows = rows.filter((row) => {
        if (row.surface === 'template') {
          return (
            row.id.toLowerCase().includes(q)
            || row.name.toLowerCase().includes(q)
            || String(row.description || '').toLowerCase().includes(q)
            || row.operation_type.toLowerCase().includes(q)
            || row.target_entity.toLowerCase().includes(q)
          )
        }
        return (
          row.alias.toLowerCase().includes(q)
          || row.name.toLowerCase().includes(q)
          || row.capability.toLowerCase().includes(q)
          || row.status.toLowerCase().includes(q)
        )
      })
    }

    const filters = table.filtersPayload
    if (filters) {
      const capabilityFilter = isPlainObject(filters.capability) ? filters.capability.value : null
      if (capabilityFilter !== null && capabilityFilter !== undefined && String(capabilityFilter).trim()) {
        const next = String(capabilityFilter).trim().toLowerCase()
        rows = rows.filter((row) => (
          row.surface === 'action_catalog' && row.capability.toLowerCase().includes(next)
        ))
      }

      const statusFilter = isPlainObject(filters.status) ? filters.status.value : null
      if (statusFilter !== null && statusFilter !== undefined && String(statusFilter).trim()) {
        const next = String(statusFilter).trim().toLowerCase()
        rows = rows.filter((row) => row.status.toLowerCase().includes(next))
      }

      const operationTypeFilter = isPlainObject(filters.operation_type) ? filters.operation_type.value : null
      if (operationTypeFilter !== null && operationTypeFilter !== undefined && String(operationTypeFilter).trim()) {
        const next = String(operationTypeFilter).trim().toLowerCase()
        rows = rows.filter((row) => (
          row.surface === 'template' && row.operation_type.toLowerCase().includes(next)
        ))
      }

      const targetEntityFilter = isPlainObject(filters.target_entity) ? filters.target_entity.value : null
      if (targetEntityFilter !== null && targetEntityFilter !== undefined && String(targetEntityFilter).trim()) {
        const next = String(targetEntityFilter).trim().toLowerCase()
        rows = rows.filter((row) => (
          row.surface === 'template' && row.target_entity.toLowerCase().includes(next)
        ))
      }

      const surfaceFilter = isPlainObject(filters.surface) ? filters.surface.value : null
      if (surfaceFilter !== null && surfaceFilter !== undefined && String(surfaceFilter).trim()) {
        const next = String(surfaceFilter).trim().toLowerCase()
        rows = rows.filter((row) => row.surface.toLowerCase().includes(next))
      }

      const isActiveFilter = isPlainObject(filters.is_active) ? parseBooleanFilter(filters.is_active.value) : null
      if (typeof isActiveFilter === 'boolean') {
        rows = rows.filter((row) => row.is_active === isActiveFilter)
      }
    }

    const sort = table.sortPayload
    if (sort?.key && sort.order) {
      const direction = sort.order === 'desc' ? -1 : 1
      rows.sort((left, right) => {
        const key = sort.key
        if (key === 'is_active') {
          return (Number(left.is_active) - Number(right.is_active)) * direction
        }

        const leftValue = (
          key === 'name' ? left.name
            : key === 'surface' ? left.surface
              : key === 'operation_type' ? (left.surface === 'template' ? left.operation_type : '')
                : key === 'target_entity' ? (left.surface === 'template' ? left.target_entity : '')
                  : key === 'capability' ? (left.surface === 'action_catalog' ? left.capability : '')
                    : key === 'status' ? left.status
                      : key === 'updated_at' ? left.updated_at
                        : left.surface === 'template' ? left.id : left.alias
        )

        const rightValue = (
          key === 'name' ? right.name
            : key === 'surface' ? right.surface
              : key === 'operation_type' ? (right.surface === 'template' ? right.operation_type : '')
                : key === 'target_entity' ? (right.surface === 'template' ? right.target_entity : '')
                  : key === 'capability' ? (right.surface === 'action_catalog' ? right.capability : '')
                    : key === 'status' ? right.status
                      : key === 'updated_at' ? right.updated_at
                        : right.surface === 'template' ? right.id : right.alias
        )

        return String(leftValue).localeCompare(String(rightValue)) * direction
      })
    }

    const total = rows.length
    const paged = rows.slice(pageStart, pageStart + table.pagination.pageSize)
    return { rows: paged, total }
  }, [pageStart, sourceRows, table.filtersPayload, table.pagination.pageSize, table.search, table.sortPayload])

  const activeLoading = (
    (activeSurface !== 'action_catalog' && templateExposuresQuery.isLoading)
    || (activeSurface !== 'template' && isStaff && (actionExposuresQuery.isLoading || actionDefinitionsQuery.isLoading))
  )

  const activeError = (
    templateExposuresQuery.error
    ?? actionExposuresQuery.error
    ?? actionDefinitionsQuery.error
  )

  const activeErrorStatus = (activeError as { response?: { status?: number } } | null)?.response?.status
  const showAccessWarning = activeErrorStatus === 403

  const modalTitle = useMemo(() => {
    if (editorSurface === 'action_catalog') {
      return editingAction ? 'Edit action' : 'New action'
    }
    return editingTemplate ? 'Edit CLI Template' : 'New CLI Template'
  }, [editingAction, editingTemplate, editorSurface])

  const handleSaveTemplate = useCallback(async () => {
    if (createMutation.isPending || updateMutation.isPending) return
    const values = await form.validateFields()
    const built = buildTemplateWritePayloadFromEditor(values, { existingId: editingTemplate?.id })
    if (!built.ok) {
      message.error(built.error)
      return
    }
    if (editingTemplate) {
      await updateMutation.mutateAsync(built.payload)
      message.success('Template updated')
    } else {
      await createMutation.mutateAsync(built.payload)
      message.success('Template created')
    }
    setTemplateReloadTick((value) => value + 1)
    closeModal()
  }, [closeModal, createMutation, editingTemplate, form, message, updateMutation])

  const handleSaveAction = useCallback(async () => {
    const values = await form.validateFields()
    const action = buildActionFromForm(editingActionBase, values)
    const existing = editingAction?.definition
      ? { exposure: editingAction.exposure, definition: editingAction.definition }
      : undefined
    const payload = buildOperationCatalogUpsertFromAction(action, {
      existing,
      displayOrder: typeof existing?.exposure.display_order === 'number'
        ? existing.exposure.display_order
        : actionRowsAll.length,
    })
    if (!payload) {
      message.error('Action ID is required')
      return
    }

    const upserted = await upsertOperationCatalogExposure(payload)
    const publishResult = await publishOperationCatalogExposure(upserted.exposure.id)
    if (!publishResult.published) {
      const firstError = publishResult.validation_errors?.[0]?.message
      message.error(firstError ? `Publish failed: ${firstError}` : 'Publish failed')
      return
    }

    message.success(editingAction ? 'Action updated' : 'Action created')
    setActionReloadTick((value) => value + 1)
    closeModal()
  }, [actionRowsAll.length, closeModal, editingAction, editingActionBase, form, message])

  const handleApply = useCallback(async () => {
    try {
      if (editorSurface === 'template') {
        await handleSaveTemplate()
        return
      }
      await handleSaveAction()
    } catch (err) {
      message.error(toErrorMessage(err, editorSurface === 'template' ? 'Failed to save template' : 'Failed to save action'))
    }
  }, [editorSurface, handleSaveAction, handleSaveTemplate, message])

  const onSync = useCallback(async () => {
    try {
      const result = await syncMutation.mutateAsync({ dry_run: dryRun })
      message.success(`${result.message}: created=${result.created}, updated=${result.updated}, unchanged=${result.unchanged}`)
      setTemplateReloadTick((value) => value + 1)
    } catch (err) {
      const status = (err as { response?: { status?: number } } | null)?.response?.status
      if (status === 403) {
        message.error('Sync requires staff access')
        return
      }
      message.error('Failed to sync templates from registry')
    }
  }, [dryRun, message, syncMutation])

  const subtitle = activeSurface === 'all'
    ? 'Unified list for template and action exposures.'
    : activeSurface === 'template'
      ? 'Filtered by template surface.'
      : 'Filtered by action_catalog surface.'

  const searchPlaceholder = activeSurface === 'all'
    ? 'Search exposures'
    : activeSurface === 'template'
      ? 'Search templates'
      : 'Search actions'

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Operation Exposures</Title>
          <Text type="secondary">{subtitle}</Text>
        </div>
        <Space>
          {isStaff && activeSurface === 'all' && (
            <>
              <Button onClick={() => openCreateModal('template')}>New Template</Button>
              <Button onClick={() => openCreateModal('action_catalog')} data-testid="action-catalog-add">New Action</Button>
            </>
          )}
          {isStaff && activeSurface === 'template' && (
            <Button onClick={() => openCreateModal('template')}>New Template</Button>
          )}
          {isStaff && activeSurface === 'action_catalog' && (
            <Button onClick={() => openCreateModal('action_catalog')} data-testid="action-catalog-add">New Action</Button>
          )}
          {activeSurface !== 'action_catalog' && (
            <>
              <Space>
                <Text>Dry run</Text>
                <Switch checked={dryRun} onChange={setDryRun} />
              </Space>
              <Button type="primary" loading={syncMutation.isPending} onClick={() => void onSync()}>
                Sync from registry
              </Button>
            </>
          )}
        </Space>
      </div>

      {showAccessWarning && (
        <Alert
          type="warning"
          message="Access denied"
          description="Operation exposures for this surface are not available for your permissions."
          showIcon
        />
      )}

      <TableToolkit
        table={table}
        data={pagedRows.rows}
        total={pagedRows.total}
        loading={activeLoading}
        rowKey={(row) => `${row.surface}:${row.id}`}
        columns={columns}
        searchPlaceholder={searchPlaceholder}
      />

      <OperationExposureEditorModal
        open={modalOpen}
        title={modalTitle}
        surface={editorSurface}
        executorKindOptions={editorSurface === 'template' ? ['designer_cli'] : undefined}
        form={form}
        initialValues={editorValues}
        onCancel={closeModal}
        onApply={() => void handleApply()}
      />
    </Space>
  )
}

export function TemplatesPage() {
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)
  const [searchParams, setSearchParams] = useSearchParams()

  const requestedSurface = searchParams.get('surface')
  const normalizedSurface: SurfaceTabKey = useMemo(() => {
    if (!isStaff) return 'template'
    if (requestedSurface === 'template') return 'template'
    if (requestedSurface === 'action_catalog') return 'action_catalog'
    if (requestedSurface === 'all') return 'all'
    return 'all'
  }, [isStaff, requestedSurface])

  const [activeSurface, setActiveSurface] = useState<SurfaceTabKey>(normalizedSurface)

  useEffect(() => {
    setActiveSurface(normalizedSurface)
  }, [normalizedSurface])

  useEffect(() => {
    const current = searchParams.get('surface')

    if (!isStaff) {
      if (current === null) return
      const next = new URLSearchParams(searchParams)
      next.delete('surface')
      setSearchParams(next, { replace: true })
      return
    }

    if (current === normalizedSurface) return
    const next = new URLSearchParams(searchParams)
    next.set('surface', normalizedSurface)
    setSearchParams(next, { replace: true })
  }, [isStaff, normalizedSurface, searchParams, setSearchParams])

  const handleSurfaceChange = useCallback((next: string | number) => {
    const nextKey = String(next)
    const resolved: SurfaceTabKey = !isStaff
      ? 'template'
      : nextKey === 'template' || nextKey === 'action_catalog' || nextKey === 'all'
        ? nextKey
        : 'all'

    setActiveSurface(resolved)

    const nextParams = new URLSearchParams(searchParams)
    if (!isStaff) {
      nextParams.delete('surface')
    } else {
      nextParams.set('surface', resolved)
    }
    setSearchParams(nextParams, { replace: true })
  }, [isStaff, searchParams, setSearchParams])

  const surfaceOptions = useMemo(() => {
    const items: Array<{ value: SurfaceTabKey; label: string }> = [
      { value: 'all', label: 'All' },
      { value: 'template', label: 'Templates' },
      { value: 'action_catalog', label: 'Action Catalog' },
    ]
    return items
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {isStaff && (
        <Space direction="vertical" size="small">
          <Text type="secondary">Surface</Text>
          <Segmented
            value={activeSurface}
            onChange={handleSurfaceChange}
            options={surfaceOptions}
          />
        </Space>
      )}
      <OperationExposureListShell activeSurface={activeSurface} isStaff={isStaff} />
    </Space>
  )
}
