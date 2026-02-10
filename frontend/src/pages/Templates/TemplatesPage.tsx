import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Alert, App, Button, Form, Popconfirm, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { listOperationCatalogExposures } from '../../api/operationCatalog'
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
import { isPlainObject } from '../Settings/actionCatalogUtils'
import type { ActionFormValues } from '../Settings/actionCatalogTypes'
import { OperationExposureEditorModal } from '../Settings/actionCatalog/OperationExposureEditorModal'
import { buildTemplateEditorValues, buildTemplateWritePayloadFromEditor } from './templateEditorAdapter'

const { Title, Text } = Typography

type TemplateRow = OperationTemplate & {
  status: string
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

function OperationTemplateListShell({
  canManageTemplate,
  canManageAnyTemplate,
}: {
  canManageTemplate: (templateId: string) => boolean
  canManageAnyTemplate: boolean
}) {
  const { message } = App.useApp()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<TemplateRow | null>(null)
  const [exposuresReloadTick, setExposuresReloadTick] = useState(0)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)
  const [form] = Form.useForm<ActionFormValues>()

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
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
    setEditorValues(null)
  }, [])

  const openCreateModal = useCallback(() => {
    setEditingTemplate(null)
    setEditorValues(buildTemplateEditorValues(null))
    setModalOpen(true)
  }, [])

  const openEditTemplateModal = useCallback((template: TemplateRow) => {
    setEditingTemplate(template)
    setEditorValues(buildTemplateEditorValues(template))
    setModalOpen(true)
  }, [])

  const handleDeleteTemplate = useCallback(async (template: TemplateRow) => {
    try {
      await deleteMutation.mutateAsync({ template_id: template.id })
      setExposuresReloadTick((value) => value + 1)
      message.success('Template deleted')
    } catch (err) {
      message.error(toErrorMessage(err, 'Failed to delete template'))
    }
  }, [deleteMutation, message])

  const columns: ColumnsType<TemplateRow> = useMemo(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (value: string, record) => (
        <div>
          <div style={{ fontWeight: 600 }}>{value}</div>
          <Text type="secondary">{record.id}</Text>
        </div>
      ),
    },
    {
      title: 'Operation Type',
      dataIndex: 'operation_type',
      key: 'operation_type',
      width: 180,
    },
    {
      title: 'Target',
      dataIndex: 'target_entity',
      key: 'target_entity',
      width: 120,
    },
    {
      title: 'Capability',
      dataIndex: 'capability',
      key: 'capability',
      width: 220,
      render: (value: string | undefined) => value || <Text type="secondary">—</Text>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 130,
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 90,
      render: (value: boolean) => (value ? 'yes' : 'no'),
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (value: string) => (value ? new Date(value).toLocaleString() : ''),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_value, record) => (
        <Space>
          <Button
            size="small"
            disabled={!canManageTemplate(record.id)}
            onClick={() => {
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
              void handleDeleteTemplate(record)
            }}
            disabled={!canManageTemplate(record.id)}
          >
            <Button
              size="small"
              danger
              disabled={!canManageTemplate(record.id)}
            >
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [canManageTemplate, handleDeleteTemplate, openEditTemplateModal])

  const table = useTableToolkit<TemplateRow>({
    tableId: 'operation-templates',
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

  const exposuresQuery = useQuery({
    queryKey: [
      'templates',
      'operation-exposures',
      exposuresReloadTick,
      searchValue,
      filtersParam ?? '',
      sortParam ?? '',
      table.pagination.page,
      table.pagination.pageSize,
    ],
    queryFn: async () => listOperationCatalogExposures({
      surface: 'template',
      search: searchValue || undefined,
      filters: filtersParam,
      sort: sortParam,
      limit: table.pagination.pageSize,
      offset: pageStart,
    }),
  })

  const pagedRows = useMemo(() => {
    const rows: TemplateRow[] = []

    for (const exposure of exposuresQuery.data?.exposures ?? []) {
      if (exposure.surface !== 'template') continue
      rows.push({
        id: String(exposure.alias || ''),
        status: String(exposure.status || (exposure.is_active !== false ? 'published' : 'draft')),
        name: String(exposure.name || ''),
        description: String(exposure.description || ''),
        operation_type: String(exposure.operation_type || 'designer_cli'),
        target_entity: String(exposure.target_entity || 'infobase'),
        capability: String(exposure.capability || '').trim() || undefined,
        capability_config: isPlainObject(exposure.capability_config) ? exposure.capability_config : {},
        template_data: isPlainObject(exposure.template_data) ? exposure.template_data : {},
        is_active: exposure.is_active !== false,
        created_at: String(exposure.created_at || ''),
        updated_at: String(exposure.updated_at || ''),
        exposure_id: String(exposure.id || ''),
        definition_id: String(exposure.definition_id || ''),
      })
    }

    return {
      rows,
      total: typeof exposuresQuery.data?.total === 'number' ? exposuresQuery.data.total : rows.length,
    }
  }, [exposuresQuery.data?.exposures, exposuresQuery.data?.total])

  const activeError = exposuresQuery.error
  const activeErrorStatus = (activeError as { response?: { status?: number } } | null)?.response?.status
  const showAccessWarning = activeErrorStatus === 403

  const modalTitle = useMemo(() => (
    editingTemplate ? 'Edit Template' : 'New Template'
  ), [editingTemplate])

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

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Operation Templates</Title>
          <Text type="secondary">Templates-only registry for manual operations and workflow execution.</Text>
        </div>
        <Space>
          {canManageAnyTemplate && <Button onClick={openCreateModal}>New Template</Button>}
          {canManageAnyTemplate && (
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
          description="Operation templates are not available for your permissions."
          showIcon
        />
      )}

      <TableToolkit
        table={table}
        data={pagedRows.rows}
        total={pagedRows.total}
        loading={exposuresQuery.isLoading}
        rowKey={(row) => row.id}
        columns={columns}
        searchPlaceholder="Search templates"
      />

      {modalOpen && (
        <OperationExposureEditorModal
          open={modalOpen}
          title={modalTitle}
          surface="template"
          executorKindOptions={['ibcmd_cli', 'designer_cli', 'workflow']}
          form={form}
          initialValues={editorValues}
          onCancel={closeModal}
          onApply={() => void handleSaveTemplate()}
        />
      )}
    </Space>
  )
}

export function TemplatesPage() {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const canManageAnyTemplate = isStaff || authz.canAnyTemplate('MANAGE')
  const canManageTemplate = useCallback((templateId: string) => (
    isStaff || authz.canTemplate(templateId, 'MANAGE')
  ), [authz, isStaff])
  const [searchParams, setSearchParams] = useSearchParams()
  const surfaceParam = searchParams.get('surface')

  useEffect(() => {
    if (surfaceParam === null) return
    const next = new URLSearchParams(searchParams)
    next.delete('surface')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, surfaceParam])

  return (
    <OperationTemplateListShell
      canManageTemplate={canManageTemplate}
      canManageAnyTemplate={canManageAnyTemplate}
    />
  )
}
