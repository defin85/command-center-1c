import type { ActionFormValues, ActionRow, DiffItem, PlainObject, SaveErrorHint } from './actionCatalogTypes'
import {
  canonicalDriverForExecutorKind,
  driverCommandConfigToExecutor,
  executorToDriverCommandConfig,
} from '../../lib/commandConfigAdapter'

export const isPlainObject = (value: unknown): value is PlainObject => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

export const safeJsonStringify = (value: unknown): string => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch (_err) {
    return '{}'
  }
}

export const deepCopy = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

export const parseJson = (raw: string): unknown => {
  try {
    return JSON.parse(raw) as unknown
  } catch (_err) {
    return null
  }
}

export const normalizeActionId = (value: unknown): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

export const extractBackendErrors = (error: unknown): string[] => {
  const err = error as { response?: { status?: number; data?: unknown }; message?: string } | null
  const data = err?.response?.data

  const message = (() => {
    if (!data || typeof data !== 'object') return null
    const maybeError = (data as Record<string, unknown>).error
    if (typeof maybeError === 'string') return maybeError
    if (!maybeError || typeof maybeError !== 'object') return null
    return (maybeError as Record<string, unknown>).message ?? null
  })()

  if (Array.isArray(message)) {
    return message.filter((item) => typeof item === 'string')
  }
  if (typeof message === 'string') {
    return [message]
  }
  if (err?.message) {
    return [err.message]
  }
  return ['Unknown error']
}

export const parseSaveErrorHint = (message: string, actionIdsByPos: Array<string | null> | null): SaveErrorHint => {
  const match = /^extensions\.actions\[(\d+)\](?:\.[^:]*)?:/.exec(message)
  if (!match) return { message }
  const pos = Number(match[1])
  if (!Number.isFinite(pos) || pos < 0) return { message }

  const actionId = actionIdsByPos?.[pos] ?? null
  if (!actionId) return { message, action_pos: pos }
  return { message, action_pos: pos, action_id: actionId }
}

export const isValidUuid = (value: string): boolean => (
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
)

export const safeText = (value: unknown, maxLen = 120): string => {
  const raw = (() => {
    if (value === null) return 'null'
    if (value === undefined) return 'undefined'
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    try {
      return JSON.stringify(value)
    } catch (_err) {
      return String(value)
    }
  })()
  if (raw.length <= maxLen) return raw
  return `${raw.slice(0, maxLen - 1)}…`
}

export const getCatalogActions = (catalog: unknown): PlainObject[] => {
  if (!isPlainObject(catalog)) return []
  const extensions = catalog.extensions
  if (!isPlainObject(extensions)) return []
  const actions = extensions.actions
  if (!Array.isArray(actions)) return []
  return actions.filter(isPlainObject)
}

export const upsertCatalogActions = (catalog: PlainObject, actions: PlainObject[]) => {
  const extensions = isPlainObject(catalog.extensions) ? catalog.extensions as PlainObject : {}
  catalog.extensions = extensions
  extensions.actions = actions
}

export const buildDefaultAction = (): PlainObject => ({
  id: '',
  label: '',
  contexts: ['database_card'],
  executor: {
    kind: 'ibcmd_cli',
    driver: 'ibcmd',
    command_id: '',
    mode: 'guided',
    params: {},
    additional_args: [],
    stdin: '',
  },
})

const cleanupJsonValue = (value: unknown): unknown => {
  if (value === undefined) return undefined
  if (Array.isArray(value)) {
    return value
      .map((item) => cleanupJsonValue(item))
      .filter((item) => item !== undefined)
  }
  if (isPlainObject(value)) {
    const out: PlainObject = {}
    for (const [key, nested] of Object.entries(value)) {
      const cleaned = cleanupJsonValue(nested)
      if (cleaned !== undefined) out[key] = cleaned
    }
    return out
  }
  return value
}

const toFixedFormValue = (value: unknown): ActionFormValues['executor']['fixed'] => {
  if (!isPlainObject(value)) return undefined
  const next = deepCopy(value as PlainObject)
  if (!isPlainObject(next)) return undefined

  if (next.confirm_dangerous !== undefined && typeof next.confirm_dangerous !== 'boolean') {
    delete next.confirm_dangerous
  }
  if (next.timeout_seconds !== undefined) {
    if (typeof next.timeout_seconds !== 'number' || !Number.isFinite(next.timeout_seconds)) {
      delete next.timeout_seconds
    }
  }

  const cleaned = cleanupJsonValue(next)
  if (!isPlainObject(cleaned)) return undefined
  if (Object.keys(cleaned).length === 0) return undefined
  return cleaned as ActionFormValues['executor']['fixed']
}

export const deriveActionFormValues = (action: PlainObject | null): ActionFormValues => {
  const source = action ?? buildDefaultAction()

  const id = typeof source.id === 'string' ? source.id : ''
  const capability = typeof source.capability === 'string' ? source.capability : ''
  const label = typeof source.label === 'string' ? source.label : ''
  const contextsRaw = Array.isArray(source.contexts) ? source.contexts : []
  const contexts = contextsRaw.filter((c) => c === 'database_card' || c === 'bulk_page') as Array<'database_card' | 'bulk_page'>

  const executorRaw = isPlainObject(source.executor) ? source.executor as PlainObject : {}
  const kind = (executorRaw.kind === 'ibcmd_cli' || executorRaw.kind === 'designer_cli' || executorRaw.kind === 'workflow')
    ? executorRaw.kind
    : 'ibcmd_cli'
  const commandConfig = executorToDriverCommandConfig(executorRaw)
  const driver = (commandConfig.driver === 'cli' || commandConfig.driver === 'ibcmd') ? commandConfig.driver : undefined
  const commandId = typeof commandConfig.command_id === 'string' ? commandConfig.command_id : ''
  const workflowId = typeof executorRaw.workflow_id === 'string' ? executorRaw.workflow_id : ''
  const mode = commandConfig.mode === 'manual' ? 'manual' : 'guided'
  const paramsJson = safeJsonStringify(isPlainObject(commandConfig.params) ? commandConfig.params : {})
  const additionalArgs = Array.isArray(commandConfig.resolved_args)
    ? commandConfig.resolved_args.filter((item) => typeof item === 'string') as string[]
    : []
  const stdin = typeof commandConfig.stdin === 'string' ? commandConfig.stdin : ''
  const targetBinding = isPlainObject(executorRaw.target_binding) ? executorRaw.target_binding : {}
  const targetBindingExtensionNameParam = typeof targetBinding.extension_name_param === 'string'
    ? targetBinding.extension_name_param
    : ''

  const fixedRaw = toFixedFormValue(executorRaw.fixed)
  const fixed = (() => {
    if (!fixedRaw || capability.trim() !== 'extensions.set_flags' || !isPlainObject(fixedRaw)) {
      return fixedRaw
    }
    const nextFixed = deepCopy(fixedRaw)
    if (!isPlainObject(nextFixed)) return undefined
    delete nextFixed.apply_mask
    return Object.keys(nextFixed).length > 0 ? nextFixed : undefined
  })()

  return {
    id,
    capability,
    label,
    contexts: contexts.length ? contexts : ['database_card'],
    executor: {
      kind,
      driver,
      command_id: commandId,
      workflow_id: workflowId,
      mode,
      params_json: paramsJson,
      additional_args: additionalArgs,
      stdin,
      target_binding_extension_name_param: targetBindingExtensionNameParam,
      fixed,
    },
  }
}

export const buildActionFromForm = (base: PlainObject | null, values: ActionFormValues): PlainObject => {
  const next = base ? deepCopy(base) : buildDefaultAction()

  next.id = values.id.trim()
  const nextCapability = typeof values.capability === 'string' ? values.capability.trim() : ''
  if (nextCapability) {
    next.capability = nextCapability
  } else {
    delete next.capability
  }
  next.label = values.label.trim()
  next.contexts = [...new Set(values.contexts)]

  const executorBase = isPlainObject(next.executor) ? next.executor as PlainObject : {}
  const executor: PlainObject = { ...executorBase }
  executor.kind = values.executor.kind

  if (values.executor.kind === 'workflow') {
    executor.workflow_id = (values.executor.workflow_id ?? '').trim()
    delete executor.driver
    delete executor.command_id
    delete executor.mode
    delete executor.params
    delete executor.additional_args
    delete executor.stdin
    delete executor.target_binding
  } else {
    const paramsRaw = typeof values.executor.params_json === 'string' ? values.executor.params_json : ''
    const parsedParams = parseJson(paramsRaw)
    const normalizedParams = isPlainObject(parsedParams) ? parsedParams : {}
    const additionalArgs = Array.isArray(values.executor.additional_args)
      ? values.executor.additional_args.filter((item) => typeof item === 'string' && item.trim()) as string[]
      : []
    const commandMode: 'guided' | 'manual' = values.executor.mode === 'manual' ? 'manual' : 'guided'
    const canonicalDriver = canonicalDriverForExecutorKind(values.executor.kind)
    const commandConfig = {
      driver: canonicalDriver ?? (
        values.executor.driver === 'cli' || values.executor.driver === 'ibcmd'
          ? values.executor.driver
          : 'ibcmd'
      ),
      mode: commandMode,
      command_id: (values.executor.command_id ?? '').trim(),
      params: normalizedParams,
      resolved_args: additionalArgs,
      stdin: typeof values.executor.stdin === 'string' ? values.executor.stdin : '',
    }
    const serialized = driverCommandConfigToExecutor(commandConfig, {
      kind: values.executor.kind as 'ibcmd_cli' | 'designer_cli',
    })
    executor.driver = serialized.driver
    executor.command_id = serialized.command_id
    if (serialized.mode !== undefined) {
      executor.mode = serialized.mode
    } else {
      delete executor.mode
    }
    if (serialized.params !== undefined) {
      executor.params = serialized.params
    } else {
      delete executor.params
    }
    if (serialized.additional_args !== undefined) {
      executor.additional_args = serialized.additional_args
    } else {
      delete executor.additional_args
    }
    if (serialized.stdin !== undefined) {
      executor.stdin = serialized.stdin
    } else {
      delete executor.stdin
    }
    delete executor.workflow_id
  }
  const targetBindingExtensionNameParam = (values.executor.target_binding_extension_name_param ?? '').trim()
  if (targetBindingExtensionNameParam) {
    executor.target_binding = { extension_name_param: targetBindingExtensionNameParam }
  } else {
    delete executor.target_binding
  }

  const fixedNextRaw = toFixedFormValue(values.executor.fixed)
  const fixedNext = (() => {
    if (!fixedNextRaw || nextCapability !== 'extensions.set_flags' || !isPlainObject(fixedNextRaw)) {
      return fixedNextRaw
    }
    const nextFixed = deepCopy(fixedNextRaw)
    if (!isPlainObject(nextFixed)) return undefined
    delete nextFixed.apply_mask
    return Object.keys(nextFixed).length > 0 ? nextFixed : undefined
  })()
  if (fixedNext) {
    executor.fixed = fixedNext
  } else {
    delete executor.fixed
  }
  delete executor.connection

  next.executor = executor
  return next
}

export const ensureUniqueId = (candidate: string, used: Set<string>): string => {
  const base = candidate.trim() || 'action'
  if (!used.has(base)) return base
  for (let i = 2; i < 1000; i += 1) {
    const next = `${base}.${i}`
    if (!used.has(next)) return next
  }
  return `${base}.${Date.now()}`
}

const isIdObjectArray = (value: unknown): value is PlainObject[] => {
  if (!Array.isArray(value)) return false
  if (!value.every(isPlainObject)) return false
  return value.every((item) => typeof item.id === 'string' && Boolean(String(item.id).trim()))
}

const diffUnknown = (
  before: unknown,
  after: unknown,
  path: string,
  out: DiffItem[],
  budget: { remaining: number }
) => {
  if (budget.remaining <= 0) return

  const add = (item: DiffItem) => {
    if (budget.remaining <= 0) return
    out.push(item)
    budget.remaining -= 1
  }

  if (before === after) return

  if (Array.isArray(before) && Array.isArray(after)) {
    const beforeIdArray = isIdObjectArray(before)
    const afterIdArray = isIdObjectArray(after)
    if (beforeIdArray && afterIdArray) {
      const beforeById = new Map(before.map((item) => [String(item.id), item]))
      const afterById = new Map(after.map((item) => [String(item.id), item]))
      const ids = new Set([...beforeById.keys(), ...afterById.keys()])
      for (const id of Array.from(ids).sort()) {
        if (budget.remaining <= 0) return
        const b = beforeById.get(id)
        const a = afterById.get(id)
        const itemPath = `${path}[id=${id}]`
        if (b && !a) {
          add({ path: itemPath, kind: 'removed', before: b })
          continue
        }
        if (!b && a) {
          add({ path: itemPath, kind: 'added', after: a })
          continue
        }
        diffUnknown(b, a, itemPath, out, budget)
      }
      return
    }

    if (before.length !== after.length) {
      add({ path, kind: 'changed', before: `len=${before.length}`, after: `len=${after.length}` })
    }

    const len = Math.max(before.length, after.length)
    for (let i = 0; i < len; i += 1) {
      if (budget.remaining <= 0) return
      const b = before[i]
      const a = after[i]
      const itemPath = `${path}[${i}]`
      if (i >= before.length) {
        add({ path: itemPath, kind: 'added', after: a })
        continue
      }
      if (i >= after.length) {
        add({ path: itemPath, kind: 'removed', before: b })
        continue
      }
      diffUnknown(b, a, itemPath, out, budget)
    }
    return
  }

  if (isPlainObject(before) && isPlainObject(after)) {
    const keys = new Set([...Object.keys(before), ...Object.keys(after)])
    for (const key of Array.from(keys).sort()) {
      if (budget.remaining <= 0) return
      const b = before[key]
      const a = after[key]
      const nextPath = path ? `${path}.${key}` : key
      if (!(key in before)) {
        add({ path: nextPath, kind: 'added', after: a })
        continue
      }
      if (!(key in after)) {
        add({ path: nextPath, kind: 'removed', before: b })
        continue
      }
      diffUnknown(b, a, nextPath, out, budget)
    }
    return
  }

  add({ path, kind: 'changed', before, after })
}

export const computeDiff = (before: unknown, after: unknown, maxItems = 200): DiffItem[] => {
  const out: DiffItem[] = []
  const budget = { remaining: maxItems }
  diffUnknown(before, after, '', out, budget)
  return out
}

export const buildActionRows = (value: unknown): ActionRow[] => {
  const actions = getCatalogActions(value)

  const rows: ActionRow[] = []
  for (const [pos, action] of actions.entries()) {
    const id = typeof action.id === 'string' ? action.id : ''
    const capability = typeof action.capability === 'string' ? action.capability : undefined
    const label = typeof action.label === 'string' ? action.label : ''
    const contexts = Array.isArray(action.contexts)
      ? action.contexts.filter((c) => typeof c === 'string') as string[]
      : []
    const executor = action.executor
    const executorObj = executor && typeof executor === 'object' && !Array.isArray(executor)
      ? executor as Record<string, unknown>
      : null
    const kind = executorObj && typeof executorObj.kind === 'string' ? executorObj.kind : ''
    const driver = executorObj && typeof executorObj.driver === 'string'
      ? executorObj.driver
      : canonicalDriverForExecutorKind(kind) ?? undefined
    const commandId = executorObj && typeof executorObj.command_id === 'string' ? executorObj.command_id : undefined
    const workflowId = executorObj && typeof executorObj.workflow_id === 'string' ? executorObj.workflow_id : undefined

    rows.push({
      pos,
      id,
      capability,
      label,
      contexts,
      executor_kind: kind,
      driver,
      command_id: commandId,
      workflow_id: workflowId,
    })
  }
  return rows
}
