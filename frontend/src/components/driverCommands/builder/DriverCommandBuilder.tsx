import { useEffect, useMemo, useState } from 'react'
import { Alert, Checkbox, Form, Modal, Select, Space, Spin, Tabs, Typography } from 'antd'

import { maskArgv } from '../../../lib/masking'
import { useDriverCommands, useMe } from '../../../api/queries'
import type {
  DriverCommandParamV2,
  DriverCommandV2,
  DriverName,
  DriverCommandScope,
  DriverCommandRiskLevel,
} from '../../../api/driverCommands'

import { ArgsEditorSection } from './ArgsEditorSection'
import { DriverOptionsSection } from './DriverOptionsSection'
import { ParamField } from './ParamField'
import { ShortcutsSection } from './ShortcutsSection'
import type { DriverCommandBuilderMode, DriverCommandOperationConfig, IbcmdCliConnectionOffline } from './types'
import {
  IBCMD_CONNECTION_PARAM_NAMES,
  buildCliArgsPreview,
  buildCommandOptions,
  buildIbcmdArgvPreview,
  buildIbcmdConnectionArgsPreview,
  isRecord,
  parseLines,
  sortParams,
} from './utils'

const { Text } = Typography

const EMPTY_COMMANDS_BY_ID: Record<string, DriverCommandV2> = {}
const EMPTY_PARAMS: Record<string, unknown> = {}
const EMPTY_DB_IDS: string[] = []

export function DriverCommandBuilder({
  driver,
  config,
  onChange,
  readOnly,
  availableDatabaseIds,
  databaseNamesById,
}: {
  driver: DriverName
  config: DriverCommandOperationConfig
  onChange: (updates: Partial<DriverCommandOperationConfig>) => void
  readOnly?: boolean
  availableDatabaseIds?: string[]
  databaseNamesById?: Record<string, string>
}) {
  const driverCommandsQuery = useDriverCommands(driver, true)
  const catalog = driverCommandsQuery.data?.catalog
  const commandsById = useMemo(() => catalog?.commands_by_id ?? EMPTY_COMMANDS_BY_ID, [catalog?.commands_by_id])
  const driverSchema = useMemo(
    () => (isRecord(catalog?.driver_schema) ? (catalog?.driver_schema as Record<string, unknown>) : undefined),
    [catalog?.driver_schema]
  )

  const shortcutsEnabled = driver === 'ibcmd'
  const meQuery = useMe()

  const mode: DriverCommandBuilderMode = config.mode ?? 'guided'
  const commandId = (config.command_id || '').trim()
  const params = useMemo(() => (config.params ?? EMPTY_PARAMS) as Record<string, unknown>, [config.params])
  const confirmDangerous = config.confirm_dangerous === true
  const [dangerousConfirmPending, setDangerousConfirmPending] = useState(false)

  const commandOptions = useMemo(() => buildCommandOptions(commandsById), [commandsById])
  const selectedCommand: DriverCommandV2 | undefined = commandId ? commandsById[commandId] : undefined

  const scope: DriverCommandScope | undefined = selectedCommand?.scope
  const risk: DriverCommandRiskLevel | undefined = selectedCommand?.risk_level

  useEffect(() => {
    if (driver !== 'ibcmd') return
    if (readOnly) return
    if (scope !== 'per_database') return

    const connection = config.connection
    const hasRemote = typeof connection?.remote === 'string' && connection.remote.trim().length > 0
    const hasPid = typeof connection?.pid === 'number'
    if (hasRemote || hasPid) return

    const offline = connection?.offline
    if (offline && typeof offline === 'object') return

    onChange({ connection: { ...(connection ?? {}), offline: {} } })
  }, [config.connection, driver, onChange, readOnly, scope])

  useEffect(() => {
    if (driver !== 'ibcmd') return
    const connection = config.connection
    const offline = connection?.offline
    if (!offline) return
    if (!('db_user' in offline) && !('db_pwd' in offline)) return

    const nextOffline = { ...(offline as IbcmdCliConnectionOffline) }
    delete (nextOffline as Record<string, unknown>).db_user
    delete (nextOffline as Record<string, unknown>).db_pwd

    onChange({ connection: { ...(connection ?? {}), offline: nextOffline } })
  }, [config.connection, driver, onChange])

  useEffect(() => {
    const nextLabel = selectedCommand?.label
    const nextScope = selectedCommand?.scope
    const nextRisk = selectedCommand?.risk_level

    const currentLabel = config.command_label
    const currentScope = config.command_scope
    const currentRisk = config.command_risk_level

    if (currentLabel === nextLabel && currentScope === nextScope && currentRisk === nextRisk) {
      return
    }

    onChange({
      command_label: nextLabel,
      command_scope: nextScope,
      command_risk_level: nextRisk,
    })
  }, [config.command_label, config.command_risk_level, config.command_scope, onChange, selectedCommand])

  useEffect(() => {
    if (risk !== 'dangerous' && confirmDangerous) {
      onChange({ confirm_dangerous: false })
    }
    if (risk !== 'dangerous' && dangerousConfirmPending) {
      setDangerousConfirmPending(false)
    }
  }, [confirmDangerous, dangerousConfirmPending, onChange, risk])

  const availableDbIds = useMemo(() => availableDatabaseIds ?? EMPTY_DB_IDS, [availableDatabaseIds])
  const stableAvailableDbIds = useMemo(() => {
    if (availableDbIds.length < 2) return availableDbIds
    const copy = [...availableDbIds]
    copy.sort((a, b) => {
      const la = databaseNamesById?.[a] ? `${databaseNamesById[a]} (${a})` : a
      const lb = databaseNamesById?.[b] ? `${databaseNamesById[b]} (${b})` : b
      return la.localeCompare(lb)
    })
    return copy
  }, [availableDbIds, databaseNamesById])
  const databaseOptions = useMemo(
    () =>
      stableAvailableDbIds.map((id) => ({
        value: id,
        label: databaseNamesById?.[id] ? `${databaseNamesById[id]} (${id})` : id,
      })),
    [stableAvailableDbIds, databaseNamesById]
  )

  useEffect(() => {
    if (driver !== 'ibcmd') return
    if (scope !== 'global') {
      if (config.auth_database_id) {
        onChange({ auth_database_id: undefined })
      }
      return
    }
    if (stableAvailableDbIds.length === 0) return

    const current = config.auth_database_id
    if (typeof current === 'string' && stableAvailableDbIds.includes(current)) return
    onChange({ auth_database_id: stableAvailableDbIds[0] })
  }, [config.auth_database_id, driver, onChange, scope, stableAvailableDbIds])

  const handleModeChange = (nextMode: string) => {
    onChange({ mode: nextMode as DriverCommandBuilderMode })
  }

  const handleCommandChange = (next: string) => {
    onChange({
      command_id: next,
      params: {},
      confirm_dangerous: false,
    })
  }

  const setParamValue = (name: string, value: unknown) => {
    onChange({ params: { ...params, [name]: value } })
  }

  const additionalArgs = useMemo(() => parseLines(config.args_text), [config.args_text])

  const preview = useMemo(() => {
    if (!selectedCommand) {
      return { argv: [] as string[], argv_masked: [] as string[] }
    }

    if (driver === 'cli') {
      const paramsByName = selectedCommand.params_by_name ?? {}
      const args = mode === 'guided' ? buildCliArgsPreview(paramsByName, params) : additionalArgs
      const argv = [commandId, ...args]
      return { argv, argv_masked: maskArgv(argv) }
    }

    const preArgs = buildIbcmdConnectionArgsPreview(driverSchema, config.connection)
    if (mode === 'manual') {
      const argv = [...(selectedCommand.argv ?? []), ...preArgs, ...additionalArgs]
      return { argv, argv_masked: maskArgv(argv) }
    }

    const argvPreview = buildIbcmdArgvPreview(selectedCommand, params, additionalArgs)
    const argv = [
      ...(selectedCommand.argv ?? []),
      ...preArgs,
      ...argvPreview.argv.slice((selectedCommand.argv ?? []).length),
    ]
    return { argv, argv_masked: maskArgv(argv) }
  }, [additionalArgs, commandId, config.connection, driver, driverSchema, mode, params, selectedCommand])

  useEffect(() => {
    if (driver !== 'cli') return
    if (!selectedCommand || !commandId) {
      if (config.resolved_args) {
        onChange({ resolved_args: undefined })
      }
      return
    }

    const paramsByName = selectedCommand.params_by_name ?? {}
    const nextArgs = mode === 'guided' ? buildCliArgsPreview(paramsByName, params) : additionalArgs

    const currentArgs = config.resolved_args ?? []
    if (currentArgs.length === nextArgs.length && currentArgs.every((item, idx) => item === nextArgs[idx])) {
      return
    }
    onChange({ resolved_args: nextArgs })
  }, [additionalArgs, commandId, config.resolved_args, driver, mode, onChange, params, selectedCommand])

  const renderGuidedParams = () => {
    if (!selectedCommand) {
      return null
    }

    const paramsByName = selectedCommand.params_by_name ?? {}
    const entries = sortParams(
      Object.entries(paramsByName)
        .filter(([, schema]) => Boolean(schema))
        .filter(([name]) => driver !== 'ibcmd' || !IBCMD_CONNECTION_PARAM_NAMES.has(name))
        .map(([name, schema]) => ({ name, schema: schema as DriverCommandParamV2 }))
    )

    if (entries.length === 0) {
      return null
    }

    return (
      <Form layout="vertical">
        {entries.map(({ name, schema }) => (
          <ParamField
            key={name}
            name={name}
            schema={schema}
            value={params[name]}
            disabled={readOnly}
            onChange={(next) => setParamValue(name, next)}
          />
        ))}
      </Form>
    )
  }

  const handleDangerousConfirmChange = (checked: boolean) => {
    if (!checked) {
      onChange({ confirm_dangerous: false })
      return
    }
    if (dangerousConfirmPending) return

    setDangerousConfirmPending(true)
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Tabs
        activeKey={mode}
        onChange={handleModeChange}
        items={[
          { key: 'guided', label: 'Guided' },
          { key: 'manual', label: 'Manual' },
        ]}
      />

      {driverCommandsQuery.isLoading && <Spin tip="Loading driver commands\u2026" />}
      {driverCommandsQuery.error && (
        <Alert
          type="warning"
          showIcon
          message="Driver commands unavailable"
          description={driverCommandsQuery.error.message}
        />
      )}

      <Form layout="vertical">
        <Form.Item label="Command" required style={{ marginBottom: 12 }}>
          <Select
            showSearch
            placeholder="Select command"
            disabled={readOnly || driverCommandsQuery.isLoading}
            value={commandId || undefined}
            options={commandOptions}
            optionFilterProp="label"
            onChange={handleCommandChange}
          />
        </Form.Item>
      </Form>

      {shortcutsEnabled && (
        <ShortcutsSection
          enabled={shortcutsEnabled}
          readOnly={readOnly}
          commandsById={commandsById}
          driverSchema={driverSchema}
          selectedCommand={selectedCommand}
          commandId={commandId}
          mode={mode}
          config={config}
          currentCatalogBaseVersion={driverCommandsQuery.data?.base_version ?? ''}
          currentCatalogOverridesVersion={driverCommandsQuery.data?.overrides_version ?? ''}
          onChange={onChange}
        />
      )}

      {selectedCommand && selectedCommand.description && (
        <Text type="secondary">{selectedCommand.description}</Text>
      )}
      {selectedCommand && selectedCommand.source_section && (
        <Text type="secondary">Source: {selectedCommand.source_section}</Text>
      )}

      {mode === 'guided' && renderGuidedParams()}

      <ArgsEditorSection
        driver={driver}
        mode={mode}
        config={config}
        onChange={onChange}
        readOnly={readOnly}
      />

      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Text strong>Driver options</Text>
        <DriverOptionsSection
          driver={driver}
          driverSchema={driverSchema}
          scope={scope}
          selectedCommand={selectedCommand}
          commandId={commandId}
          isStaff={meQuery.data?.is_staff === true}
          databaseOptions={databaseOptions}
          stableAvailableDbIds={stableAvailableDbIds}
          config={config}
          onChange={onChange}
          readOnly={readOnly}
        />
      </Space>

      {commandId && preview.argv_masked.length > 0 && (
        <Alert
          type="info"
          showIcon
          message="Preview"
          description={preview.argv_masked.join('\n')}
        />
      )}

      {risk === 'dangerous' && (
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Text strong>Safety</Text>
          <Alert
            type="warning"
            showIcon
            message="Dangerous command"
            description="This command is marked as dangerous. Review carefully before execution."
          />
        </Space>
      )}

      {risk === 'dangerous' && (
        <Form layout="vertical">
          <Form.Item style={{ marginBottom: 0 }}>
            <Checkbox
              checked={confirmDangerous}
              disabled={readOnly || dangerousConfirmPending}
              onChange={(event) => handleDangerousConfirmChange(event.target.checked)}
            >
              I confirm this dangerous command
            </Checkbox>
          </Form.Item>
        </Form>
      )}

      <Modal
        title="Confirm dangerous command"
        open={dangerousConfirmPending}
        okText="Confirm"
        cancelText="Cancel"
        okButtonProps={{ danger: true }}
        onOk={() => {
          setDangerousConfirmPending(false)
          onChange({ confirm_dangerous: true })
        }}
        onCancel={() => {
          setDangerousConfirmPending(false)
        }}
      >
        <Space direction="vertical" size="small">
          <Text>
            This command is marked as dangerous and may cause irreversible changes. Review the command and its parameters before proceeding.
          </Text>
          {selectedCommand?.description && <Text type="secondary">{selectedCommand.description}</Text>}
          {selectedCommand?.source_section && <Text type="secondary">Source: {selectedCommand.source_section}</Text>}
          <Text type="secondary">Command: {selectedCommand?.label || commandId}</Text>
        </Space>
      </Modal>
    </Space>
  )
}

export default DriverCommandBuilder
