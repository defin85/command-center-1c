import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Alert, App, Button, Form, Popconfirm, Space, Switch, Tabs, Typography } from 'antd'
import type { TabsProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'

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
import { ActionCatalogPage } from '../Settings/ActionCatalogPage'
import type { ActionFormValues } from '../Settings/actionCatalogTypes'
import { OperationExposureEditorModal } from '../Settings/actionCatalog/OperationExposureEditorModal'
import { buildTemplateEditorValues, buildTemplateWritePayloadFromEditor } from './templateEditorAdapter'

const { Title, Text } = Typography

type SurfaceTabKey = 'template' | 'action_catalog'

function OperationTemplatesSurface({ isStaff }: { isStaff: boolean }) {
  const { message } = App.useApp()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<OperationTemplate | null>(null)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)
  const [form] = Form.useForm<ActionFormValues>()
  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'operation_type', label: 'Operation Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'target_entity', label: 'Target', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Active', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'updated_at', label: 'Updated', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', sortable: false, groupKey: 'meta', groupLabel: 'Meta' },
  ], [])

  const syncMutation = useSyncTemplatesFromRegistry()
  const createMutation = useCreateTemplate()
  const updateMutation = useUpdateTemplate()
  const deleteMutation = useDeleteTemplate()

  const openCreateModal = useCallback(() => {
    setEditingTemplate(null)
    const nextValues = buildTemplateEditorValues(null)
    setEditorValues(nextValues)
    form.resetFields()
    form.setFieldsValue(nextValues)
    setModalOpen(true)
  }, [form])

  const openEditModal = useCallback((template: OperationTemplate) => {
    setEditingTemplate(template)
    const nextValues = buildTemplateEditorValues(template)
    setEditorValues(nextValues)
    form.resetFields()
    form.setFieldsValue(nextValues)
    setModalOpen(true)
  }, [form])

  const closeModal = useCallback(() => {
    setModalOpen(false)
    setEditingTemplate(null)
    setEditorValues(null)
    form.resetFields()
  }, [form])

  const handleSaveTemplate = useCallback(async () => {
    try {
      if (createMutation.isPending || updateMutation.isPending) return
      const values = await form.validateFields()
      const built = buildTemplateWritePayloadFromEditor(values, { existingId: editingTemplate?.id })
      if (!built.ok) {
        message.error(built.error)
        return
      }
      const payload = built.payload

      if (editingTemplate) {
        await updateMutation.mutateAsync(payload)
        message.success('Template updated')
      } else {
        await createMutation.mutateAsync(payload)
        message.success('Template created')
      }
      closeModal()
    } catch (err) {
      if (err instanceof Error) {
        message.error(err.message)
      }
    }
  }, [closeModal, createMutation, editingTemplate, form, message, updateMutation])

  const handleDeleteTemplate = useCallback(async (template: OperationTemplate) => {
    try {
      await deleteMutation.mutateAsync({ template_id: template.id })
      message.success('Template deleted')
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to delete template'
      message.error(text)
    }
  }, [deleteMutation, message])

  const columns: ColumnsType<OperationTemplate> = useMemo(() => ([
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
      width: 220,
    },
    {
      title: 'Target',
      dataIndex: 'target_entity',
      key: 'target_entity',
      width: 120,
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
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
            disabled={!isStaff || record.operation_type !== 'designer_cli'}
            onClick={() => openEditModal(record)}
          >
            Edit
          </Button>
          <Popconfirm
            title="Delete template?"
            okText="Delete"
            cancelText="Cancel"
            onConfirm={() => handleDeleteTemplate(record)}
            disabled={!isStaff}
          >
            <Button size="small" danger disabled={!isStaff}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [handleDeleteTemplate, isStaff, openEditModal])

  const table = useTableToolkit({
    tableId: 'templates',
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

  const templates = templatesQuery.data?.templates ?? []
  const totalTemplates = typeof templatesQuery.data?.total === 'number'
    ? templatesQuery.data.total
    : typeof templatesQuery.data?.count === 'number'
      ? templatesQuery.data.count
      : templates.length

  const onSync = async () => {
    try {
      const result = await syncMutation.mutateAsync({ dry_run: dryRun })
      message.success(`${result.message}: created=${result.created}, updated=${result.updated}, unchanged=${result.unchanged}`)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } } | null)?.response?.status
      if (status === 403) {
        message.error('Sync requires staff access')
        return
      }
      message.error('Failed to sync templates from registry')
    }
  }

  const showStaffWarning = templatesQuery.error
    && (templatesQuery.error as { response?: { status?: number } } | null)?.response?.status === 403

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Operation Templates</Title>
          <Text type="secondary">List templates and sync from in-code registry (staff-only).</Text>
        </div>
        <Space>
          {isStaff && (
            <Button onClick={openCreateModal}>
              New CLI Template
            </Button>
          )}
          <Space>
            <Text>Dry run</Text>
            <Switch checked={dryRun} onChange={setDryRun} />
          </Space>
          <Button type="primary" loading={syncMutation.isPending} onClick={onSync}>
            Sync from registry
          </Button>
        </Space>
      </div>

      {showStaffWarning && (
        <Alert
          type="warning"
          message="Access denied"
          description="Templates endpoints require authentication; sync requires staff access."
          showIcon
        />
      )}

      <TableToolkit
        table={table}
        data={templates}
        total={totalTemplates}
        loading={templatesQuery.isLoading}
        rowKey="id"
        columns={columns}
        searchPlaceholder="Search templates"
      />

      <OperationExposureEditorModal
        open={modalOpen}
        title={editingTemplate ? 'Edit CLI Template' : 'New CLI Template'}
        surface="template"
        executorKindOptions={['designer_cli']}
        form={form}
        initialValues={editorValues}
        onCancel={closeModal}
        onApply={() => void handleSaveTemplate()}
      />
    </Space>
  )
}

export function TemplatesPage() {
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)
  const [searchParams, setSearchParams] = useSearchParams()

  const requestedSurface = searchParams.get('surface')
  const normalizedSurface: SurfaceTabKey = (requestedSurface === 'action_catalog' && isStaff)
    ? 'action_catalog'
    : 'template'

  const [activeTab, setActiveTab] = useState<SurfaceTabKey>(normalizedSurface)

  useEffect(() => {
    setActiveTab(normalizedSurface)
  }, [normalizedSurface])

  const handleTabChange = useCallback((next: string) => {
    const resolved: SurfaceTabKey = (next === 'action_catalog' && isStaff) ? 'action_catalog' : 'template'
    setActiveTab(resolved)
    const nextParams = new URLSearchParams(searchParams)
    if (resolved === 'action_catalog') {
      nextParams.set('surface', 'action_catalog')
    } else {
      nextParams.delete('surface')
    }
    setSearchParams(nextParams, { replace: true })
  }, [isStaff, searchParams, setSearchParams])

  const tabItems: TabsProps['items'] = useMemo(() => {
    const items: TabsProps['items'] = [
      {
        key: 'template',
        label: 'Templates',
        children: <OperationTemplatesSurface isStaff={isStaff} />,
      },
    ]
    if (isStaff) {
      items.push({
        key: 'action_catalog',
        label: 'Action Catalog',
        children: <ActionCatalogPage />,
      })
    }
    return items
  }, [isStaff])

  return (
    <Tabs
      activeKey={activeTab}
      onChange={handleTabChange}
      items={tabItems}
      destroyInactiveTabPane={false}
    />
  )
}
