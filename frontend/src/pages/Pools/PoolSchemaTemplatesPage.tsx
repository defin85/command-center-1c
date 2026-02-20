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
  updatePoolSchemaTemplate,
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

type TemplateModalMode = 'create' | 'edit'

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

const stringifyJsonObject = (value: unknown): string => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return DEFAULT_METADATA_JSON
  }
  return JSON.stringify(value, null, 2)
}

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

const resolveWorkflowBindingHint = (metadata: Record<string, unknown>): string | null => {
  const raw = metadata.workflow_binding
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null
  }
  const binding = raw as Record<string, unknown>
  const bindingTemplateId = typeof binding.workflow_template_id === 'string'
    ? binding.workflow_template_id.trim()
    : ''
  const bindingVersion = typeof binding.version === 'string' ? binding.version.trim() : ''
  const bindingLabel = typeof binding.label === 'string' ? binding.label.trim() : ''

  if (bindingTemplateId) {
    if (bindingVersion) {
      return `${bindingTemplateId} (${bindingVersion})`
    }
    return bindingTemplateId
  }
  if (bindingLabel) {
    return bindingLabel
  }
  return JSON.stringify(binding)
}

export function PoolSchemaTemplatesPage() {
  const { message } = AntApp.useApp()
  const [templates, setTemplates] = useState<PoolSchemaTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<TemplateModalMode>('create')
  const [editingTemplate, setEditingTemplate] = useState<PoolSchemaTemplate | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
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
    setModalMode('create')
    setEditingTemplate(null)
    setSubmitError(null)
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

  const openEditModal = useCallback((template: PoolSchemaTemplate) => {
    setModalMode('edit')
    setEditingTemplate(template)
    setSubmitError(null)
    form.setFieldsValue({
      code: template.code,
      name: template.name,
      format: template.format,
      is_public: template.is_public,
      is_active: template.is_active,
      workflow_template_id: template.workflow_template_id ?? '',
      schema_json: stringifyJsonObject(template.schema),
      metadata_json: stringifyJsonObject(template.metadata),
    })
    setIsModalOpen(true)
  }, [form])

  const closeModal = useCallback(() => {
    if (isSubmitting) {
      return
    }
    setIsModalOpen(false)
    setSubmitError(null)
  }, [isSubmitting])

  const handleSubmitTemplate = useCallback(async () => {
    setSubmitError(null)
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
      setSubmitError(err instanceof Error ? err.message : 'Неверный JSON.')
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        code: values.code,
        name: values.name,
        format: values.format,
        is_public: values.is_public,
        is_active: values.is_active,
        schema,
        metadata,
        workflow_template_id: values.workflow_template_id?.trim() || null,
      }
      if (modalMode === 'edit') {
        if (!editingTemplate) {
          setSubmitError('Шаблон для редактирования не выбран.')
          return
        }
        await updatePoolSchemaTemplate(editingTemplate.id, payload)
        message.success('Шаблон обновлён')
      } else {
        await createPoolSchemaTemplate(payload)
        message.success('Шаблон создан')
      }
      closeModal()
      await loadTemplates()
    } catch {
      setSubmitError(modalMode === 'edit' ? 'Не удалось обновить шаблон.' : 'Не удалось создать шаблон.')
    } finally {
      setIsSubmitting(false)
    }
  }, [closeModal, editingTemplate, form, loadTemplates, message, modalMode])

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
        title: 'Unified Workflow',
        dataIndex: 'workflow_template_id',
        key: 'workflow_template_id',
        width: 280,
        render: (value: string | null) => (
          value
            ? (
              <Space size={4}>
                <Tag color="blue">template</Tag>
                <Text code>{value}</Text>
              </Space>
            )
            : <Text type="secondary">not linked</Text>
        ),
      },
      {
        title: 'workflow_binding hint',
        key: 'workflow_binding_hint',
        width: 320,
        render: (_value, record) => {
          const hint = resolveWorkflowBindingHint(record.metadata ?? {})
          if (!hint) {
            return <Text type="secondary">absent</Text>
          }
          return (
            <Space size={4} data-testid="pool-template-workflow-binding-hint">
              <Tag color="gold">compat</Tag>
              <Text code>{hint}</Text>
            </Space>
          )
        },
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 200,
        render: (value: string) => new Date(value).toLocaleString(),
      },
      {
        title: 'Actions',
        key: 'actions',
        width: 120,
        render: (_value, record) => (
          <Button
            size="small"
            onClick={() => openEditModal(record)}
            data-testid={`pool-template-edit-${record.id}`}
          >
            Edit
          </Button>
        ),
      },
    ],
    [openEditModal]
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ marginBottom: 0 }}>
          Pool Schema Templates
        </Title>
        <Text type="secondary">
          Публичные XLSX/JSON шаблоны для bottom-up импорта. `workflow_binding` в metadata поддерживается как
          compatibility hint компилятора и не является отдельным runtime.
        </Text>
      </div>

      <Alert
        type="info"
        showIcon
        message="Unified execution source-of-truth: workflow execution provenance в /pools/runs. Поле workflow_binding на template используется только как optional compiler hint."
      />

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
        title={modalMode === 'edit' ? 'Edit Pool Schema Template' : 'Create Pool Schema Template'}
        open={isModalOpen}
        onCancel={closeModal}
        onOk={() => void handleSubmitTemplate()}
        confirmLoading={isSubmitting}
        okText={modalMode === 'edit' ? 'Save' : 'Create'}
        width={760}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {submitError && <Alert type="error" message={submitError} />}
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
