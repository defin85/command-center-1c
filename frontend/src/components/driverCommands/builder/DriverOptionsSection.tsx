import { useState } from 'react'
import { Alert, Collapse, Divider, Form, Input, InputNumber, Select, Space, Switch, Typography } from 'antd'

import type { DriverCommandV2, DriverName } from '../../../api/driverCommands'
import type { CliExtraOptions, DriverCommandOperationConfig } from './types'
import { createDriverOptionFieldRenderer } from './createDriverOptionFieldRenderer'
import { IbcmdConnectionForm } from './IbcmdConnectionForm'
import { IbcmdDerivedConnectionSummary } from './IbcmdDerivedConnectionSummary'
import { getSchemaAtPath, hasIbcmdConnection, isRecord } from './utils'

const { Text } = Typography

export function DriverOptionsSection({
  driver,
  driverSchema,
  scope,
  selectedCommand,
  commandId,
  isStaff,
  databaseOptions,
  stableAvailableDbIds,
  config,
  onChange,
  readOnly,
}: {
  driver: DriverName
  driverSchema: Record<string, unknown> | undefined
  scope: string | undefined
  selectedCommand: DriverCommandV2 | undefined
  commandId: string
  isStaff: boolean
  databaseOptions: Array<{ label: string; value: string }>
  stableAvailableDbIds: string[]
  config: DriverCommandOperationConfig
  onChange: (updates: Partial<DriverCommandOperationConfig>) => void
  readOnly?: boolean
}) {
  const [driverOptionsQuery, setDriverOptionsQuery] = useState('')
  const connectionOverride = config.connection_override === true
  const canOverrideConnection = driver === 'ibcmd' && scope === 'per_database'
  const hideConnectionFields = canOverrideConnection && !connectionOverride

  const { renderDriverOptionField } = createDriverOptionFieldRenderer({
    driver,
    driverSchema,
    scope,
    selectedCommand,
    commandId,
    isStaff,
    databaseOptions,
    config,
    onChange,
    readOnly,
  })

  const renderLegacyIbcmdExecution = () => {
    const connection = config.connection ?? {}
    const timeout = typeof config.timeout_seconds === 'number' ? config.timeout_seconds : 900

    return (
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {scope === 'global' && (
          <Alert
            type="info"
            showIcon
            message="Global scope command"
            description="This command will run once. Selected databases are used only for RBAC and infobase user mapping (auth_database_id)."
          />
        )}

        {scope === 'global' && (
          <Form layout="vertical">
            <Form.Item label="Auth database" required style={{ marginBottom: 12 }}>
              <Select
                showSearch
                disabled={readOnly}
                value={config.auth_database_id}
                options={databaseOptions}
                onChange={(next) => onChange({ auth_database_id: next })}
                optionFilterProp="label"
              />
            </Form.Item>
          </Form>
        )}

        {canOverrideConnection && (
          <Space align="center" wrap>
            <span data-testid="ibcmd-connection-override">
              <Switch
                checked={connectionOverride}
                disabled={readOnly}
                onChange={(checked) => {
                  onChange({
                    connection_override: checked,
                    connection: checked ? (config.connection ?? {}) : undefined,
                  })
                }}
              />
            </span>
            <Text>Override connection for this run</Text>
          </Space>
        )}

        {!hideConnectionFields ? (
          <>
            <Text strong>Connection</Text>
            <IbcmdConnectionForm
              connection={connection}
              readOnly={readOnly}
              onChange={(next) => onChange({ connection: next })}
            />
          </>
        ) : (
          <IbcmdDerivedConnectionSummary selectedDatabaseIds={stableAvailableDbIds} />
        )}

        {scope === 'global' && !hasIbcmdConnection(connection) && (
          <Alert
            type="warning"
            showIcon
            message="Connection required for global scope"
            description="Set remote, pid, or offline connection parameters."
          />
        )}

        <Divider style={{ margin: '12px 0' }} />
        <Form layout="vertical">
          <Form.Item label="Timeout (seconds)" style={{ marginBottom: 12 }}>
            <InputNumber
              min={1}
              max={3600}
              style={{ width: '100%' }}
              disabled={readOnly}
              value={timeout}
              onChange={(value) => onChange({ timeout_seconds: typeof value === 'number' ? value : 900 })}
            />
          </Form.Item>
          <Form.Item label="Stdin (optional)" style={{ marginBottom: 12 }}>
            <Input.TextArea
              rows={4}
              disabled={readOnly}
              value={config.stdin || ''}
              onChange={(event) => onChange({ stdin: event.target.value })}
            />
          </Form.Item>
        </Form>
      </Space>
    )
  }

  const renderLegacyCliOptions = () => {
    const opt = config.cli_options ?? {}
    const update = (updates: Partial<CliExtraOptions>) => {
      onChange({ cli_options: { ...opt, ...updates } })
    }

    return (
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Text strong>Startup options</Text>
        <Space>
          <Switch
            checked={opt.disable_startup_messages !== false}
            disabled={readOnly}
            onChange={(checked) => update({ disable_startup_messages: checked })}
          />
          <Text>Disable startup messages</Text>
        </Space>
        <Space>
          <Switch
            checked={opt.disable_startup_dialogs !== false}
            disabled={readOnly}
            onChange={(checked) => update({ disable_startup_dialogs: checked })}
          />
          <Text>Disable startup dialogs</Text>
        </Space>

        <Divider style={{ margin: '12px 0' }} />
        <Text strong>Logging</Text>
        <Space>
          <Switch
            checked={opt.log_capture === true}
            disabled={readOnly}
            onChange={(checked) => update({ log_capture: checked })}
          />
          <Text>Capture 1C log (/Out)</Text>
        </Space>
        {opt.log_capture && (
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Input
              value={opt.log_path || ''}
              disabled={readOnly}
              placeholder="Log file path (optional, auto if empty)"
              onChange={(event) => update({ log_path: event.target.value })}
            />
            <Space>
              <Switch
                checked={opt.log_no_truncate === true}
                disabled={readOnly}
                onChange={(checked) => update({ log_no_truncate: checked })}
              />
              <Text>Append log (-NoTruncate)</Text>
            </Space>
          </Space>
        )}
      </Space>
    )
  }

  const renderDriverOptions = () => {
    type UiSection = { id: string; title: string; paths: string[]; when?: Record<string, unknown> }

    const parseUiSections = (rawSections: unknown): UiSection[] => {
      if (!Array.isArray(rawSections)) return []
      const out: UiSection[] = []
      for (const raw of rawSections) {
        if (!isRecord(raw)) continue
        const id = typeof raw.id === 'string' ? raw.id : ''
        const title = typeof raw.title === 'string' ? raw.title : ''
        const paths = Array.isArray(raw.paths) ? raw.paths.filter((p): p is string => typeof p === 'string' && p.length > 0) : []
        if (!id || !title || paths.length === 0) continue
        const when = isRecord(raw.when) ? (raw.when as Record<string, unknown>) : undefined
        out.push({ id, title, paths, when })
      }
      return out
    }

    const synthesizeUiSections = (schema: Record<string, unknown>): UiSection[] => {
      if (driver === 'cli') {
        const hasCliOptions = isRecord(schema.cli_options)
        if (!hasCliOptions) return []
        const startupPaths = ['cli_options.disable_startup_messages', 'cli_options.disable_startup_dialogs']
          .filter((path) => Boolean(getSchemaAtPath(schema, path)))
        const loggingPaths = ['cli_options.log_capture', 'cli_options.log_path', 'cli_options.log_no_truncate']
          .filter((path) => Boolean(getSchemaAtPath(schema, path)))
        const out: UiSection[] = []
        if (startupPaths.length > 0) out.push({ id: 'cli.startup', title: 'Startup options', paths: startupPaths })
        if (loggingPaths.length > 0) out.push({ id: 'cli.logging', title: 'Logging', paths: loggingPaths })
        return out
      }

      const hasConnection = isRecord(schema.connection)
      if (!hasConnection) return []

      const authPaths = ['auth_database_id'].filter((path) => Boolean(getSchemaAtPath(schema, path)))
      const connectionPaths: string[] = []
      for (const key of ['remote', 'pid'] as const) {
        const path = `connection.${key}`
        if (getSchemaAtPath(schema, path)) connectionPaths.push(path)
      }
      const offlineSchema = getSchemaAtPath(schema, 'connection.offline')
      const offlineKeys = isRecord(offlineSchema)
        ? Object.keys(offlineSchema)
            .filter((key) => Boolean(getSchemaAtPath(schema, `connection.offline.${key}`)))
            .sort()
        : []
      for (const key of offlineKeys) {
        connectionPaths.push(`connection.offline.${key}`)
      }
      const executionPaths = ['timeout_seconds', 'stdin'].filter((path) => Boolean(getSchemaAtPath(schema, path)))

      const out: UiSection[] = []
      if (authPaths.length > 0) out.push({ id: 'ibcmd.auth', title: 'Auth context', paths: authPaths, when: { command_scope: 'global' } })
      if (connectionPaths.length > 0) out.push({ id: 'ibcmd.connection', title: 'Connection', paths: connectionPaths })
      if (executionPaths.length > 0) out.push({ id: 'ibcmd.execution', title: 'Execution', paths: executionPaths })
      return out
    }

    const ui = isRecord(driverSchema?.ui) ? (driverSchema?.ui as Record<string, unknown>) : undefined
    const version = typeof ui?.version === 'number' ? ui.version : undefined
    const schemaSections = version === 1 ? parseUiSections(ui?.sections) : []
    const sections = schemaSections.length > 0
      ? schemaSections
      : driverSchema
        ? synthesizeUiSections(driverSchema)
        : []

    if (!driverSchema || sections.length === 0) {
      return driver === 'ibcmd' ? renderLegacyIbcmdExecution() : renderLegacyCliOptions()
    }

    const visibleSections: UiSection[] = []
    for (const section of sections) {
      const when = section.when
      if (when && typeof when.command_scope === 'string' && when.command_scope !== scope) continue
      visibleSections.push(section)
    }

    if (visibleSections.length === 0) {
      return null
    }

    const query = driverOptionsQuery.trim().toLowerCase()
    const matchesQuery = (path: string) => {
      if (!query) return true
      const schema = getSchemaAtPath(driverSchema, path)
      const label = typeof schema?.label === 'string' ? schema.label : ''
      const description = typeof schema?.description === 'string' ? schema.description : ''
      const flag = typeof schema?.flag === 'string' ? schema.flag : ''
      const ui = schema?.ui
      const aliases = isRecord(ui) && Array.isArray(ui.aliases)
        ? (ui.aliases as unknown[]).filter((v): v is string => typeof v === 'string' && v.trim().length > 0).map((v) => v.trim())
        : []

      const haystack = [path, label, description, flag, ...aliases].join(' ').toLowerCase()
      return haystack.includes(query)
    }

    const filteredSections: UiSection[] = []
    for (const section of visibleSections) {
      const basePaths = query ? section.paths.filter(matchesQuery) : section.paths
      const nextPaths = hideConnectionFields ? basePaths.filter((p) => !p.startsWith('connection.')) : basePaths
      if (nextPaths.length === 0) continue
      filteredSections.push({ ...section, paths: nextPaths })
    }

    if (filteredSections.length === 0) {
      if (canOverrideConnection) {
        return (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Space align="center" wrap>
              <span data-testid="ibcmd-connection-override">
                <Switch
                  checked={connectionOverride}
                  disabled={readOnly}
                  onChange={(checked) => {
                    onChange({
                      connection_override: checked,
                      connection: checked ? (config.connection ?? {}) : undefined,
                    })
                  }}
                />
              </span>
              <Text>Override connection for this run</Text>
            </Space>

            {hideConnectionFields && (
              <IbcmdDerivedConnectionSummary selectedDatabaseIds={stableAvailableDbIds} />
            )}

            <Alert
              type="info"
              showIcon
              message="No driver options matched"
              description="Clear the search query to show all available driver options."
            />
          </Space>
        )
      }
      return (
        <Alert
          type="info"
          showIcon
          message="No driver options matched"
          description="Clear the search query to show all available driver options."
        />
      )
    }

    const renderSectionFields = (paths: string[]) => {
      const offlinePaths = paths.filter((p) => p.startsWith('connection.offline.'))
      const mainPaths = paths.filter((p) => !p.startsWith('connection.offline.'))
      const offlineDbCore = new Set([
        'connection.offline.dbms',
        'connection.offline.db_server',
        'connection.offline.db_name',
        'connection.offline.db_path',
      ])
      const offlineDbPaths = offlinePaths.filter((p) => offlineDbCore.has(p))
      const offlineOtherPaths = offlinePaths.filter((p) => !offlineDbCore.has(p))
      return (
        <>
          {mainPaths.map((path) => renderDriverOptionField(path))}
          {offlinePaths.length > 0 && (
            <>
              <Divider style={{ margin: '12px 0' }} />
              <Text strong>Offline</Text>
              {driver === 'ibcmd' && (
                <Alert
                  type="info"
                  showIcon
                  style={{ margin: '8px 0 12px' }}
                  message="Offline DB connection"
                  description="DBMS credentials are resolved per database via mapping; some parameters (e.g. db_name) may be resolved per target."
                />
              )}
              {offlineDbPaths.map((path) => renderDriverOptionField(path))}
              {offlineOtherPaths.length > 0 && (
                <Collapse
                  size="small"
                  items={[
                    {
                      key: 'offline-advanced',
                      label: 'Offline: advanced',
                      children: <>{offlineOtherPaths.map((path) => renderDriverOptionField(path))}</>,
                    },
                  ]}
                />
              )}
            </>
          )}
        </>
      )
    }

    return (
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {driver === 'ibcmd' && scope === 'global' && (
          <Alert
            type="info"
            showIcon
            message="Global scope command"
            description="This command will run once. Selected databases are used only for RBAC and infobase user mapping (auth_database_id)."
          />
        )}
        {driver === 'ibcmd' && scope === 'global' && stableAvailableDbIds.length === 0 && (
          <Alert
            type="warning"
            showIcon
            message="Auth context requires selected targets"
            description="Select at least one database target to provide auth_database_id options."
          />
        )}

        {canOverrideConnection && (
          <Space align="center" wrap>
            <span data-testid="ibcmd-connection-override">
              <Switch
                checked={connectionOverride}
                disabled={readOnly}
                onChange={(checked) => {
                  onChange({
                    connection_override: checked,
                    connection: checked ? (config.connection ?? {}) : undefined,
                  })
                }}
              />
            </span>
            <Text>Override connection for this run</Text>
          </Space>
        )}

        {hideConnectionFields && <IbcmdDerivedConnectionSummary selectedDatabaseIds={stableAvailableDbIds} />}

        <Input
          allowClear
          value={driverOptionsQuery}
          onChange={(event) => setDriverOptionsQuery(event.target.value)}
          placeholder={'Search driver options\u2026'}
        />

        {filteredSections.map((section, idx) => (
          <Space key={section.id} direction="vertical" style={{ width: '100%' }} size="small">
            {idx > 0 && <Divider style={{ margin: '12px 0' }} />}
            <Text strong>{section.title}</Text>
            <Form layout="vertical">
              {renderSectionFields(section.paths)}
            </Form>
          </Space>
        ))}

        {driver === 'ibcmd' && scope === 'global' && !hasIbcmdConnection(config.connection) && (
          <Alert
            type="warning"
            showIcon
            message="Connection required for global scope"
            description="Set remote, pid, or offline connection parameters."
          />
        )}

        {driver === 'ibcmd' && scope === 'per_database' && connectionOverride && !hasIbcmdConnection(config.connection) && (
          <Alert
            type="warning"
            showIcon
            message="Connection override is enabled but empty"
            description="Either set remote/pid/offline connection parameters, or disable override to use per-database connection profiles."
          />
        )}
      </Space>
    )
  }

  return renderDriverOptions()
}
