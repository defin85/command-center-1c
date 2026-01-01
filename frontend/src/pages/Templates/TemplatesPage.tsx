import { useCallback, useMemo, useState } from 'react'
import { Alert, App, Button, Form, Input, Modal, Popconfirm, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { OperationTemplate } from '../../api/generated/model/operationTemplate'
import {
  useCreateTemplate,
  useDeleteTemplate,
  useOperationTemplates,
  useSyncTemplatesFromRegistry,
  useUpdateTemplate,
} from '../../api/queries/templates'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { DesignerCliBuilder, type DesignerCliConfig } from '../../components/cli/DesignerCliBuilder'
import { useMe } from '../../api/queries/me'

const { Title, Text } = Typography
const { TextArea } = Input

export function TemplatesPage() {
  const { message } = App.useApp()
  const meQuery = useMe()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<OperationTemplate | null>(null)
  const [cliConfig, setCliConfig] = useState<DesignerCliConfig>({})
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

  const isStaff = Boolean(meQuery.data?.is_staff)

  const normalizeArgs = (value: DesignerCliConfig['args']): string[] | undefined => {
    if (Array.isArray(value)) {
      const list = value.filter((item) => typeof item === 'string' && item.trim().length > 0)
      return list.length > 0 ? list : undefined
    }
    if (typeof value === 'string') {
      const list = value
        .split('\n')
        .map((item) => item.trim())
        .filter((item) => item.length > 0)
      return list.length > 0 ? list : undefined
    }
    return undefined
  }

  const openCreateModal = useCallback(() => {
    setEditingTemplate(null)
    setCliConfig({
      cli_mode: 'guided',
      disable_startup_messages: true,
      disable_startup_dialogs: true,
    })
    form.setFieldsValue({ name: '', description: '', is_active: true })
    setModalOpen(true)
  }, [form])

  const openEditModal = useCallback((template: OperationTemplate) => {
    setEditingTemplate(template)
    const data = (template.template_data as Record<string, unknown>) || {}
    const options = (data.options as Record<string, unknown>) || {}
    setCliConfig({
      command: typeof data.command === 'string' ? data.command : undefined,
      args: Array.isArray(data.args) ? (data.args as string[]) : undefined,
      disable_startup_messages: typeof options.disable_startup_messages === 'boolean'
        ? (options.disable_startup_messages as boolean)
        : typeof data.disable_startup_messages === 'boolean'
          ? (data.disable_startup_messages as boolean)
          : true,
      disable_startup_dialogs: typeof options.disable_startup_dialogs === 'boolean'
        ? (options.disable_startup_dialogs as boolean)
        : typeof data.disable_startup_dialogs === 'boolean'
          ? (data.disable_startup_dialogs as boolean)
          : true,
      cli_mode: (data.cli_mode as DesignerCliConfig['cli_mode']) || 'guided',
      cli_params: (data.cli_params as Record<string, string | boolean>) || {},
    })
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
      const command = typeof cliConfig.command === 'string' ? cliConfig.command.trim() : ''
      if (!command) {
        message.error('Command is required')
        return
      }
      const payload = {
        id: editingTemplate?.id,
        name: values.name,
        description: values.description || '',
        operation_type: 'designer_cli',
        target_entity: 'infobase',
        template_data: {
          command,
          args: normalizeArgs(cliConfig.args),
          options: {
            disable_startup_messages: cliConfig.disable_startup_messages !== false,
            disable_startup_dialogs: cliConfig.disable_startup_dialogs !== false,
          },
          cli_mode: cliConfig.cli_mode,
          cli_params: cliConfig.cli_params,
        },
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

        <DesignerCliBuilder
          config={cliConfig}
          onChange={(updates) => setCliConfig((prev) => ({ ...prev, ...updates }))}
        />
      </Modal>
    </Space>
  )
}
