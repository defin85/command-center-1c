import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Alert, App, Button, Form, Popconfirm, Segmented, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  deleteOperationCatalogExposure,
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
import { useAuthz } from '../../authz/useAuthz'
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
  canManageTemplate,
  canManageAnyTemplate,
}: {
  activeSurface: SurfaceTabKey
  isStaff: boolean
  canManageTemplate: (templateId: string) => boolean
  canManageAnyTemplate: boolean
}) {
  const { message } = App.useApp()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editorSurface, setEditorSurface] = useState<EditorSurfaceKey>('template')
  const [editingTemplate, setEditingTemplate] = useState<TemplateRow | null>(null)
  const [editingAction, setEditingAction] = useState<ActionRow | null>(null)
  const [editingActionBase, setEditingActionBase] = useState<PlainObject | null>(null)
  const [exposuresReloadTick, setExposuresReloadTick] = useState(0)
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
  }, [])

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
    setModalOpen(true)
  }, [activeSurface])

  const openEditTemplateModal = useCallback((template: TemplateRow) => {
    setEditingTemplate(template)
    setEditingAction(null)
    setEditingActionBase(null)
    setEditorSurface('template')
    const nextValues = buildTemplateEditorValues(template)
    setEditorValues(nextValues)
    setModalOpen(true)
  }, [])

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
    setModalOpen(true)
  }, [message])

  const handleDeleteTemplate = useCallback(async (template: TemplateRow) => {
    try {
      await deleteMutation.mutateAsync({ template_id: template.id })
      setExposuresReloadTick((value) => value + 1)
      message.success('Template deleted')
    } catch (err) {
      message.error(toErrorMessage(err, 'Failed to delete template'))
    }
  }, [deleteMutation, message])

  const handleDeleteAction = useCallback(async (row: ActionRow) => {
    try {
      await deleteOperationCatalogExposure(row.id)
      setExposuresReloadTick((value) => value + 1)
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
                ? (!canManageTemplate(record.id) || record.operation_type !== 'designer_cli')
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
            disabled={record.surface === 'template' ? !canManageTemplate(record.id) : !isStaff}
          >
            <Button
              size="small"
              danger
              disabled={record.surface === 'template' ? !canManageTemplate(record.id) : !isStaff}
            >
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [canManageTemplate, handleDeleteAction, handleDeleteTemplate, isStaff, openEditActionModal, openEditTemplateModal])

  const table = useTableToolkit<UnifiedRow>({
    tableId: `operation-exposures-${activeSurface}`,
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
    disableServerMetadata: true,
  })
  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const searchValue = table.search.trim()
  const filtersParam = useMemo(() => (
    table.filtersPayload ? JSON.stringify(table.filtersPayload) : undefined
  ), [table.filtersPayload])
  const sortParam = useMemo(() => (
    table.sortPayload ? JSON.stringify(table.sortPayload) : undefined
  ), [table.sortPayload])
  const requestSurface = activeSurface === 'all' ? undefined : activeSurface
  const includeDefinitions = isStaff && activeSurface !== 'template'

  const exposuresQuery = useQuery({
    queryKey: [
      'templates',
      'operation-exposures',
      requestSurface ?? 'all',
      exposuresReloadTick,
      searchValue,
      filtersParam ?? '',
      sortParam ?? '',
      table.pagination.page,
      table.pagination.pageSize,
      includeDefinitions ? 'definitions' : 'plain',
    ],
    enabled: activeSurface !== 'action_catalog' || isStaff,
    queryFn: async () => listOperationCatalogExposures({
      surface: requestSurface,
      search: searchValue || undefined,
      filters: filtersParam,
      sort: sortParam,
      include: includeDefinitions ? 'definitions' : undefined,
      limit: table.pagination.pageSize,
      offset: pageStart,
    }),
  })

  const definitionsById = useMemo(() => {
    const map = new Map<string, OperationCatalogDefinition>()
    for (const definition of exposuresQuery.data?.definitions ?? []) {
      if (typeof definition.id === 'string') {
        map.set(definition.id, definition)
      }
    }
    return map
  }, [exposuresQuery.data?.definitions])

  const pagedRows = useMemo(() => {
    const rows: UnifiedRow[] = []

    for (const exposure of exposuresQuery.data?.exposures ?? []) {
      if (exposure.surface === 'template') {
        rows.push({
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
        })
        continue
      }

      if (exposure.surface === 'action_catalog') {
        rows.push({
          id: String(exposure.id || ''),
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
          definition: definitionsById.get(String(exposure.definition_id || '')) ?? null,
        })
      }
    }

    return {
      rows,
      total: typeof exposuresQuery.data?.total === 'number' ? exposuresQuery.data.total : rows.length,
    }
  }, [definitionsById, exposuresQuery.data?.exposures, exposuresQuery.data?.total])

  const activeLoading = exposuresQuery.isLoading
  const activeError = exposuresQuery.error

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
    setExposuresReloadTick((value) => value + 1)
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
        : 0,
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
    setExposuresReloadTick((value) => value + 1)
    closeModal()
  }, [closeModal, editingAction, editingActionBase, form, message])

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
      setExposuresReloadTick((value) => value + 1)
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
          {activeSurface === 'all' && (
            <>
              {canManageAnyTemplate && <Button onClick={() => openCreateModal('template')}>New Template</Button>}
              {isStaff && <Button onClick={() => openCreateModal('action_catalog')} data-testid="action-catalog-add">New Action</Button>}
            </>
          )}
          {canManageAnyTemplate && activeSurface === 'template' && (
            <Button onClick={() => openCreateModal('template')}>New Template</Button>
          )}
          {isStaff && activeSurface === 'action_catalog' && (
            <Button onClick={() => openCreateModal('action_catalog')} data-testid="action-catalog-add">New Action</Button>
          )}
          {activeSurface !== 'action_catalog' && canManageAnyTemplate && (
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

      {modalOpen && (
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
      )}
    </Space>
  )
}

export function TemplatesPage() {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const authzResolved = !authz.isLoading
  const canManageAnyTemplate = isStaff || authz.canAnyTemplate('MANAGE')
  const canManageTemplate = useCallback((templateId: string) => (
    isStaff || authz.canTemplate(templateId, 'MANAGE')
  ), [authz, isStaff])
  const [searchParams, setSearchParams] = useSearchParams()

  const requestedSurface = searchParams.get('surface')
  const normalizedSurface: SurfaceTabKey = useMemo(() => {
    if (!authzResolved) {
      if (requestedSurface === 'template') return 'template'
      if (requestedSurface === 'action_catalog') return 'action_catalog'
      if (requestedSurface === 'all') return 'all'
      return 'all'
    }
    if (!isStaff) return 'template'
    if (requestedSurface === 'template') return 'template'
    if (requestedSurface === 'action_catalog') return 'action_catalog'
    if (requestedSurface === 'all') return 'all'
    return 'all'
  }, [authzResolved, isStaff, requestedSurface])

  const [activeSurface, setActiveSurface] = useState<SurfaceTabKey>(normalizedSurface)

  useEffect(() => {
    setActiveSurface(normalizedSurface)
  }, [normalizedSurface])

  useEffect(() => {
    if (!authzResolved) return
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
  }, [authzResolved, isStaff, normalizedSurface, searchParams, setSearchParams])

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
      <OperationExposureListShell
        activeSurface={activeSurface}
        isStaff={isStaff}
        canManageTemplate={canManageTemplate}
        canManageAnyTemplate={canManageAnyTemplate}
      />
    </Space>
  )
}
