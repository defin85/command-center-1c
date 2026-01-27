import type * as Monaco from 'monaco-editor'

import { maskArgv } from '../../../lib/masking'
import type { DriverCommandParamV2, DriverCommandV2, DriverName } from '../../../api/driverCommands'
import type { IbcmdCliConnection } from './types'

type MonacoInstance = typeof import('monaco-editor')

export const ARTIFACT_PREFIX = 'artifact://'

export const ARGV_LANGUAGE_ID = 'argv-lines'
export const ARGV_MARKER_OWNER = 'driver-command-args'

let argvLanguageRegistered = false

export const IBCMD_CONNECTION_PARAM_NAMES = new Set([
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

export const ensureArgvLanguage = (monaco: MonacoInstance) => {
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

export const normalizeText = (value: unknown): string => {
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

export const parseLines = (value: string | undefined): string[] => {
  if (!value) return []
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

export const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

export const getValueAtPath = (root: unknown, path: string): unknown => {
  const parts = path.split('.').filter(Boolean)
  let node: unknown = root
  for (const part of parts) {
    if (!isRecord(node)) return undefined
    node = node[part]
  }
  return node
}

export const getSchemaAtPath = (
  driverSchema: Record<string, unknown> | undefined,
  path: string
): Record<string, unknown> | undefined => {
  if (!driverSchema) return undefined
  const parts = path.split('.').filter(Boolean)
  let node: unknown = driverSchema
  for (const part of parts) {
    if (!isRecord(node)) return undefined
    node = node[part]
  }
  return isRecord(node) ? node : undefined
}

export const setObjectPath = (root: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> => {
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

export const detectIbcmdPidInArgs = (value: string | undefined): number[] => {
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

export const buildArgsMarkers = (
  monaco: MonacoInstance,
  driver: DriverName,
  value: string | undefined
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

export const parseArtifactKey = (value: string | boolean | number | undefined): string | undefined => {
  if (typeof value !== 'string') {
    return undefined
  }
  if (!value.startsWith(ARTIFACT_PREFIX)) {
    return undefined
  }
  const key = value.slice(ARTIFACT_PREFIX.length).replace(/^\/+/, '')
  return key || undefined
}

export const parseArtifactIdFromKey = (key?: string): string | undefined => {
  if (!key) {
    return undefined
  }
  const parts = key.split('/')
  if (parts.length >= 2 && parts[0] === 'artifacts') {
    return parts[1]
  }
  return undefined
}

export const safeString = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

export const buildCliArgsPreview = (paramsByName: Record<string, DriverCommandParamV2>, values: Record<string, unknown>) => {
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

export const stringifyIbcmdValue = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

export const buildIbcmdArgvPreview = (
  command: DriverCommandV2,
  params: Record<string, unknown>,
  additionalArgs: string[]
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

export const buildIbcmdConnectionArgsPreview = (
  driverSchema: Record<string, unknown> | undefined,
  connection: IbcmdCliConnection | undefined
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

export const sortParams = (entries: Array<{ name: string; schema: DriverCommandParamV2 }>) =>
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

export const buildCommandOptions = (commandsById: Record<string, DriverCommandV2>) => {
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

export const hasIbcmdConnection = (connection?: IbcmdCliConnection) => {
  const flat = flattenIbcmdConnection(connection)
  return Object.keys(flat).length > 0
}
