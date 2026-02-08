import type { PlainObject } from '../actionCatalogTypes'
import { isPlainObject, isValidUuid, normalizeActionId } from '../actionCatalogUtils'

const CAPABILITY_RE = /^[a-z0-9_-]+(\.[a-z0-9_-]+)+$/

type JsonObject = Record<string, unknown>

type ActionCatalogEditorCapabilityHints = {
  fixed_schema?: unknown
  target_binding_schema?: unknown
}

export type ActionCatalogEditorHintsLike = {
  capabilities?: Record<string, ActionCatalogEditorCapabilityHints> | unknown
}

export type ActionCatalogValidationResult = {
  ok: boolean
  errors: string[]
  warnings: string[]
  actionsCount: number
}

type ActionCatalogValidationOptions = {
  editorHints?: ActionCatalogEditorHintsLike | null
}

const getObject = (value: unknown): JsonObject | null => (
  isPlainObject(value) ? value as JsonObject : null
)

const getString = (value: unknown): string | null => (
  typeof value === 'string' ? value.trim() || null : null
)

const getArrayOfStrings = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.length > 0)
}

const schemaAdditionalPropsAllowed = (schema: JsonObject): boolean => {
  const raw = schema.additionalProperties
  if (raw === false) return false
  return true
}

const schemaProperties = (schema: JsonObject): Record<string, JsonObject> => {
  const raw = getObject(schema.properties)
  if (!raw) return {}
  const out: Record<string, JsonObject> = {}
  for (const [key, value] of Object.entries(raw)) {
    const parsed = getObject(value)
    if (parsed) out[key] = parsed
  }
  return out
}

const validateBySchema = (
  value: unknown,
  schema: JsonObject,
  path: string,
  errors: string[]
) => {
  const schemaType = getString(schema.type)
  if (!schemaType) return

  if (schemaType === 'boolean') {
    if (typeof value !== 'boolean') errors.push(`${path}: must be a boolean`)
    return
  }

  if (schemaType === 'string') {
    if (typeof value !== 'string') errors.push(`${path}: must be a string`)
    return
  }

  if (schemaType === 'number') {
    if (typeof value !== 'number' || !Number.isFinite(value)) errors.push(`${path}: must be a number`)
    return
  }

  if (schemaType === 'integer') {
    if (typeof value !== 'number' || !Number.isInteger(value)) errors.push(`${path}: must be an integer`)
    return
  }

  if (schemaType !== 'object') return

  const objectValue = getObject(value)
  if (!objectValue) {
    errors.push(`${path}: must be an object`)
    return
  }

  const props = schemaProperties(schema)
  const knownKeys = new Set(Object.keys(props))
  if (!schemaAdditionalPropsAllowed(schema)) {
    for (const key of Object.keys(objectValue)) {
      if (!knownKeys.has(key)) errors.push(`${path}: unknown key: ${key}`)
    }
  }

  const required = getArrayOfStrings(schema.required)
  for (const requiredKey of required) {
    if (objectValue[requiredKey] === undefined) {
      errors.push(`${path}.${requiredKey}: is required`)
    }
  }

  for (const [key, propSchema] of Object.entries(props)) {
    const nextValue = objectValue[key]
    if (nextValue === undefined) continue
    validateBySchema(nextValue, propSchema, `${path}.${key}`, errors)
  }
}

const getCapabilityFixedSchema = (
  capability: string | null,
  options: ActionCatalogValidationOptions
): JsonObject | null => {
  if (!capability) return null
  const capabilities = getObject(options.editorHints?.capabilities)
  if (!capabilities) return null
  const capabilityHints = getObject(capabilities[capability])
  if (!capabilityHints) return null
  return getObject(capabilityHints.fixed_schema)
}

const getCapabilityTargetBindingSchema = (
  capability: string | null,
  options: ActionCatalogValidationOptions
): JsonObject | null => {
  if (!capability) return null
  const capabilities = getObject(options.editorHints?.capabilities)
  if (!capabilities) return null
  const capabilityHints = getObject(capabilities[capability])
  if (!capabilityHints) return null
  return getObject(capabilityHints.target_binding_schema)
}

export const validateActionCatalogDraft = (
  draftParsed: unknown,
  options: ActionCatalogValidationOptions = {}
): ActionCatalogValidationResult => {
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
    if (!isPlainObject(action)) {
      errors.push(`extensions.actions[${idx}]: must be an object`)
      continue
    }

    for (const key of Object.keys(action)) {
      if (key !== 'id' && key !== 'capability' && key !== 'label' && key !== 'contexts' && key !== 'executor') {
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

    const capability = normalizeActionId(action.capability)
    if (capability && !CAPABILITY_RE.test(capability)) {
      errors.push(`extensions.actions[${idx}].capability: must be a namespaced string (e.g. extensions.list)`)
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
        && key !== 'target_binding'
      ) {
        errors.push(`extensions.actions[${idx}].executor: unknown key: ${key}`)
      }
    }

    const kind = normalizeActionId(executor.kind)
    if (kind !== 'ibcmd_cli' && kind !== 'designer_cli' && kind !== 'workflow') {
      errors.push(`extensions.actions[${idx}].executor.kind: must be one of ibcmd_cli, designer_cli, workflow`)
      continue
    }

    if (executor.connection !== undefined) {
      errors.push(`extensions.actions[${idx}].executor.connection: is not supported (configure per-database ibcmd connection profile instead)`)
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
        if (fixed.confirm_dangerous !== undefined && typeof fixed.confirm_dangerous !== 'boolean') {
          errors.push(`extensions.actions[${idx}].executor.fixed.confirm_dangerous: must be a boolean`)
        }
        if (fixed.timeout_seconds !== undefined) {
          const timeout = fixed.timeout_seconds
          if (typeof timeout !== 'number' || !Number.isInteger(timeout) || timeout <= 0) {
            errors.push(`extensions.actions[${idx}].executor.fixed.timeout_seconds: must be a positive integer`)
          }
        }

        const fixedSchema = getCapabilityFixedSchema(capability, options)
        if (fixedSchema) {
          validateBySchema(fixed, fixedSchema, `extensions.actions[${idx}].executor.fixed`, errors)
        }
      }
    }

    const targetBindingSchema = getCapabilityTargetBindingSchema(capability, options)
    if (targetBindingSchema) {
      const targetBinding = executor.target_binding
      if (targetBinding === undefined) {
        errors.push(`extensions.actions[${idx}].executor.target_binding: is required`)
      } else {
        validateBySchema(targetBinding, targetBindingSchema, `extensions.actions[${idx}].executor.target_binding`, errors)
      }
    } else if (executor.target_binding !== undefined && !isPlainObject(executor.target_binding)) {
      errors.push(`extensions.actions[${idx}].executor.target_binding: must be an object`)
    }
  }

  return { ok: errors.length === 0, errors, warnings, actionsCount: actions.length }
}
