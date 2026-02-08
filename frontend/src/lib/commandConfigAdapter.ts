import type { DriverName } from '../api/driverCommands'
import type { DriverCommandOperationConfig } from '../components/driverCommands/DriverCommandBuilder'

type JsonObject = Record<string, unknown>

const isObject = (value: unknown): value is JsonObject => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const normalizeStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean)
}

const normalizeDriver = (raw: unknown, fallback: DriverName): DriverName => {
  const value = typeof raw === 'string' ? raw.trim() : ''
  if (value === 'ibcmd' || value === 'cli') return value
  return fallback
}

export const canonicalDriverForExecutorKind = (kind: unknown): DriverName | null => {
  const value = typeof kind === 'string' ? kind.trim() : ''
  if (value === 'ibcmd_cli') return 'ibcmd'
  if (value === 'designer_cli') return 'cli'
  return null
}

export const templateDataToDriverCommandConfig = (raw: unknown): DriverCommandOperationConfig => {
  const data = isObject(raw) ? raw : {}
  const options = isObject(data.options) ? data.options : {}
  const args = normalizeStringList(data.args)
  const params = isObject(data.cli_params) ? data.cli_params : {}
  const mode = data.cli_mode === 'manual' ? 'manual' : 'guided'
  const commandId = typeof data.command === 'string' ? data.command.trim() : ''

  return {
    driver: 'cli',
    mode,
    command_id: commandId || undefined,
    args_text: mode === 'manual' ? args.join('\n') : '',
    resolved_args: args.length > 0 ? args : undefined,
    params,
    cli_options: {
      disable_startup_messages: typeof options.disable_startup_messages === 'boolean'
        ? options.disable_startup_messages
        : typeof data.disable_startup_messages === 'boolean'
          ? data.disable_startup_messages
          : true,
      disable_startup_dialogs: typeof options.disable_startup_dialogs === 'boolean'
        ? options.disable_startup_dialogs
        : typeof data.disable_startup_dialogs === 'boolean'
          ? data.disable_startup_dialogs
          : true,
    },
  }
}

export const driverCommandConfigToTemplateData = (config: DriverCommandOperationConfig): JsonObject => {
  const params = isObject(config.params) ? config.params : {}
  const cliParams: Record<string, string | boolean> = {}
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === 'boolean') {
      cliParams[key] = value
      continue
    }
    if (typeof value === 'string' && value.trim().length > 0) {
      cliParams[key] = value
      continue
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      cliParams[key] = String(value)
    }
  }

  const args = normalizeStringList(config.resolved_args)
  const options = isObject(config.cli_options) ? config.cli_options : {}
  return {
    command: typeof config.command_id === 'string' ? config.command_id.trim() : '',
    args: args.length > 0 ? args : undefined,
    options: {
      disable_startup_messages: options.disable_startup_messages !== false,
      disable_startup_dialogs: options.disable_startup_dialogs !== false,
    },
    cli_mode: config.mode === 'manual' ? 'manual' : 'guided',
    cli_params: cliParams,
  }
}

export const executorToDriverCommandConfig = (raw: unknown): DriverCommandOperationConfig => {
  const executor = isObject(raw) ? raw : {}
  const fallbackDriver = canonicalDriverForExecutorKind(executor.kind) ?? 'ibcmd'
  return {
    driver: normalizeDriver(executor.driver, fallbackDriver),
    mode: executor.mode === 'manual' ? 'manual' : 'guided',
    command_id: typeof executor.command_id === 'string' ? executor.command_id : undefined,
    params: isObject(executor.params) ? executor.params : {},
    resolved_args: normalizeStringList(executor.additional_args),
    stdin: typeof executor.stdin === 'string' ? executor.stdin : '',
  }
}

export const driverCommandConfigToExecutor = (
  config: DriverCommandOperationConfig,
  opts: { kind: 'ibcmd_cli' | 'designer_cli' }
): JsonObject => {
  const executor: JsonObject = {
    kind: opts.kind,
    driver: normalizeDriver(config.driver, opts.kind === 'designer_cli' ? 'cli' : 'ibcmd'),
    command_id: typeof config.command_id === 'string' ? config.command_id.trim() : '',
  }

  if (opts.kind === 'ibcmd_cli' && (config.mode === 'manual' || config.mode === 'guided')) {
    executor.mode = config.mode
  }

  const params = isObject(config.params) ? config.params : {}
  executor.params = params

  const additionalArgs = normalizeStringList(config.resolved_args)
  if (additionalArgs.length > 0) {
    executor.additional_args = additionalArgs
  } else {
    delete executor.additional_args
  }

  if (typeof config.stdin === 'string' && config.stdin.trim().length > 0) {
    executor.stdin = config.stdin
  } else {
    delete executor.stdin
  }

  return executor
}
