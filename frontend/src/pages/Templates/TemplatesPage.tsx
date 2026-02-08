import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Alert, App, Button, Form, Input, Modal, Popconfirm, Space, Switch, Tabs, Typography } from 'antd'
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
import { DriverCommandBuilder, type DriverCommandOperationConfig } from '../../components/driverCommands/DriverCommandBuilder'
import { useMe } from '../../api/queries/me'
import { driverCommandConfigToTemplateData, templateDataToDriverCommandConfig } from '../../lib/commandConfigAdapter'
import { ActionCatalogPage } from '../Settings/ActionCatalogPage'

const { Title, Text } = Typography
const { TextArea } = Input

type SurfaceTabKey = 'template' | 'action_catalog'

function OperationTemplatesSurface({ isStaff }: { isStaff: boolean }) {
  const { message } = App.useApp()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<OperationTemplate | null>(null)
  const [cliConfig, setCliConfig] = useState<DriverCommandOperationConfig>({ driver: 'cli', mode: 'guided', params: {} })
  const [form] = Form.useForm<{ name: string; description?: string; is_active?: boolean }>()
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
    setCliConfig({
      driver: 'cli',
      mode: 'guided',
      params: {},
      args_text: '',
      cli_options: {
        disable_startup_messages: true,
        disable_startup_dialogs: true,
      },
    })
    form.setFieldsValue({ name: '', description: '', is_active: true })
    setModalOpen(true)
  }, [form])

  const openEditModal = useCallback((template: OperationTemplate) => {
    setEditingTemplate(template)
    setCliConfig(templateDataToDriverCommandConfig(template.template_data))
    form.setFieldsValue({
      name: template.name,
      description: template.description || '',
      is_active: template.is_active,
    })
    setModalOpen(true)
  }, [form])

  const handleSaveTemplate = useCallback(async () => {
    try {
      const values = await form.validateFields()
      const command = typeof cliConfig.command_id === 'string' ? cliConfig.command_id.trim() : ''
      if (!command) {
        message.error('Command is required')
        return
      }
      const templateData = driverCommandConfigToTemplateData(cliConfig)

      const payload = {
        id: editingTemplate?.id,
        name: values.name,
        description: values.description || '',
        operation_type: 'designer_cli',
        target_entity: 'infobase',
        template_data: templateData,
        is_active: values.is_active !== false,
      }

      if (editingTemplate) {
        await updateMutation.mutateAsync(payload)
        message.success('Template updated')
      } else {
        await createMutation.mutateAsync(payload)
        message.success('Template created')
      }
      setModalOpen(false)
    } catch (err) {
      if (err instanceof Error) {
        message.error(err.message)
      }
    }
  }, [cliConfig, createMutation, editingTemplate, form, message, updateMutation])

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

      <Modal
        title={editingTemplate ? 'Edit CLI Template' : 'New CLI Template'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSaveTemplate}
        okText={editingTemplate ? 'Save' : 'Create'}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={720}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="Name"
            name="name"
            rules={[{ required: true, message: 'Name is required' }]}
          >
            <Input placeholder="Template name" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <TextArea rows={2} placeholder="Optional description" />
          </Form.Item>
          <Form.Item label="Active" name="is_active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>

        <DriverCommandBuilder
          driver="cli"
          config={cliConfig}
          onChange={(updates) => setCliConfig((prev) => ({ ...prev, ...updates }))}
        />
      </Modal>
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
