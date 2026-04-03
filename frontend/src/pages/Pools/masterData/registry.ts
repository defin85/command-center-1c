import type {
  PoolMasterBindingCatalogKind,
  PoolMasterDataEntityType,
  PoolMasterDataRegistryEntry,
} from '../../../api/intercompanyPools'

export const MASTER_DATA_TOKEN_PREFIX = 'master_data.'

export type PoolMasterDataRegistryOption<T extends string> = {
  value: T
  label: string
}

export type ParsedMasterDataToken = {
  entity_type: PoolMasterDataEntityType
  canonical_id: string
  qualifier_kind: 'none' | 'ib_catalog_kind' | 'owner_counterparty_canonical_id'
  qualifier?: string
}

type MasterDataTokenSourceShape = {
  token_entity_type?: string
  token_canonical_id?: string
  token_party_role?: string
  token_owner_counterparty_canonical_id?: string
}

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

const asCanonicalEntityType = (value: string): PoolMasterDataEntityType | null => {
  if (value === 'party' || value === 'item' || value === 'contract' || value === 'tax_profile') {
    return value
  }
  return null
}

export function getDirectBindingEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<PoolMasterDataEntityType>> {
  return sortByDisplayOrder(
    entries.filter((entry) => entry.capabilities.direct_binding)
  )
    .map((entry) => {
      const entityType = asCanonicalEntityType(entry.entity_type)
      return entityType ? { value: entityType, label: entry.entity_type } : null
    })
    .filter(Boolean) as Array<PoolMasterDataRegistryOption<PoolMasterDataEntityType>>
}

export function getBootstrapEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<PoolMasterDataEntityType | 'binding'>> {
  return sortByBootstrapOrder(
    entries.filter((entry) => entry.capabilities.bootstrap_import)
  ).map((entry) => ({
    value: entry.entity_type,
    label: entry.entity_type,
  }))
}

export function getSyncEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<PoolMasterDataEntityType>> {
  return sortByDisplayOrder(
    entries.filter(
      (entry) => entry.capabilities.sync_outbound || entry.capabilities.sync_inbound || entry.capabilities.sync_reconcile
    )
  )
    .map((entry) => {
      const entityType = asCanonicalEntityType(entry.entity_type)
      return entityType ? { value: entityType, label: entry.entity_type } : null
    })
    .filter(Boolean) as Array<PoolMasterDataRegistryOption<PoolMasterDataEntityType>>
}

export function getTokenEntityOptions(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataRegistryOption<PoolMasterDataEntityType>> {
  return sortByDisplayOrder(
    entries.filter((entry) => entry.capabilities.token_exposure && entry.token_contract.enabled)
  )
    .map((entry) => {
      const entityType = asCanonicalEntityType(entry.entity_type)
      return entityType ? { value: entityType, label: entry.entity_type } : null
    })
    .filter(Boolean) as Array<PoolMasterDataRegistryOption<PoolMasterDataEntityType>>
}

export function getTokenQualifierOptions(
  entries: PoolMasterDataRegistryEntry[],
  entityType: string | undefined
): Array<PoolMasterDataRegistryOption<Exclude<PoolMasterBindingCatalogKind, ''>>> {
  const entry = entries.find((item) => item.entity_type === entityType)
  if (!entry || entry.token_contract.qualifier_kind !== 'ib_catalog_kind') {
    return []
  }
  return entry.token_contract.qualifier_options
    .filter((value): value is Exclude<PoolMasterBindingCatalogKind, ''> => (
      value === 'organization' || value === 'counterparty'
    ))
    .map((value) => ({ value, label: value }))
}

export function getDefaultDirectBindingEntityType(
  entries: PoolMasterDataRegistryEntry[]
): PoolMasterDataEntityType | undefined {
  return getDirectBindingEntityOptions(entries)[0]?.value
}

export function getDefaultBootstrapScope(
  entries: PoolMasterDataRegistryEntry[]
): Array<PoolMasterDataEntityType | 'binding'> {
  return getBootstrapEntityOptions(entries)
    .filter((entry) => entry.value !== 'binding')
    .slice(0, 2)
    .map((entry) => entry.value)
}

export function isMasterDataTokenLike(value: string): boolean {
  return value.trim().startsWith(MASTER_DATA_TOKEN_PREFIX)
}

export function parseMasterDataToken(
  value: string,
  entries: PoolMasterDataRegistryEntry[]
): ParsedMasterDataToken | null {
  const source = value.trim()
  if (!source.startsWith(MASTER_DATA_TOKEN_PREFIX)) {
    return null
  }
  const parts = source.split('.')
  if (parts[0] !== 'master_data' || parts[parts.length - 1] !== 'ref' || parts.length < 4) {
    return null
  }

  const entityType = asCanonicalEntityType(String(parts[1] || '').trim())
  if (!entityType) {
    return null
  }
  const entry = entries.find((item) => item.entity_type === entityType)
  if (!entry || !entry.capabilities.token_exposure || !entry.token_contract.enabled) {
    return null
  }

  const canonicalId = String(parts[2] || '').trim()
  if (!canonicalId) {
    return null
  }
  const qualifier = String(parts[3] || '').trim()

  if (entry.token_contract.qualifier_kind === 'none') {
    if (parts.length !== 4) {
      return null
    }
    return {
      entity_type: entityType,
      canonical_id: canonicalId,
      qualifier_kind: 'none',
    }
  }

  if (parts.length !== 5 || !qualifier) {
    return null
  }
  if (
    entry.token_contract.qualifier_options.length > 0
    && !entry.token_contract.qualifier_options.includes(qualifier)
  ) {
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
  const entityType = asCanonicalEntityType(String(sourceValue.token_entity_type ?? '').trim())
  const canonicalId = String(sourceValue.token_canonical_id ?? '').trim()
  if (!entityType || !canonicalId) {
    return null
  }
  const entry = entries.find((item) => item.entity_type === entityType)
  if (!entry || !entry.capabilities.token_exposure || !entry.token_contract.enabled) {
    return null
  }
  if (entry.token_contract.qualifier_kind === 'none') {
    return `${MASTER_DATA_TOKEN_PREFIX}${entityType}.${canonicalId}.ref`
  }

  const qualifier = entry.token_contract.qualifier_kind === 'ib_catalog_kind'
    ? String(sourceValue.token_party_role ?? '').trim()
    : String(sourceValue.token_owner_counterparty_canonical_id ?? '').trim()
  if (!qualifier) {
    return null
  }
  if (
    entry.token_contract.qualifier_options.length > 0
    && !entry.token_contract.qualifier_options.includes(qualifier)
  ) {
    return null
  }
  return `${MASTER_DATA_TOKEN_PREFIX}${entityType}.${canonicalId}.${qualifier}.ref`
}
