import type { ActionFormValues, ActionRow, DiffItem, IbcmdCliConnectionForm, PlainObject, SaveErrorHint } from './actionCatalogTypes'

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

const isRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const normalizeConnectionFromExecutor = (executor: PlainObject): { raw: Record<string, unknown> | null; form: IbcmdCliConnectionForm | undefined } => {
  const raw = isRecord(executor.connection) ? (executor.connection as Record<string, unknown>) : null
  if (!raw) return { raw: null, form: undefined }

  const remote = typeof raw.remote === 'string' ? raw.remote : undefined
  const pid = typeof raw.pid === 'number' ? raw.pid : undefined

  const offlineRaw = isRecord(raw.offline) ? (raw.offline as Record<string, unknown>) : null
  const offline: IbcmdCliConnectionForm['offline'] | undefined = offlineRaw ? {
    config: typeof offlineRaw.config === 'string' ? offlineRaw.config : undefined,
    data: typeof offlineRaw.data === 'string' ? offlineRaw.data : undefined,
    dbms: typeof offlineRaw.dbms === 'string' ? offlineRaw.dbms : undefined,
    db_server: typeof offlineRaw.db_server === 'string' ? offlineRaw.db_server : undefined,
    db_name: typeof offlineRaw.db_name === 'string' ? offlineRaw.db_name : undefined,
  } : undefined

  const form: IbcmdCliConnectionForm = {}
  if (remote !== undefined) form.remote = remote
  if (pid !== undefined) form.pid = pid
  if (offline !== undefined) form.offline = offline

  return { raw, form: Object.keys(form).length ? form : {} }
}

const applyConnectionFormToBase = (base: Record<string, unknown> | null, form: IbcmdCliConnectionForm | undefined): Record<string, unknown> | null => {
  const next: Record<string, unknown> = base ? deepCopy(base) : {}

  const remote = typeof form?.remote === 'string' ? form.remote.trim() : ''
  if (remote) next.remote = remote
  else delete next.remote

  if (typeof form?.pid === 'number') next.pid = form.pid
  else delete next.pid

  const offlineBase = isRecord(next.offline) ? (next.offline as Record<string, unknown>) : {}
  const offline: Record<string, unknown> = { ...offlineBase }
  delete offline.db_user
  delete offline.db_pwd

  const offlineForm = form?.offline
  const setOrDelete = (key: keyof NonNullable<IbcmdCliConnectionForm['offline']>) => {
    const raw = typeof offlineForm?.[key] === 'string' ? offlineForm[key].trim() : ''
    if (raw) offline[key] = raw
    else delete offline[key]
  }

  setOrDelete('config')
  setOrDelete('data')
  setOrDelete('dbms')
  setOrDelete('db_server')
  setOrDelete('db_name')

  if (Object.keys(offline).length > 0) next.offline = offline
  else delete next.offline

  if (Object.keys(next).length === 0) return null
  return next
}

export const deriveActionFormValues = (action: PlainObject | null): ActionFormValues => {
  const source = action ?? buildDefaultAction()

  const id = typeof source.id === 'string' ? source.id : ''
  const label = typeof source.label === 'string' ? source.label : ''
  const contextsRaw = Array.isArray(source.contexts) ? source.contexts : []
  const contexts = contextsRaw.filter((c) => c === 'database_card' || c === 'bulk_page') as Array<'database_card' | 'bulk_page'>

  const executorRaw = isPlainObject(source.executor) ? source.executor as PlainObject : {}
  const kind = (executorRaw.kind === 'ibcmd_cli' || executorRaw.kind === 'designer_cli' || executorRaw.kind === 'workflow')
    ? executorRaw.kind
    : 'ibcmd_cli'
  const driver = (executorRaw.driver === 'cli' || executorRaw.driver === 'ibcmd') ? executorRaw.driver : undefined
  const commandId = typeof executorRaw.command_id === 'string' ? executorRaw.command_id : ''
  const workflowId = typeof executorRaw.workflow_id === 'string' ? executorRaw.workflow_id : ''

  const mode = executorRaw.mode === 'manual' ? 'manual' : 'guided'

  const params = isPlainObject(executorRaw.params) ? executorRaw.params : {}
  const paramsJson = safeJsonStringify(params)

  const additionalArgs = Array.isArray(executorRaw.additional_args)
    ? executorRaw.additional_args.filter((item) => typeof item === 'string') as string[]
    : []
  const stdin = typeof executorRaw.stdin === 'string' ? executorRaw.stdin : ''

  const fixed = isPlainObject(executorRaw.fixed) ? executorRaw.fixed as PlainObject : {}
  const confirmDangerous = fixed.confirm_dangerous === true
  const timeoutSeconds = typeof fixed.timeout_seconds === 'number' ? fixed.timeout_seconds : undefined

  const { form: connectionForm } = normalizeConnectionFromExecutor(executorRaw)

  return {
    id,
    label,
    contexts: contexts.length ? contexts : ['database_card'],
    executor: {
      kind,
      driver,
      command_id: commandId,
      workflow_id: workflowId,
      connection: connectionForm,
      mode,
      params_json: paramsJson,
      additional_args: additionalArgs,
      stdin,
      fixed: {
        confirm_dangerous: confirmDangerous,
        timeout_seconds: timeoutSeconds,
      },
    },
  }
}

export const buildActionFromForm = (base: PlainObject | null, values: ActionFormValues): PlainObject => {
  const next = base ? deepCopy(base) : buildDefaultAction()

  next.id = values.id.trim()
  next.label = values.label.trim()
  next.contexts = [...new Set(values.contexts)]

  const executorBase = isPlainObject(next.executor) ? next.executor as PlainObject : {}
  const executor: PlainObject = { ...executorBase }
  executor.kind = values.executor.kind

  if (values.executor.kind === 'workflow') {
    executor.workflow_id = (values.executor.workflow_id ?? '').trim()
    delete executor.driver
    delete executor.command_id
  } else {
    executor.driver = (values.executor.driver ?? '').trim()
    executor.command_id = (values.executor.command_id ?? '').trim()
    delete executor.workflow_id
  }

  const mode = values.executor.mode === 'manual' ? 'manual' : (values.executor.mode === 'guided' ? 'guided' : undefined)
  if (values.executor.kind === 'ibcmd_cli' && mode) {
    executor.mode = mode
  } else {
    delete executor.mode
  }

  const stdin = typeof values.executor.stdin === 'string' ? values.executor.stdin : ''
  if (stdin.trim()) {
    executor.stdin = stdin
  } else {
    delete executor.stdin
  }

  const additionalArgs = Array.isArray(values.executor.additional_args)
    ? values.executor.additional_args.filter((item) => typeof item === 'string' && item.trim()) as string[]
    : []
  if (additionalArgs.length) {
    executor.additional_args = additionalArgs
  } else {
    delete executor.additional_args
  }

  const paramsRaw = typeof values.executor.params_json === 'string' ? values.executor.params_json : ''
  if (paramsRaw.trim()) {
    const parsed = parseJson(paramsRaw)
    if (isPlainObject(parsed)) {
      executor.params = parsed
    } else {
      delete executor.params
    }
  } else {
    delete executor.params
  }

  const fixedNext: PlainObject = {}
  const fixedForm = values.executor.fixed
  if (fixedForm?.confirm_dangerous === true) {
    fixedNext.confirm_dangerous = true
  }
  if (typeof fixedForm?.timeout_seconds === 'number' && Number.isFinite(fixedForm.timeout_seconds)) {
    fixedNext.timeout_seconds = fixedForm.timeout_seconds
  }
  if (Object.keys(fixedNext).length) {
    executor.fixed = fixedNext
  } else {
    delete executor.fixed
  }

  const { raw: existingConnection } = normalizeConnectionFromExecutor(executorBase)
  const nextConnection = applyConnectionFormToBase(existingConnection, values.executor.connection)
  if (values.executor.kind === 'ibcmd_cli') {
    if (nextConnection) executor.connection = nextConnection
    else delete executor.connection
  } else {
    delete executor.connection
  }

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
    const label = typeof action.label === 'string' ? action.label : ''
    const contexts = Array.isArray(action.contexts)
      ? action.contexts.filter((c) => typeof c === 'string') as string[]
      : []
    const executor = action.executor
    const executorObj = executor && typeof executor === 'object' && !Array.isArray(executor)
      ? executor as Record<string, unknown>
      : null
    const kind = executorObj && typeof executorObj.kind === 'string' ? executorObj.kind : ''
    const driver = executorObj && typeof executorObj.driver === 'string' ? executorObj.driver : undefined
    const commandId = executorObj && typeof executorObj.command_id === 'string' ? executorObj.command_id : undefined
    const workflowId = executorObj && typeof executorObj.workflow_id === 'string' ? executorObj.workflow_id : undefined

    rows.push({
      pos,
      id,
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
