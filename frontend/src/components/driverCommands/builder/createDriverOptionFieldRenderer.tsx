import { Form, Input, InputNumber, Select, Switch } from 'antd'

import type { DriverCommandV2, DriverName } from '../../../api/driverCommands'
import type { CliExtraOptions, DriverCommandOperationConfig, IbcmdCliConnection, IbcmdIbAuth } from './types'
import { getSchemaAtPath, getValueAtPath, isRecord, setObjectPath } from './utils'

export const createDriverOptionFieldRenderer = ({
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
}: {
  driver: DriverName
  driverSchema: Record<string, unknown> | undefined
  scope: string | undefined
  selectedCommand: DriverCommandV2 | undefined
  commandId: string
  isStaff: boolean
  databaseOptions: Array<{ label: string; value: string }>
  config: DriverCommandOperationConfig
  onChange: (updates: Partial<DriverCommandOperationConfig>) => void
  readOnly?: boolean
}) => {
  const getConfigValueAtPath = (path: string): unknown => {
    if (path.startsWith('connection.')) {
      const subPath = path.slice('connection.'.length)
      const connection = (config.connection ?? {}) as Record<string, unknown>
      return getValueAtPath(connection, subPath)
    }
    if (path.startsWith('ib_auth.')) {
      const subPath = path.slice('ib_auth.'.length)
      const ibAuth = (config.ib_auth ?? {}) as Record<string, unknown>
      return getValueAtPath(ibAuth, subPath)
    }
    if (path.startsWith('cli_options.')) {
      const subPath = path.slice('cli_options.'.length)
      const cliOptions = (config.cli_options ?? {}) as Record<string, unknown>
      return getValueAtPath(cliOptions, subPath)
    }
    return (config as unknown as Record<string, unknown>)[path]
  }

  const updateConfigAtPath = (path: string, value: unknown) => {
    if (path.startsWith('connection.')) {
      const subPath = path.slice('connection.'.length)
      const connection = (config.connection ?? {}) as Record<string, unknown>
      onChange({ connection: setObjectPath(connection, subPath, value) as unknown as IbcmdCliConnection })
      return
    }
    if (path.startsWith('ib_auth.')) {
      const subPath = path.slice('ib_auth.'.length)
      const ibAuth = (config.ib_auth ?? {}) as Record<string, unknown>
      onChange({ ib_auth: setObjectPath(ibAuth, subPath, value) as unknown as IbcmdIbAuth })
      return
    }
    if (path.startsWith('cli_options.')) {
      const subPath = path.slice('cli_options.'.length)
      const cliOptions = (config.cli_options ?? {}) as Record<string, unknown>
      onChange({ cli_options: setObjectPath(cliOptions, subPath, value) as unknown as CliExtraOptions })
      return
    }
    onChange({ [path]: value } as Partial<DriverCommandOperationConfig>)
  }

  const isVisibleBySchema = (schema: Record<string, unknown> | undefined): boolean => {
    if (!schema) return true
    const ui = schema.ui
    if (!isRecord(ui)) return true
    const visibleWhen = ui.visible_when
    if (!isRecord(visibleWhen)) return true

    const condPath = typeof visibleWhen.path === 'string' ? visibleWhen.path : ''
    if (!condPath) return true
    const condValue = (visibleWhen as Record<string, unknown>).equals
    return getConfigValueAtPath(condPath) === condValue
  }

  const isRequiredBySchema = (schema: Record<string, unknown> | undefined): boolean => {
    if (!schema) return false
    if (schema.required === true) return true
    const ui = schema.ui
    if (!isRecord(ui)) return false
    const requiredWhen = ui.required_when
    if (!isRecord(requiredWhen)) return false
    const scopeCond = typeof requiredWhen.command_scope === 'string' ? requiredWhen.command_scope : ''
    return scopeCond !== '' && scopeCond === scope
  }

  const renderDriverOptionField = (path: string) => {
    const schema = getSchemaAtPath(driverSchema, path)
    if (!schema) return null
    if (!isVisibleBySchema(schema)) return null

    const ui = schema.ui
    if (isRecord(ui) && ui.hidden === true) {
      return null
    }

    const semantics = isRecord(schema.semantics) ? (schema.semantics as Record<string, unknown>) : undefined
    const credentialKind = typeof semantics?.credential_kind === 'string' ? semantics.credential_kind : ''
    if (
      driver === 'ibcmd' &&
      (credentialKind === 'db_user' ||
        credentialKind === 'db_password' ||
        credentialKind === 'ib_user' ||
        credentialKind === 'ib_password')
    ) {
      // Credentials are resolved at runtime via mappings; do not expose raw secrets in UI.
      return null
    }

    const label = (typeof schema.label === 'string' ? schema.label : path.split('.').slice(-1)[0]).trim()
    const description = typeof schema.description === 'string' ? schema.description : undefined
    const required = isRequiredBySchema(schema)
    const kind = typeof schema.kind === 'string' ? schema.kind : ''
    const valueType = typeof schema.value_type === 'string' ? schema.value_type : ''
    const sensitive = schema.sensitive === true

    const rawValue = getConfigValueAtPath(path)
    const hasDefault = schema.default !== undefined
    const isEmpty = rawValue === null || rawValue === undefined || rawValue === ''
    const missingRequired = required && !hasDefault && isEmpty

    const helpParts: string[] = []
    if (description) helpParts.push(description)
    const aliases =
      isRecord(ui) && Array.isArray(ui.aliases)
        ? (ui.aliases as unknown[])
            .filter((v): v is string => typeof v === 'string' && v.trim().length > 0)
            .map((v) => v.trim())
        : []
    if (aliases.length > 0) helpParts.push(`Aliases: ${aliases.join(' ')}`)
    if (missingRequired) helpParts.push('Required.')

    if (driver === 'ibcmd' && path === 'ib_auth.strategy') {
      const allowedServiceCommands = new Set(['infobase.extension.list', 'infobase.extension.info'])
      const canShow = Boolean(selectedCommand) && selectedCommand?.risk_level === 'safe' && allowedServiceCommands.has(commandId)
      if (!canShow) return null

      const canUseService = isStaff
      const options = [
        { value: 'actor', label: 'actor (per-user mapping)' },
        ...(canUseService ? [{ value: 'service', label: 'service (service account)' }] : []),
        { value: 'none', label: 'none (no IB auth)' },
      ]
      const rawValue = getConfigValueAtPath(path)
      const value = rawValue === 'actor' || rawValue === 'service' || rawValue === 'none' ? rawValue : 'actor'

      return (
        <Form.Item
          key={path}
          label={label}
          style={{ marginBottom: 12 }}
          help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
        >
          <Select
            disabled={readOnly}
            value={value}
            options={options}
            onChange={(next) => updateConfigAtPath(path, next)}
          />
        </Form.Item>
      )
    }

    if (driver === 'ibcmd' && path === 'dbms_auth.strategy') {
      const allowedServiceCommands = new Set(['infobase.extension.list', 'infobase.extension.info'])
      const canShow = Boolean(selectedCommand) && selectedCommand?.risk_level === 'safe' && allowedServiceCommands.has(commandId)
      if (!canShow) return null

      const canUseService = isStaff
      const options = [
        { value: 'actor', label: 'actor (per-user mapping)' },
        ...(canUseService ? [{ value: 'service', label: 'service (service account)' }] : []),
      ]
      const rawValue = getConfigValueAtPath(path)
      const value = rawValue === 'actor' || rawValue === 'service' ? rawValue : 'actor'

      return (
        <Form.Item
          key={path}
          label={label}
          style={{ marginBottom: 12 }}
          help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
        >
          <Select
            disabled={readOnly}
            value={value}
            options={options}
            onChange={(next) => updateConfigAtPath(path, next)}
          />
        </Form.Item>
      )
    }

    if (kind === 'database_ref') {
      if (databaseOptions.length === 0) {
        helpParts.push('Select at least one target database to provide options.')
      }
      return (
        <Form.Item
          key={path}
          label={label}
          required={required}
          validateStatus={missingRequired ? 'error' : undefined}
          style={{ marginBottom: 12 }}
          help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
        >
          <Select
            showSearch
            disabled={readOnly || databaseOptions.length === 0}
            value={typeof rawValue === 'string' ? rawValue : undefined}
            options={databaseOptions}
            onChange={(next) => updateConfigAtPath(path, next)}
            optionFilterProp="label"
          />
        </Form.Item>
      )
    }

    const asBool = (fallback: boolean): boolean => (typeof rawValue === 'boolean' ? rawValue : fallback)
    const asNumber = (fallback?: number): number | undefined => (typeof rawValue === 'number' ? rawValue : fallback)
    const asString = (): string => (typeof rawValue === 'string' ? rawValue : '')

    const expectsValue = schema.expects_value === true
    const defaultValue = schema.default
    const min = typeof schema.min === 'number' ? schema.min : undefined
    const max = typeof schema.max === 'number' ? schema.max : undefined

    if (kind === 'bool' || (kind === 'flag' && !expectsValue)) {
      const fallback = typeof defaultValue === 'boolean' ? defaultValue : false
      return (
        <Form.Item
          key={path}
          label={label}
          style={{ marginBottom: 12 }}
          help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
          required={required}
          validateStatus={missingRequired ? 'error' : undefined}
        >
          <Switch checked={asBool(fallback)} disabled={readOnly} onChange={(checked) => updateConfigAtPath(path, checked)} />
        </Form.Item>
      )
    }

    if (kind === 'int' || kind === 'float' || (kind === 'flag' && valueType === 'int')) {
      const fallback = typeof defaultValue === 'number' ? defaultValue : undefined
      const emptyValue = typeof defaultValue === 'number' ? defaultValue : null
      return (
        <Form.Item
          key={path}
          label={label}
          style={{ marginBottom: 12 }}
          help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
          required={required}
          validateStatus={missingRequired ? 'error' : undefined}
        >
          <InputNumber
            min={min}
            max={max}
            style={{ width: '100%' }}
            disabled={readOnly}
            value={asNumber(fallback)}
            onChange={(next) => updateConfigAtPath(path, typeof next === 'number' ? next : emptyValue)}
          />
        </Form.Item>
      )
    }

    if (kind === 'text') {
      const ui = schema.ui
      const rows = isRecord(ui) && typeof ui.rows === 'number' ? ui.rows : 4
      return (
        <Form.Item
          key={path}
          label={label}
          style={{ marginBottom: 12 }}
          help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
          required={required}
          validateStatus={missingRequired ? 'error' : undefined}
        >
          <Input.TextArea
            rows={rows}
            disabled={readOnly}
            value={asString()}
            onChange={(event) => updateConfigAtPath(path, event.target.value)}
          />
        </Form.Item>
      )
    }

    if (sensitive) {
      return (
        <Form.Item
          key={path}
          label={label}
          style={{ marginBottom: 12 }}
          help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
          required={required}
          validateStatus={missingRequired ? 'error' : undefined}
        >
          <Input.Password
            disabled={readOnly}
            value={asString()}
            placeholder={typeof schema.flag === 'string' ? schema.flag : undefined}
            onChange={(event) => updateConfigAtPath(path, event.target.value)}
          />
        </Form.Item>
      )
    }

    return (
      <Form.Item
        key={path}
        label={label}
        style={{ marginBottom: 12 }}
        help={helpParts.length > 0 ? helpParts.join(' ') : undefined}
        required={required}
        validateStatus={missingRequired ? 'error' : undefined}
      >
        <Input
          disabled={readOnly}
          value={asString()}
          placeholder={typeof schema.flag === 'string' ? schema.flag : undefined}
          onChange={(event) => updateConfigAtPath(path, event.target.value)}
        />
      </Form.Item>
    )
  }

  return { renderDriverOptionField }
}
