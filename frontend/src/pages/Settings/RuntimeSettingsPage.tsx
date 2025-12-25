import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, InputNumber, Space, Switch, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useMe } from '../../api/queries/me'
import { getRuntimeSettings, updateRuntimeSetting, type RuntimeSetting } from '../../api/runtimeSettings'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

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

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'key', label: 'Key', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'description', label: 'Описание', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'value', label: 'Значение', sortable: true, groupKey: 'value', groupLabel: 'Value' },
    { key: 'default', label: 'Default', sortable: true, groupKey: 'value', groupLabel: 'Value' },
    { key: 'range', label: 'Диапазон', groupKey: 'value', groupLabel: 'Value' },
    { key: 'actions', label: 'Действия', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

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

  const table = useTableToolkit({
    tableId: 'runtime_settings',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const filteredSettings = useMemo(() => {
    const searchValue = table.search.trim().toLowerCase()
    return settings.filter((item) => {
      if (searchValue) {
        const matchesSearch = [
          item.key,
          item.description ?? '',
          String(item.value ?? ''),
        ].some((value) => String(value || '').toLowerCase().includes(searchValue))
        if (!matchesSearch) return false
      }

      for (const [key, value] of Object.entries(table.filters)) {
        if (value === null || value === undefined || value === '') {
          continue
        }
        const recordValue = (() => {
          switch (key) {
            case 'key':
              return item.key
            case 'description':
              return item.description ?? ''
            case 'value':
              return item.draftValue
            case 'default':
              return item.default
            case 'range':
              return `${item.min_value ?? '-'}..${item.max_value ?? '-'}`
            default:
              return null
          }
        })()

        if (Array.isArray(value)) {
          if (!value.map(String).includes(String(recordValue ?? ''))) {
            return false
          }
          continue
        }

        if (typeof value === 'boolean') {
          if (Boolean(recordValue) !== value) return false
          continue
        }

        if (typeof value === 'number') {
          if (Number(recordValue) !== value) return false
          continue
        }

        const needle = String(value).toLowerCase()
        const haystack = String(recordValue ?? '').toLowerCase()
        if (!haystack.includes(needle)) return false
      }

      return true
    })
  }, [settings, table.filters, table.search])

  const sortedSettings = useMemo(() => {
    if (!table.sort.key || !table.sort.order) {
      return filteredSettings
    }
    const key = table.sort.key
    const direction = table.sort.order === 'asc' ? 1 : -1
    const getValue = (item: RuntimeSettingRow) => {
      switch (key) {
        case 'key':
          return item.key
        case 'description':
          return item.description ?? ''
        case 'value':
          return item.draftValue ?? ''
        case 'default':
          return item.default ?? ''
        case 'range':
          return `${item.min_value ?? '-'}..${item.max_value ?? '-'}`
        default:
          return ''
      }
    }
    return [...filteredSettings].sort((a, b) => {
      const left = getValue(a)
      const right = getValue(b)
      if (typeof left === 'number' && typeof right === 'number') {
        return (left - right) * direction
      }
      return String(left).localeCompare(String(right)) * direction
    })
  }, [filteredSettings, table.sort.key, table.sort.order])

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const pageItems = sortedSettings.slice(pageStart, pageStart + table.pagination.pageSize)

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
        <TableToolkit
          table={table}
          data={pageItems}
          total={sortedSettings.length}
          loading={loading}
          rowKey="key"
          columns={columns}
          searchPlaceholder="Search settings"
        />
      </Card>
    </Space>
  )
}
