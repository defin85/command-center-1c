import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, InputNumber, Space, Switch, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useSearchParams } from 'react-router-dom'

import { useAuthz } from '../../authz/useAuthz'
import { getRuntimeSettings, updateRuntimeSetting, type RuntimeSetting } from '../../api/runtimeSettings'
import { DrawerSurfaceShell, PageHeader, WorkspacePage } from '../../components/platform'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { useAdminSupportTranslation, useCommonTranslation } from '../../i18n'
import { trackUiAction } from '../../observability/uiActionJournal'

const { Text } = Typography
const RUNTIME_CONTROL_SETTING_PREFIX = 'runtime.scheduler.'

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
const isRuntimeControlSetting = (key: string) => key.startsWith(RUNTIME_CONTROL_SETTING_PREFIX)

export function RuntimeSettingsPage() {
  const { isStaff, canManageRuntimeControls } = useAuthz()
  const { t } = useAdminSupportTranslation()
  const { t: tCommon } = useCommonTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [settings, setSettings] = useState<RuntimeSettingRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const unavailableShort = tCommon(($) => $.values.unavailableShort)

  const canEdit = isStaff
  const selectedSettingKey = (searchParams.get('setting') || '').trim() || null

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

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
      setError(t(($) => $.runtimeSettings.errors.loadFailed))
    } finally {
      setLoading(false)
    }
  }, [t])

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

  const canEditSetting = useCallback((setting: RuntimeSettingRow) => (
    canEdit && (!isRuntimeControlSetting(setting.key) || canManageRuntimeControls)
  ), [canEdit, canManageRuntimeControls])

  const saveSetting = useCallback(async (setting: RuntimeSettingRow) => {
    if (!canEditSetting(setting)) {
      setError(t(($) => $.runtimeSettings.errors.runtimeControlCapabilityRequired))
      return
    }
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
      setError(t(($) => $.runtimeSettings.errors.saveFailed))
    }
  }, [canEditSetting, t])

  const fallbackColumnConfigs = useMemo(() => [
    {
      key: 'key',
      label: t(($) => $.runtimeSettings.table.key),
      sortable: true,
      groupKey: 'core',
      groupLabel: t(($) => $.runtimeSettings.groups.core),
    },
    {
      key: 'description',
      label: t(($) => $.runtimeSettings.table.description),
      sortable: true,
      groupKey: 'core',
      groupLabel: t(($) => $.runtimeSettings.groups.core),
    },
    {
      key: 'value',
      label: t(($) => $.runtimeSettings.table.value),
      sortable: true,
      groupKey: 'value',
      groupLabel: t(($) => $.runtimeSettings.groups.value),
    },
    {
      key: 'default',
      label: t(($) => $.runtimeSettings.table.default),
      sortable: true,
      groupKey: 'value',
      groupLabel: t(($) => $.runtimeSettings.groups.value),
    },
    {
      key: 'range',
      label: t(($) => $.runtimeSettings.table.range),
      groupKey: 'value',
      groupLabel: t(($) => $.runtimeSettings.groups.value),
    },
    {
      key: 'actions',
      label: t(($) => $.runtimeSettings.table.actions),
      groupKey: 'actions',
      groupLabel: t(($) => $.runtimeSettings.groups.actions),
    },
  ], [t])

  const columns: ColumnsType<RuntimeSettingRow> = useMemo(() => ([
    {
      title: t(($) => $.runtimeSettings.table.key),
      dataIndex: 'key',
      key: 'key',
      width: 280,
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: t(($) => $.runtimeSettings.table.description),
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: t(($) => $.runtimeSettings.table.value),
      dataIndex: 'draftValue',
      key: 'value',
      width: 180,
      render: (_value, record) => {
        if (record.value_type === 'bool') {
          return <Tag color={isBool(record.draftValue) ? (record.draftValue ? 'green' : 'default') : 'default'}>{String(record.draftValue)}</Tag>
        }
        return <Text>{String(record.draftValue ?? '')}</Text>
      },
    },
    {
      title: t(($) => $.runtimeSettings.table.default),
      dataIndex: 'default',
      key: 'default',
      width: 120,
      render: (value: unknown) => <Tag>{String(value)}</Tag>,
    },
    {
      title: t(($) => $.runtimeSettings.table.range),
      key: 'range',
      width: 140,
      render: (_value, record) => {
        if (record.min_value === null && record.max_value === null) return unavailableShort
        return `${record.min_value ?? unavailableShort}..${record.max_value ?? unavailableShort}`
      },
    },
    {
      title: t(($) => $.runtimeSettings.table.actions),
      key: 'actions',
      width: 140,
      render: (_value, record) => (
        <Button
          size="small"
          type="primary"
          disabled={!canEditSetting(record)}
          onClick={() => updateSearchParams({ setting: record.key, context: 'setting' })}
        >
          {t(($) => $.runtimeSettings.table.edit)}
        </Button>
      ),
    },
  ]), [canEditSetting, t, unavailableShort, updateSearchParams])

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
  const selectedSetting = selectedSettingKey
    ? sortedSettings.find((item) => item.key === selectedSettingKey) ?? null
    : null
  const selectedSettingLocked = selectedSetting ? !canEditSetting(selectedSetting) : false

  const renderSettingEditor = (setting: RuntimeSettingRow) => {
    if (setting.value_type === 'int') {
      return (
        <InputNumber
          min={setting.min_value ?? undefined}
          max={setting.max_value ?? undefined}
          value={toNumber(setting.draftValue) ?? undefined}
          onChange={(next) => updateDraft(setting.key, next ?? 0)}
          disabled={!canEditSetting(setting)}
          style={{ width: '100%' }}
        />
      )
    }
    if (setting.value_type === 'bool') {
      return (
        <Switch
          checked={isBool(setting.draftValue) ? setting.draftValue : Boolean(setting.draftValue)}
          onChange={(next) => updateDraft(setting.key, next)}
          disabled={!canEditSetting(setting)}
        />
      )
    }
    return <Text>{String(setting.draftValue ?? '')}</Text>
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.runtimeSettings.page.title)}
          subtitle={t(($) => $.runtimeSettings.page.subtitle)}
          actions={(
            <Button onClick={() => void loadSettings()} loading={loading}>
              {t(($) => $.runtimeSettings.page.refresh)}
            </Button>
          )}
        />
      )}
    >
      {!isStaff && (
        <Alert
          type="warning"
          message={t(($) => $.runtimeSettings.page.insufficientPermissionsTitle)}
          description={t(($) => $.runtimeSettings.page.insufficientPermissionsDescription)}
        />
      )}

      {isStaff && !canManageRuntimeControls && settings.some((item) => isRuntimeControlSetting(item.key)) ? (
        <Alert
          type="info"
          showIcon
          message={t(($) => $.runtimeSettings.page.runtimeControlReadonly)}
        />
      ) : null}

      {error && (
        <Alert type="error" message={error} />
      )}

      <div data-testid="runtime-settings-page">
        <TableToolkit
          table={table}
          data={pageItems}
          total={sortedSettings.length}
          loading={loading}
          rowKey="key"
          columns={columns}
          searchPlaceholder={t(($) => $.runtimeSettings.page.searchPlaceholder)}
          onRow={(record) => ({
            onClick: () => updateSearchParams({ setting: record.key, context: 'setting' }),
            style: { cursor: 'pointer' },
          })}
        />
      </div>

      <DrawerSurfaceShell
        open={Boolean(selectedSetting)}
        onClose={() => updateSearchParams({ setting: null, context: null })}
        title={selectedSetting?.key ?? t(($) => $.runtimeSettings.detail.titleFallback)}
        subtitle={selectedSetting?.description ?? undefined}
        drawerTestId="runtime-settings-detail-drawer"
        extra={selectedSetting ? (
          <Button
            type="primary"
            disabled={!canEditSetting(selectedSetting) || selectedSetting.draftValue === selectedSetting.value}
            onClick={() => {
              void trackUiAction({
                actionKind: 'drawer.submit',
                actionName: 'Save runtime setting',
                context: {
                  setting: selectedSetting.key,
                  manual_operation: 'settings.runtime.update',
                },
              }, () => saveSetting(selectedSetting))
            }}
          >
            {t(($) => $.runtimeSettings.detail.save)}
          </Button>
        ) : null}
      >
        {selectedSetting ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {selectedSettingLocked ? (
              <Alert
                type="warning"
                showIcon
                message={t(($) => $.runtimeSettings.detail.lockedWarning)}
              />
            ) : null}
            <Text><strong>{t(($) => $.shared.current)}:</strong> {String(selectedSetting.value ?? unavailableShort)}</Text>
            <Text><strong>{t(($) => $.shared.default)}:</strong> {String(selectedSetting.default ?? unavailableShort)}</Text>
            <Text><strong>{t(($) => $.shared.range)}:</strong> {selectedSetting.min_value === null && selectedSetting.max_value === null ? unavailableShort : `${selectedSetting.min_value ?? unavailableShort}..${selectedSetting.max_value ?? unavailableShort}`}</Text>
            <div>{renderSettingEditor(selectedSetting)}</div>
          </Space>
        ) : null}
      </DrawerSurfaceShell>
    </WorkspacePage>
  )
}
