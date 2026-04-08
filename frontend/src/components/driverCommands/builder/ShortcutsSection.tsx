import { useEffect, useMemo, useState } from 'react'
import { Alert, App, Button, Input, Select, Space, Typography } from 'antd'

import {
  useDriverCommandShortcuts,
  useCreateDriverCommandShortcut,
  useDeleteDriverCommandShortcut,
} from '../../../api/queries'
import type { DriverCommandV2 } from '../../../api/driverCommands'
import type { DriverCommandShortcut } from '../../../api/commandShortcuts'
import { confirmWithTracking } from '../../../observability/confirmWithTracking'
import type { DriverCommandBuilderMode, DriverCommandOperationConfig, IbcmdCliConnection, IbcmdDbmsAuth, IbcmdIbAuth } from './types'
import { getSchemaAtPath, isRecord } from './utils'

const { Text } = Typography

const EMPTY_SHORTCUT_ITEMS: DriverCommandShortcut[] = []

export function ShortcutsSection({
  enabled,
  readOnly,
  commandsById,
  driverSchema,
  selectedCommand,
  commandId,
  mode,
  config,
  currentCatalogBaseVersion,
  currentCatalogOverridesVersion,
  onChange,
}: {
  enabled: boolean
  readOnly?: boolean
  commandsById: Record<string, DriverCommandV2>
  driverSchema: Record<string, unknown> | undefined
  selectedCommand: DriverCommandV2 | undefined
  commandId: string
  mode: DriverCommandBuilderMode
  config: DriverCommandOperationConfig
  currentCatalogBaseVersion: string
  currentCatalogOverridesVersion: string
  onChange: (updates: Partial<DriverCommandOperationConfig>) => void
}) {
  const { modal } = App.useApp()

  const shortcutsQuery = useDriverCommandShortcuts('ibcmd', enabled)
  const createShortcutMutation = useCreateDriverCommandShortcut('ibcmd')
  const deleteShortcutMutation = useDeleteDriverCommandShortcut('ibcmd')

  const shortcutItems = shortcutsQuery.data?.items ?? EMPTY_SHORTCUT_ITEMS
  const shortcutsById = useMemo(() => {
    const map: Record<string, { id: string; command_id: string; title: string; payload?: unknown; catalog_base_version?: string; catalog_overrides_version?: string }> = {}
    for (const item of shortcutItems) {
      map[item.id] = {
        id: item.id,
        command_id: item.command_id,
        title: item.title,
        payload: item.payload,
        catalog_base_version: item.catalog_base_version,
        catalog_overrides_version: item.catalog_overrides_version,
      }
    }
    return map
  }, [shortcutItems])
  const shortcutOptions = useMemo(
    () => shortcutItems.map((item) => ({ value: item.id, label: item.title })),
    [shortcutItems]
  )
  const [selectedShortcutId, setSelectedShortcutId] = useState<string | undefined>(undefined)

  useEffect(() => {
    if (!selectedShortcutId) return
    if (!shortcutsById[selectedShortcutId]) {
      setSelectedShortcutId(undefined)
    }
  }, [selectedShortcutId, shortcutsById])

  const parseShortcutConfig = (payload: unknown): Partial<DriverCommandOperationConfig> => {
    if (!isRecord(payload)) return {}
    const maybeConfig = payload.config
    if (isRecord(maybeConfig)) return maybeConfig as unknown as Partial<DriverCommandOperationConfig>
    return payload as unknown as Partial<DriverCommandOperationConfig>
  }

  const sanitizeLoadedShortcutConfig = (
    cfg: Partial<DriverCommandOperationConfig>,
    cmd: DriverCommandV2 | undefined,
  ): { config: Partial<DriverCommandOperationConfig>; dropped: string[] } => {
    const dropped: string[] = []
    const out: Partial<DriverCommandOperationConfig> = {}

    if (cfg.mode === 'guided' || cfg.mode === 'manual') out.mode = cfg.mode
    if (typeof cfg.args_text === 'string') out.args_text = cfg.args_text
    if (typeof cfg.timeout_seconds === 'number') out.timeout_seconds = cfg.timeout_seconds
    if (typeof cfg.auth_database_id === 'string') out.auth_database_id = cfg.auth_database_id

    // Never load raw stdin from shortcuts (safety).
    if (typeof (cfg as Record<string, unknown>).stdin === 'string' && (cfg as Record<string, unknown>).stdin) {
      dropped.push('stdin')
    }

    const rawIbAuth = cfg.ib_auth
    if (isRecord(rawIbAuth)) {
      const nextIbAuth: Record<string, unknown> = {}
      if (rawIbAuth.strategy === 'actor' || rawIbAuth.strategy === 'service' || rawIbAuth.strategy === 'none') {
        nextIbAuth.strategy = rawIbAuth.strategy
      }
      out.ib_auth = nextIbAuth as unknown as IbcmdIbAuth
    }

    const rawDbmsAuth = cfg.dbms_auth
    if (isRecord(rawDbmsAuth)) {
      const nextDbmsAuth: Record<string, unknown> = {}
      if (rawDbmsAuth.strategy === 'actor' || rawDbmsAuth.strategy === 'service') {
        nextDbmsAuth.strategy = rawDbmsAuth.strategy
      }
      out.dbms_auth = nextDbmsAuth as unknown as IbcmdDbmsAuth
    }

    const rawConnection = cfg.connection
    if (isRecord(rawConnection)) {
      const nextConnection: Record<string, unknown> = {}
      if (typeof rawConnection.remote === 'string') nextConnection.remote = rawConnection.remote
      if (typeof rawConnection.pid === 'number' || rawConnection.pid === null) nextConnection.pid = rawConnection.pid

      const rawOffline = rawConnection.offline
      if (isRecord(rawOffline)) {
        const nextOffline: Record<string, unknown> = {}
        const offlineSchema = getSchemaAtPath(driverSchema, 'connection.offline')
        const allowedKeys = isRecord(offlineSchema) ? new Set(Object.keys(offlineSchema)) : new Set<string>()

        for (const [key, value] of Object.entries(rawOffline)) {
          if (key === 'db_user' || key === 'db_pwd') {
            dropped.push(`connection.offline.${key}`)
            continue
          }
          if (allowedKeys.size > 0 && !allowedKeys.has(key)) {
            dropped.push(`connection.offline.${key}`)
            continue
          }
          if (typeof value === 'string' && value.trim()) nextOffline[key] = value
        }

        nextConnection.offline = nextOffline
      }

      out.connection = nextConnection as unknown as IbcmdCliConnection
    }

    // Filter params by current command schema.
    const rawParams = cfg.params
    if (cmd && isRecord(rawParams)) {
      const allowed = new Set(Object.keys(cmd.params_by_name ?? {}))
      const nextParams: Record<string, unknown> = {}
      for (const [key, value] of Object.entries(rawParams)) {
        if (!allowed.has(key)) {
          dropped.push(`params.${key}`)
          continue
        }
        nextParams[key] = value
      }
      out.params = nextParams
    } else if (isRecord(rawParams)) {
      out.params = rawParams
    }

    return { config: out, dropped }
  }

  const handleShortcutSelect = (shortcutId?: string) => {
    if (!shortcutId) {
      setSelectedShortcutId(undefined)
      return
    }
    const shortcut = shortcutsById[shortcutId]
    if (!shortcut) {
      setSelectedShortcutId(undefined)
      return
    }
    const cmd = shortcut.command_id ? commandsById[shortcut.command_id] : undefined
    const loaded = parseShortcutConfig(shortcut.payload)
    const sanitized = sanitizeLoadedShortcutConfig(loaded, cmd)
    const isLegacy = !shortcut.payload || Object.keys(loaded).length === 0

    const baseMismatch = (shortcut.catalog_base_version || '') !== (currentCatalogBaseVersion || '')
    const overridesMismatch = (shortcut.catalog_overrides_version || '') !== (currentCatalogOverridesVersion || '')
    const hasMismatch = baseMismatch || overridesMismatch

    const apply = () => {
      setSelectedShortcutId(shortcutId)
      if (isLegacy) {
        onChange({
          command_id: shortcut.command_id,
          mode: 'guided',
          params: {},
          args_text: '',
          connection: undefined,
          ib_auth: undefined,
          timeout_seconds: undefined,
        })
        return
      }

      onChange({ command_id: shortcut.command_id, ...sanitized.config })
    }

    if (hasMismatch || sanitized.dropped.length > 0) {
      confirmWithTracking(modal, {
        title: 'Load shortcut',
        okText: 'Apply',
        cancelText: 'Cancel',
        content: (
          <Space direction="vertical" size="small">
            {hasMismatch && (
              <Text type="warning">
                Shortcut was saved for a different driver catalog version. It may require adjustments.
              </Text>
            )}
            {sanitized.dropped.length > 0 && (
              <Text type="secondary">
                Dropped fields: {sanitized.dropped.join(', ')}
              </Text>
            )}
          </Space>
        ),
        onOk: apply,
      })
      return
    }

    apply()
  }

  const handleSaveShortcut = () => {
    if (!enabled) return
    if (readOnly) return
    if (!commandId) {
      modal.error({ title: 'Select command', content: 'Pick a command first.' })
      return
    }

    let nextTitle = (selectedCommand?.label || commandId).trim()

    confirmWithTracking(modal, {
      title: 'Save shortcut',
      okText: 'Save',
      cancelText: 'Cancel',
      content: (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <div>
            <Text type="secondary">Command</Text>
            <div>{selectedCommand?.label || commandId}</div>
          </div>
          <Input
            defaultValue={nextTitle}
            placeholder="Shortcut title"
            onChange={(event) => {
              nextTitle = event.target.value
            }}
          />
        </Space>
      ),
      onOk: async () => {
        const title = nextTitle.trim()
        if (!title) {
          modal.error({ title: 'Title required', content: 'Shortcut title cannot be empty.' })
          return
        }
        const payload = {
          version: 1,
          config: {
            mode,
            params: config.params ?? {},
            args_text: config.args_text ?? '',
            connection: config.connection ?? {},
            timeout_seconds: config.timeout_seconds,
            auth_database_id: config.auth_database_id,
            ib_auth: config.ib_auth ?? {},
            dbms_auth: config.dbms_auth ?? {},
          },
        }
        await createShortcutMutation.mutateAsync({ driver: 'ibcmd', command_id: commandId, title, payload })
      },
    })
  }

  const handleDeleteShortcut = () => {
    if (!enabled) return
    if (readOnly) return
    if (!selectedShortcutId) {
      modal.info({ title: 'Select shortcut', content: 'Pick a shortcut to delete.' })
      return
    }

    const shortcut = shortcutsById[selectedShortcutId]
    const label = shortcut?.title || selectedShortcutId

    confirmWithTracking(modal, {
      title: 'Delete shortcut?',
      okText: 'Delete',
      cancelText: 'Cancel',
      okButtonProps: { danger: true },
      content: <Text>Shortcut: {label}</Text>,
      onOk: async () => {
        await deleteShortcutMutation.mutateAsync(selectedShortcutId)
        setSelectedShortcutId(undefined)
      },
    })
  }

  if (!enabled) return null

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      {shortcutsQuery.isError && (
        <Alert
          type="warning"
          showIcon
          message="Shortcuts unavailable"
          description={(shortcutsQuery.error as Error).message}
        />
      )}
      <Space wrap>
        <Select
          allowClear
          showSearch
          placeholder="Load shortcut"
          style={{ minWidth: 260 }}
          disabled={readOnly || shortcutsQuery.isLoading}
          value={selectedShortcutId}
          options={shortcutOptions}
          optionFilterProp="label"
          onChange={(value) => handleShortcutSelect(value || undefined)}
        />
        <Button
          disabled={!commandId || readOnly || createShortcutMutation.isPending}
          loading={createShortcutMutation.isPending}
          onClick={handleSaveShortcut}
        >
          Save shortcut
        </Button>
        <Button
          danger
          disabled={!selectedShortcutId || readOnly || deleteShortcutMutation.isPending}
          loading={deleteShortcutMutation.isPending}
          onClick={handleDeleteShortcut}
        >
          Delete
        </Button>
      </Space>
    </Space>
  )
}
