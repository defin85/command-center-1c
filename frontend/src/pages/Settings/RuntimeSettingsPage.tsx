import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, InputNumber, Space, Switch, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useMe } from '../../api/queries/me'
import { getRuntimeSettings, updateRuntimeSetting, type RuntimeSetting } from '../../api/runtimeSettings'

const { Title, Text } = Typography

type RuntimeSettingRow = RuntimeSetting & { draftValue: unknown }

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

const isBool = (value: unknown): value is boolean => typeof value === 'boolean'

export function RuntimeSettingsPage() {
  const meQuery = useMe()
  const [settings, setSettings] = useState<RuntimeSettingRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canEdit = Boolean(meQuery.data?.is_superuser)
  const isStaff = Boolean(meQuery.data?.is_staff)

  const loadSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getRuntimeSettings()
      const filtered = data.filter((item) => !item.key.startsWith('observability.timeline.'))
      setSettings(
        filtered.map((item) => ({
          ...item,
          draftValue: item.value,
        }))
      )
    } catch (_err) {
      setError('Не удалось загрузить настройки')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isStaff) {
      return
    }
    void loadSettings()
  }, [isStaff, loadSettings])

  const updateDraft = useCallback((key: string, value: unknown) => {
    setSettings((current) =>
      current.map((item) =>
        item.key === key ? { ...item, draftValue: value } : item
      )
    )
  }, [])

  const saveSetting = useCallback(async (setting: RuntimeSettingRow) => {
    try {
      const updated = await updateRuntimeSetting(setting.key, setting.draftValue)
      setSettings((current) =>
        current.map((item) =>
          item.key === updated.key
            ? { ...item, ...updated, draftValue: updated.value }
            : item
        )
      )
    } catch (_err) {
      setError('Не удалось сохранить настройку')
    }
  }, [])

  const columns: ColumnsType<RuntimeSettingRow> = useMemo(() => ([
    {
      title: 'Key',
      dataIndex: 'key',
      key: 'key',
      width: 280,
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: 'Описание',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Значение',
      dataIndex: 'draftValue',
      key: 'value',
      width: 180,
      render: (_value, record) => {
        if (record.value_type === 'int') {
          return (
            <InputNumber
              min={record.min_value ?? undefined}
              max={record.max_value ?? undefined}
              value={toNumber(record.draftValue) ?? undefined}
              onChange={(next) => updateDraft(record.key, next ?? 0)}
              disabled={!canEdit}
              style={{ width: '100%' }}
            />
          )
        }
        if (record.value_type === 'bool') {
          return (
            <Switch
              checked={isBool(record.draftValue) ? record.draftValue : Boolean(record.draftValue)}
              onChange={(next) => updateDraft(record.key, next)}
              disabled={!canEdit}
            />
          )
        }
        return <Text>{String(record.draftValue ?? '')}</Text>
      },
    },
    {
      title: 'Default',
      dataIndex: 'default',
      key: 'default',
      width: 120,
      render: (value: unknown) => <Tag>{String(value)}</Tag>,
    },
    {
      title: 'Диапазон',
      key: 'range',
      width: 140,
      render: (_value, record) => {
        if (record.min_value === null && record.max_value === null) return '-'
        return `${record.min_value ?? '-'}..${record.max_value ?? '-'}`
      },
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 140,
      render: (_value, record) => {
        const isChanged = record.draftValue !== record.value
        return (
          <Button
            type="primary"
            size="small"
            disabled={!canEdit || !isChanged}
            onClick={() => saveSetting(record)}
          >
            Save
          </Button>
        )
      },
    },
  ]), [canEdit, saveSetting, updateDraft])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ marginBottom: 0 }}>Runtime Settings</Title>
        <Text type="secondary">Управление runtime-настройками UI и операций.</Text>
      </div>

      {!isStaff && (
        <Alert
          type="warning"
          message="Недостаточно прав"
          description="Доступ только для staff пользователей."
        />
      )}

      {error && (
        <Alert type="error" message={error} />
      )}

      <Card>
        <Table
          rowKey="key"
          columns={columns}
          dataSource={settings}
          loading={loading}
          pagination={false}
        />
      </Card>
    </Space>
  )
}
