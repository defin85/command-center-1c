import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Spin, Switch, Table, Tabs, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ArrowDownOutlined, ArrowUpOutlined, CopyOutlined, DeleteOutlined, EditOutlined, EyeOutlined, PlusOutlined, RollbackOutlined } from '@ant-design/icons'

import { useMe } from '../../api/queries/me'
import { apiClient } from '../../api/client'
import { getRuntimeSettings, updateRuntimeSetting } from '../../api/runtimeSettings'
import { useDriverCommands } from '../../api/queries/driverCommands'
import type { DriverName } from '../../api/driverCommands'
import { useWorkflowTemplates } from '../../api/queries/workflowTemplates'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'

const { Title, Text } = Typography

const ACTION_CATALOG_KEY = 'ui.action_catalog'
const DISABLED_ACTIONS_STORAGE_KEY = 'action-catalog.disabled-actions.v1'

type ActionCatalogMode = 'guided' | 'raw'

type ActionRow = {
  pos: number
  id: string
  label: string
  contexts: string[]
  executor_kind: string
  driver?: string
  command_id?: string
  workflow_id?: string
}

type ActionContext = 'database_card' | 'bulk_page'
type ExecutorKind = 'ibcmd_cli' | 'designer_cli' | 'workflow'

type PlainObject = Record<string, unknown>

type DiffKind = 'added' | 'removed' | 'changed'

type DiffItem = {
  path: string
  kind: DiffKind
  before?: unknown
  after?: unknown
}

type SaveErrorHint = {
  message: string
  action_pos?: number
  action_id?: string
}

type ActionFormValues = {
  id: string
  label: string
  contexts: ActionContext[]
  executor: {
    kind: ExecutorKind
    driver?: DriverName
    command_id?: string
    workflow_id?: string
    mode?: 'guided' | 'manual'
    params_json?: string
    additional_args?: string[]
    stdin?: string
    fixed?: {
      confirm_dangerous?: boolean
      timeout_seconds?: number
    }
  }
}

const ACTION_CONTEXT_OPTIONS: { value: ActionContext; label: string }[] = [
  { value: 'database_card', label: 'database_card' },
  { value: 'bulk_page', label: 'bulk_page' },
]

const EXECUTOR_KIND_OPTIONS: { value: ExecutorKind; label: string }[] = [
  { value: 'ibcmd_cli', label: 'ibcmd_cli' },
  { value: 'designer_cli', label: 'designer_cli' },
  { value: 'workflow', label: 'workflow' },
]

const DRIVER_OPTIONS: { value: DriverName; label: string }[] = [
  { value: 'ibcmd', label: 'ibcmd' },
  { value: 'cli', label: 'cli' },
]

const MODE_OPTIONS: { value: 'guided' | 'manual'; label: string }[] = [
  { value: 'guided', label: 'guided' },
  { value: 'manual', label: 'manual' },
]

const isPlainObject = (value: unknown): value is PlainObject => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const safeJsonStringify = (value: unknown): string => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch (_err) {
    return '{}'
  }
}

const deepCopy = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

const parseJson = (raw: string): unknown => {
  try {
    return JSON.parse(raw) as unknown
  } catch (_err) {
    return null
  }
}

const normalizeActionId = (value: unknown): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

const extractBackendErrors = (error: unknown): string[] => {
  const err = error as { response?: { status?: number; data?: any }; message?: string } | null
  const data = err?.response?.data
  const message = data?.error?.message
  if (Array.isArray(message)) {
    return message.filter((item: unknown) => typeof item === 'string') as string[]
  }
  if (typeof message === 'string') {
    return [message]
  }
  if (err?.message) {
    return [err.message]
  }
  return ['Unknown error']
}

const parseSaveErrorHint = (message: string, actionIdsByPos: Array<string | null> | null): SaveErrorHint => {
  const match = /^extensions\.actions\[(\d+)\](?:\.[^:]*)?:/.exec(message)
  if (!match) return { message }
  const pos = Number(match[1])
  if (!Number.isFinite(pos) || pos < 0) return { message }

  const actionId = actionIdsByPos?.[pos] ?? null
  if (!actionId) return { message, action_pos: pos }
  return { message, action_pos: pos, action_id: actionId }
}

const isValidUuid = (value: string): boolean => (
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
)

const safeText = (value: unknown, maxLen = 120): string => {
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

const getCatalogActions = (catalog: unknown): PlainObject[] => {
  if (!isPlainObject(catalog)) return []
  const extensions = catalog.extensions
  if (!isPlainObject(extensions)) return []
  const actions = extensions.actions
  if (!Array.isArray(actions)) return []
  return actions.filter(isPlainObject)
}

const upsertCatalogActions = (catalog: PlainObject, actions: PlainObject[]) => {
  const extensions = isPlainObject(catalog.extensions) ? catalog.extensions as PlainObject : {}
  catalog.extensions = extensions
  extensions.actions = actions
}

const buildDefaultAction = (): PlainObject => ({
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

const deriveActionFormValues = (action: PlainObject | null): ActionFormValues => {
  const source = action ?? buildDefaultAction()

  const id = typeof source.id === 'string' ? source.id : ''
  const label = typeof source.label === 'string' ? source.label : ''
  const contextsRaw = Array.isArray(source.contexts) ? source.contexts : []
  const contexts = contextsRaw.filter((c) => c === 'database_card' || c === 'bulk_page') as ActionContext[]

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

  return {
    id,
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
      fixed: {
        confirm_dangerous: confirmDangerous,
        timeout_seconds: timeoutSeconds,
      },
    },
  }
}

const buildActionFromForm = (base: PlainObject | null, values: ActionFormValues): PlainObject => {
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
  if (mode) {
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

  next.executor = executor
  return next
}

const ensureUniqueId = (candidate: string, used: Set<string>): string => {
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

const computeDiff = (before: unknown, after: unknown, maxItems = 200): DiffItem[] => {
  const out: DiffItem[] = []
  const budget = { remaining: maxItems }
  diffUnknown(before, after, '', out, budget)
  return out
}

const buildActionRows = (value: unknown): ActionRow[] => {
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

export function ActionCatalogPage() {
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)

  const [mode, setMode] = useState<ActionCatalogMode>('guided')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [serverRaw, setServerRaw] = useState<string | null>(null)
  const [draftRaw, setDraftRaw] = useState<string>('{}')
  const [settingDescription, setSettingDescription] = useState<string | null>(null)
  const [disabledActions, setDisabledActions] = useState<PlainObject[]>([])
  const [saveErrors, setSaveErrors] = useState<string[]>([])
  const [saveErrorsDraftActionIds, setSaveErrorsDraftActionIds] = useState<Array<string | null> | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saving, setSaving] = useState(false)

  const [editorOpen, setEditorOpen] = useState(false)
  const [editorTitle, setEditorTitle] = useState('Edit action')
  const [editingPos, setEditingPos] = useState<number | null>(null)
  const [editingBase, setEditingBase] = useState<PlainObject | null>(null)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)
  const [workflowSearch, setWorkflowSearch] = useState('')

  const [form] = Form.useForm<ActionFormValues>()

  const editorKind = (Form.useWatch(['executor', 'kind'], form) as ExecutorKind | undefined) ?? 'ibcmd_cli'
  const editorDriver = Form.useWatch(['executor', 'driver'], form) as DriverName | undefined
  const commandsDriver: DriverName = (editorDriver === 'cli' || editorDriver === 'ibcmd')
    ? editorDriver
    : (editorKind === 'designer_cli' ? 'cli' : 'ibcmd')

  const commandsQuery = useDriverCommands(
    commandsDriver,
    editorOpen && (editorKind === 'ibcmd_cli' || editorKind === 'designer_cli')
  )

  const workflowTemplatesQuery = useWorkflowTemplates(
    workflowSearch.trim() ? { search: workflowSearch.trim() } : undefined,
    editorOpen && editorKind === 'workflow'
  )

  const commandOptions = useMemo(() => {
    const commandsById = commandsQuery.data?.catalog?.commands_by_id
    if (!commandsById || typeof commandsById !== 'object') return []
    return Object.entries(commandsById)
      .map(([id, cmd]) => {
        const label = cmd?.label ? String(cmd.label) : ''
        const risk = cmd?.risk_level ? String(cmd.risk_level) : ''
        const suffix = label ? ` — ${label}` : ''
        const riskSuffix = risk ? ` (${risk})` : ''
        return { value: id, label: `${id}${suffix}${riskSuffix}` }
      })
      .sort((a, b) => a.value.localeCompare(b.value))
  }, [commandsQuery.data])

  const workflowOptions = useMemo(() => {
    const items = workflowTemplatesQuery.data?.templates ?? []
    return items.map((tpl) => ({
      value: tpl.id,
      label: `${tpl.name} (${tpl.category})`,
    }))
  }, [workflowTemplatesQuery.data])

  const driverCatalogUnavailable = Boolean(
    (editorOpen && (editorKind === 'ibcmd_cli' || editorKind === 'designer_cli'))
    && (commandsQuery.isError || (!commandsQuery.isLoading && commandOptions.length === 0))
  )

  const workflowTemplatesUnavailable = Boolean(
    (editorOpen && editorKind === 'workflow')
    && (workflowTemplatesQuery.isError || (!workflowTemplatesQuery.isLoading && workflowOptions.length === 0))
  )

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(DISABLED_ACTIONS_STORAGE_KEY)
      if (!raw) {
        setDisabledActions([])
        return
      }
      const parsed = JSON.parse(raw) as unknown
      if (Array.isArray(parsed)) {
        setDisabledActions(parsed.filter(isPlainObject))
      } else {
        setDisabledActions([])
      }
    } catch (_err) {
      setDisabledActions([])
    }
  }, [])

  useEffect(() => {
    try {
      sessionStorage.setItem(DISABLED_ACTIONS_STORAGE_KEY, JSON.stringify(disabledActions))
    } catch (_err) {
      // ignore storage errors
    }
  }, [disabledActions])

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSaveErrors([])
    setSaveErrorsDraftActionIds(null)
    setSaveSuccess(false)
    try {
      const settings = await getRuntimeSettings()
      const entry = settings.find((item) => item.key === ACTION_CATALOG_KEY)
      if (!entry) {
        setError(`RuntimeSetting ${ACTION_CATALOG_KEY} не найден`)
        setServerRaw(null)
        setDraftRaw('{}')
        setSettingDescription(null)
        return
      }
      const raw = safeJsonStringify(entry.value)
      setServerRaw(raw)
      setDraftRaw(raw)
      setSettingDescription(entry.description || null)
    } catch (_err) {
      setError('Не удалось загрузить ui.action_catalog')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isStaff) {
      return
    }
    void loadCatalog()
  }, [isStaff, loadCatalog])

  const dirty = useMemo(() => {
    return serverRaw !== null && draftRaw !== serverRaw
  }, [draftRaw, serverRaw])

  const serverParsed = useMemo(() => (serverRaw === null ? null : parseJson(serverRaw)), [serverRaw])
  const draftParsed = useMemo(() => parseJson(draftRaw), [draftRaw])
  const draftIsValidJson = draftParsed !== null
  const actionRows = useMemo(() => buildActionRows(draftParsed), [draftParsed])

  const rawValidation = useMemo(() => {
    const errors: string[] = []
    const warnings: string[] = []

    if (draftParsed === null) {
      errors.push('Draft is not a valid JSON')
      return { ok: false, errors, warnings, actionsCount: 0 }
    }

    if (!isPlainObject(draftParsed)) {
      errors.push('Draft must be a JSON object')
      return { ok: false, errors, warnings, actionsCount: 0 }
    }

    const version = draftParsed.catalog_version
    if (version !== 1) {
      errors.push('catalog_version must be 1')
    }

    const rootKeys = Object.keys(draftParsed)
    for (const key of rootKeys) {
      if (key !== 'catalog_version' && key !== 'extensions') {
        errors.push(`Unknown root key: ${key}`)
      }
    }

    const extensions = draftParsed.extensions
    if (!isPlainObject(extensions)) {
      warnings.push('extensions is missing or not an object')
      return { ok: errors.length === 0, errors, warnings, actionsCount: 0 }
    }

    for (const key of Object.keys(extensions)) {
      if (key !== 'actions') {
        errors.push(`Unknown extensions key: ${key}`)
      }
    }

    const actions = (extensions as PlainObject).actions
    if (!Array.isArray(actions)) {
      warnings.push('extensions.actions is missing or not an array')
      return { ok: errors.length === 0, errors, warnings, actionsCount: 0 }
    }

    const seenIds = new Set<string>()

    for (let idx = 0; idx < actions.length; idx += 1) {
      const action = actions[idx]
      if (action === null || action === undefined) {
        errors.push(`extensions.actions[${idx}]: must be an object`)
        continue
      }
      if (!isPlainObject(action)) {
        errors.push(`extensions.actions[${idx}]: must be an object`)
        continue
      }

      for (const key of Object.keys(action)) {
        if (key !== 'id' && key !== 'label' && key !== 'contexts' && key !== 'executor') {
          errors.push(`extensions.actions[${idx}]: unknown key: ${key}`)
        }
      }

      const id = normalizeActionId(action.id)
      if (!id) {
        errors.push(`extensions.actions[${idx}].id: must be a non-empty string`)
      } else if (seenIds.has(id)) {
        errors.push(`extensions.actions[${idx}].id: must be unique (duplicate: ${id})`)
      } else {
        seenIds.add(id)
      }

      const label = normalizeActionId(action.label)
      if (!label) {
        errors.push(`extensions.actions[${idx}].label: must be a non-empty string`)
      }

      const contexts = action.contexts
      if (!Array.isArray(contexts) || contexts.length === 0) {
        errors.push(`extensions.actions[${idx}].contexts: must be a non-empty array`)
      } else {
        const normalized = contexts
          .filter((c) => typeof c === 'string')
          .map((c) => c.trim())
          .filter(Boolean)
        const unknown = normalized.filter((c) => c !== 'database_card' && c !== 'bulk_page')
        if (unknown.length > 0) {
          errors.push(`extensions.actions[${idx}].contexts: unknown values: ${unknown.join(', ')}`)
        }
      }

      const executor = isPlainObject(action.executor) ? action.executor as PlainObject : null
      if (!executor) {
        errors.push(`extensions.actions[${idx}].executor: must be an object`)
        continue
      }

      for (const key of Object.keys(executor)) {
        if (
          key !== 'kind'
          && key !== 'driver'
          && key !== 'command_id'
          && key !== 'workflow_id'
          && key !== 'mode'
          && key !== 'params'
          && key !== 'additional_args'
          && key !== 'stdin'
          && key !== 'fixed'
        ) {
          errors.push(`extensions.actions[${idx}].executor: unknown key: ${key}`)
        }
      }

      const kind = normalizeActionId(executor.kind)
      if (kind !== 'ibcmd_cli' && kind !== 'designer_cli' && kind !== 'workflow') {
        errors.push(`extensions.actions[${idx}].executor.kind: must be one of ibcmd_cli, designer_cli, workflow`)
        continue
      }

      if (kind === 'workflow') {
        const workflowId = normalizeActionId(executor.workflow_id)
        if (!workflowId) {
          errors.push(`extensions.actions[${idx}].executor.workflow_id: must be a non-empty string`)
        } else if (!isValidUuid(workflowId)) {
          warnings.push(`extensions.actions[${idx}].executor.workflow_id: not a UUID (${workflowId})`)
        }
      } else {
        const driver = normalizeActionId(executor.driver)
        if (driver !== 'ibcmd' && driver !== 'cli') {
          errors.push(`extensions.actions[${idx}].executor.driver: must be ibcmd or cli`)
        }
        const commandId = normalizeActionId(executor.command_id)
        if (!commandId) {
          errors.push(`extensions.actions[${idx}].executor.command_id: must be a non-empty string`)
        }
      }

      if (executor.fixed !== undefined) {
        const fixed = isPlainObject(executor.fixed) ? executor.fixed as PlainObject : null
        if (!fixed) {
          errors.push(`extensions.actions[${idx}].executor.fixed: must be an object`)
        } else {
          for (const key of Object.keys(fixed)) {
            if (key !== 'confirm_dangerous' && key !== 'timeout_seconds') {
              errors.push(`extensions.actions[${idx}].executor.fixed: unknown key: ${key}`)
            }
          }
        }
      }
    }

    return { ok: errors.length === 0, errors, warnings, actionsCount: actions.length }
  }, [draftParsed])

  const saveErrorHints = useMemo(() => {
    return saveErrors.map((msg) => parseSaveErrorHint(msg, saveErrorsDraftActionIds))
  }, [saveErrors, saveErrorsDraftActionIds])

  const saveErrorsByActionPos = useMemo(() => {
    const map = new Map<number, string[]>()
    for (const item of saveErrorHints) {
      const pos = item.action_pos
      if (typeof pos !== 'number') continue
      const existing = map.get(pos) ?? []
      existing.push(item.message)
      map.set(pos, existing)
    }
    return map
  }, [saveErrorHints])

  const diffItems = useMemo(() => {
    if (!dirty) return []
    if (serverParsed === null || draftParsed === null) return []
    return computeDiff(serverParsed, draftParsed)
  }, [dirty, draftParsed, serverParsed])

  const diffSummary = useMemo(() => {
    const summary = { added: 0, removed: 0, changed: 0 }
    for (const item of diffItems) {
      summary[item.kind] += 1
    }
    return summary
  }, [diffItems])

  const canSave = Boolean(
    isStaff
    && dirty
    && rawValidation.ok
    && isPlainObject(draftParsed)
    && !saving
  )

  const handleSave = useCallback(async () => {
    if (saving) return
    setSaveSuccess(false)
    setSaveErrors([])
    setSaveErrorsDraftActionIds(null)
    setError(null)

    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setSaveErrors(['Draft must be a JSON object'])
      return
    }
    if (parsed.catalog_version !== 1) {
      setSaveErrors(['catalog_version must be 1'])
      return
    }

    const actionIdsByPos: Array<string | null> = []
    const extensions = parsed.extensions
    const actions = isPlainObject(extensions) ? (extensions.actions as unknown) : null
    if (Array.isArray(actions)) {
      for (const item of actions) {
        actionIdsByPos.push(isPlainObject(item) ? normalizeActionId((item as PlainObject).id) : null)
      }
    }
    setSaveErrorsDraftActionIds(actionIdsByPos)
    setSaving(true)
    try {
      const updated = await updateRuntimeSetting(ACTION_CATALOG_KEY, parsed)
      const nextServerRaw = safeJsonStringify(updated.value)
      setServerRaw(nextServerRaw)
      setDraftRaw(nextServerRaw)
      setSaveSuccess(true)
      setSaveErrors([])
    } catch (err) {
      setSaveErrors(extractBackendErrors(err))
    } finally {
      setSaving(false)
    }
  }, [draftRaw, saving])

  const updateActions = useCallback((updater: (actions: PlainObject[]) => PlainObject[]) => {
    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно применить изменения: draft не является JSON-объектом')
      return
    }
    parsed.catalog_version = 1
    const currentActions = getCatalogActions(parsed)
    const nextActions = updater(deepCopy(currentActions))
    upsertCatalogActions(parsed, nextActions)
    setDraftRaw(safeJsonStringify(parsed))
  }, [draftRaw])

  const openEditor = useCallback((opts: { mode: 'add' | 'edit' | 'copy'; pos?: number }) => {
    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно открыть редактор: draft не является JSON-объектом')
      return
    }
    const actions = getCatalogActions(parsed)
    const pos = typeof opts.pos === 'number' ? opts.pos : null
    const base = (pos !== null && actions[pos]) ? deepCopy(actions[pos]) : null

    const usedIds = new Set(actions.map((a) => (typeof a.id === 'string' ? a.id : '')).filter(Boolean))

    if (opts.mode === 'add') {
      const nextValues = deriveActionFormValues(null)
      setEditorTitle('Add action')
      setEditingPos(null)
      setEditingBase(null)
      setEditorValues(nextValues)
      form.resetFields()
      form.setFieldsValue(nextValues)
      setEditorOpen(true)
      return
    }

    if (!base) {
      setError('Action не найден')
      return
    }

    if (opts.mode === 'edit') {
      const nextValues = deriveActionFormValues(base)
      setEditorTitle('Edit action')
      setEditingPos(pos)
      setEditingBase(base)
      setEditorValues(nextValues)
      form.resetFields()
      form.setFieldsValue(nextValues)
      setEditorOpen(true)
      return
    }

    const copied = deepCopy(base)
    const baseId = typeof copied.id === 'string' ? copied.id : 'action'
    const candidate = `${baseId}.copy`
    copied.id = ensureUniqueId(candidate, usedIds)
    const nextValues = deriveActionFormValues(copied)
    setEditorTitle('Copy action')
    setEditingPos(null)
    setEditingBase(copied)
    setEditorValues(nextValues)
    form.resetFields()
    form.setFieldsValue(nextValues)
    setEditorOpen(true)
  }, [draftRaw, form])

  const closeEditor = useCallback(() => {
    setEditorOpen(false)
    setEditingPos(null)
    setEditingBase(null)
    setEditorValues(null)
    form.resetFields()
  }, [form])

  const submitEditor = useCallback(async () => {
    const values = await form.validateFields()

    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно применить изменения: draft не является JSON-объектом')
      return
    }
    parsed.catalog_version = 1

    const actions = getCatalogActions(parsed)
    const next = buildActionFromForm(editingBase, values)
    const trimmedId = typeof next.id === 'string' ? next.id.trim() : ''

    const usedIds = new Set(
      actions
        .map((a) => (typeof a.id === 'string' ? a.id.trim() : ''))
        .filter(Boolean)
    )

    if (editingPos !== null) {
      const currentId = typeof actions[editingPos]?.id === 'string' ? String(actions[editingPos].id).trim() : ''
      usedIds.delete(currentId)
    }

    if (!trimmedId || usedIds.has(trimmedId)) {
      form.setFields([{ name: 'id', errors: ['ID уже используется'] }])
      return
    }

    const nextActions = [...actions]
    if (editingPos !== null) {
      nextActions[editingPos] = next
    } else {
      nextActions.push(next)
    }
    upsertCatalogActions(parsed, nextActions)
    setDraftRaw(safeJsonStringify(parsed))
    closeEditor()
  }, [closeEditor, draftRaw, editingBase, editingPos, form])

  const moveAction = useCallback((pos: number, delta: -1 | 1) => {
    updateActions((actions) => {
      const nextPos = pos + delta
      if (nextPos < 0 || nextPos >= actions.length) return actions
      const next = [...actions]
      const tmp = next[pos]
      next[pos] = next[nextPos]
      next[nextPos] = tmp
      return next
    })
  }, [updateActions])

  const disableAction = useCallback((pos: number) => {
    updateActions((actions) => {
      const target = actions[pos]
      if (!target) return actions
      setDisabledActions((current) => [...current, deepCopy(target)])
      return actions.filter((_item, idx) => idx !== pos)
    })
  }, [updateActions])

  const restoreLastDisabled = useCallback(() => {
    setDisabledActions((current) => {
      if (current.length === 0) return current
      const last = deepCopy(current[current.length - 1])
      const remaining = current.slice(0, -1)

      updateActions((actions) => {
        const usedIds = new Set(
          actions
            .map((a) => (typeof a.id === 'string' ? a.id : ''))
            .filter(Boolean)
        )
        const id = typeof last.id === 'string' ? last.id : 'action'
        last.id = ensureUniqueId(id, usedIds)
        return [...actions, last]
      })

      return remaining
    })
  }, [updateActions])

  const actionsEditable = isStaff && draftIsValidJson && isPlainObject(draftParsed)

  const [previewModal, setPreviewModal] = useState<{
    open: boolean
    title: string
    loading: boolean
    error: string | null
    payload: unknown | null
  }>({ open: false, title: 'Preview', loading: false, error: null, payload: null })

  const closePreview = useCallback(() => {
    setPreviewModal({ open: false, title: 'Preview', loading: false, error: null, payload: null })
  }, [])

  const openPreview = useCallback(async (pos: number) => {
    if (!actionsEditable) return
    const parsed = draftParsed
    if (!parsed || typeof parsed !== 'object') return
    const root = parsed as PlainObject
    const extensions = root.extensions
    if (!isPlainObject(extensions)) return
    const actions = (extensions as PlainObject).actions
    if (!Array.isArray(actions)) return
    const action = actions[pos]
    if (!isPlainObject(action)) return
    const executor = action.executor
    if (!isPlainObject(executor)) return

    setPreviewModal({ open: true, title: `Preview: ${String(action.id ?? 'action')}`, loading: true, error: null, payload: null })
    try {
      const response = await apiClient.post('/api/v2/ui/execution-plan/preview/', {
        executor,
        database_ids: [],
      })
      setPreviewModal((current) => ({ ...current, loading: false, payload: response.data as unknown }))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'preview failed'
      setPreviewModal((current) => ({ ...current, loading: false, error: msg }))
    }
  }, [actionsEditable, draftParsed])

  const columns: ColumnsType<ActionRow> = useMemo(() => ([
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 260,
      render: (value: string, record) => {
        const errs = saveErrorsByActionPos.get(record.pos) ?? []
        if (errs.length === 0) return <Text code>{value}</Text>
        return (
          <Space size={6}>
            <Text code>{value}</Text>
            <Tooltip title={(
              <Space direction="vertical" size={0}>
                {errs.slice(0, 6).map((msg, idx) => (
                  <Text key={`${idx}:${msg}`}>{msg}</Text>
                ))}
                {errs.length > 6 && <Text type="secondary">… and {errs.length - 6} more</Text>}
              </Space>
            )}>
              <Tag color="red">ERR</Tag>
            </Tooltip>
          </Space>
        )
      },
    },
    {
      title: 'Label',
      dataIndex: 'label',
      key: 'label',
      render: (value: string) => <Text>{value}</Text>,
    },
    {
      title: 'Contexts',
      dataIndex: 'contexts',
      key: 'contexts',
      width: 180,
      render: (value: string[]) => (
        <Space size={4} wrap>
          {value.map((ctx) => <Tag key={ctx}>{ctx}</Tag>)}
        </Space>
      ),
    },
    {
      title: 'Executor',
      dataIndex: 'executor_kind',
      key: 'executor_kind',
      width: 140,
      render: (value: string) => <Tag>{value || '-'}</Tag>,
    },
    {
      title: 'Ref',
      key: 'ref',
      width: 260,
      render: (_value, record) => {
        if (record.executor_kind === 'workflow') {
          return <Text code>{record.workflow_id || '-'}</Text>
        }
        if (record.executor_kind === 'ibcmd_cli' || record.executor_kind === 'designer_cli') {
          return <Text code>{`${record.driver || '-'} / ${record.command_id || '-'}`}</Text>
        }
        return '-'
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 230,
      render: (_value, record) => (
        <Space size={0}>
          <Button
            size="small"
            type="text"
            icon={<ArrowUpOutlined />}
            aria-label="Move up"
            onClick={() => moveAction(record.pos, -1)}
            disabled={!actionsEditable || record.pos === 0}
          />
          <Button
            size="small"
            type="text"
            icon={<ArrowDownOutlined />}
            aria-label="Move down"
            onClick={() => moveAction(record.pos, 1)}
            disabled={!actionsEditable || record.pos === actionRows.length - 1}
          />
          <Button
            size="small"
            type="text"
            icon={<EditOutlined />}
            aria-label="Edit"
            onClick={() => openEditor({ mode: 'edit', pos: record.pos })}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            aria-label="Preview"
            onClick={() => void openPreview(record.pos)}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            icon={<CopyOutlined />}
            aria-label="Copy"
            onClick={() => openEditor({ mode: 'copy', pos: record.pos })}
            disabled={!actionsEditable}
          />
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            aria-label="Disable"
            onClick={() => disableAction(record.pos)}
            disabled={!actionsEditable}
          />
        </Space>
      ),
    },
  ]), [actionRows.length, actionsEditable, disableAction, moveAction, openEditor, openPreview, saveErrorsByActionPos])

  const tabs = useMemo(() => ([
    {
      key: 'guided',
      label: 'Guided',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {!draftIsValidJson && (
            <Alert
              type="warning"
              showIcon
              message="Текущий draft не является валидным JSON"
              description="Перейдите в Raw режим, чтобы исправить JSON."
            />
          )}
          {saveErrorHints.length > 0 && (
            <Alert
              type="error"
              showIcon
              message="Server validation errors"
              description="См. список ошибок выше; строки таблицы с ошибками помечены ERR."
            />
          )}

          <Card size="small">
            <Space size="middle" wrap align="center">
              <Text strong>Actions:</Text>
              <Tag data-testid="action-catalog-actions-count">{actionRows.length}</Tag>
              {dirty && <Tag color="orange" data-testid="action-catalog-dirty">Unsaved changes</Tag>}
              <Button
                size="small"
                icon={<PlusOutlined />}
                onClick={() => openEditor({ mode: 'add' })}
                disabled={!actionsEditable}
                data-testid="action-catalog-add"
              >
                Add
              </Button>
              <Button
                size="small"
                icon={<RollbackOutlined />}
                onClick={restoreLastDisabled}
                disabled={!actionsEditable || disabledActions.length === 0}
                data-testid="action-catalog-restore-last"
              >
                Restore last disabled
              </Button>
              {disabledActions.length > 0 && (
                <Text type="secondary" data-testid="action-catalog-disabled-count">
                  Disabled: {disabledActions.length}
                </Text>
              )}
            </Space>
          </Card>

          <Table<ActionRow>
            data-testid="action-catalog-guided-table"
            size="small"
            bordered
            pagination={false}
            columns={columns}
            dataSource={actionRows}
            rowKey={(row) => row.pos}
            locale={{ emptyText: 'Нет actions' }}
          />
        </Space>
      ),
    },
    {
      key: 'raw',
      label: 'Raw JSON',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {dirty && <Tag color="orange" data-testid="action-catalog-dirty-raw">Unsaved changes</Tag>}
          {!rawValidation.ok && (
            <Alert
              type="error"
              showIcon
              message="Draft JSON is invalid"
              description={rawValidation.errors.join('; ')}
            />
          )}
          {rawValidation.ok && rawValidation.warnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message="Draft JSON warnings"
              description={rawValidation.warnings.join('; ')}
            />
          )}

          <Card size="small">
            <Space size="middle" wrap>
              <Text strong>Preview:</Text>
              <Tag>Actions: {rawValidation.actionsCount}</Tag>
              {dirty && (
                <Tag data-testid="action-catalog-diff-count">
                  Changes: {diffItems.length}
                </Tag>
              )}
              {dirty && (
                <Text type="secondary">
                  Added: {diffSummary.added}, Removed: {diffSummary.removed}, Changed: {diffSummary.changed}
                </Text>
              )}
            </Space>
          </Card>

          {dirty && diffItems.length > 0 && (
            <Table<DiffItem>
              data-testid="action-catalog-diff-table"
              size="small"
              bordered
              pagination={{ pageSize: 10, showSizeChanger: false }}
              rowKey={(row) => `${row.kind}:${row.path}`}
              columns={[
                { title: 'Path', dataIndex: 'path', key: 'path', width: 320, render: (v: string) => <Text code>{v || '(root)'}</Text> },
                { title: 'Kind', dataIndex: 'kind', key: 'kind', width: 110, render: (v: string) => <Tag>{v}</Tag> },
                { title: 'Before', dataIndex: 'before', key: 'before', render: (v: unknown) => <Text>{safeText(v)}</Text> },
                { title: 'After', dataIndex: 'after', key: 'after', render: (v: unknown) => <Text>{safeText(v)}</Text> },
              ]}
              dataSource={diffItems}
            />
          )}

          <LazyJsonCodeEditor
            id="action-catalog-raw"
            title={ACTION_CATALOG_KEY}
            value={draftRaw}
            onChange={setDraftRaw}
            height={520}
            readOnly={false}
            enableFormat
            enableCopy
            path="ui.action_catalog"
          />

          {serverRaw !== null && (
            <LazyJsonCodeEditor
              id="action-catalog-server"
              title="Server snapshot (read-only)"
              value={serverRaw}
              onChange={() => {}}
              height={280}
              readOnly
              enableFormat={false}
              enableCopy
              path="ui.action_catalog.server"
            />
          )}
        </Space>
      ),
    },
  ]), [actionRows, actionsEditable, columns, diffItems, diffSummary, dirty, disabledActions.length, draftIsValidJson, draftRaw, openEditor, rawValidation, restoreLastDisabled, saveErrorHints.length, serverRaw])

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div>
        <Space size="middle" align="center" wrap>
          <Title level={2} style={{ marginBottom: 0 }}>Action Catalog</Title>
          <Text type="secondary">
            RuntimeSetting <Text code>{ACTION_CATALOG_KEY}</Text>
          </Text>
          {dirty && <Tag color="orange">Draft</Tag>}
        </Space>
        {settingDescription && (
          <Text type="secondary" style={{ display: 'block' }}>{settingDescription}</Text>
        )}
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      {saveErrors.length > 0 && (
        <Alert
          type="error"
          showIcon
          message="Save failed"
              description={(
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {saveErrorHints.map((item, idx) => (
                <li key={`${idx}:${item.message}`}>
                  <Text>{item.message}</Text>
                  {item.action_id && (
                    <Text type="secondary">{` (action_id=${item.action_id})`}</Text>
                  )}
                </li>
              ))}
            </ul>
          )}
        />
      )}
      {saveSuccess && (
        <Alert
          type="success"
          showIcon
          closable
          message="Saved"
          onClose={() => setSaveSuccess(false)}
        />
      )}

      <Card size="small">
        <Space wrap>
          <Button onClick={loadCatalog} disabled={loading || dirty} data-testid="action-catalog-reload">
            Reload
          </Button>
          <Button
            type="primary"
            onClick={() => void handleSave()}
            disabled={!canSave}
            loading={saving}
            data-testid="action-catalog-save"
          >
            Save
          </Button>
          {dirty && (
            <Text type="secondary">Reload disabled while draft has unsaved changes.</Text>
          )}
        </Space>
      </Card>

      {loading ? (
        <Card>
          <Spin />
        </Card>
      ) : (
        <Tabs
          activeKey={mode}
          onChange={(next) => setMode(next as ActionCatalogMode)}
          items={tabs}
        />
      )}

      <Modal
        title={editorTitle}
        open={editorOpen}
        onCancel={closeEditor}
        onOk={() => void submitEditor()}
        okText="Apply"
        okButtonProps={{ 'data-testid': 'action-catalog-editor-apply' }}
        destroyOnClose
      >
        <Form<ActionFormValues>
          form={form}
          layout="vertical"
          preserve={false}
          initialValues={editorValues ?? undefined}
        >
          <Form.Item
            label="ID"
            name="id"
            rules={[
              { required: true, message: 'ID is required' },
              { whitespace: true, message: 'ID is required' },
            ]}
          >
            <Input data-testid="action-catalog-editor-id" />
          </Form.Item>

          <Form.Item
            label="Label"
            name="label"
            rules={[
              { required: true, message: 'Label is required' },
              { whitespace: true, message: 'Label is required' },
            ]}
          >
            <Input data-testid="action-catalog-editor-label" />
          </Form.Item>

          <Form.Item
            label="Contexts"
            name="contexts"
            rules={[
              { required: true, message: 'At least one context is required' },
            ]}
          >
            <Select
              mode="multiple"
              options={ACTION_CONTEXT_OPTIONS}
              data-testid="action-catalog-editor-contexts"
            />
          </Form.Item>

          <Form.Item
            label="Executor kind"
            name={['executor', 'kind']}
            rules={[{ required: true, message: 'Executor kind is required' }]}
          >
            <Select
              options={EXECUTOR_KIND_OPTIONS}
              data-testid="action-catalog-editor-executor-kind"
              onChange={(next: ExecutorKind) => {
                if (next === 'workflow') {
                  form.setFieldValue(['executor', 'driver'], undefined)
                  form.setFieldValue(['executor', 'command_id'], undefined)
                  form.setFieldValue(['executor', 'workflow_id'], form.getFieldValue(['executor', 'workflow_id']) ?? '')
                  return
                }
                form.setFieldValue(['executor', 'workflow_id'], undefined)
                const currentDriver = form.getFieldValue(['executor', 'driver']) as unknown
                if (currentDriver !== 'cli' && currentDriver !== 'ibcmd') {
                  form.setFieldValue(['executor', 'driver'], next === 'designer_cli' ? 'cli' : 'ibcmd')
                }
                form.setFieldValue(['executor', 'command_id'], undefined)
              }}
            />
          </Form.Item>

          {editorKind === 'workflow' ? (
            <Form.Item
              label="workflow_id"
              name={['executor', 'workflow_id']}
              rules={[
                { required: true, message: 'workflow_id is required' },
                { whitespace: true, message: 'workflow_id is required' },
              ]}
            >
              {workflowTemplatesUnavailable ? (
                <Input
                  placeholder="Workflow templates unavailable — enter workflow_id manually"
                  data-testid="action-catalog-editor-workflow-id"
                />
              ) : (
                <Select
                  showSearch
                  options={workflowOptions}
                  loading={workflowTemplatesQuery.isLoading}
                  filterOption={false}
                  onSearch={(value) => setWorkflowSearch(value)}
                  placeholder={workflowTemplatesQuery.isLoading ? 'Loading workflow templates...' : 'Select workflow template'}
                  data-testid="action-catalog-editor-workflow-id"
                  notFoundContent={workflowTemplatesQuery.isError ? 'Failed to load workflow templates' : 'No templates'}
                />
              )}
            </Form.Item>
          ) : (
            <Space size="middle" style={{ width: '100%' }} align="start">
              <Form.Item
                label="driver"
                name={['executor', 'driver']}
                rules={[{ required: true, message: 'driver is required' }]}
                style={{ flex: 1 }}
              >
                <Select
                  options={DRIVER_OPTIONS}
                  data-testid="action-catalog-editor-driver"
                  onChange={() => {
                    form.setFieldValue(['executor', 'command_id'], undefined)
                  }}
                />
              </Form.Item>
              <Form.Item
                label="command_id"
                name={['executor', 'command_id']}
                rules={[{ required: true, message: 'command_id is required' }]}
                style={{ flex: 2 }}
              >
                {driverCatalogUnavailable ? (
                  <Input
                    placeholder="Driver catalog unavailable — enter command_id manually"
                    data-testid="action-catalog-editor-command-id"
                  />
                ) : (
                  <Select
                    showSearch
                    options={commandOptions}
                    loading={commandsQuery.isLoading}
                    placeholder={commandsQuery.isLoading ? 'Loading driver catalog...' : 'Select command_id'}
                    optionFilterProp="label"
                    data-testid="action-catalog-editor-command-id"
                    notFoundContent={commandsQuery.isError ? 'Failed to load driver catalog' : 'No commands'}
                  />
                )}
              </Form.Item>
            </Space>
          )}

          <Card size="small" style={{ marginBottom: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && (
                <Form.Item
                  label="additional_args"
                  name={['executor', 'additional_args']}
                  tooltip="Для designer_cli это args; для ibcmd_cli — дополнительные argv-параметры."
                >
                  <Select
                    mode="tags"
                    tokenSeparators={['\n', ' ']}
                    placeholder="Enter args (space/newline-separated)"
                    data-testid="action-catalog-editor-additional-args"
                  />
                </Form.Item>
              )}

              {editorKind === 'ibcmd_cli' && (
                <Form.Item label="mode" name={['executor', 'mode']}>
                  <Select options={MODE_OPTIONS} data-testid="action-catalog-editor-mode" />
                </Form.Item>
              )}

              <Form.Item
                label="params (JSON object)"
                name={['executor', 'params_json']}
                rules={[
                  {
                    validator: async (_rule, value) => {
                      const raw = typeof value === 'string' ? value : ''
                      if (!raw.trim()) return
                      const parsed = parseJson(raw)
                      if (!isPlainObject(parsed)) {
                        throw new Error('params must be a JSON object')
                      }
                    },
                  },
                ]}
              >
                <Input.TextArea
                  rows={6}
                  placeholder="{ }"
                  data-testid="action-catalog-editor-params"
                />
              </Form.Item>

              {(editorKind === 'ibcmd_cli' || editorKind === 'designer_cli') && (
                <Form.Item label="stdin" name={['executor', 'stdin']}>
                  <Input.TextArea
                    rows={3}
                    placeholder="Optional stdin"
                    data-testid="action-catalog-editor-stdin"
                  />
                </Form.Item>
              )}

              <Space size="middle" wrap>
                <Form.Item
                  label="fixed.confirm_dangerous"
                  name={['executor', 'fixed', 'confirm_dangerous']}
                  valuePropName="checked"
                >
                  <Switch data-testid="action-catalog-editor-confirm-dangerous" />
                </Form.Item>
                <Form.Item
                  label="fixed.timeout_seconds"
                  name={['executor', 'fixed', 'timeout_seconds']}
                >
                  <InputNumber
                    min={1}
                    max={3600}
                    style={{ width: 160 }}
                    data-testid="action-catalog-editor-timeout"
                  />
                </Form.Item>
              </Space>
            </Space>
          </Card>

          {(commandsQuery.isError || workflowTemplatesQuery.isError) && (
            <Alert
              type="warning"
              showIcon
              message="Catalogs unavailable"
              description="Если списки команд/шаблонов не загрузились, можно ввести command_id/workflow_id вручную и сохранить — сервер проверит ссылки."
            />
          )}
        </Form>
      </Modal>

      <Modal
        title={previewModal.title}
        open={previewModal.open}
        onCancel={closePreview}
        footer={[
          <Button key="close" onClick={closePreview}>Close</Button>,
        ]}
        width={900}
      >
        {previewModal.loading ? (
          <Spin />
        ) : previewModal.error ? (
          <Alert type="error" showIcon message="Preview failed" description={previewModal.error} />
        ) : (
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(previewModal.payload, null, 2)}
          </pre>
        )}
      </Modal>
    </Space>
  )
}
