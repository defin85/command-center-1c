import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Spin, Table, Tabs, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ArrowDownOutlined, ArrowUpOutlined, CopyOutlined, DeleteOutlined, EditOutlined, PlusOutlined, RollbackOutlined } from '@ant-design/icons'

import { useMe } from '../../api/queries/me'
import { getRuntimeSettings } from '../../api/runtimeSettings'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'

const { Title, Text } = Typography

const ACTION_CATALOG_KEY = 'ui.action_catalog'
const DISABLED_ACTIONS_STORAGE_KEY = 'action-catalog.disabled-actions.v1'

type ActionCatalogMode = 'guided' | 'raw'

type ActionRow = {
  pos: number
  id: string
  label: string
  contexts: string[]
  executor_kind: string
  driver?: string
  command_id?: string
  workflow_id?: string
}

type ActionContext = 'database_card' | 'bulk_page'
type ExecutorKind = 'ibcmd_cli' | 'designer_cli' | 'workflow'

type PlainObject = Record<string, unknown>

type ActionFormValues = {
  id: string
  label: string
  contexts: ActionContext[]
  executor: {
    kind: ExecutorKind
    driver?: string
    command_id?: string
    workflow_id?: string
  }
}

const ACTION_CONTEXT_OPTIONS: { value: ActionContext; label: string }[] = [
  { value: 'database_card', label: 'database_card' },
  { value: 'bulk_page', label: 'bulk_page' },
]

const EXECUTOR_KIND_OPTIONS: { value: ExecutorKind; label: string }[] = [
  { value: 'ibcmd_cli', label: 'ibcmd_cli' },
  { value: 'designer_cli', label: 'designer_cli' },
  { value: 'workflow', label: 'workflow' },
]

const isPlainObject = (value: unknown): value is PlainObject => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const safeJsonStringify = (value: unknown): string => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch (_err) {
    return '{}'
  }
}

const deepCopy = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

const parseJson = (raw: string): unknown => {
  try {
    return JSON.parse(raw) as unknown
  } catch (_err) {
    return null
  }
}

const getCatalogActions = (catalog: unknown): PlainObject[] => {
  if (!isPlainObject(catalog)) return []
  const extensions = catalog.extensions
  if (!isPlainObject(extensions)) return []
  const actions = extensions.actions
  if (!Array.isArray(actions)) return []
  return actions.filter(isPlainObject)
}

const upsertCatalogActions = (catalog: PlainObject, actions: PlainObject[]) => {
  const extensions = isPlainObject(catalog.extensions) ? catalog.extensions as PlainObject : {}
  catalog.extensions = extensions
  extensions.actions = actions
}

const buildDefaultAction = (): PlainObject => ({
  id: '',
  label: '',
  contexts: ['database_card'],
  executor: {
    kind: 'ibcmd_cli',
    driver: 'ibcmd',
    command_id: '',
  },
})

const deriveActionFormValues = (action: PlainObject | null): ActionFormValues => {
  const source = action ?? buildDefaultAction()

  const id = typeof source.id === 'string' ? source.id : ''
  const label = typeof source.label === 'string' ? source.label : ''
  const contextsRaw = Array.isArray(source.contexts) ? source.contexts : []
  const contexts = contextsRaw.filter((c) => c === 'database_card' || c === 'bulk_page') as ActionContext[]

  const executorRaw = isPlainObject(source.executor) ? source.executor as PlainObject : {}
  const kind = (executorRaw.kind === 'ibcmd_cli' || executorRaw.kind === 'designer_cli' || executorRaw.kind === 'workflow')
    ? executorRaw.kind
    : 'ibcmd_cli'
  const driver = typeof executorRaw.driver === 'string' ? executorRaw.driver : ''
  const commandId = typeof executorRaw.command_id === 'string' ? executorRaw.command_id : ''
  const workflowId = typeof executorRaw.workflow_id === 'string' ? executorRaw.workflow_id : ''

  return {
    id,
    label,
    contexts: contexts.length ? contexts : ['database_card'],
    executor: {
      kind,
      driver,
      command_id: commandId,
      workflow_id: workflowId,
    },
  }
}

const buildActionFromForm = (base: PlainObject | null, values: ActionFormValues): PlainObject => {
  const next = base ? deepCopy(base) : buildDefaultAction()

  next.id = values.id.trim()
  next.label = values.label.trim()
  next.contexts = [...new Set(values.contexts)]

  const executorBase = isPlainObject(next.executor) ? next.executor as PlainObject : {}
  const executor: PlainObject = { ...executorBase }
  executor.kind = values.executor.kind

  if (values.executor.kind === 'workflow') {
    executor.workflow_id = (values.executor.workflow_id ?? '').trim()
    delete executor.driver
    delete executor.command_id
  } else {
    executor.driver = (values.executor.driver ?? '').trim()
    executor.command_id = (values.executor.command_id ?? '').trim()
    delete executor.workflow_id
  }

  next.executor = executor
  return next
}

const ensureUniqueId = (candidate: string, used: Set<string>): string => {
  const base = candidate.trim() || 'action'
  if (!used.has(base)) return base
  for (let i = 2; i < 1000; i += 1) {
    const next = `${base}.${i}`
    if (!used.has(next)) return next
  }
  return `${base}.${Date.now()}`
}

const buildActionRows = (value: unknown): ActionRow[] => {
  const actions = getCatalogActions(value)

  const rows: ActionRow[] = []
  for (const [pos, action] of actions.entries()) {
    const id = typeof action.id === 'string' ? action.id : ''
    const label = typeof action.label === 'string' ? action.label : ''
    const contexts = Array.isArray(action.contexts)
      ? action.contexts.filter((c) => typeof c === 'string') as string[]
      : []
    const executor = action.executor
    const executorObj = executor && typeof executor === 'object' && !Array.isArray(executor)
      ? executor as Record<string, unknown>
      : null
    const kind = executorObj && typeof executorObj.kind === 'string' ? executorObj.kind : ''
    const driver = executorObj && typeof executorObj.driver === 'string' ? executorObj.driver : undefined
    const commandId = executorObj && typeof executorObj.command_id === 'string' ? executorObj.command_id : undefined
    const workflowId = executorObj && typeof executorObj.workflow_id === 'string' ? executorObj.workflow_id : undefined

    rows.push({
      pos,
      id,
      label,
      contexts,
      executor_kind: kind,
      driver,
      command_id: commandId,
      workflow_id: workflowId,
    })
  }
  return rows
}

export function ActionCatalogPage() {
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)

  const [mode, setMode] = useState<ActionCatalogMode>('guided')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [serverRaw, setServerRaw] = useState<string | null>(null)
  const [draftRaw, setDraftRaw] = useState<string>('{}')
  const [settingDescription, setSettingDescription] = useState<string | null>(null)
  const [disabledActions, setDisabledActions] = useState<PlainObject[]>([])

  const [editorOpen, setEditorOpen] = useState(false)
  const [editorTitle, setEditorTitle] = useState('Edit action')
  const [editingPos, setEditingPos] = useState<number | null>(null)
  const [editingBase, setEditingBase] = useState<PlainObject | null>(null)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)

  const [form] = Form.useForm<ActionFormValues>()

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(DISABLED_ACTIONS_STORAGE_KEY)
      if (!raw) {
        setDisabledActions([])
        return
      }
      const parsed = JSON.parse(raw) as unknown
      if (Array.isArray(parsed)) {
        setDisabledActions(parsed.filter(isPlainObject))
      } else {
        setDisabledActions([])
      }
    } catch (_err) {
      setDisabledActions([])
    }
  }, [])

  useEffect(() => {
    try {
      sessionStorage.setItem(DISABLED_ACTIONS_STORAGE_KEY, JSON.stringify(disabledActions))
    } catch (_err) {
      // ignore storage errors
    }
  }, [disabledActions])

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const settings = await getRuntimeSettings()
      const entry = settings.find((item) => item.key === ACTION_CATALOG_KEY)
      if (!entry) {
        setError(`RuntimeSetting ${ACTION_CATALOG_KEY} не найден`)
        setServerRaw(null)
        setDraftRaw('{}')
        setSettingDescription(null)
        return
      }
      const raw = safeJsonStringify(entry.value)
      setServerRaw(raw)
      setDraftRaw(raw)
      setSettingDescription(entry.description || null)
    } catch (_err) {
      setError('Не удалось загрузить ui.action_catalog')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isStaff) {
      return
    }
    void loadCatalog()
  }, [isStaff, loadCatalog])

  const dirty = useMemo(() => {
    return serverRaw !== null && draftRaw !== serverRaw
  }, [draftRaw, serverRaw])

  const draftParsed = useMemo(() => parseJson(draftRaw), [draftRaw])
  const draftIsValidJson = draftParsed !== null
  const actionRows = useMemo(() => buildActionRows(draftParsed), [draftParsed])

  const updateActions = useCallback((updater: (actions: PlainObject[]) => PlainObject[]) => {
    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно применить изменения: draft не является JSON-объектом')
      return
    }
    parsed.catalog_version = 1
    const currentActions = getCatalogActions(parsed)
    const nextActions = updater(deepCopy(currentActions))
    upsertCatalogActions(parsed, nextActions)
    setDraftRaw(safeJsonStringify(parsed))
  }, [draftRaw])

  const openEditor = useCallback((opts: { mode: 'add' | 'edit' | 'copy'; pos?: number }) => {
    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно открыть редактор: draft не является JSON-объектом')
      return
    }
    const actions = getCatalogActions(parsed)
    const pos = typeof opts.pos === 'number' ? opts.pos : null
    const base = (pos !== null && actions[pos]) ? deepCopy(actions[pos]) : null

    const usedIds = new Set(actions.map((a) => (typeof a.id === 'string' ? a.id : '')).filter(Boolean))

    if (opts.mode === 'add') {
      setEditorTitle('Add action')
      setEditingPos(null)
      setEditingBase(null)
      setEditorValues(deriveActionFormValues(null))
      setEditorOpen(true)
      return
    }

    if (!base) {
      setError('Action не найден')
      return
    }

    if (opts.mode === 'edit') {
      setEditorTitle('Edit action')
      setEditingPos(pos)
      setEditingBase(base)
      setEditorValues(deriveActionFormValues(base))
      setEditorOpen(true)
      return
    }

    const copied = deepCopy(base)
    const baseId = typeof copied.id === 'string' ? copied.id : 'action'
    const candidate = `${baseId}.copy`
    copied.id = ensureUniqueId(candidate, usedIds)
    setEditorTitle('Copy action')
    setEditingPos(null)
    setEditingBase(copied)
    setEditorValues(deriveActionFormValues(copied))
    setEditorOpen(true)
  }, [draftRaw])

  const closeEditor = useCallback(() => {
    setEditorOpen(false)
    setEditingPos(null)
    setEditingBase(null)
    setEditorValues(null)
    form.resetFields()
  }, [form])

  const submitEditor = useCallback(async () => {
    const values = await form.validateFields()

    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно применить изменения: draft не является JSON-объектом')
      return
    }
    parsed.catalog_version = 1

    const actions = getCatalogActions(parsed)
    const next = buildActionFromForm(editingBase, values)
    const trimmedId = typeof next.id === 'string' ? next.id.trim() : ''

    const usedIds = new Set(
      actions
        .map((a) => (typeof a.id === 'string' ? a.id.trim() : ''))
        .filter(Boolean)
    )

    if (editingPos !== null) {
      const currentId = typeof actions[editingPos]?.id === 'string' ? String(actions[editingPos].id).trim() : ''
      usedIds.delete(currentId)
    }

    if (!trimmedId || usedIds.has(trimmedId)) {
      form.setFields([{ name: 'id', errors: ['ID уже используется'] }])
      return
    }

    const nextActions = [...actions]
    if (editingPos !== null) {
      nextActions[editingPos] = next
    } else {
      nextActions.push(next)
    }
    upsertCatalogActions(parsed, nextActions)
    setDraftRaw(safeJsonStringify(parsed))
    closeEditor()
  }, [closeEditor, draftRaw, editingBase, editingPos, form])

  const moveAction = useCallback((pos: number, delta: -1 | 1) => {
    updateActions((actions) => {
      const nextPos = pos + delta
      if (nextPos < 0 || nextPos >= actions.length) return actions
      const next = [...actions]
      const tmp = next[pos]
      next[pos] = next[nextPos]
      next[nextPos] = tmp
      return next
    })
  }, [updateActions])

  const disableAction = useCallback((pos: number) => {
    updateActions((actions) => {
      const target = actions[pos]
      if (!target) return actions
      setDisabledActions((current) => [...current, deepCopy(target)])
      return actions.filter((_item, idx) => idx !== pos)
    })
  }, [updateActions])

  const restoreLastDisabled = useCallback(() => {
    setDisabledActions((current) => {
      if (current.length === 0) return current
      const last = deepCopy(current[current.length - 1])
      const remaining = current.slice(0, -1)

      updateActions((actions) => {
        const usedIds = new Set(
          actions
            .map((a) => (typeof a.id === 'string' ? a.id : ''))
            .filter(Boolean)
        )
        const id = typeof last.id === 'string' ? last.id : 'action'
        last.id = ensureUniqueId(id, usedIds)
        return [...actions, last]
      })

      return remaining
    })
  }, [updateActions])

  const actionsEditable = isStaff && draftIsValidJson && isPlainObject(draftParsed)

  const columns: ColumnsType<ActionRow> = useMemo(() => ([
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 260,
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: 'Label',
      dataIndex: 'label',
      key: 'label',
      render: (value: string) => <Text>{value}</Text>,
    },
    {
      title: 'Contexts',
      dataIndex: 'contexts',
      key: 'contexts',
      width: 180,
      render: (value: string[]) => (
        <Space size={4} wrap>
          {value.map((ctx) => <Tag key={ctx}>{ctx}</Tag>)}
        </Space>
      ),
    },
    {
      title: 'Executor',
      dataIndex: 'executor_kind',
      key: 'executor_kind',
      width: 140,
      render: (value: string) => <Tag>{value || '-'}</Tag>,
    },
    {
      title: 'Ref',
      key: 'ref',
      width: 260,
      render: (_value, record) => {
        if (record.executor_kind === 'workflow') {
          return <Text code>{record.workflow_id || '-'}</Text>
        }
        if (record.executor_kind === 'ibcmd_cli' || record.executor_kind === 'designer_cli') {
          return <Text code>{`${record.driver || '-'} / ${record.command_id || '-'}`}</Text>
        }
        return '-'
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 190,
      render: (_value, record) => (
        <Space size={0}>
          <Button
            size="small"
            type="text"
            icon={<ArrowUpOutlined />}
            aria-label="Move up"
            onClick={() => moveAction(record.pos, -1)}
            disabled={!actionsEditable || record.pos === 0}
          />
          <Button
            size="small"
            type="text"
            icon={<ArrowDownOutlined />}
            aria-label="Move down"
            onClick={() => moveAction(record.pos, 1)}
            disabled={!actionsEditable || record.pos === actionRows.length - 1}
          />
          <Button
            size="small"
            type="text"
            icon={<EditOutlined />}
            aria-label="Edit"
            onClick={() => openEditor({ mode: 'edit', pos: record.pos })}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            icon={<CopyOutlined />}
            aria-label="Copy"
            onClick={() => openEditor({ mode: 'copy', pos: record.pos })}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            aria-label="Disable"
            onClick={() => disableAction(record.pos)}
            disabled={!actionsEditable}
          />
        </Space>
      ),
    },
  ]), [actionRows.length, actionsEditable, disableAction, moveAction, openEditor])

  const tabs = useMemo(() => ([
    {
      key: 'guided',
      label: 'Guided',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {!draftIsValidJson && (
            <Alert
              type="warning"
              showIcon
              message="Текущий draft не является валидным JSON"
              description="Перейдите в Raw режим, чтобы исправить JSON."
            />
          )}

          <Card size="small">
            <Space size="middle" wrap align="center">
              <Text strong>Actions:</Text>
              <Tag data-testid="action-catalog-actions-count">{actionRows.length}</Tag>
              {dirty && <Tag color="orange" data-testid="action-catalog-dirty">Unsaved changes</Tag>}
              <Button
                size="small"
                icon={<PlusOutlined />}
                onClick={() => openEditor({ mode: 'add' })}
                disabled={!actionsEditable}
                data-testid="action-catalog-add"
              >
                Add
              </Button>
              <Button
                size="small"
                icon={<RollbackOutlined />}
                onClick={restoreLastDisabled}
                disabled={!actionsEditable || disabledActions.length === 0}
                data-testid="action-catalog-restore-last"
              >
                Restore last disabled
              </Button>
              {disabledActions.length > 0 && (
                <Text type="secondary" data-testid="action-catalog-disabled-count">
                  Disabled: {disabledActions.length}
                </Text>
              )}
            </Space>
          </Card>

          <Table<ActionRow>
            data-testid="action-catalog-guided-table"
            size="small"
            bordered
            pagination={false}
            columns={columns}
            dataSource={actionRows}
            rowKey={(row) => row.pos}
            locale={{ emptyText: 'Нет actions' }}
          />
        </Space>
      ),
    },
    {
      key: 'raw',
      label: 'Raw JSON',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {dirty && <Tag color="orange" data-testid="action-catalog-dirty-raw">Unsaved changes</Tag>}
          <LazyJsonCodeEditor
            id="action-catalog-raw"
            title={ACTION_CATALOG_KEY}
            value={draftRaw}
            onChange={setDraftRaw}
            height={520}
            readOnly={false}
            enableFormat
            enableCopy
            path="ui.action_catalog"
          />
        </Space>
      ),
    },
  ]), [actionRows, actionsEditable, columns, dirty, disabledActions.length, draftIsValidJson, draftRaw, openEditor, restoreLastDisabled])

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div>
        <Space size="middle" align="center" wrap>
          <Title level={2} style={{ marginBottom: 0 }}>Action Catalog</Title>
          <Text type="secondary">
            RuntimeSetting <Text code>{ACTION_CATALOG_KEY}</Text>
          </Text>
          {dirty && <Tag color="orange">Draft</Tag>}
        </Space>
        {settingDescription && (
          <Text type="secondary" style={{ display: 'block' }}>{settingDescription}</Text>
        )}
      </div>

      {error && <Alert type="error" showIcon message={error} />}

      <Card size="small">
        <Space wrap>
          <Button onClick={loadCatalog} disabled={loading || dirty} data-testid="action-catalog-reload">
            Reload
          </Button>
          {dirty && (
            <Text type="secondary">Reload disabled while draft has unsaved changes.</Text>
          )}
        </Space>
      </Card>

      {loading ? (
        <Card>
          <Spin />
        </Card>
      ) : (
        <Tabs
          activeKey={mode}
          onChange={(next) => setMode(next as ActionCatalogMode)}
          items={tabs}
        />
      )}

      <Modal
        title={editorTitle}
        open={editorOpen}
        onCancel={closeEditor}
        onOk={() => void submitEditor()}
        afterOpenChange={(open) => {
          if (!open || !editorValues) {
            return
          }
          form.setFieldsValue(editorValues)
        }}
        okText="Apply"
        okButtonProps={{ 'data-testid': 'action-catalog-editor-apply' }}
        destroyOnClose
      >
        <Form<ActionFormValues>
          form={form}
          layout="vertical"
          preserve={false}
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
            />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, next) => prev.executor?.kind !== next.executor?.kind}>
            {({ getFieldValue }) => {
              const kind = getFieldValue(['executor', 'kind']) as ExecutorKind | undefined
              if (kind === 'workflow') {
                return (
                  <Form.Item
                    label="workflow_id"
                    name={['executor', 'workflow_id']}
                    rules={[
                      { required: true, message: 'workflow_id is required' },
                      { whitespace: true, message: 'workflow_id is required' },
                    ]}
                  >
                    <Input data-testid="action-catalog-editor-workflow-id" />
                  </Form.Item>
                )
              }

              return (
                <Space size="middle" style={{ width: '100%' }} align="start">
                  <Form.Item
                    label="driver"
                    name={['executor', 'driver']}
                    rules={[
                      { required: true, message: 'driver is required' },
                      { whitespace: true, message: 'driver is required' },
                    ]}
                    style={{ flex: 1 }}
                  >
                    <Input data-testid="action-catalog-editor-driver" />
                  </Form.Item>
                  <Form.Item
                    label="command_id"
                    name={['executor', 'command_id']}
                    rules={[
                      { required: true, message: 'command_id is required' },
                      { whitespace: true, message: 'command_id is required' },
                    ]}
                    style={{ flex: 2 }}
                  >
                    <Input data-testid="action-catalog-editor-command-id" />
                  </Form.Item>
                </Space>
              )
            }}
          </Form.Item>

          <Alert
            type="info"
            showIcon
            message="Advanced executor fields (mode/params/additional_args/stdin/fixed) пока не редактируются в guided."
          />
        </Form>
      </Modal>
    </Space>
  )
}
