import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  createPoolSchemaTemplate,
  listPoolSchemaTemplates,
  type PoolSchemaTemplate,
  type PoolSchemaTemplateFormat,
} from '../../api/intercompanyPools'

const { Title, Text } = Typography
const { TextArea } = Input

type FormValues = {
  code: string
  name: string
  format: PoolSchemaTemplateFormat
  is_public: boolean
  is_active: boolean
  workflow_template_id?: string
  schema_json: string
  metadata_json: string
}

const DEFAULT_SCHEMA_JSON = JSON.stringify(
  {
    columns: {
      inn: 'inn',
      amount: 'amount',
    },
  },
  null,
  2
)

const DEFAULT_METADATA_JSON = JSON.stringify({}, null, 2)

const parseJsonObject = (text: string, fieldLabel: string): Record<string, unknown> => {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error(`${fieldLabel}: invalid JSON`)
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${fieldLabel}: object expected`)
  }
  return parsed as Record<string, unknown>
}

export function PoolSchemaTemplatesPage() {
  const { message } = AntApp.useApp()
  const [templates, setTemplates] = useState<PoolSchemaTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [formatFilter, setFormatFilter] = useState<'all' | PoolSchemaTemplateFormat>('all')
  const [includePrivate, setIncludePrivate] = useState(false)
  const [includeInactive, setIncludeInactive] = useState(false)
  const [form] = Form.useForm<FormValues>()

  const loadTemplates = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listPoolSchemaTemplates({
        format: formatFilter === 'all' ? undefined : formatFilter,
        isPublic: includePrivate ? undefined : true,
        isActive: includeInactive ? undefined : true,
      })
      setTemplates(data)
    } catch {
      setError('Не удалось загрузить шаблоны.')
    } finally {
      setLoading(false)
    }
  }, [formatFilter, includePrivate, includeInactive])

  useEffect(() => {
    void loadTemplates()
  }, [loadTemplates])

  const openCreateModal = useCallback(() => {
    setCreateError(null)
    form.setFieldsValue({
      code: '',
      name: '',
      format: 'xlsx',
      is_public: true,
      is_active: true,
      workflow_template_id: '',
      schema_json: DEFAULT_SCHEMA_JSON,
      metadata_json: DEFAULT_METADATA_JSON,
    })
    setIsModalOpen(true)
  }, [form])

  const closeCreateModal = useCallback(() => {
    setIsModalOpen(false)
    setCreateError(null)
  }, [])

  const handleCreateTemplate = useCallback(async () => {
    setCreateError(null)
    let values: FormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }

    let schema: Record<string, unknown>
    let metadata: Record<string, unknown>
    try {
      schema = parseJsonObject(values.schema_json, 'Schema')
      metadata = parseJsonObject(values.metadata_json, 'Metadata')
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Неверный JSON.')
      return
    }

    setIsCreating(true)
    try {
      await createPoolSchemaTemplate({
        code: values.code,
        name: values.name,
        format: values.format,
        is_public: values.is_public,
        is_active: values.is_active,
        schema,
        metadata,
        workflow_template_id: values.workflow_template_id?.trim() || null,
      })
      message.success('Шаблон создан')
      closeCreateModal()
      await loadTemplates()
    } catch {
      setCreateError('Не удалось создать шаблон.')
    } finally {
      setIsCreating(false)
    }
  }, [closeCreateModal, form, loadTemplates, message])

  const columns: ColumnsType<PoolSchemaTemplate> = useMemo(
    () => [
      {
        title: 'Code',
        dataIndex: 'code',
        key: 'code',
        width: 220,
        render: (value: string) => <Text code>{value}</Text>,
      },
      {
        title: 'Name',
        dataIndex: 'name',
        key: 'name',
      },
      {
        title: 'Format',
        dataIndex: 'format',
        key: 'format',
        width: 120,
        render: (value: string) => <Tag color={value === 'xlsx' ? 'blue' : 'green'}>{value.toUpperCase()}</Tag>,
      },
      {
        title: 'Visibility',
        key: 'visibility',
        width: 180,
        render: (_value, record) => (
          <Space size={4}>
            <Tag color={record.is_public ? 'cyan' : 'default'}>
              {record.is_public ? 'public' : 'private'}
            </Tag>
            <Tag color={record.is_active ? 'success' : 'default'}>
              {record.is_active ? 'active' : 'inactive'}
            </Tag>
          </Space>
        ),
      },
      {
        title: 'Workflow Binding',
        dataIndex: 'workflow_template_id',
        key: 'workflow_template_id',
        width: 250,
        render: (value: string | null) => (value ? <Text code>{value}</Text> : <Text type="secondary">not bound</Text>),
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 200,
        render: (value: string) => new Date(value).toLocaleString(),
      },
    ],
    []
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ marginBottom: 0 }}>
          Pool Schema Templates
        </Title>
        <Text type="secondary">
          Публичные XLSX/JSON шаблоны для bottom-up импорта с опциональной привязкой к workflow.
        </Text>
      </div>

      <Card>
        <Space size="middle" wrap>
          <Select
            value={formatFilter}
            style={{ width: 180 }}
            options={[
              { value: 'all', label: 'All formats' },
              { value: 'xlsx', label: 'XLSX' },
              { value: 'json', label: 'JSON' },
            ]}
            onChange={(value) => setFormatFilter(value)}
          />
          <Space size={6}>
            <Switch checked={includePrivate} onChange={setIncludePrivate} />
            <Text>Include private</Text>
          </Space>
          <Space size={6}>
            <Switch checked={includeInactive} onChange={setIncludeInactive} />
            <Text>Include inactive</Text>
          </Space>
          <Button onClick={() => void loadTemplates()} loading={loading}>
            Refresh
          </Button>
          <Button type="primary" onClick={openCreateModal}>
            Create Template
          </Button>
        </Space>
      </Card>

      {error && <Alert type="error" message={error} />}

      <Card>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={templates}
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true }}
        />
      </Card>

      <Modal
        title="Create Pool Schema Template"
        open={isModalOpen}
        onCancel={closeCreateModal}
        onOk={() => void handleCreateTemplate()}
        confirmLoading={isCreating}
        okText="Create"
        width={760}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {createError && <Alert type="error" message={createError} />}
          <Form form={form} layout="vertical" requiredMark={false}>
            <Form.Item
              name="code"
              label="Code"
              rules={[{ required: true, message: 'Code is required' }]}
            >
              <Input placeholder="xlsx-sales-v1" />
            </Form.Item>
            <Form.Item
              name="name"
              label="Name"
              rules={[{ required: true, message: 'Name is required' }]}
            >
              <Input placeholder="XLSX Sales V1" />
            </Form.Item>
            <Form.Item
              name="format"
              label="Format"
              rules={[{ required: true, message: 'Format is required' }]}
            >
              <Select
                options={[
                  { value: 'xlsx', label: 'XLSX' },
                  { value: 'json', label: 'JSON' },
                ]}
              />
            </Form.Item>
            <Form.Item name="workflow_template_id" label="Workflow Template ID (optional)">
              <Input placeholder="11111111-1111-1111-1111-111111111111" />
            </Form.Item>
            <Form.Item name="is_public" label="Public" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_active" label="Active" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              name="schema_json"
              label="Schema JSON"
              rules={[{ required: true, message: 'Schema JSON is required' }]}
            >
              <TextArea rows={8} />
            </Form.Item>
            <Form.Item
              name="metadata_json"
              label="Metadata JSON"
              rules={[{ required: true, message: 'Metadata JSON is required' }]}
            >
              <TextArea rows={6} />
            </Form.Item>
          </Form>
        </Space>
      </Modal>
    </Space>
  )
}
