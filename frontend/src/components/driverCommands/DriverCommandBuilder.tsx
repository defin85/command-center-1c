import '../../lib/monacoEnv'

import { useEffect, useMemo, useState } from 'react'
import { Alert, App, Button, Checkbox, Divider, Form, Input, InputNumber, Modal, Radio, Select, Space, Spin, Switch, Tabs, Typography } from 'antd'
import Editor from '@monaco-editor/react'
import type * as Monaco from 'monaco-editor'

import { maskArgv } from '../../lib/masking'
import {
  useDriverCommands,
  useMe,
  useArtifacts,
  useArtifactAliases,
  useArtifactVersions,
  useDriverCommandShortcuts,
  useCreateDriverCommandShortcut,
  useDeleteDriverCommandShortcut,
} from '../../api/queries'
import type {
  DriverCommandParamV2,
  DriverCommandV2,
  DriverName,
  DriverCommandScope,
  DriverCommandRiskLevel,
} from '../../api/driverCommands'
import type { ArtifactKind } from '../../api/artifacts'
import type { DriverCommandShortcut } from '../../api/commandShortcuts'

const { Text } = Typography

export type DriverCommandBuilderMode = 'guided' | 'manual'

export interface IbcmdCliConnectionOffline {
  config?: string
  data?: string
  dbms?: string
  db_server?: string
  db_name?: string
  db_path?: string
  db_user?: string
  db_pwd?: string
  ftext2_data?: string
  ftext_data?: string
  lock?: string
  log_data?: string
  openid_data?: string
  session_data?: string
  stt_data?: string
  system?: string
  temp?: string
  users_data?: string
}

export interface IbcmdCliConnection {
  remote?: string
  pid?: number | null
  offline?: IbcmdCliConnectionOffline
}

export interface IbcmdIbAuth {
  strategy?: 'actor' | 'service' | 'none'
}

export interface CliExtraOptions {
  disable_startup_messages?: boolean
  disable_startup_dialogs?: boolean
  log_capture?: boolean
  log_path?: string
  log_no_truncate?: boolean
}

export interface DriverCommandOperationConfig {
  driver: DriverName
  mode?: DriverCommandBuilderMode
  command_id?: string
  command_label?: string
  command_scope?: DriverCommandScope
  command_risk_level?: DriverCommandRiskLevel
  params?: Record<string, unknown>
  args_text?: string
  /** Precomputed args list for CLI execution/template payloads */
  resolved_args?: string[]
  confirm_dangerous?: boolean

  // IBCMD-only execution context
  connection?: IbcmdCliConnection
  ib_auth?: IbcmdIbAuth
  stdin?: string
  timeout_seconds?: number
  auth_database_id?: string

  // CLI-only options
  cli_options?: CliExtraOptions
}

const ARTIFACT_PREFIX = 'artifact://'

const EMPTY_COMMANDS_BY_ID: Record<string, DriverCommandV2> = {}
const EMPTY_SHORTCUT_ITEMS: DriverCommandShortcut[] = []
const EMPTY_PARAMS: Record<string, unknown> = {}
const EMPTY_DB_IDS: string[] = []

type MonacoInstance = typeof import('monaco-editor')

const ARGV_LANGUAGE_ID = 'argv-lines'
const ARGV_MARKER_OWNER = 'driver-command-args'

let argvLanguageRegistered = false

const IBCMD_CONNECTION_PARAM_NAMES = new Set([
  'remote',
  'pid',
  'config',
  'data',
  'dbms',
  'db_server',
  'db_name',
  'db_path',
  'db_user',
  'db_pwd',
  'ftext2_data',
  'ftext_data',
  'lock',
  'log_data',
  'openid_data',
  'session_data',
  'stt_data',
  'system',
  'temp',
  'users_data',
])

const ensureArgvLanguage = (monaco: MonacoInstance) => {
  if (argvLanguageRegistered) return
  argvLanguageRegistered = true

  const exists = monaco.languages.getLanguages().some((lang) => lang.id === ARGV_LANGUAGE_ID)
  if (!exists) {
    monaco.languages.register({ id: ARGV_LANGUAGE_ID })
  }

  monaco.languages.setMonarchTokensProvider(ARGV_LANGUAGE_ID, {
    tokenizer: {
      root: [
        [/artifact:\/\/\S+/, 'string'],
        [/--?[a-zA-Z0-9][a-zA-Z0-9_-]*(?:=.*)?/, 'keyword'],
        [/\d+/, 'number'],
        [/\S+/, 'identifier'],
      ],
    },
  })
}

const normalizeText = (value: unknown): string => {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === 'string')
      .join('\n')
  }
  return ''
}

const parseLines = (value: string | undefined): string[] => {
  if (!value) return []
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

const getValueAtPath = (root: unknown, path: string): unknown => {
  const parts = path.split('.').filter(Boolean)
  let node: unknown = root
  for (const part of parts) {
    if (!isRecord(node)) return undefined
    node = node[part]
  }
  return node
}

const getSchemaAtPath = (driverSchema: Record<string, unknown> | undefined, path: string): Record<string, unknown> | undefined => {
  if (!driverSchema) return undefined
  const parts = path.split('.').filter(Boolean)
  let node: unknown = driverSchema
  for (const part of parts) {
    if (!isRecord(node)) return undefined
    node = node[part]
  }
  return isRecord(node) ? node : undefined
}

const setObjectPath = (root: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> => {
  const parts = path.split('.').filter(Boolean)
  if (parts.length === 0) return root

  const nextRoot: Record<string, unknown> = { ...root }
  let cursor: Record<string, unknown> = nextRoot
  for (let idx = 0; idx < parts.length - 1; idx += 1) {
    const key = parts[idx]
    const current = cursor[key]
    const next = isRecord(current) ? { ...current } : {}
    cursor[key] = next
    cursor = next
  }
  const lastKey = parts[parts.length - 1]
  cursor[lastKey] = value
  return nextRoot
}

const detectIbcmdPidInArgs = (value: string | undefined): number[] => {
  if (!value) return []
  const badLines: number[] = []
  const lines = value.split('\n')
  for (let idx = 0; idx < lines.length; idx += 1) {
    const token = lines[idx].trim().toLowerCase()
    if (!token) continue
    if (token === '--pid' || token.startsWith('--pid=')) {
      badLines.push(idx + 1)
    }
  }
  return badLines
}

const buildArgsMarkers = (
  monaco: MonacoInstance,
  driver: DriverName,
  value: string | undefined,
): Monaco.editor.IMarkerData[] => {
  if (!value) return []

  if (driver === 'ibcmd') {
    const markers: Monaco.editor.IMarkerData[] = []
    const lines = value.split('\n')
    for (let idx = 0; idx < lines.length; idx += 1) {
      const raw = lines[idx]
      const token = raw.trim()
      const lowered = token.toLowerCase()
      if (!lowered) continue

      if (lowered === '--pid' || lowered.startsWith('--pid=')) {
        markers.push({
          severity: monaco.MarkerSeverity.Error,
          message: '--pid is not allowed here; set PID via Connection form.',
          startLineNumber: idx + 1,
          endLineNumber: idx + 1,
          startColumn: 1,
          endColumn: Math.max(raw.length, 1) + 1,
        })
      }
    }
    return markers
  }

  return []
}

const parseArtifactKey = (value: string | boolean | number | undefined): string | undefined => {
  if (typeof value !== 'string') {
    return undefined
  }
  if (!value.startsWith(ARTIFACT_PREFIX)) {
    return undefined
  }
  const key = value.slice(ARTIFACT_PREFIX.length).replace(/^\/+/, '')
  return key || undefined
}

const parseArtifactIdFromKey = (key?: string): string | undefined => {
  if (!key) {
    return undefined
  }
  const parts = key.split('/')
  if (parts.length >= 2 && parts[0] === 'artifacts') {
    return parts[1]
  }
  return undefined
}

const safeString = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

const buildCliArgsPreview = (paramsByName: Record<string, DriverCommandParamV2>, values: Record<string, unknown>) => {
  const flags: string[] = []
  const positionals: Array<{ position: number; value: string }> = []

  const normalizeValues = (raw: unknown): string[] => {
    if (raw === null || raw === undefined) return []
    if (Array.isArray(raw)) {
      return raw
        .map((item) => safeString(item).trim())
        .filter((item) => item.length > 0)
    }
    const v = safeString(raw).trim()
    return v ? [v] : []
  }

  for (const [name, schema] of Object.entries(paramsByName)) {
    if (!schema || schema.disabled) continue

    const rawValue = values[name]
    if (schema.kind === 'positional') {
      const pos = typeof schema.position === 'number' ? schema.position : 999
      for (const value of normalizeValues(rawValue)) {
        positionals.push({ position: pos, value })
      }
      continue
    }

    const flag = typeof schema.flag === 'string' && schema.flag ? schema.flag : `-${name}`
    if (!schema.expects_value) {
      if (rawValue === true) {
        flags.push(flag)
      }
      continue
    }

    const normalizedValues = normalizeValues(rawValue)
    if (normalizedValues.length === 0) continue

    if (schema.repeatable) {
      for (const value of normalizedValues) {
        flags.push(flag)
        flags.push(value)
      }
      continue
    }

    flags.push(flag)
    flags.push(normalizedValues[0])
  }

  positionals.sort((a, b) => a.position - b.position)
  return [...flags, ...positionals.map((item) => item.value)]
}

const stringifyIbcmdValue = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

const buildIbcmdArgvPreview = (
  command: DriverCommandV2,
  params: Record<string, unknown>,
  additionalArgs: string[],
) => {
  const paramsByName = command.params_by_name ?? {}
  const flags: string[] = []
  const positionals: Array<{ position: number; value: string }> = []

  const normalizeValues = (raw: unknown): string[] => {
    if (raw === null || raw === undefined) return []
    if (Array.isArray(raw)) {
      return raw
        .map((item) => stringifyIbcmdValue(item).trim())
        .filter((item) => item.length > 0)
    }
    const v = stringifyIbcmdValue(raw).trim()
    return v ? [v] : []
  }

  for (const [name, schema] of Object.entries(paramsByName)) {
    if (!schema || schema.disabled) continue
    if (!(name in params)) continue

    const rawValue = params[name]
    if (rawValue === null || rawValue === undefined || rawValue === '') continue

    if (schema.kind === 'positional') {
      const pos = typeof schema.position === 'number' ? schema.position : 999
      for (const value of normalizeValues(rawValue)) {
        positionals.push({ position: pos, value })
      }
      continue
    }

    const flag = typeof schema.flag === 'string' ? schema.flag : ''
    if (!flag) continue

    if (!schema.expects_value) {
      if (rawValue === true) {
        flags.push(flag)
      }
      continue
    }

    for (const value of normalizeValues(rawValue)) {
      flags.push(`${flag}=${value}`)
    }
  }

  positionals.sort((a, b) => a.position - b.position)
  flags.sort()
  const argv = [...(command.argv ?? []), ...flags, ...positionals.map((item) => item.value), ...additionalArgs]
  return {
    argv,
    argv_masked: maskArgv(argv),
  }
}

const flattenIbcmdConnection = (connection?: IbcmdCliConnection): Record<string, unknown> => {
  if (!connection) return {}

  const out: Record<string, unknown> = {}
  if (typeof connection.remote === 'string' && connection.remote.trim().length > 0) {
    out.remote = connection.remote.trim()
  }
  if (typeof connection.pid === 'number') {
    out.pid = connection.pid
  }

  const offline = connection.offline
  if (offline && typeof offline === 'object') {
    for (const [key, raw] of Object.entries(offline as Record<string, unknown>)) {
      if (typeof raw === 'string') {
        const value = raw.trim()
        if (value) out[key] = value
        continue
      }
      if (raw === true) {
        out[key] = true
      }
    }
  }

  return out
}

const IBCMD_CONNECTION_DEFAULT_FLAGS: Record<string, string> = {
  remote: '--remote',
  pid: '--pid',
  config: '--config',
  data: '--data',
  dbms: '--dbms',
  db_server: '--db-server',
  db_name: '--db-name',
  db_path: '--db-path',
  db_user: '--db-user',
  db_pwd: '--db-pwd',
  ftext2_data: '--ftext2-data',
  ftext_data: '--ftext-data',
  lock: '--lock',
  log_data: '--log-data',
  openid_data: '--openid-data',
  session_data: '--session-data',
  stt_data: '--stt-data',
  system: '--system',
  temp: '--temp',
  users_data: '--users-data',
}

const buildIbcmdConnectionArgsPreview = (
  driverSchema: Record<string, unknown> | undefined,
  connection: IbcmdCliConnection | undefined,
): string[] => {
  const flattened = flattenIbcmdConnection(connection)
  if (Object.keys(flattened).length === 0) return []

  const renderFlag = (path: string, key: string, value: unknown): string | undefined => {
    if (value === null || value === undefined || value === '') return undefined

    const schema = getSchemaAtPath(driverSchema, path)
    const kind = typeof schema?.kind === 'string' ? schema.kind : ''
    const expectsValue = schema?.expects_value === true
    const schemaFlag = typeof schema?.flag === 'string' && schema.flag.startsWith('-') ? schema.flag : undefined

    const fallbackFlag = IBCMD_CONNECTION_DEFAULT_FLAGS[key]
    const flag = schemaFlag ?? fallbackFlag
    if (!flag) return undefined

    if (kind === 'flag' && !expectsValue) {
      return value === true ? flag : undefined
    }

    const rendered = typeof value === 'number' || typeof value === 'boolean' ? String(value) : String(value).trim()
    if (!rendered) return undefined
    return `${flag}=${rendered}`
  }

  const args: string[] = []

  for (const key of ['remote', 'pid'] as const) {
    if (!(key in flattened)) continue
    const token = renderFlag(`connection.${key}`, key, flattened[key])
    if (token) args.push(token)
  }

  const offlineKeys = Object.keys(flattened)
    .filter((key) => key !== 'remote' && key !== 'pid')
    .sort()

  for (const key of offlineKeys) {
    const token = renderFlag(`connection.offline.${key}`, key, flattened[key])
    if (token) args.push(token)
  }

  return args
}

const sortParams = (entries: Array<{ name: string; schema: DriverCommandParamV2 }>) =>
  entries.sort((a, b) => {
    const ak = a.schema.kind
    const bk = b.schema.kind
    if (ak !== bk) {
      return ak === 'positional' ? -1 : 1
    }
    if (ak === 'positional') {
      const ap = typeof a.schema.position === 'number' ? a.schema.position : 999
      const bp = typeof b.schema.position === 'number' ? b.schema.position : 999
      if (ap !== bp) return ap - bp
    }
    const af = typeof a.schema.flag === 'string' ? a.schema.flag : a.name
    const bf = typeof b.schema.flag === 'string' ? b.schema.flag : b.name
    return af.localeCompare(bf)
  })

const detectCommandGroup = (commandId: string) => {
  const parts = commandId.split('.').filter(Boolean)
  return parts.length > 0 ? parts[0] : 'general'
}

const buildCommandOptions = (commandsById: Record<string, DriverCommandV2>) => {
  const groups = new Map<string, Array<{ label: string; value: string }>>()
  for (const [id, cmd] of Object.entries(commandsById)) {
    if (!cmd || cmd.disabled) continue
    const group = detectCommandGroup(id)
    const list = groups.get(group) ?? []
    list.push({ value: id, label: cmd.label || id })
    groups.set(group, list)
  }

  return Array.from(groups.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([group, list]) => ({
      label: group,
      options: list.sort((a, b) => a.label.localeCompare(b.label)),
    }))
}

const hasIbcmdConnection = (connection?: IbcmdCliConnection) => {
  const flat = flattenIbcmdConnection(connection)
  return Object.keys(flat).length > 0
}

function ArtifactValueField({
  label,
  value,
  required,
  artifactKinds,
  disabled,
  onChange,
}: {
  label: string
  value: string | undefined
  required?: boolean
  artifactKinds: ArtifactKind[]
  disabled?: boolean
  onChange: (next: string) => void
}) {
  const artifactKey = parseArtifactKey(value)
  const [source, setSource] = useState<'artifact' | 'path'>(artifactKey ? 'artifact' : 'path')
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | undefined>(
    parseArtifactIdFromKey(artifactKey)
  )

  useEffect(() => {
    setSource(artifactKey ? 'artifact' : 'path')
    if (artifactKey) {
      setSelectedArtifactId((current) => current || parseArtifactIdFromKey(artifactKey))
    }
  }, [artifactKey])

  const artifactsQuery = useArtifacts(
    { kind: artifactKinds.length === 1 ? artifactKinds[0] : undefined },
    { enabled: source === 'artifact' }
  )
  const versionsQuery = useArtifactVersions(selectedArtifactId)
  const aliasesQuery = useArtifactAliases(selectedArtifactId)

  const artifacts = useMemo(() => {
    const list = artifactsQuery.data?.artifacts ?? []
    if (artifactKinds.length <= 1) {
      return list
    }
    return list.filter((artifact) => artifactKinds.includes(artifact.kind))
  }, [artifactKinds, artifactsQuery.data])

  const artifactOptions = useMemo(
    () =>
      artifacts.map((artifact) => ({
        label: `${artifact.name} (${artifact.kind})`,
        value: artifact.id,
      })),
    [artifacts]
  )

  const aliasByVersion = useMemo(() => {
    const map = new Map<string, string>()
    for (const alias of aliasesQuery.data?.aliases ?? []) {
      map.set(alias.version_id, alias.alias)
    }
    return map
  }, [aliasesQuery.data])

  const versionOptions = useMemo(
    () =>
      (versionsQuery.data?.versions ?? []).map((version) => {
        const alias = aliasByVersion.get(version.id)
        const versionLabel = alias
          ? `${alias} (${version.version}) • ${version.filename}`
          : `${version.version} • ${version.filename}`
        return {
          label: versionLabel,
          value: version.storage_key,
        }
      }),
    [aliasByVersion, versionsQuery.data]
  )

  const handleSourceChange = (next: 'artifact' | 'path') => {
    setSource(next)
    onChange('')
  }

  const handleArtifactChange = (nextArtifactId?: string) => {
    setSelectedArtifactId(nextArtifactId)
    onChange('')
  }

  const handleArtifactVersionChange = (storageKey?: string) => {
    if (!storageKey) {
      onChange('')
      return
    }
    onChange(`${ARTIFACT_PREFIX}${storageKey}`)
  }

  return (
    <Form.Item label={label} required={required} style={{ marginBottom: 12 }}>
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Radio.Group
          value={source}
          disabled={disabled}
          onChange={(event) => handleSourceChange(event.target.value)}
        >
          <Radio.Button value="artifact">Artifact</Radio.Button>
          <Radio.Button value="path">Path</Radio.Button>
        </Radio.Group>

        {source === 'path' && (
          <Input
            value={value || ''}
            disabled={disabled}
            placeholder="/path/to/file"
            onChange={(event) => onChange(event.target.value)}
          />
        )}

        {source === 'artifact' && (
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {artifactsQuery.error && (
              <Alert
                type="warning"
                showIcon
                message="Artifact list unavailable"
                description={artifactsQuery.error.message}
              />
            )}
            <Select
              showSearch
              placeholder="Select artifact"
              disabled={disabled || artifactsQuery.isLoading}
              value={selectedArtifactId}
              options={artifactOptions}
              optionFilterProp="label"
              onChange={handleArtifactChange}
              notFoundContent={artifactsQuery.isLoading ? <Spin size="small" /> : null}
            />
            <Select
              showSearch
              placeholder="Select version"
              disabled={disabled || versionsQuery.isLoading || !selectedArtifactId}
              value={parseArtifactKey(value)}
              options={versionOptions}
              optionFilterProp="label"
              onChange={handleArtifactVersionChange}
              notFoundContent={versionsQuery.isLoading ? <Spin size="small" /> : null}
            />
          </Space>
        )}
      </Space>
    </Form.Item>
  )
}

function ParamField({
  name,
  schema,
  value,
  disabled,
  onChange,
}: {
  name: string
  schema: DriverCommandParamV2
  value: unknown
  disabled?: boolean
  onChange: (next: unknown) => void
}) {
  const label = (schema.label || name).trim()
  const description = typeof schema.description === 'string' ? schema.description : undefined
  const isRequired = schema.required === true

  const artifactKinds = useMemo(() => {
    const artifact = schema.artifact as { kinds?: unknown } | undefined
    const rawKinds = artifact?.kinds
    if (!Array.isArray(rawKinds)) return []
    return rawKinds.filter((item): item is ArtifactKind => typeof item === 'string' && item.length > 0)
  }, [schema.artifact])

  if (artifactKinds.length > 0) {
    return (
      <ArtifactValueField
        label={label}
        value={typeof value === 'string' ? value : ''}
        required={isRequired}
        disabled={disabled}
        artifactKinds={artifactKinds}
        onChange={(next) => onChange(next)}
      />
    )
  }

  if (schema.kind === 'flag' && !schema.expects_value) {
    return (
      <Form.Item
        label={label}
        style={{ marginBottom: 12 }}
        help={description}
      >
        <Switch checked={value === true} disabled={disabled} onChange={(checked) => onChange(checked)} />
      </Form.Item>
    )
  }

  if (schema.enum && Array.isArray(schema.enum) && schema.enum.length > 0) {
    const options = schema.enum.map((item) => ({ value: item, label: item }))
    const mode = schema.repeatable ? 'multiple' : undefined
    return (
      <Form.Item
        label={label}
        required={isRequired}
        style={{ marginBottom: 12 }}
        help={description}
      >
        <Select
          showSearch
          allowClear
          mode={mode as 'multiple' | undefined}
          disabled={disabled}
          value={schema.repeatable ? (Array.isArray(value) ? value : undefined) : safeString(value) || undefined}
          options={options}
          onChange={(next) => onChange(next)}
          optionFilterProp="value"
        />
      </Form.Item>
    )
  }

  if (schema.repeatable && schema.expects_value) {
    return (
      <Form.Item
        label={label}
        required={isRequired}
        style={{ marginBottom: 12 }}
        help={description || 'One value per line'}
      >
        <Input.TextArea
          rows={4}
          disabled={disabled}
          value={normalizeText(value)}
          onChange={(event) => onChange(parseLines(event.target.value))}
        />
      </Form.Item>
    )
  }

  if (schema.value_type === 'int' || schema.value_type === 'float') {
    const numericValue = typeof value === 'number' ? value : undefined
    return (
      <Form.Item
        label={label}
        required={isRequired}
        style={{ marginBottom: 12 }}
        help={description}
      >
        <InputNumber
          style={{ width: '100%' }}
          disabled={disabled}
          value={numericValue}
          onChange={(next) => onChange(typeof next === 'number' ? next : undefined)}
        />
      </Form.Item>
    )
  }

  return (
    <Form.Item
      label={label}
      required={isRequired}
      style={{ marginBottom: 12 }}
      help={description}
    >
      <Input
        disabled={disabled}
        value={safeString(value)}
        placeholder={schema.kind === 'flag' ? schema.flag : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </Form.Item>
  )
}

function IbcmdConnectionForm({
  connection,
  onChange,
  readOnly,
}: {
  connection: IbcmdCliConnection
  onChange: (next: IbcmdCliConnection) => void
  readOnly?: boolean
}) {
  const offline = connection.offline ?? {}

  const update = (updates: Partial<IbcmdCliConnection>) => {
    onChange({ ...connection, ...updates })
  }

  const updateOffline = (updates: Partial<IbcmdCliConnectionOffline>) => {
    update({ offline: { ...offline, ...updates } })
  }

  return (
    <Form layout="vertical">
      <Form.Item label="Remote (optional)" style={{ marginBottom: 12 }}>
        <Input
          value={connection.remote || ''}
          disabled={readOnly}
          placeholder="http://host:port"
          onChange={(event) => update({ remote: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="PID (optional)" style={{ marginBottom: 12 }}>
        <InputNumber
          style={{ width: '100%' }}
          value={typeof connection.pid === 'number' ? connection.pid : undefined}
          disabled={readOnly}
          onChange={(value) => update({ pid: typeof value === 'number' ? value : null })}
        />
      </Form.Item>

      <Divider style={{ margin: '8px 0 16px' }} />
      <Text strong>Offline (optional)</Text>

      <Form.Item label="Config path" style={{ marginBottom: 12 }}>
        <Input
          value={offline.config || ''}
          disabled={readOnly}
          placeholder="/path/to/config"
          onChange={(event) => updateOffline({ config: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="Data path" style={{ marginBottom: 12 }}>
        <Input
          value={offline.data || ''}
          disabled={readOnly}
          placeholder="/path/to/data"
          onChange={(event) => updateOffline({ data: event.target.value })}
        />
      </Form.Item>

      <Form.Item label="DBMS" style={{ marginBottom: 12 }}>
        <Input
          value={offline.dbms || ''}
          disabled={readOnly}
          placeholder="PostgreSQL"
          onChange={(event) => updateOffline({ dbms: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB server" style={{ marginBottom: 12 }}>
        <Input
          value={offline.db_server || ''}
          disabled={readOnly}
          placeholder="db-host:5432"
          onChange={(event) => updateOffline({ db_server: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB name" style={{ marginBottom: 12 }}>
        <Input
          value={offline.db_name || ''}
          disabled={readOnly}
          placeholder="infobase_db"
          onChange={(event) => updateOffline({ db_name: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB user" style={{ marginBottom: 12 }}>
        <Input
          value={offline.db_user || ''}
          disabled={readOnly}
          placeholder="dbuser"
          onChange={(event) => updateOffline({ db_user: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB password" style={{ marginBottom: 12 }}>
        <Input.Password
          value={offline.db_pwd || ''}
          disabled={readOnly}
          placeholder="db password"
          onChange={(event) => updateOffline({ db_pwd: event.target.value })}
        />
      </Form.Item>
    </Form>
  )
}

function buildEditorOptions(readOnly?: boolean): Monaco.editor.IStandaloneEditorConstructionOptions {
  return {
    readOnly,
    domReadOnly: readOnly,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    tabSize: 2,
    insertSpaces: true,
    automaticLayout: true,
    lineNumbers: 'on',
    renderWhitespace: 'selection',
    fontSize: 13,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  }
}

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
  const { modal } = App.useApp()
  const driverCommandsQuery = useDriverCommands(driver, true)
  const catalog = driverCommandsQuery.data?.catalog
  const commandsById = useMemo(() => catalog?.commands_by_id ?? EMPTY_COMMANDS_BY_ID, [catalog?.commands_by_id])
  const driverSchema = useMemo(
    () => (isRecord(catalog?.driver_schema) ? (catalog?.driver_schema as Record<string, unknown>) : undefined),
    [catalog?.driver_schema]
  )

  const shortcutsEnabled = driver === 'ibcmd'
  const shortcutsQuery = useDriverCommandShortcuts('ibcmd', shortcutsEnabled)
  const createShortcutMutation = useCreateDriverCommandShortcut('ibcmd')
  const deleteShortcutMutation = useDeleteDriverCommandShortcut('ibcmd')
  const meQuery = useMe()

  const mode: DriverCommandBuilderMode = config.mode ?? 'guided'
  const commandId = (config.command_id || '').trim()
  const params = useMemo(() => (config.params ?? EMPTY_PARAMS) as Record<string, unknown>, [config.params])
  const confirmDangerous = config.confirm_dangerous === true
  const [dangerousConfirmPending, setDangerousConfirmPending] = useState(false)
  const [driverOptionsQuery, setDriverOptionsQuery] = useState('')
  const pidInArgsLines = useMemo(() => (driver === 'ibcmd' ? detectIbcmdPidInArgs(config.args_text) : []), [config.args_text, driver])

  const commandOptions = useMemo(() => buildCommandOptions(commandsById), [commandsById])
  const selectedCommand: DriverCommandV2 | undefined = commandId ? commandsById[commandId] : undefined

  const shortcutItems = shortcutsQuery.data?.items ?? EMPTY_SHORTCUT_ITEMS
  const shortcutsById = useMemo(() => {
    const map: Record<string, { id: string; command_id: string; title: string }> = {}
    for (const item of shortcutItems) {
      map[item.id] = { id: item.id, command_id: item.command_id, title: item.title }
    }
    return map
  }, [shortcutItems])
  const shortcutOptions = useMemo(
    () => shortcutItems.map((item) => ({ value: item.id, label: item.title })),
    [shortcutItems]
  )
  const [selectedShortcutId, setSelectedShortcutId] = useState<string | undefined>(undefined)

  const scope: DriverCommandScope | undefined = selectedCommand?.scope
  const risk: DriverCommandRiskLevel | undefined = selectedCommand?.risk_level

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

  useEffect(() => {
    if (!selectedShortcutId) return
    if (!shortcutsById[selectedShortcutId]) {
      setSelectedShortcutId(undefined)
    }
  }, [selectedShortcutId, shortcutsById])

  const [argsEditorRef, setArgsEditorRef] = useState<{
    monaco: MonacoInstance
    model: Monaco.editor.ITextModel
  } | null>(null)

  useEffect(() => {
    if (!argsEditorRef) return
    const { monaco, model } = argsEditorRef
    const markers = buildArgsMarkers(monaco, driver, config.args_text)
    monaco.editor.setModelMarkers(model, ARGV_MARKER_OWNER, markers)
    return () => {
      monaco.editor.setModelMarkers(model, ARGV_MARKER_OWNER, [])
    }
  }, [argsEditorRef, config.args_text, driver])

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

    if (driver === 'ibcmd' && (path === 'ib_auth.user' || path === 'ib_auth.password')) {
      // These are resolved at runtime via credentials mapping; do not expose raw IB creds in UI.
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
    const ui = schema.ui
    const aliases = isRecord(ui) && Array.isArray(ui.aliases)
      ? (ui.aliases as unknown[]).filter((v): v is string => typeof v === 'string' && v.trim().length > 0).map((v) => v.trim())
      : []
    if (aliases.length > 0) helpParts.push(`Aliases: ${aliases.join(' ')}`)
    if (missingRequired) helpParts.push('Required.')

    if (driver === 'ibcmd' && path === 'ib_auth.strategy') {
      const allowedServiceCommands = new Set(['infobase.extension.list', 'infobase.extension.info'])
      const canShow = Boolean(selectedCommand) && selectedCommand?.risk_level === 'safe' && allowedServiceCommands.has(commandId)
      if (!canShow) return null

      const canUseService = meQuery.data?.is_staff === true
      const options = [
        { value: 'actor', label: 'actor (per-user mapping)' },
        ...(canUseService ? [{ value: 'service', label: 'service (service account)' }] : []),
        { value: 'none', label: 'none (no IB auth)' },
      ]
      const rawValue = getConfigValueAtPath(path)
      const value = (rawValue === 'actor' || rawValue === 'service' || rawValue === 'none') ? rawValue : 'actor'

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

  const handleDangerousConfirmChange = (checked: boolean) => {
    if (!checked) {
      onChange({ confirm_dangerous: false })
      return
    }
    if (dangerousConfirmPending) return

    setDangerousConfirmPending(true)
  }

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

        <Text strong>Connection</Text>
        <IbcmdConnectionForm
          connection={connection}
          readOnly={readOnly}
          onChange={(next) => onChange({ connection: next })}
        />

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
      const nextPaths = query ? section.paths.filter(matchesQuery) : section.paths
      if (nextPaths.length === 0) continue
      filteredSections.push({ ...section, paths: nextPaths })
    }

    if (filteredSections.length === 0) {
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
      return (
        <>
          {mainPaths.map((path) => renderDriverOptionField(path))}
          {offlinePaths.length > 0 && (
            <>
              <Divider style={{ margin: '12px 0' }} />
              <Text strong>Offline</Text>
              {offlinePaths.map((path) => renderDriverOptionField(path))}
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

        <Input
          allowClear
          value={driverOptionsQuery}
          onChange={(event) => setDriverOptionsQuery(event.target.value)}
          placeholder="Search driver options..."
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
      </Space>
    )
  }

  const renderGuidedParams = () => {
    if (!selectedCommand) {
      return null
    }

    const paramsByName = selectedCommand.params_by_name ?? {}
    const entries = sortParams(
      Object.entries(paramsByName)
        .filter(([, schema]) => Boolean(schema))
        .filter(([name]) => driver !== 'ibcmd' || !IBCMD_CONNECTION_PARAM_NAMES.has(name))
        .map(([name, schema]) => ({ name, schema }))
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

  const argsEditorTitle = driver === 'cli' ? 'Args (one per line)' : 'Additional args (one per line)'
  const argsEditorDescription = driver === 'cli'
    ? 'Manual mode: you are responsible for the command syntax and parameters.'
    : 'Extra ibcmd arguments appended after canonical argv.'

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
    setSelectedShortcutId(shortcutId)
    onChange({ command_id: shortcut.command_id, mode: 'guided' })
  }

  const handleSaveShortcut = () => {
    if (!shortcutsEnabled) return
    if (readOnly) return
    if (!commandId) {
      modal.error({ title: 'Select command', content: 'Pick a command first.' })
      return
    }

    let nextTitle = (selectedCommand?.label || commandId).trim()

    modal.confirm({
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
        await createShortcutMutation.mutateAsync({ driver: 'ibcmd', command_id: commandId, title })
      },
    })
  }

  const handleDeleteShortcut = () => {
    if (!shortcutsEnabled) return
    if (readOnly) return
    if (!selectedShortcutId) {
      modal.info({ title: 'Select shortcut', content: 'Pick a shortcut to delete.' })
      return
    }

    const shortcut = shortcutsById[selectedShortcutId]
    const label = shortcut?.title || selectedShortcutId

    modal.confirm({
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
      )}

      {selectedCommand && selectedCommand.description && (
        <Text type="secondary">{selectedCommand.description}</Text>
      )}
      {selectedCommand && selectedCommand.source_section && (
        <Text type="secondary">Source: {selectedCommand.source_section}</Text>
      )}

      {mode === 'guided' && renderGuidedParams()}

      {(mode === 'manual' || driver === 'ibcmd') && (
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          {mode === 'manual' && (
            <Alert type="warning" showIcon message="Manual mode" description={argsEditorDescription} />
          )}
          {driver === 'ibcmd' && pidInArgsLines.length > 0 && (
            <Alert
              type="error"
              showIcon
              message="--pid is not allowed in args"
              description={`Remove --pid from args and set it via Connection → PID. Lines: ${pidInArgsLines.join(', ')}`}
            />
          )}
          <Text strong>{argsEditorTitle}</Text>
          <div style={{ border: '1px solid #d9d9d9', borderRadius: 6, overflow: 'hidden' }}>
            <Editor
              height={driver === 'cli' ? 220 : 160}
              language={ARGV_LANGUAGE_ID}
              theme="vs"
              value={config.args_text || ''}
              onChange={(next) => onChange({ args_text: next ?? '' })}
              beforeMount={ensureArgvLanguage}
              onMount={(editor, monaco) => {
                const model = editor.getModel()
                if (model) {
                  setArgsEditorRef({ monaco, model })
                }
              }}
              options={buildEditorOptions(readOnly)}
            />
          </div>
        </Space>
      )}

      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Text strong>Driver options</Text>
        {renderDriverOptions()}
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
