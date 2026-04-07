import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PoolMasterDataRegistryEntry } from '../../../../api/intercompanyPools'

const mockListMasterDataParties = vi.fn()
const mockListMasterDataItems = vi.fn()
const mockListMasterDataContracts = vi.fn()
const mockListMasterDataTaxProfiles = vi.fn()
const mockListMasterDataGlAccounts = vi.fn()

vi.mock('../../../../api/intercompanyPools', async () => {
  const actual = await vi.importActual<typeof import('../../../../api/intercompanyPools')>(
    '../../../../api/intercompanyPools'
  )
  return {
    ...actual,
    listMasterDataParties: (...args: unknown[]) => mockListMasterDataParties(...args),
    listMasterDataItems: (...args: unknown[]) => mockListMasterDataItems(...args),
    listMasterDataContracts: (...args: unknown[]) => mockListMasterDataContracts(...args),
    listMasterDataTaxProfiles: (...args: unknown[]) => mockListMasterDataTaxProfiles(...args),
    listMasterDataGlAccounts: (...args: unknown[]) => mockListMasterDataGlAccounts(...args),
  }
})

import {
  getSupportedPoolMasterDataTokenEntityOptions,
  loadPoolMasterDataTokenCatalog,
} from '../tokenCatalog'

const registryEntries: PoolMasterDataRegistryEntry[] = [
  {
    entity_type: 'party',
    label: 'Party',
    kind: 'canonical',
    display_order: 10,
    binding_scope_fields: ['canonical_id', 'database_id', 'ib_catalog_kind'],
    capabilities: {
      direct_binding: true,
      token_exposure: true,
      bootstrap_import: true,
      outbox_fanout: true,
      sync_outbound: true,
      sync_inbound: true,
      sync_reconcile: true,
    },
    token_contract: {
      enabled: true,
      qualifier_kind: 'ib_catalog_kind',
      qualifier_required: true,
      qualifier_options: ['organization', 'counterparty'],
    },
    bootstrap_contract: { enabled: true, dependency_order: 10 },
    runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
  },
  {
    entity_type: 'item',
    label: 'Item',
    kind: 'canonical',
    display_order: 20,
    binding_scope_fields: ['canonical_id', 'database_id'],
    capabilities: {
      direct_binding: true,
      token_exposure: true,
      bootstrap_import: true,
      outbox_fanout: true,
      sync_outbound: true,
      sync_inbound: true,
      sync_reconcile: true,
    },
    token_contract: {
      enabled: true,
      qualifier_kind: 'none',
      qualifier_required: false,
      qualifier_options: [],
    },
    bootstrap_contract: { enabled: true, dependency_order: 20 },
    runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
  },
  {
    entity_type: 'gl_account',
    label: 'GL Account',
    kind: 'canonical',
    display_order: 25,
    binding_scope_fields: ['canonical_id', 'database_id', 'chart_identity'],
    capabilities: {
      direct_binding: true,
      token_exposure: true,
      bootstrap_import: true,
      outbox_fanout: false,
      sync_outbound: false,
      sync_inbound: false,
      sync_reconcile: false,
    },
    token_contract: {
      enabled: true,
      qualifier_kind: 'none',
      qualifier_required: false,
      qualifier_options: [],
    },
    bootstrap_contract: { enabled: true, dependency_order: 25 },
    runtime_consumers: ['bindings', 'bootstrap_import', 'token_catalog', 'token_parser'],
  },
  {
    entity_type: 'contract',
    label: 'Contract',
    kind: 'canonical',
    display_order: 30,
    binding_scope_fields: ['canonical_id', 'database_id', 'owner_counterparty_canonical_id'],
    capabilities: {
      direct_binding: true,
      token_exposure: true,
      bootstrap_import: true,
      outbox_fanout: true,
      sync_outbound: true,
      sync_inbound: true,
      sync_reconcile: true,
    },
    token_contract: {
      enabled: true,
      qualifier_kind: 'owner_counterparty_canonical_id',
      qualifier_required: true,
      qualifier_options: [],
    },
    bootstrap_contract: { enabled: true, dependency_order: 30 },
    runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
  },
]

describe('pool master-data token catalog adapter', () => {
  beforeEach(() => {
    mockListMasterDataParties.mockReset()
    mockListMasterDataItems.mockReset()
    mockListMasterDataContracts.mockReset()
    mockListMasterDataTaxProfiles.mockReset()
    mockListMasterDataGlAccounts.mockReset()

    mockListMasterDataParties.mockResolvedValue({
      parties: [
        {
          canonical_id: 'party-001',
          name: 'Party One',
          is_counterparty: true,
        },
        {
          canonical_id: 'party-002',
          name: 'Party Two',
          is_counterparty: false,
        },
      ],
    })
    mockListMasterDataItems.mockResolvedValue({
      items: [
        {
          canonical_id: 'item-001',
          name: 'Item One',
        },
      ],
    })
    mockListMasterDataContracts.mockResolvedValue({
      contracts: [
        {
          canonical_id: 'contract-001',
          name: 'Contract One',
          owner_counterparty_canonical_id: 'party-001',
        },
      ],
    })
    mockListMasterDataTaxProfiles.mockResolvedValue({
      tax_profiles: [],
    })
    mockListMasterDataGlAccounts.mockResolvedValue({
      gl_accounts: [
        {
          canonical_id: 'gl-account-001',
          code: '10.01',
          name: 'Main Account',
          chart_identity: 'ChartOfAccounts_Main',
        },
      ],
    })
  })

  it('loads shipped token catalogs from registry-published entity types through one compatibility adapter', async () => {
    const result = await loadPoolMasterDataTokenCatalog(registryEntries)

    expect(mockListMasterDataParties).toHaveBeenCalledWith({ limit: 200, offset: 0 })
    expect(mockListMasterDataItems).toHaveBeenCalledWith({ limit: 200, offset: 0 })
    expect(mockListMasterDataGlAccounts).toHaveBeenCalledWith({ limit: 200, offset: 0 })
    expect(mockListMasterDataContracts).toHaveBeenCalledWith({ limit: 200, offset: 0 })
    expect(result.options_by_entity_type.party).toEqual([{ value: 'party-001', label: 'party-001 - Party One' }, { value: 'party-002', label: 'party-002 - Party Two' }])
    expect(result.options_by_entity_type.item).toEqual([{ value: 'item-001', label: 'item-001 - Item One' }])
    expect(result.options_by_entity_type.gl_account).toEqual([
      {
        value: 'gl-account-001',
        label: 'gl-account-001 - Main Account (10.01 · ChartOfAccounts_Main)',
      },
    ])
    expect(result.options_by_entity_type.contract).toEqual([{ value: 'contract-001', label: 'contract-001 - Contract One' }])
    expect(result.counterparty_options).toEqual([{ value: 'party-001', label: 'party-001 - Party One' }])
    expect(result.contract_owner_by_canonical_id).toEqual({ 'contract-001': 'party-001' })
    expect(result.unsupported_entity_types).toEqual([])
  })

  it('surfaces registry-published token entities that do not yet have a compatibility loader', async () => {
    const registryEntriesWithUnsupportedType: PoolMasterDataRegistryEntry[] = [
      ...registryEntries,
      {
        entity_type: 'cost_center',
        label: 'Cost Center',
        kind: 'canonical',
        display_order: 40,
        binding_scope_fields: ['canonical_id', 'database_id', 'ib_catalog_kind'],
        capabilities: {
          direct_binding: false,
          token_exposure: true,
          bootstrap_import: false,
          outbox_fanout: false,
          sync_outbound: false,
          sync_inbound: false,
          sync_reconcile: false,
        },
        token_contract: {
          enabled: true,
          qualifier_kind: 'ib_catalog_kind',
          qualifier_required: true,
          qualifier_options: ['vendor'],
        },
        bootstrap_contract: { enabled: false, dependency_order: null },
        runtime_consumers: ['token_catalog', 'token_parser'],
      },
    ]
    const result = await loadPoolMasterDataTokenCatalog(registryEntriesWithUnsupportedType)

    expect(result.unsupported_entity_types).toEqual(['cost_center'])
    expect(
      getSupportedPoolMasterDataTokenEntityOptions(registryEntriesWithUnsupportedType, result).map((item) => item.value)
    ).toEqual(['party', 'item', 'gl_account', 'contract'])
  })
})
