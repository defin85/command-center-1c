import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Space, Spin, Table, Tabs, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useMe } from '../../api/queries/me'
import { getRuntimeSettings } from '../../api/runtimeSettings'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'

const { Title, Text } = Typography

const ACTION_CATALOG_KEY = 'ui.action_catalog'

type ActionCatalogMode = 'guided' | 'raw'

type ActionRow = {
  id: string
  label: string
  contexts: string[]
  executor_kind: string
  driver?: string
  command_id?: string
  workflow_id?: string
}

const safeJsonStringify = (value: unknown): string => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch (_err) {
    return '{}'
  }
}

const parseJson = (raw: string): unknown => {
  try {
    return JSON.parse(raw) as unknown
  } catch (_err) {
    return null
  }
}

const buildActionRows = (value: unknown): ActionRow[] => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []
  const obj = value as Record<string, unknown>
  const extensions = obj.extensions
  if (!extensions || typeof extensions !== 'object' || Array.isArray(extensions)) return []
  const actions = (extensions as Record<string, unknown>).actions
  if (!Array.isArray(actions)) return []

  const rows: ActionRow[] = []
  for (const item of actions) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue
    const action = item as Record<string, unknown>
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
  ]), [])

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
            <Space size="middle" wrap>
              <Text strong>Actions:</Text>
              <Tag data-testid="action-catalog-actions-count">{actionRows.length}</Tag>
              {dirty && <Tag color="orange" data-testid="action-catalog-dirty">Unsaved changes</Tag>}
            </Space>
          </Card>

          <Table<ActionRow>
            data-testid="action-catalog-guided-table"
            size="small"
            bordered
            pagination={false}
            columns={columns}
            dataSource={actionRows}
            rowKey={(row, index) => row.id || `row-${index ?? 0}`}
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
  ]), [actionRows, columns, dirty, draftIsValidJson, draftRaw])

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
    </Space>
  )
}
