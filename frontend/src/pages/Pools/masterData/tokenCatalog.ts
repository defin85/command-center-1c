import {
  listMasterDataContracts,
  listMasterDataItems,
  listMasterDataParties,
  listMasterDataTaxProfiles,
  type PoolMasterDataRegistryEntry,
} from '../../../api/intercompanyPools'
import { getTokenEntityOptions } from './registry'

export type PoolMasterDataTokenCatalogOption = {
  value: string
  label: string
}

export type PoolMasterDataTokenCatalogSnapshot = {
  options_by_entity_type: Record<string, PoolMasterDataTokenCatalogOption[]>
  counterparty_options: PoolMasterDataTokenCatalogOption[]
  contract_owner_by_canonical_id: Record<string, string>
  unsupported_entity_types: string[]
}

type PoolMasterDataTokenCatalogLoaderResult = {
  entity_type: string
  options: PoolMasterDataTokenCatalogOption[]
  counterparty_options?: PoolMasterDataTokenCatalogOption[]
  contract_owner_by_canonical_id?: Record<string, string>
}

type PoolMasterDataTokenCatalogLoader = () => Promise<PoolMasterDataTokenCatalogLoaderResult>

export const EMPTY_POOL_MASTER_DATA_TOKEN_CATALOG: PoolMasterDataTokenCatalogSnapshot = {
  options_by_entity_type: {},
  counterparty_options: [],
  contract_owner_by_canonical_id: {},
  unsupported_entity_types: [],
}

const sortCatalogOptions = (
  options: PoolMasterDataTokenCatalogOption[],
): PoolMasterDataTokenCatalogOption[] => [...options].sort((left, right) => left.label.localeCompare(right.label))

const loadPartiesTokenCatalog: PoolMasterDataTokenCatalogLoader = async () => {
  const response = await listMasterDataParties({ limit: 200, offset: 0 })
  const parties = Array.isArray(response.parties) ? response.parties : []
  const options = sortCatalogOptions(
    parties.map((item) => ({
      value: item.canonical_id,
      label: `${item.canonical_id} - ${item.name}`,
    }))
  )
  const counterpartyOptions = sortCatalogOptions(
    parties
      .filter((item) => item.is_counterparty)
      .map((item) => ({
        value: item.canonical_id,
        label: `${item.canonical_id} - ${item.name}`,
      }))
  )
  return {
    entity_type: 'party',
    options,
    counterparty_options: counterpartyOptions,
  }
}

const loadItemsTokenCatalog: PoolMasterDataTokenCatalogLoader = async () => {
  const response = await listMasterDataItems({ limit: 200, offset: 0 })
  const items = Array.isArray(response.items) ? response.items : []
  return {
    entity_type: 'item',
    options: sortCatalogOptions(
      items.map((item) => ({
        value: item.canonical_id,
        label: `${item.canonical_id} - ${item.name}`,
      }))
    ),
  }
}

const loadContractsTokenCatalog: PoolMasterDataTokenCatalogLoader = async () => {
  const response = await listMasterDataContracts({ limit: 200, offset: 0 })
  const contracts = Array.isArray(response.contracts) ? response.contracts : []
  return {
    entity_type: 'contract',
    options: sortCatalogOptions(
      contracts.map((item) => ({
        value: item.canonical_id,
        label: `${item.canonical_id} - ${item.name}`,
      }))
    ),
    contract_owner_by_canonical_id: Object.fromEntries(
      contracts.map((item) => [item.canonical_id, String(item.owner_counterparty_canonical_id || '').trim()])
    ),
  }
}

const loadTaxProfilesTokenCatalog: PoolMasterDataTokenCatalogLoader = async () => {
  const response = await listMasterDataTaxProfiles({ limit: 200, offset: 0 })
  const taxProfiles = Array.isArray(response.tax_profiles) ? response.tax_profiles : []
  return {
    entity_type: 'tax_profile',
    options: sortCatalogOptions(
      taxProfiles.map((item) => ({
        value: item.canonical_id,
        label: item.canonical_id,
      }))
    ),
  }
}

const TOKEN_CATALOG_COMPATIBILITY_LOADERS: Record<string, PoolMasterDataTokenCatalogLoader> = {
  party: loadPartiesTokenCatalog,
  item: loadItemsTokenCatalog,
  contract: loadContractsTokenCatalog,
  tax_profile: loadTaxProfilesTokenCatalog,
}

export async function loadPoolMasterDataTokenCatalog(
  registryEntries: PoolMasterDataRegistryEntry[]
): Promise<PoolMasterDataTokenCatalogSnapshot> {
  const tokenEntityTypes = getTokenEntityOptions(registryEntries).map((option) => option.value)
  if (tokenEntityTypes.length === 0) {
    return EMPTY_POOL_MASTER_DATA_TOKEN_CATALOG
  }

  const unsupportedEntityTypes = tokenEntityTypes.filter(
    (entityType) => !TOKEN_CATALOG_COMPATIBILITY_LOADERS[entityType]
  )
  const supportedEntityTypes = tokenEntityTypes.filter(
    (entityType) => Boolean(TOKEN_CATALOG_COMPATIBILITY_LOADERS[entityType])
  )
  const results = await Promise.all(
    supportedEntityTypes.map((entityType) => TOKEN_CATALOG_COMPATIBILITY_LOADERS[entityType]())
  )

  const optionsByEntityType: Record<string, PoolMasterDataTokenCatalogOption[]> = {}
  let counterpartyOptions: PoolMasterDataTokenCatalogOption[] = []
  const contractOwnerByCanonicalId: Record<string, string> = {}

  for (const result of results) {
    optionsByEntityType[result.entity_type] = result.options
    if (result.counterparty_options) {
      counterpartyOptions = result.counterparty_options
    }
    if (result.contract_owner_by_canonical_id) {
      Object.assign(contractOwnerByCanonicalId, result.contract_owner_by_canonical_id)
    }
  }

  return {
    options_by_entity_type: optionsByEntityType,
    counterparty_options: counterpartyOptions,
    contract_owner_by_canonical_id: contractOwnerByCanonicalId,
    unsupported_entity_types: unsupportedEntityTypes,
  }
}

export function getPoolMasterDataTokenCatalogOptions(
  snapshot: PoolMasterDataTokenCatalogSnapshot,
  entityType: string
): PoolMasterDataTokenCatalogOption[] {
  return snapshot.options_by_entity_type[String(entityType || '').trim()] ?? []
}
