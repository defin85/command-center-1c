import type { PlainObject } from '../actionCatalogTypes'
import { isPlainObject, isValidUuid, normalizeActionId } from '../actionCatalogUtils'

export type ActionCatalogValidationResult = {
  ok: boolean
  errors: string[]
  warnings: string[]
  actionsCount: number
}

export const validateActionCatalogDraft = (draftParsed: unknown): ActionCatalogValidationResult => {
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
        for (const key of Object.keys(fixed)) {
          if (key !== 'confirm_dangerous' && key !== 'timeout_seconds') {
            errors.push(`extensions.actions[${idx}].executor.fixed: unknown key: ${key}`)
          }
        }
      }
    }
  }

  return { ok: errors.length === 0, errors, warnings, actionsCount: actions.length }
}
