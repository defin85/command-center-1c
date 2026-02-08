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
  useOperationTemplates,
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

type SurfaceTabKey = 'template' | 'action_catalog'

type TemplateRow = OperationTemplate & { surface: 'template' }

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
  const [editorSurface, setEditorSurface] = useState<SurfaceTabKey>('template')
  const [editingTemplate, setEditingTemplate] = useState<TemplateRow | null>(null)
  const [editingAction, setEditingAction] = useState<ActionRow | null>(null)
  const [editingActionBase, setEditingActionBase] = useState<PlainObject | null>(null)
  const [actionReloadTick, setActionReloadTick] = useState(0)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)
  const [form] = Form.useForm<ActionFormValues>()

  const templateFallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'operation_type', label: 'Operation Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'target_entity', label: 'Target', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Active', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'updated_at', label: 'Updated', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', sortable: false, groupKey: 'meta', groupLabel: 'Meta' },
  ], [])
  const actionFallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'capability', label: 'Capability', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Active', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
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

  const openCreateModal = useCallback(() => {
    setEditingTemplate(null)
    setEditingAction(null)
    setEditingActionBase(null)
    setEditorSurface(activeSurface)
    const nextValues = activeSurface === 'template'
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
      message.success('Template deleted')
    } catch (err) {
      message.error(toErrorMessage(err, 'Failed to delete template'))
    }
  }, [deleteMutation, message])

  const handleDeleteAction = useCallback(async (row: ActionRow) => {
    try {
      await deleteOperationCatalogExposure(row.id)
      message.success('Action deleted')
      setActionReloadTick((value) => value + 1)
    } catch (err) {
      message.error(toErrorMessage(err, 'Failed to delete action'))
    }
  }, [message])

  const templateColumns: ColumnsType<UnifiedRow> = useMemo(() => ([
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
      title: 'Operation Type',
      dataIndex: 'operation_type' as const,
      key: 'operation_type',
      width: 220,
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
      width: 140,
      render: (_value, record) => (
        <Space>
          <Button
            size="small"
            disabled={record.surface !== 'template' || !isStaff || record.operation_type !== 'designer_cli'}
            onClick={() => {
              if (record.surface !== 'template') return
              openEditTemplateModal(record)
            }}
          >
            Edit
          </Button>
          <Popconfirm
            title="Delete template?"
            okText="Delete"
            cancelText="Cancel"
            onConfirm={() => {
              if (record.surface !== 'template') return
              void handleDeleteTemplate(record)
            }}
            disabled={record.surface !== 'template' || !isStaff}
          >
            <Button size="small" danger disabled={record.surface !== 'template' || !isStaff}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [handleDeleteTemplate, isStaff, openEditTemplateModal])

  const actionColumns: ColumnsType<UnifiedRow> = useMemo(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (value: string, record) => (
        <div>
          <div style={{ fontWeight: 600 }}>{value}</div>
          <Text type="secondary">{record.surface === 'action_catalog' ? record.alias : record.id}</Text>
        </div>
      ),
    },
    {
      title: 'Capability',
      dataIndex: 'capability' as const,
      key: 'capability',
      width: 220,
      render: (_value, record) => (record.surface === 'action_catalog' ? record.capability : ''),
    },
    {
      title: 'Active',
      dataIndex: 'is_active' as const,
      key: 'is_active',
      width: 90,
      render: (v: boolean) => (v ? 'yes' : 'no'),
    },
    {
      title: 'Status',
      dataIndex: 'status' as const,
      key: 'status',
      width: 110,
      render: (_value, record) => (record.surface === 'action_catalog' ? record.status : ''),
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
      width: 160,
      render: (_value, record) => (
        <Space>
          <Button
            size="small"
            disabled={record.surface !== 'action_catalog' || !isStaff}
            onClick={() => {
              if (record.surface !== 'action_catalog') return
              openEditActionModal(record)
            }}
          >
            Edit
          </Button>
          <Popconfirm
            title="Delete action?"
            okText="Delete"
            cancelText="Cancel"
            onConfirm={() => {
              if (record.surface !== 'action_catalog') return
              void handleDeleteAction(record)
            }}
            disabled={record.surface !== 'action_catalog' || !isStaff}
          >
            <Button size="small" danger disabled={record.surface !== 'action_catalog' || !isStaff}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [handleDeleteAction, isStaff, openEditActionModal])

  const columns = activeSurface === 'template' ? templateColumns : actionColumns
  const fallbackColumnConfigs = activeSurface === 'template'
    ? templateFallbackColumnConfigs
    : actionFallbackColumnConfigs
  const table = useTableToolkit<UnifiedRow>({
    tableId: activeSurface === 'template' ? 'templates' : 'operation-catalog-action-exposures',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })
  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

  const templatesQuery = useOperationTemplates({
    search: table.search,
    filters: table.filtersPayload,
    sort: table.sortPayload,
    limit: table.pagination.pageSize,
    offset: pageStart,
  })

  const actionExposuresQuery = useQuery({
    queryKey: ['templates', 'action-catalog-exposures', actionReloadTick],
    enabled: isStaff && activeSurface === 'action_catalog',
    queryFn: async () => listOperationCatalogExposures({
      surface: 'action_catalog',
      limit: 1000,
      offset: 0,
    }),
  })

  const actionDefinitionsQuery = useQuery({
    queryKey: ['templates', 'action-catalog-definitions', actionReloadTick],
    enabled: isStaff && activeSurface === 'action_catalog',
    queryFn: async () => listOperationCatalogDefinitions({
      limit: 1000,
      offset: 0,
    }),
  })

  const templateRows = useMemo<TemplateRow[]>(() => (
    (templatesQuery.data?.templates ?? []).map((template) => ({ ...template, surface: 'template' }))
  ), [templatesQuery.data?.templates])
  const totalTemplates = typeof templatesQuery.data?.total === 'number'
    ? templatesQuery.data.total
    : typeof templatesQuery.data?.count === 'number'
      ? templatesQuery.data.count
      : templateRows.length

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

  const actionRowsPage = useMemo(() => {
    let rows = actionRowsAll.slice()
    const q = table.search.trim().toLowerCase()
    if (q) {
      rows = rows.filter((row) => (
        row.alias.toLowerCase().includes(q)
        || row.name.toLowerCase().includes(q)
        || row.capability.toLowerCase().includes(q)
      ))
    }

    const filters = table.filtersPayload
    if (filters) {
      const capabilityFilter = isPlainObject(filters.capability) ? filters.capability.value : null
      if (capabilityFilter !== null && capabilityFilter !== undefined && String(capabilityFilter).trim()) {
        const next = String(capabilityFilter).trim().toLowerCase()
        rows = rows.filter((row) => row.capability.toLowerCase().includes(next))
      }
      const statusFilter = isPlainObject(filters.status) ? filters.status.value : null
      if (statusFilter !== null && statusFilter !== undefined && String(statusFilter).trim()) {
        const next = String(statusFilter).trim().toLowerCase()
        rows = rows.filter((row) => row.status.toLowerCase().includes(next))
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
            : key === 'capability' ? left.capability
              : key === 'status' ? left.status
                : key === 'updated_at' ? left.updated_at
                  : left.alias
        )
        const rightValue = (
          key === 'name' ? right.name
            : key === 'capability' ? right.capability
              : key === 'status' ? right.status
                : key === 'updated_at' ? right.updated_at
                  : right.alias
        )
        return leftValue.localeCompare(rightValue) * direction
      })
    }

    const total = rows.length
    const paged = rows.slice(pageStart, pageStart + table.pagination.pageSize)
    return { rows: paged, total }
  }, [actionRowsAll, pageStart, table.filtersPayload, table.pagination.pageSize, table.search, table.sortPayload])

  const activeRows: UnifiedRow[] = activeSurface === 'template' ? templateRows : actionRowsPage.rows
  const activeTotal = activeSurface === 'template' ? totalTemplates : actionRowsPage.total
  const activeLoading = activeSurface === 'template'
    ? templatesQuery.isLoading
    : (actionExposuresQuery.isLoading || actionDefinitionsQuery.isLoading)
  const activeError = activeSurface === 'template'
    ? templatesQuery.error
    : (actionExposuresQuery.error ?? actionDefinitionsQuery.error)
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
      if (activeSurface === 'template') {
        templatesQuery.refetch()
      }
    } catch (err) {
      const status = (err as { response?: { status?: number } } | null)?.response?.status
      if (status === 403) {
        message.error('Sync requires staff access')
        return
      }
      message.error('Failed to sync templates from registry')
    }
  }, [activeSurface, dryRun, message, syncMutation, templatesQuery])

  const title = activeSurface === 'template' ? 'Operation Templates' : 'Action Catalog'
  const subtitle = activeSurface === 'template'
    ? 'Manage template exposures and sync from the in-code registry.'
    : 'Manage action exposures in the same list + editor flow.'

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>{title}</Title>
          <Text type="secondary">{subtitle}</Text>
        </div>
        <Space>
          {isStaff && (
            <Button
              onClick={openCreateModal}
              data-testid={activeSurface === 'action_catalog' ? 'action-catalog-add' : undefined}
            >
              {activeSurface === 'template' ? 'New CLI Template' : 'New Action'}
            </Button>
          )}
          {activeSurface === 'template' && (
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
          description={activeSurface === 'template'
            ? 'Templates endpoints require authentication; sync requires staff access.'
            : 'Action catalog management is staff-only.'}
          showIcon
        />
      )}

      <TableToolkit
        table={table}
        data={activeRows}
        total={activeTotal}
        loading={activeLoading}
        rowKey={(row) => `${row.surface}:${row.id}`}
        columns={columns}
        searchPlaceholder={activeSurface === 'template' ? 'Search templates' : 'Search actions'}
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
  const normalizedSurface: SurfaceTabKey = requestedSurface === 'action_catalog' && isStaff
    ? 'action_catalog'
    : 'template'

  const [activeSurface, setActiveSurface] = useState<SurfaceTabKey>(normalizedSurface)

  useEffect(() => {
    setActiveSurface(normalizedSurface)
  }, [normalizedSurface])

  useEffect(() => {
    const current = searchParams.get('surface')
    if (normalizedSurface === 'action_catalog') {
      if (current === 'action_catalog') return
      const next = new URLSearchParams(searchParams)
      next.set('surface', 'action_catalog')
      setSearchParams(next, { replace: true })
      return
    }
    if (current === null) return
    const next = new URLSearchParams(searchParams)
    next.delete('surface')
    setSearchParams(next, { replace: true })
  }, [normalizedSurface, searchParams, setSearchParams])

  const handleSurfaceChange = useCallback((next: string | number) => {
    const nextKey = String(next)
    const resolved: SurfaceTabKey = nextKey === 'action_catalog' && isStaff ? 'action_catalog' : 'template'
    setActiveSurface(resolved)
    const nextParams = new URLSearchParams(searchParams)
    if (resolved === 'action_catalog') {
      nextParams.set('surface', 'action_catalog')
    } else {
      nextParams.delete('surface')
    }
    setSearchParams(nextParams, { replace: true })
  }, [isStaff, searchParams, setSearchParams])

  const surfaceOptions = useMemo(() => {
    const items: Array<{ value: SurfaceTabKey; label: string }> = [
      { value: 'template', label: 'Templates' },
    ]
    if (isStaff) {
      items.push({ value: 'action_catalog', label: 'Action Catalog' })
    }
    return items
  }, [isStaff])

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
