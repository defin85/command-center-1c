import type {
  OperationCatalogDefinition,
  OperationCatalogDefinitionInput,
  OperationCatalogExposure,
  OperationCatalogExposureInput,
  OperationCatalogExposureUpsertRequest,
} from '../../../api/operationCatalog'
import type { PlainObject } from '../actionCatalogTypes'
import { deepCopy, isPlainObject } from '../actionCatalogUtils'

export type OperationCatalogActionRecord = {
  exposure: OperationCatalogExposure
  definition: OperationCatalogDefinition
}

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string').map((item) => item.trim()).filter(Boolean)
}

const mergeExecutorPayload = (
  definition: OperationCatalogDefinition,
  exposure: OperationCatalogExposure
): PlainObject => {
  const payload = isPlainObject(definition.executor_payload) ? deepCopy(definition.executor_payload) : {}
  if (!isPlainObject(payload)) return {}

  const capabilityConfig = isPlainObject(exposure.capability_config) ? exposure.capability_config : {}
  const payloadFixed = isPlainObject(payload.fixed) ? payload.fixed : {}
  const cfgFixed = isPlainObject(capabilityConfig.fixed) ? capabilityConfig.fixed : {}
  const mergedFixed: PlainObject = {}
  for (const [key, value] of Object.entries(payloadFixed)) mergedFixed[key] = value
  for (const [key, value] of Object.entries(cfgFixed)) mergedFixed[key] = value
  if (capabilityConfig.apply_mask !== undefined) {
    mergedFixed.apply_mask = capabilityConfig.apply_mask
  }
  if (Object.keys(mergedFixed).length > 0) {
    payload.fixed = mergedFixed
  } else {
    delete payload.fixed
  }

  const targetBinding = capabilityConfig.target_binding
  if (isPlainObject(targetBinding)) {
    payload.target_binding = deepCopy(targetBinding)
  } else {
    delete payload.target_binding
  }

  if (typeof payload.kind !== 'string' || !payload.kind.trim()) {
    payload.kind = definition.executor_kind
  }
  return payload
}

export const buildActionFromOperationCatalogRecord = (record: OperationCatalogActionRecord): PlainObject => {
  const contexts = asStringArray(record.exposure.contexts)
  const action: PlainObject = {
    id: record.exposure.alias,
    label: record.exposure.name,
    contexts: contexts.length > 0 ? contexts : ['database_card'],
    executor: mergeExecutorPayload(record.definition, record.exposure),
  }
  if (record.exposure.description) {
    action.description = record.exposure.description
  }
  const capability = String(record.exposure.capability || '').trim()
  if (capability) {
    action.capability = capability
  }
  return action
}

export const buildCatalogFromOperationCatalogRecords = (records: OperationCatalogActionRecord[]): PlainObject => {
  const actions = records
    .slice()
    .sort((a, b) => (a.exposure.display_order ?? 0) - (b.exposure.display_order ?? 0) || a.exposure.alias.localeCompare(b.exposure.alias))
    .map((record) => buildActionFromOperationCatalogRecord(record))
  return {
    catalog_version: 1,
    extensions: {
      actions,
    },
  }
}

const splitExecutorForOperationCatalog = (executorRaw: unknown): {
  definitionPayload: PlainObject
  capabilityConfig: PlainObject
} => {
  const executor = isPlainObject(executorRaw) ? deepCopy(executorRaw) : {}
  if (!isPlainObject(executor)) {
    return { definitionPayload: {}, capabilityConfig: {} }
  }

  const capabilityConfig: PlainObject = {}
  const fixed = isPlainObject(executor.fixed) ? deepCopy(executor.fixed) : null
  if (isPlainObject(fixed)) {
    const fixedPayload = deepCopy(fixed)
    if (fixedPayload.apply_mask !== undefined) {
      capabilityConfig.apply_mask = fixedPayload.apply_mask
      delete fixedPayload.apply_mask
    }
    if (Object.keys(fixedPayload).length > 0) {
      capabilityConfig.fixed = fixedPayload
    }
  }

  const targetBinding = isPlainObject(executor.target_binding) ? deepCopy(executor.target_binding) : null
  if (isPlainObject(targetBinding)) {
    capabilityConfig.target_binding = targetBinding
  }

  delete executor.fixed
  delete executor.target_binding
  return {
    definitionPayload: executor,
    capabilityConfig,
  }
}

const asPositiveInt = (value: unknown, fallback: number): number => {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.max(0, Math.trunc(value))
  return fallback
}

export const buildOperationCatalogUpsertFromAction = (
  action: PlainObject,
  opts: {
    existing?: OperationCatalogActionRecord
    displayOrder: number
  }
): OperationCatalogExposureUpsertRequest | null => {
  const alias = typeof action.id === 'string' ? action.id.trim() : ''
  if (!alias) return null
  const label = typeof action.label === 'string' ? action.label.trim() : alias
  const description = typeof action.description === 'string' ? action.description : ''
  const capability = typeof action.capability === 'string' ? action.capability.trim() : ''
  const contexts = asStringArray(action.contexts)
  const { definitionPayload, capabilityConfig } = splitExecutorForOperationCatalog(action.executor)

  const fallbackKind = opts.existing?.definition.executor_kind ?? 'ibcmd_cli'
  const definitionKind = typeof definitionPayload.kind === 'string' && definitionPayload.kind.trim()
    ? String(definitionPayload.kind).trim()
    : fallbackKind

  const definition: OperationCatalogDefinitionInput = {
    tenant_scope: opts.existing?.definition.tenant_scope ?? 'global',
    executor_kind: definitionKind,
    executor_payload: definitionPayload,
    contract_version: opts.existing?.definition.contract_version ?? 1,
  }

  const exposure: OperationCatalogExposureInput = {
    surface: 'action_catalog',
    alias,
    tenant_id: opts.existing?.exposure.tenant_id ?? null,
    name: label,
    description,
    is_active: true,
    capability,
    contexts,
    display_order: asPositiveInt(opts.displayOrder, 0),
    capability_config: capabilityConfig,
    status: 'draft',
  }

  return {
    exposure_id: opts.existing?.exposure.id,
    definition_id: opts.existing?.definition.id ?? null,
    definition,
    exposure,
  }
}

export const buildOperationCatalogDisablePayload = (
  record: OperationCatalogActionRecord
): OperationCatalogExposureUpsertRequest => ({
  exposure_id: record.exposure.id,
  definition_id: record.definition.id,
  exposure: {
    surface: record.exposure.surface,
    alias: record.exposure.alias,
    tenant_id: record.exposure.tenant_id ?? null,
    name: record.exposure.name,
    description: record.exposure.description ?? '',
    is_active: false,
    capability: record.exposure.capability,
    contexts: asStringArray(record.exposure.contexts),
    display_order: asPositiveInt(record.exposure.display_order, 0),
    capability_config: isPlainObject(record.exposure.capability_config) ? deepCopy(record.exposure.capability_config) : {},
    status: 'draft',
  },
})
