import type {
  PoolMasterDataRegistryEntry,
} from '../../../api/intercompanyPools'

export const MASTER_DATA_TOKEN_PREFIX = 'master_data.'

export type PoolMasterDataRegistryOption<T extends string> = {
  value: T
  label: string
}

export type ParsedMasterDataToken = {
  entity_type: string
  canonical_id: string
  qualifier_kind: string
  qualifier?: string
}

type MasterDataTokenSourceShape = {
  token_entity_type?: string
  token_canonical_id?: string
  token_party_role?: string
  token_owner_counterparty_canonical_id?: string
}

const NON_PRESENTATION_SCOPE_FIELDS = new Set(['canonical_id', 'database_id'])

const sortByDisplayOrder = (entries: PoolMasterDataRegistryEntry[]): PoolMasterDataRegistryEntry[] => (
  [...entries].sort((left, right) => left.display_order - right.display_order)
)

const sortByBootstrapOrder = (entries: PoolMasterDataRegistryEntry[]): PoolMasterDataRegistryEntry[] => (
  [...entries].sort((left, right) => {
    const leftOrder = left.bootstrap_contract.dependency_order ?? Number.MAX_SAFE_INTEGER
    const rightOrder = right.bootstrap_contract.dependency_order ?? Number.MAX_SAFE_INTEGER
    return leftOrder - rightOrder || left.display_order - right.display_order
  })
)

const normalizeRegistryEntityType = (value: string | undefined): string | null => {
  const normalized = String(value ?? '').trim()
  return normalized ? normalized : null
}

const hasRegistryCapability = (
  entry: PoolMasterDataRegistryEntry,
  capability: string
): boolean => Boolean((entry.capabilities as unknown as Record<string, unknown>)[capability])

export function getRegistryEntryLabel(entry: PoolMasterDataRegistryEntry | null | undefined): string {
  const label = String(entry?.label ?? '').trim()
  if (label) {
    return label
  }
  return String(entry?.entity_type ?? '').trim()
}

export function findRegistryEntryByEntityType(
  entries: PoolMasterDataRegistryEntry[],
  entityType: string | undefined
): PoolMasterDataRegistryEntry | null {
  const normalizedEntityType = normalizeRegistryEntityType(entityType)
  if (!normalizedEntityType) {
    return null
  }
  return entries.find((entry) => entry.entity_type === normalizedEntityType) ?? null
}

export function getRegistryEntityLabel(
  entries: PoolMasterDataRegistryEntry[],
  entityType: string | undefined
): string {
  const entry = findRegistryEntryByEntityType(entries, entityType)
  return getRegistryEntryLabel(entry) || String(entityType ?? '').trim()
}

export function getDirectBindingEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<string>> {
  return sortByDisplayOrder(
    entries.filter((entry) => entry.capabilities.direct_binding)
  )
    .map((entry) => ({ value: entry.entity_type, label: getRegistryEntryLabel(entry) }))
}

export function getBootstrapEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<string>> {
  return sortByBootstrapOrder(
    entries.filter((entry) => entry.capabilities.bootstrap_import)
  ).map((entry) => ({
    value: entry.entity_type,
    label: getRegistryEntryLabel(entry),
  }))
}

export function getSyncEntityOptions(
  entries: PoolMasterDataRegistryEntry[],
  mode?: 'inbound' | 'outbound' | 'reconcile'
): Array<PoolMasterDataRegistryOption<string>> {
  return sortByDisplayOrder(
    entries.filter(
      (entry) => {
        if (mode === 'inbound') {
          return entry.capabilities.sync_inbound
        }
        if (mode === 'outbound') {
          return entry.capabilities.sync_outbound
        }
        if (mode === 'reconcile') {
          return entry.capabilities.sync_reconcile
        }
        return entry.capabilities.sync_outbound || entry.capabilities.sync_inbound || entry.capabilities.sync_reconcile
      }
    )
    )
    .map((entry) => ({ value: entry.entity_type, label: getRegistryEntryLabel(entry) }))
}

export function getDedupeEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<string>> {
  return sortByDisplayOrder(
    entries.filter((entry) => hasRegistryCapability(entry, 'cross_infobase_dedupe'))
  )
    .map((entry) => ({ value: entry.entity_type, label: getRegistryEntryLabel(entry) }))
}

export function getTokenEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<string>> {
  return sortByDisplayOrder(
    entries.filter((entry) => entry.capabilities.token_exposure && entry.token_contract.enabled)
  )
    .map((entry) => ({ value: entry.entity_type, label: getRegistryEntryLabel(entry) }))
}

export function getTokenQualifierOptions(
  entries: PoolMasterDataRegistryEntry[],
  entityType: string | undefined
): Array<PoolMasterDataRegistryOption<string>> {
  const entry = findRegistryEntryByEntityType(entries, entityType)
  if (!entry) {
    return []
  }
  return entry.token_contract.qualifier_options
    .map((value) => String(value).trim())
    .filter((value) => value.length > 0)
    .map((value) => ({ value, label: value }))
}

export function getDefaultDirectBindingEntityType(
  entries: PoolMasterDataRegistryEntry[]
): string | undefined {
  return getDirectBindingEntityOptions(entries)[0]?.value
}

export function getDefaultBootstrapScope(
  entries: PoolMasterDataRegistryEntry[]
): string[] {
  const bootstrapCandidates = sortByBootstrapOrder(
    entries.filter((entry) => entry.capabilities.bootstrap_import)
  )
  const preferredCandidates = bootstrapCandidates.filter((entry) => entry.kind === 'canonical')
  const defaults = preferredCandidates.length > 0 ? preferredCandidates : bootstrapCandidates
  return defaults.slice(0, 2).map((entry) => entry.entity_type)
}

export function getBindingScopePresentationFields(
  entries: PoolMasterDataRegistryEntry[],
  entityType: string | undefined
): string[] {
  const entry = findRegistryEntryByEntityType(entries, entityType)
  if (!entry) {
    return []
  }
  return entry.binding_scope_fields.filter((field) => !NON_PRESENTATION_SCOPE_FIELDS.has(field))
}

export function isMasterDataTokenLike(value: string): boolean {
  return value.trim().startsWith(MASTER_DATA_TOKEN_PREFIX)
}

export function parseMasterDataToken(
  value: string,
  entries: PoolMasterDataRegistryEntry[]
): ParsedMasterDataToken | null {
  const source = value.trim()
  if (!source.startsWith(MASTER_DATA_TOKEN_PREFIX) || !source.endsWith('.ref')) {
    return null
  }
  const body = source.slice(MASTER_DATA_TOKEN_PREFIX.length, -'.ref'.length)
  const separatorIndex = body.indexOf('.')
  if (separatorIndex <= 0 || separatorIndex === body.length - 1) {
    return null
  }
  const entityType = normalizeRegistryEntityType(body.slice(0, separatorIndex))
  if (!entityType) {
    return null
  }
  const entry = findRegistryEntryByEntityType(entries, entityType)
  if (!entry || !entry.capabilities.token_exposure || !entry.token_contract.enabled) {
    return null
  }
  const remainder = String(body.slice(separatorIndex + 1)).trim()
  if (!remainder) {
    return null
  }

  if (entry.token_contract.qualifier_kind === 'none') {
    return {
      entity_type: entityType,
      canonical_id: remainder,
      qualifier_kind: 'none',
    }
  }

  const qualifierOptions = entry.token_contract.qualifier_options
    .map((value) => String(value).trim())
    .filter((value) => value.length > 0)

  if (qualifierOptions.length > 0) {
    const matchedQualifier = [...qualifierOptions]
      .sort((left, right) => right.length - left.length)
      .find((option) => remainder.endsWith(`.${option}`))
    if (matchedQualifier) {
      const canonicalId = remainder.slice(0, -(matchedQualifier.length + 1)).trim()
      if (!canonicalId) {
        return null
      }
      return {
        entity_type: entityType,
        canonical_id: canonicalId,
        qualifier_kind: entry.token_contract.qualifier_kind,
        qualifier: matchedQualifier,
      }
    }
    if (entry.token_contract.qualifier_required) {
      return null
    }
    return {
      entity_type: entityType,
      canonical_id: remainder,
      qualifier_kind: entry.token_contract.qualifier_kind,
      qualifier: '',
    }
  }

  if (!entry.token_contract.qualifier_required) {
    return {
      entity_type: entityType,
      canonical_id: remainder,
      qualifier_kind: entry.token_contract.qualifier_kind,
      qualifier: '',
    }
  }

  const lastSeparatorIndex = remainder.lastIndexOf('.')
  if (lastSeparatorIndex <= 0 || lastSeparatorIndex === remainder.length - 1) {
    return null
  }
  const canonicalId = remainder.slice(0, lastSeparatorIndex).trim()
  const qualifier = remainder.slice(lastSeparatorIndex + 1).trim()
  if (!canonicalId || !qualifier) {
    return null
  }

  return {
    entity_type: entityType,
    canonical_id: canonicalId,
    qualifier_kind: entry.token_contract.qualifier_kind,
    qualifier,
  }
}

export function buildMasterDataToken(
  sourceValue: MasterDataTokenSourceShape,
  entries: PoolMasterDataRegistryEntry[]
): string | null {
  const entityType = normalizeRegistryEntityType(String(sourceValue.token_entity_type ?? '').trim())
  const canonicalId = String(sourceValue.token_canonical_id ?? '').trim()
  if (!entityType || !canonicalId) {
    return null
  }
  const entry = findRegistryEntryByEntityType(entries, entityType)
  if (!entry || !entry.capabilities.token_exposure || !entry.token_contract.enabled) {
    return null
  }
  if (entry.token_contract.qualifier_kind === 'none') {
    return `${MASTER_DATA_TOKEN_PREFIX}${entityType}.${canonicalId}.ref`
  }

  let qualifier = ''
  if (entry.token_contract.qualifier_options.length > 0) {
    qualifier = String(sourceValue.token_party_role ?? '').trim()
  } else if (entry.token_contract.qualifier_kind === 'owner_counterparty_canonical_id') {
    qualifier = String(sourceValue.token_owner_counterparty_canonical_id ?? '').trim()
  } else {
    return null
  }
  if (!qualifier) {
    return entry.token_contract.qualifier_required
      ? null
      : `${MASTER_DATA_TOKEN_PREFIX}${entityType}.${canonicalId}.ref`
  }
  if (
    entry.token_contract.qualifier_options.length > 0
    && !entry.token_contract.qualifier_options.includes(qualifier)
  ) {
    return null
  }
  return `${MASTER_DATA_TOKEN_PREFIX}${entityType}.${canonicalId}.${qualifier}.ref`
}
