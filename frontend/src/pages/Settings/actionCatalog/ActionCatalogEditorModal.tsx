import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, App, AutoComplete, Button, Collapse, Descriptions, Form, Input, InputNumber, Modal, Segmented, Select, Space, Switch, Tabs, Typography } from 'antd'
import type { FormInstance } from 'antd'

import { useDriverCommands } from '../../../api/queries/driverCommands'
import type { DriverCommandParamV2, DriverCommandV2, DriverName } from '../../../api/driverCommands'
import { useActionCatalogEditorHints } from '../../../api/queries/ui'
import { useWorkflowTemplates } from '../../../api/queries/workflowTemplates'
import type { ActionContext, ActionFormValues, ExecutorKind } from '../actionCatalogTypes'
import { isPlainObject, parseJson, safeText } from '../actionCatalogUtils'
import { buildParamsTemplate, getCommandParamsFromSchema } from '../../../components/driverCommands/builder/utils'
import { ParamField } from '../../../components/driverCommands/builder/ParamField'
import { ActionCatalogCapabilityFixedSection } from './ActionCatalogCapabilityFixedSection'

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
const GUIDED_PARAMS_RENDER_BATCH = 60

type ParamsEditorMode = 'guided' | 'raw'
type GuidedGroupKey = 'filled' | 'required' | 'optional'

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
  const { modal, message } = App.useApp()
  const [workflowSearch, setWorkflowSearch] = useState('')
  const [paramsTouched, setParamsTouched] = useState(false)
  const autoFilledCommandIdsRef = useRef<Set<string>>(new Set())
  const [paramsEditorMode, setParamsEditorMode] = useState<ParamsEditorMode>('guided')
  const [paramsObject, setParamsObject] = useState<Record<string, unknown>>({})
  const [rawParamsError, setRawParamsError] = useState<string | null>(null)
  const [paramsSearch, setParamsSearch] = useState('')
  const [activeTabKey, setActiveTabKey] = useState('basics')
  const [guidedParamsGroupsOpen, setGuidedParamsGroupsOpen] = useState<string[]>(['filled', 'required'])
  const [guidedRenderLimitByGroup, setGuidedRenderLimitByGroup] = useState<Record<GuidedGroupKey, number>>({
    filled: GUIDED_PARAMS_RENDER_BATCH,
    required: GUIDED_PARAMS_RENDER_BATCH,
    optional: GUIDED_PARAMS_RENDER_BATCH,
  })

  const editorKind = (Form.useWatch(['executor', 'kind'], form) as ExecutorKind | undefined) ?? 'ibcmd_cli'
  const editorCapability = (Form.useWatch(['capability'], form) as string | undefined) ?? ''
  const editorDriver = Form.useWatch(['executor', 'driver'], form) as DriverName | undefined
  const editorCommandId = Form.useWatch(['executor', 'command_id'], form) as string | undefined
  const commandsDriver: DriverName = (editorDriver === 'cli' || editorDriver === 'ibcmd')
    ? editorDriver
    : (editorKind === 'designer_cli' ? 'cli' : 'ibcmd')

  const commandsQuery = useDriverCommands(
    commandsDriver,
    open && (editorKind === 'ibcmd_cli' || editorKind === 'designer_cli')
  )

  const hintsQuery = useActionCatalogEditorHints(open)

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

  const paramsTemplateObject = useMemo(() => {
    if (!selectedCommand) return null
    return buildParamsTemplate(selectedCommand, commandsDriver)
  }, [commandsDriver, selectedCommand])

  const paramsTemplateJson = useMemo(() => (
    paramsTemplateObject ? JSON.stringify(paramsTemplateObject, null, 2) : ''
  ), [paramsTemplateObject])

  const isEmptyOrEmptyObjectParamsJson = (value: unknown): boolean => {
    const raw = typeof value === 'string' ? value.trim() : ''
    if (!raw) return true
    const parsed = parseJson(raw)
    return isPlainObject(parsed) && Object.keys(parsed).length === 0
  }

  const parseParamsJsonToObject = (
    value: unknown
  ): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } => {
    const raw = typeof value === 'string' ? value.trim() : ''
    if (!raw) return { ok: true, value: {} }
    const parsed = parseJson(raw)
    if (parsed === null) return { ok: false, error: 'Invalid JSON' }
    if (!isPlainObject(parsed)) return { ok: false, error: 'params must be a JSON object' }
    return { ok: true, value: parsed }
  }

  const syncParamsEditorFromValue = (value: unknown) => {
    const parsed = parseParamsJsonToObject(value)
    if (parsed.ok) {
      setParamsObject(parsed.value)
      setRawParamsError(null)
      setParamsEditorMode('guided')
      return
    }
    setParamsObject({})
    setRawParamsError(parsed.error)
    setParamsEditorMode('raw')
  }

  useEffect(() => {
    if (!open) return
    autoFilledCommandIdsRef.current.clear()
    setParamsTouched(false)
    setActiveTabKey('basics')
    setParamsSearch('')
    setGuidedParamsGroupsOpen(['filled', 'required'])
    setGuidedRenderLimitByGroup({
      filled: GUIDED_PARAMS_RENDER_BATCH,
      required: GUIDED_PARAMS_RENDER_BATCH,
      optional: GUIDED_PARAMS_RENDER_BATCH,
    })

    const current = form.getFieldValue(['executor', 'params_json']) ?? initialValues?.executor?.params_json
    syncParamsEditorFromValue(current)
  }, [form, initialValues?.executor?.params_json, open])

  useEffect(() => {
    if (!open) return
    if (!selectedCommand) return
    if (!editorCommandId) return
    if (paramsTouched) return
    if (autoFilledCommandIdsRef.current.has(editorCommandId)) return
    if (!hasParamsTemplate) return

    const current = form.getFieldValue(['executor', 'params_json'])
    if (!isEmptyOrEmptyObjectParamsJson(current)) return

    if (!paramsTemplateObject) return
    form.setFieldValue(['executor', 'params_json'], paramsTemplateJson)
    setParamsObject(paramsTemplateObject)
    setRawParamsError(null)
    autoFilledCommandIdsRef.current.add(editorCommandId)
  }, [editorCommandId, form, hasParamsTemplate, open, paramsTemplateJson, paramsTemplateObject, paramsTouched, selectedCommand])

  const handleInsertParamsTemplate = () => {
    if (!paramsTemplateJson || !paramsTemplateObject || !hasParamsTemplate) return

    const current = form.getFieldValue(['executor', 'params_json'])
    if (isEmptyOrEmptyObjectParamsJson(current)) {
      form.setFieldValue(['executor', 'params_json'], paramsTemplateJson)
      setParamsObject(paramsTemplateObject)
      setRawParamsError(null)
      setParamsTouched(true)
      return
    }

    modal.confirm({
      title: 'Overwrite params?',
      content: 'This will replace the current params JSON with a template built from the command schema.',
      okText: 'Overwrite',
      cancelText: 'Keep current',
      onOk: () => {
        form.setFieldValue(['executor', 'params_json'], paramsTemplateJson)
        setParamsObject(paramsTemplateObject)
        setRawParamsError(null)
        setParamsTouched(true)
      },
    })
  }

  const allowGuidedParams = editorKind === 'ibcmd_cli' || editorKind === 'designer_cli'
  const effectiveParamsEditorMode: ParamsEditorMode = allowGuidedParams ? paramsEditorMode : 'raw'

  const schemaParamNames = useMemo(() => (
    new Set(commandParams.map((p) => p.name))
  ), [commandParams])

  const unknownKeysCount = useMemo(() => {
    const keys = Object.keys(paramsObject)
    if (!keys.length) return 0
    if (schemaParamNames.size === 0) return 0
    let count = 0
    for (const key of keys) {
      if (!schemaParamNames.has(key)) count += 1
    }
    return count
  }, [paramsObject, schemaParamNames])

  const handleParamsEditorModeChange = (next: ParamsEditorMode) => {
    if (next === 'guided') {
      if (rawParamsError) {
        modal.info({
          title: 'Fix params JSON',
          content: 'Guided mode requires params to be a valid JSON object.',
        })
        return
      }
      const current = form.getFieldValue(['executor', 'params_json'])
      const parsed = parseParamsJsonToObject(current)
      if (!parsed.ok) {
        setRawParamsError(parsed.error)
        modal.info({
          title: 'Fix params JSON',
          content: 'Guided mode requires params to be a valid JSON object.',
        })
        return
      }
      setParamsObject(parsed.value)
      setRawParamsError(null)
    }
    setParamsEditorMode(next)
  }

  const handleResetParamsJson = () => {
    setParamsTouched(true)
    form.setFieldValue(['executor', 'params_json'], '{}')
    setParamsObject({})
    setRawParamsError(null)
    setParamsEditorMode('raw')
  }

  const getGuidedParamValue = (name: string, schema: DriverCommandParamV2): unknown => {
    const value = paramsObject[name]
    if (schema.value_type === 'int' || schema.value_type === 'float') {
      if (typeof value === 'number') return value
      if (typeof value === 'string') {
        const num = Number(value)
        return Number.isFinite(num) ? num : undefined
      }
      return undefined
    }
    if (schema.kind === 'flag' && !schema.expects_value) {
      if (value === true || value === false) return value
      if (typeof value === 'string') {
        if (value.toLowerCase() === 'true') return true
        if (value.toLowerCase() === 'false') return false
      }
    }
    return value
  }

  const handleGuidedParamChange = (name: string, nextValue: unknown) => {
    setParamsTouched(true)
    setGuidedParamsGroupsOpen((current) => (
      current.includes('filled') ? current : [...current, 'filled']
    ))
    setParamsObject((current) => {
      const next: Record<string, unknown> = { ...current }
      if (nextValue === undefined) {
        // Keep the key in paramsObject to avoid UI "jump" between groups when user clears a field via allowClear.
        // JSON.stringify omits undefined values, so params_json stays clean.
        next[name] = undefined
      } else {
        next[name] = nextValue
      }
      form.setFieldValue(['executor', 'params_json'], JSON.stringify(next, null, 2))
      setRawParamsError(null)
      return next
    })
  }

  const workflowTemplatesUnavailable = Boolean(
    (open && editorKind === 'workflow')
    && (workflowTemplatesQuery.isError || (!workflowTemplatesQuery.isLoading && workflowOptions.length === 0))
  )

  const filteredCommandParams = useMemo(() => {
    const q = paramsSearch.trim().toLowerCase()
    if (!q) return commandParams
    return commandParams.filter(({ name, schema }) => {
      const label = typeof schema.label === 'string' ? schema.label : ''
      return name.toLowerCase().includes(q) || label.toLowerCase().includes(q)
    })
  }, [commandParams, paramsSearch])

  const hasParamKey = (name: string): boolean => Object.prototype.hasOwnProperty.call(paramsObject, name)

  const groupedCommandParams = useMemo(() => {
    const filled: Array<{ name: string; schema: DriverCommandParamV2 }> = []
    const required: Array<{ name: string; schema: DriverCommandParamV2 }> = []
    const optional: Array<{ name: string; schema: DriverCommandParamV2 }> = []

    for (const item of filteredCommandParams) {
      if (hasParamKey(item.name)) {
        filled.push(item)
        continue
      }
      if (item.schema.required) {
        required.push(item)
        continue
      }
      optional.push(item)
    }

    const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name)
    filled.sort(byName)
    required.sort(byName)
    optional.sort(byName)

    return { filled, required, optional }
  }, [filteredCommandParams, paramsObject])

  const visibleGroupedCommandParams = useMemo(() => ({
    filled: groupedCommandParams.filled.slice(0, guidedRenderLimitByGroup.filled),
    required: groupedCommandParams.required.slice(0, guidedRenderLimitByGroup.required),
    optional: groupedCommandParams.optional.slice(0, guidedRenderLimitByGroup.optional),
  }), [groupedCommandParams, guidedRenderLimitByGroup])

  const hasMoreInGroup = (group: GuidedGroupKey): boolean => (
    groupedCommandParams[group].length > visibleGroupedCommandParams[group].length
  )

  const handleShowMoreGroupItems = (group: GuidedGroupKey) => {
    setGuidedRenderLimitByGroup((current) => ({
      ...current,
      [group]: current[group] + GUIDED_PARAMS_RENDER_BATCH,
    }))
  }

  const handleCopyPreviewJson = async () => {
    try {
      const raw = JSON.stringify(form.getFieldsValue(true), null, 2)
      await navigator.clipboard.writeText(raw)
      message.success('Copied')
    } catch (_err) {
      message.error('Copy failed')
    }
  }

  const handleOpenPreviewTab = () => {
    setActiveTabKey('preview')
  }

  const handleResetForm = () => {
    form.resetFields()
    setParamsTouched(false)
    setParamsSearch('')
    setGuidedParamsGroupsOpen(['filled', 'required'])
    setGuidedRenderLimitByGroup({
      filled: GUIDED_PARAMS_RENDER_BATCH,
      required: GUIDED_PARAMS_RENDER_BATCH,
      optional: GUIDED_PARAMS_RENDER_BATCH,
    })
    const current = form.getFieldValue(['executor', 'params_json']) ?? initialValues?.executor?.params_json
    syncParamsEditorFromValue(current)
    setActiveTabKey('basics')
  }

  const footer = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Space>
        <Button size="small" onClick={handleOpenPreviewTab} data-testid="action-catalog-editor-open-preview-tab">
          Preview
        </Button>
        <Button size="small" onClick={handleCopyPreviewJson} data-testid="action-catalog-editor-copy-json">
          Copy JSON
        </Button>
        <Button size="small" onClick={handleResetForm} data-testid="action-catalog-editor-reset-form">
          Reset
        </Button>
      </Space>
      <Space>
        <Button onClick={onCancel}>Cancel</Button>
        <Button type="primary" onClick={onApply} data-testid="action-catalog-editor-apply">
          Save
        </Button>
      </Space>
    </div>
  )

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onCancel}
      footer={footer}
      destroyOnClose
      styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
    >
      <Form<ActionFormValues>
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={initialValues ?? undefined}
      >
        <Tabs
          activeKey={activeTabKey}
          onChange={(next) => setActiveTabKey(next)}
          destroyInactiveTabPane={false}
          items={[
            {
              key: 'basics',
              label: 'Basics',
              forceRender: true,
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
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
                    <div style={{ display: 'flex', gap: 16, width: '100%' }}>
                      <Form.Item
                        label="driver"
                        name={['executor', 'driver']}
                        rules={[{ required: true, message: 'driver is required' }]}
                        style={{ flex: 1, minWidth: 0 }}
                      >
                        <Select
                          options={DRIVER_OPTIONS}
                          style={{ width: '100%' }}
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
                        style={{ flex: 2, minWidth: 0 }}
                      >
                        {driverCatalogUnavailable ? (
                          <Input
                            placeholder="Driver catalog unavailable — enter command_id manually"
                            style={{ width: '100%' }}
                            data-testid="action-catalog-editor-command-id"
                          />
                        ) : (
                          <Select
                            showSearch
                            options={commandOptions}
                            loading={commandsQuery.isLoading}
                            style={{ width: '100%' }}
                            placeholder={commandsQuery.isLoading ? 'Loading driver catalog…' : 'Select command_id'}
                            optionFilterProp="label"
                            data-testid="action-catalog-editor-command-id"
                            notFoundContent={commandsQuery.isError ? 'Failed to load driver catalog' : 'No commands'}
                          />
                        )}
                      </Form.Item>
                    </div>
                  )}

                  {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && !driverCatalogUnavailable && selectedCommand && (
                    <div style={{ marginBottom: 12 }} data-testid="action-catalog-editor-schema-panel">
                      <Collapse
                        size="small"
                        defaultActiveKey={[]}
                        items={[
                          {
                            key: 'schema',
                            label: `Command parameters (from schema) (${commandParams.length})`,
                            children: commandParams.length === 0 ? (
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
                            ),
                          },
                        ]}
                      />
                    </div>
                  )}
                </Space>
              ),
            },
            {
              key: 'executor',
              label: 'Executor',
              forceRender: true,
              children: (
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

                  {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && (
                    <Form.Item label="stdin" name={['executor', 'stdin']}>
                      <Input.TextArea
                        rows={3}
                        placeholder="Optional stdin"
                        data-testid="action-catalog-editor-stdin"
                      />
                    </Form.Item>
                  )}
                </Space>
              ),
            },
            {
              key: 'params',
              label: 'Params',
              forceRender: true,
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Form.Item
                    label={(
                      <Space align="center" wrap>
                        <span>params</span>
                        {allowGuidedParams && (
                          <Segmented
                            size="small"
                            value={effectiveParamsEditorMode}
                            options={[
                              { label: 'Guided', value: 'guided' },
                              { label: 'Raw JSON', value: 'raw' },
                            ]}
                            onChange={(next) => handleParamsEditorModeChange(next as ParamsEditorMode)}
                            data-testid="action-catalog-editor-params-mode"
                          />
                        )}
                        {effectiveParamsEditorMode === 'raw' && rawParamsError && (
                          <Button
                            size="small"
                            onClick={(event) => {
                              event.preventDefault()
                              event.stopPropagation()
                              handleResetParamsJson()
                            }}
                            data-testid="action-catalog-editor-params-reset"
                          >
                            Reset to {'{}'}
                          </Button>
                        )}
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
                    validateStatus={effectiveParamsEditorMode === 'raw' && rawParamsError ? 'error' : undefined}
                    help={effectiveParamsEditorMode === 'raw' && rawParamsError ? rawParamsError : undefined}
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
                    {effectiveParamsEditorMode === 'raw' ? (
                      <Input.TextArea
                        rows={6}
                        placeholder="{ }"
                        data-testid="action-catalog-editor-params"
                        onChange={(event) => {
                          setParamsTouched(true)
                          const nextRaw = event.target.value
                          const parsed = parseParamsJsonToObject(nextRaw)
                          if (parsed.ok) {
                            setParamsObject(parsed.value)
                            setRawParamsError(null)
                          } else {
                            setRawParamsError(parsed.error)
                          }
                        }}
                      />
                    ) : (
                      <Input.TextArea rows={1} style={{ display: 'none' }} aria-hidden />
                    )}
                  </Form.Item>

                  {allowGuidedParams && effectiveParamsEditorMode === 'guided' && (
                    <div data-testid="action-catalog-editor-params-guided">
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Input
                          allowClear
                          placeholder="Search params…"
                          value={paramsSearch}
                          onChange={(event) => setParamsSearch(event.target.value)}
                          data-testid="action-catalog-editor-params-search"
                        />

                        {unknownKeysCount > 0 && (
                          <div style={{ marginBottom: 8 }}>
                            <Text type="secondary">Unknown keys: {unknownKeysCount}</Text>
                          </div>
                        )}

                        <Collapse
                          size="small"
                          ghost
                          destroyInactivePanel
                          activeKey={guidedParamsGroupsOpen}
                          onChange={(next) => setGuidedParamsGroupsOpen(Array.isArray(next) ? next.map(String) : [String(next)])}
                          items={[
                            {
                              key: 'filled',
                              label: `Filled (${driverCatalogUnavailable || !selectedCommand ? '—' : groupedCommandParams.filled.length})`,
                              children: driverCatalogUnavailable || !selectedCommand ? (
                                <Text type="secondary">Select driver and command_id to edit schema params.</Text>
                              ) : groupedCommandParams.filled.length === 0 ? (
                                <Text type="secondary">No filled params.</Text>
                              ) : (
                                <div>
                                  {visibleGroupedCommandParams.filled.map(({ name, schema }) => (
                                    <ParamField
                                      key={name}
                                      name={name}
                                      schema={schema}
                                      value={getGuidedParamValue(name, schema)}
                                      onChange={(next) => handleGuidedParamChange(name, next)}
                                    />
                                  ))}
                                  {hasMoreInGroup('filled') && (
                                    <Button
                                      size="small"
                                      onClick={() => handleShowMoreGroupItems('filled')}
                                      data-testid="action-catalog-editor-params-show-more-filled"
                                    >
                                      Show more
                                    </Button>
                                  )}
                                </div>
                              ),
                            },
                            {
                              key: 'required',
                              label: `Required (${driverCatalogUnavailable || !selectedCommand ? '—' : groupedCommandParams.required.length})`,
                              children: driverCatalogUnavailable || !selectedCommand ? (
                                <Text type="secondary">Select driver and command_id to edit schema params.</Text>
                              ) : groupedCommandParams.required.length === 0 ? (
                                <Text type="secondary">No required params.</Text>
                              ) : (
                                <div>
                                  {visibleGroupedCommandParams.required.map(({ name, schema }) => (
                                    <ParamField
                                      key={name}
                                      name={name}
                                      schema={schema}
                                      value={getGuidedParamValue(name, schema)}
                                      onChange={(next) => handleGuidedParamChange(name, next)}
                                    />
                                  ))}
                                  {hasMoreInGroup('required') && (
                                    <Button
                                      size="small"
                                      onClick={() => handleShowMoreGroupItems('required')}
                                      data-testid="action-catalog-editor-params-show-more-required"
                                    >
                                      Show more
                                    </Button>
                                  )}
                                </div>
                              ),
                            },
                            {
                              key: 'optional',
                              label: `Optional (${driverCatalogUnavailable || !selectedCommand ? '—' : groupedCommandParams.optional.length})`,
                              children: driverCatalogUnavailable || !selectedCommand ? (
                                <Text type="secondary">Select driver and command_id to edit schema params.</Text>
                              ) : groupedCommandParams.optional.length === 0 ? (
                                <Text type="secondary">No optional params.</Text>
                              ) : (
                                <div>
                                  {visibleGroupedCommandParams.optional.map(({ name, schema }) => (
                                    <ParamField
                                      key={name}
                                      name={name}
                                      schema={schema}
                                      value={getGuidedParamValue(name, schema)}
                                      onChange={(next) => handleGuidedParamChange(name, next)}
                                    />
                                  ))}
                                  {hasMoreInGroup('optional') && (
                                    <Button
                                      size="small"
                                      onClick={() => handleShowMoreGroupItems('optional')}
                                      data-testid="action-catalog-editor-params-show-more-optional"
                                    >
                                      Show more
                                    </Button>
                                  )}
                                </div>
                              ),
                            },
                          ]}
                        />
                      </Space>
                    </div>
                  )}
                </Space>
              ),
            },
            {
              key: 'safety',
              label: 'Safety & Fixed',
              forceRender: true,
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
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

                  {hintsQuery.isError && (
                    <Alert
                      type="warning"
                      showIcon
                      message="Hints unavailable"
                      description="Capability-driven fixed UI is unavailable."
                    />
                  )}

                  {!hintsQuery.isError && (
                    <ActionCatalogCapabilityFixedSection
                      form={form}
                      capability={editorCapability}
                      hints={hintsQuery.data}
                    />
                  )}
                </Space>
              ),
            },
            {
              key: 'preview',
              label: 'Preview',
              forceRender: true,
              children: (
                <Input.TextArea
                  rows={10}
                  value={JSON.stringify(form.getFieldsValue(true), null, 2)}
                  readOnly
                  data-testid="action-catalog-editor-preview-json"
                />
              ),
            },
          ]}
        />

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
