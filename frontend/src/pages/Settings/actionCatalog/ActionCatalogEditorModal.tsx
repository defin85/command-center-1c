import { useEffect, useMemo, useState } from 'react'
import { Alert, App, AutoComplete, Button, Card, Descriptions, Form, Input, InputNumber, Modal, Select, Space, Switch, Typography } from 'antd'
import type { FormInstance } from 'antd'

import { useDriverCommands } from '../../../api/queries/driverCommands'
import type { DriverCommandParamV2, DriverCommandV2, DriverName } from '../../../api/driverCommands'
import { useWorkflowTemplates } from '../../../api/queries/workflowTemplates'
import type { ActionContext, ActionFormValues, ExecutorKind } from '../actionCatalogTypes'
import { isPlainObject, parseJson, safeText } from '../actionCatalogUtils'
import { buildParamsTemplate, getCommandParamsFromSchema } from '../../../components/driverCommands/builder/utils'

const ACTION_CONTEXT_OPTIONS: { value: ActionContext; label: string }[] = [
  { value: 'database_card', label: 'database_card' },
  { value: 'bulk_page', label: 'bulk_page' },
]

const EXECUTOR_KIND_OPTIONS: { value: ExecutorKind; label: string }[] = [
  { value: 'ibcmd_cli', label: 'ibcmd_cli' },
  { value: 'designer_cli', label: 'designer_cli' },
  { value: 'workflow', label: 'workflow' },
]

const DRIVER_OPTIONS: { value: DriverName; label: string }[] = [
  { value: 'ibcmd', label: 'ibcmd' },
  { value: 'cli', label: 'cli' },
]

const MODE_OPTIONS: { value: 'guided' | 'manual'; label: string }[] = [
  { value: 'guided', label: 'guided' },
  { value: 'manual', label: 'manual' },
]

const CAPABILITY_OPTIONS: { value: string; label: string }[] = [
  { value: 'extensions.list', label: 'extensions.list' },
  { value: 'extensions.sync', label: 'extensions.sync' },
  { value: 'extensions.set_flags', label: 'extensions.set_flags' },
]

const CAPABILITY_RE = /^[a-z0-9_-]+(\.[a-z0-9_-]+)+$/

export type ActionCatalogEditorModalProps = {
  open: boolean
  title: string
  form: FormInstance<ActionFormValues>
  initialValues: ActionFormValues | null
  onCancel: () => void
  onApply: () => void
}

export function ActionCatalogEditorModal({
  open,
  title,
  form,
  initialValues,
  onCancel,
  onApply,
}: ActionCatalogEditorModalProps) {
  const { Text } = Typography
  const { modal } = App.useApp()
  const [workflowSearch, setWorkflowSearch] = useState('')
  const [paramsTouched, setParamsTouched] = useState(false)
  const [lastAutoFilledCommandId, setLastAutoFilledCommandId] = useState<string | null>(null)

  const editorKind = (Form.useWatch(['executor', 'kind'], form) as ExecutorKind | undefined) ?? 'ibcmd_cli'
  const editorDriver = Form.useWatch(['executor', 'driver'], form) as DriverName | undefined
  const editorCommandId = Form.useWatch(['executor', 'command_id'], form) as string | undefined
  const commandsDriver: DriverName = (editorDriver === 'cli' || editorDriver === 'ibcmd')
    ? editorDriver
    : (editorKind === 'designer_cli' ? 'cli' : 'ibcmd')

  const commandsQuery = useDriverCommands(
    commandsDriver,
    open && (editorKind === 'ibcmd_cli' || editorKind === 'designer_cli')
  )

  const workflowTemplatesQuery = useWorkflowTemplates(
    workflowSearch.trim() ? { search: workflowSearch.trim() } : undefined,
    open && editorKind === 'workflow'
  )

  const commandOptions = useMemo(() => {
    const commandsById = commandsQuery.data?.catalog?.commands_by_id
    if (!commandsById || typeof commandsById !== 'object') return []
    return Object.entries(commandsById)
      .map(([id, cmd]) => {
        const label = cmd?.label ? String(cmd.label) : ''
        const risk = cmd?.risk_level ? String(cmd.risk_level) : ''
        const suffix = label ? ` — ${label}` : ''
        const riskSuffix = risk ? ` (${risk})` : ''
        return { value: id, label: `${id}${suffix}${riskSuffix}` }
      })
      .sort((a, b) => a.value.localeCompare(b.value))
  }, [commandsQuery.data])

  const workflowOptions = useMemo(() => {
    const items = workflowTemplatesQuery.data?.templates ?? []
    return items.map((tpl) => ({
      value: tpl.id,
      label: `${tpl.name} (${tpl.category})`,
    }))
  }, [workflowTemplatesQuery.data])

  const driverCatalogUnavailable = Boolean(
    (open && (editorKind === 'ibcmd_cli' || editorKind === 'designer_cli'))
    && (commandsQuery.isError || (!commandsQuery.isLoading && commandOptions.length === 0))
  )

  const selectedCommand = useMemo((): DriverCommandV2 | null => {
    const commandsById = commandsQuery.data?.catalog?.commands_by_id
    if (!editorCommandId || !commandsById || typeof commandsById !== 'object') return null
    const cmd = (commandsById as Record<string, DriverCommandV2 | undefined>)[editorCommandId]
    return cmd ?? null
  }, [commandsQuery.data, editorCommandId])

  const commandParams = useMemo((): Array<{ name: string; schema: DriverCommandParamV2 }> => {
    if (!selectedCommand) return []
    return getCommandParamsFromSchema(selectedCommand.params_by_name, commandsDriver)
  }, [commandsDriver, selectedCommand])

  const hasParamsTemplate = commandParams.length > 0

  const paramsTemplateJson = useMemo(() => {
    if (!selectedCommand) return ''
    const template = buildParamsTemplate(selectedCommand, commandsDriver)
    return JSON.stringify(template, null, 2)
  }, [commandsDriver, selectedCommand])

  const isEmptyOrEmptyObjectParamsJson = (value: unknown): boolean => {
    const raw = typeof value === 'string' ? value.trim() : ''
    if (!raw) return true
    const parsed = parseJson(raw)
    return isPlainObject(parsed) && Object.keys(parsed).length === 0
  }

  useEffect(() => {
    if (!open) return
    if (!selectedCommand) return
    if (!editorCommandId) return
    if (paramsTouched) return
    if (lastAutoFilledCommandId === editorCommandId) return
    if (!hasParamsTemplate) return

    const current = form.getFieldValue(['executor', 'params_json'])
    if (!isEmptyOrEmptyObjectParamsJson(current)) return

    form.setFieldValue(['executor', 'params_json'], paramsTemplateJson)
    setLastAutoFilledCommandId(editorCommandId)
  }, [editorCommandId, form, hasParamsTemplate, lastAutoFilledCommandId, open, paramsTemplateJson, paramsTouched, selectedCommand])

  const handleInsertParamsTemplate = () => {
    if (!paramsTemplateJson || !hasParamsTemplate) return

    const current = form.getFieldValue(['executor', 'params_json'])
    if (isEmptyOrEmptyObjectParamsJson(current)) {
      form.setFieldValue(['executor', 'params_json'], paramsTemplateJson)
      return
    }

    modal.confirm({
      title: 'Overwrite params?',
      content: 'This will replace the current params JSON with a template built from the command schema.',
      okText: 'Overwrite',
      cancelText: 'Keep current',
      onOk: () => {
        form.setFieldValue(['executor', 'params_json'], paramsTemplateJson)
      },
    })
  }

  const workflowTemplatesUnavailable = Boolean(
    (open && editorKind === 'workflow')
    && (workflowTemplatesQuery.isError || (!workflowTemplatesQuery.isLoading && workflowOptions.length === 0))
  )

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onCancel}
      onOk={onApply}
      okText="Apply"
      okButtonProps={{ 'data-testid': 'action-catalog-editor-apply' }}
      destroyOnClose
    >
      <Form<ActionFormValues>
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={initialValues ?? undefined}
      >
        <Form.Item
          label="ID"
          name="id"
          rules={[
            { required: true, message: 'ID is required' },
            { whitespace: true, message: 'ID is required' },
          ]}
        >
          <Input data-testid="action-catalog-editor-id" />
        </Form.Item>

        <Form.Item
          label="Capability (optional)"
          name="capability"
          rules={[
            {
              validator: (_rule, value) => {
                const raw = typeof value === 'string' ? value.trim() : ''
                if (!raw) return Promise.resolve()
                if (CAPABILITY_RE.test(raw)) return Promise.resolve()
                return Promise.reject(new Error('Capability must be a namespaced string (e.g. extensions.list)'))
              },
            },
          ]}
        >
          <AutoComplete
            options={CAPABILITY_OPTIONS}
            placeholder="e.g. extensions.list"
            allowClear
            filterOption={(inputValue, option) => (option?.value ?? '').includes(inputValue)}
            data-testid="action-catalog-editor-capability"
          />
        </Form.Item>

        <Form.Item
          label="Label"
          name="label"
          rules={[
            { required: true, message: 'Label is required' },
            { whitespace: true, message: 'Label is required' },
          ]}
        >
          <Input data-testid="action-catalog-editor-label" />
        </Form.Item>

        <Form.Item
          label="Contexts"
          name="contexts"
          rules={[
            { required: true, message: 'At least one context is required' },
          ]}
        >
          <Select
            mode="multiple"
            options={ACTION_CONTEXT_OPTIONS}
            data-testid="action-catalog-editor-contexts"
          />
        </Form.Item>

        <Form.Item
          label="Executor kind"
          name={['executor', 'kind']}
          rules={[{ required: true, message: 'Executor kind is required' }]}
        >
          <Select
            options={EXECUTOR_KIND_OPTIONS}
            data-testid="action-catalog-editor-executor-kind"
            onChange={(next: ExecutorKind) => {
              if (next === 'workflow') {
                form.setFieldValue(['executor', 'driver'], undefined)
                form.setFieldValue(['executor', 'command_id'], undefined)
                form.setFieldValue(['executor', 'workflow_id'], form.getFieldValue(['executor', 'workflow_id']) ?? '')
                return
              }
              form.setFieldValue(['executor', 'workflow_id'], undefined)
              const currentDriver = form.getFieldValue(['executor', 'driver']) as unknown
              if (currentDriver !== 'cli' && currentDriver !== 'ibcmd') {
                form.setFieldValue(['executor', 'driver'], next === 'designer_cli' ? 'cli' : 'ibcmd')
              }
              form.setFieldValue(['executor', 'command_id'], undefined)
            }}
          />
        </Form.Item>

        {editorKind === 'workflow' ? (
          <Form.Item
            label="workflow_id"
            name={['executor', 'workflow_id']}
            rules={[
              { required: true, message: 'workflow_id is required' },
              { whitespace: true, message: 'workflow_id is required' },
            ]}
          >
            {workflowTemplatesUnavailable ? (
              <Input
                placeholder="Workflow templates unavailable — enter workflow_id manually"
                data-testid="action-catalog-editor-workflow-id"
              />
            ) : (
              <Select
                showSearch
                options={workflowOptions}
                loading={workflowTemplatesQuery.isLoading}
                filterOption={false}
                onSearch={(value) => setWorkflowSearch(value)}
                placeholder={workflowTemplatesQuery.isLoading ? 'Loading workflow templates…' : 'Select workflow template'}
                data-testid="action-catalog-editor-workflow-id"
                notFoundContent={workflowTemplatesQuery.isError ? 'Failed to load workflow templates' : 'No templates'}
              />
            )}
          </Form.Item>
        ) : (
          <Space size="middle" style={{ width: '100%' }} align="start">
            <Form.Item
              label="driver"
              name={['executor', 'driver']}
              rules={[{ required: true, message: 'driver is required' }]}
              style={{ flex: 1 }}
            >
              <Select
                options={DRIVER_OPTIONS}
                data-testid="action-catalog-editor-driver"
                onChange={() => {
                  form.setFieldValue(['executor', 'command_id'], undefined)
                }}
              />
            </Form.Item>
            <Form.Item
              label="command_id"
              name={['executor', 'command_id']}
              rules={[{ required: true, message: 'command_id is required' }]}
              style={{ flex: 2 }}
            >
              {driverCatalogUnavailable ? (
                <Input
                  placeholder="Driver catalog unavailable — enter command_id manually"
                  data-testid="action-catalog-editor-command-id"
                />
              ) : (
                <Select
                  showSearch
                  options={commandOptions}
                  loading={commandsQuery.isLoading}
                  placeholder={commandsQuery.isLoading ? 'Loading driver catalog…' : 'Select command_id'}
                  optionFilterProp="label"
                  data-testid="action-catalog-editor-command-id"
                  notFoundContent={commandsQuery.isError ? 'Failed to load driver catalog' : 'No commands'}
                  onChange={() => {
                    setParamsTouched(false)
                    setLastAutoFilledCommandId(null)
                  }}
                />
              )}
            </Form.Item>
          </Space>
        )}

        {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && !driverCatalogUnavailable && selectedCommand && (
          <Card
            size="small"
            title="Command parameters (from schema)"
            style={{ marginBottom: 12 }}
            data-testid="action-catalog-editor-schema-panel"
          >
            {commandParams.length === 0 ? (
              <Text type="secondary">No command parameters in schema.</Text>
            ) : (
              <Descriptions bordered size="small" column={1}>
                {commandParams.map(({ name, schema }) => {
                  const bits: string[] = []
                  if (schema.required) bits.push('required')
                  if (schema.kind) bits.push(schema.kind)
                  if (schema.value_type) bits.push(String(schema.value_type))
                  if (schema.repeatable) bits.push('repeatable')
                  const titleBits = bits.length ? ` (${bits.join(', ')})` : ''

                  const defaultValue = schema.default !== undefined ? safeText(schema.default, 200) : '—'
                  const description = schema.description ? String(schema.description) : ''

                  return (
                    <Descriptions.Item key={name} label={`${name}${titleBits}`}>
                      <Space direction="vertical" size={0} style={{ width: '100%' }}>
                        <Text type="secondary">default: {defaultValue}</Text>
                        {description && <Text type="secondary">{description}</Text>}
                      </Space>
                    </Descriptions.Item>
                  )
                })}
              </Descriptions>
            )}
          </Card>
        )}

        <Card size="small" style={{ marginBottom: 12 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && (
              <Form.Item
                label="additional_args"
                name={['executor', 'additional_args']}
                tooltip="Для designer_cli это args; для ibcmd_cli — дополнительные argv-параметры."
              >
                <Select
                  mode="tags"
                  tokenSeparators={['\n', ' ']}
                  placeholder="Enter args (space/newline-separated)"
                  data-testid="action-catalog-editor-additional-args"
                />
              </Form.Item>
            )}

            {editorKind === 'ibcmd_cli' && (
              <Form.Item label="mode" name={['executor', 'mode']}>
                <Select options={MODE_OPTIONS} data-testid="action-catalog-editor-mode" />
              </Form.Item>
            )}

            <Form.Item
              label={(
                <Space align="center">
                  <span>params (JSON object)</span>
                  {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && (
                    <Button
                      size="small"
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        handleInsertParamsTemplate()
                      }}
                      disabled={!hasParamsTemplate || driverCatalogUnavailable || !selectedCommand}
                      data-testid="action-catalog-editor-insert-params-template"
                    >
                      Insert params template
                    </Button>
                  )}
                </Space>
              )}
              name={['executor', 'params_json']}
              rules={[
                {
                  validator: async (_rule, value) => {
                    const raw = typeof value === 'string' ? value : ''
                    if (!raw.trim()) return
                    const parsed = parseJson(raw)
                    if (!isPlainObject(parsed)) {
                      throw new Error('params must be a JSON object')
                    }
                  },
                },
              ]}
            >
              <Input.TextArea
                rows={6}
                placeholder="{ }"
                data-testid="action-catalog-editor-params"
                onChange={() => setParamsTouched(true)}
              />
            </Form.Item>

            {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && (
              <Form.Item label="stdin" name={['executor', 'stdin']}>
                <Input.TextArea
                  rows={3}
                  placeholder="Optional stdin"
                  data-testid="action-catalog-editor-stdin"
                />
              </Form.Item>
            )}

            <Space size="middle" wrap>
              <Form.Item
                label="fixed.confirm_dangerous"
                name={['executor', 'fixed', 'confirm_dangerous']}
                valuePropName="checked"
              >
                <Switch data-testid="action-catalog-editor-confirm-dangerous" />
              </Form.Item>
              <Form.Item
                label="fixed.timeout_seconds"
                name={['executor', 'fixed', 'timeout_seconds']}
              >
                <InputNumber
                  min={1}
                  max={3600}
                  style={{ width: 160 }}
                  data-testid="action-catalog-editor-timeout"
                />
              </Form.Item>
            </Space>
          </Space>
        </Card>

        {(commandsQuery.isError || workflowTemplatesQuery.isError) && (
          <Alert
            type="warning"
            showIcon
            message="Catalogs unavailable"
            description="Если списки команд/шаблонов не загрузились, можно ввести command_id/workflow_id вручную и сохранить — сервер проверит ссылки."
          />
        )}
      </Form>
    </Modal>
  )
}
