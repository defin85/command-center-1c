import { describe, expect, it } from 'vitest'

import type { PoolMasterDataRegistryEntry } from '../../../../api/intercompanyPools'
import {
  buildMasterDataToken,
  getBootstrapEntityOptions,
  getDirectBindingEntityOptions,
  getSyncEntityOptions,
  getTokenEntityOptions,
  getTokenQualifierOptions,
  parseMasterDataToken,
} from '../registry'

const registryEntries: PoolMasterDataRegistryEntry[] = [
  {
    entity_type: 'contract',
    label: 'Contract',
    kind: 'canonical',
    display_order: 5,
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
    bootstrap_contract: { enabled: true, dependency_order: 40 },
    runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
  },
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
      direct_binding: false,
      token_exposure: true,
      bootstrap_import: true,
      outbox_fanout: true,
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
    bootstrap_contract: { enabled: true, dependency_order: 20 },
    runtime_consumers: ['bootstrap_import', 'token_catalog', 'token_parser'],
  },
  {
    entity_type: 'binding',
    label: 'Binding',
    kind: 'bootstrap_helper',
    display_order: 50,
    binding_scope_fields: [],
    capabilities: {
      direct_binding: false,
      token_exposure: false,
      bootstrap_import: true,
      outbox_fanout: false,
      sync_outbound: false,
      sync_inbound: false,
      sync_reconcile: false,
    },
    token_contract: {
      enabled: false,
      qualifier_kind: 'none',
      qualifier_required: false,
      qualifier_options: [],
    },
    bootstrap_contract: { enabled: true, dependency_order: 50 },
    runtime_consumers: ['bootstrap_import'],
  },
]

describe('pool master-data registry helpers', () => {
  it('derives UI options from registry capabilities and ordering', () => {
    expect(getDirectBindingEntityOptions(registryEntries).map((item) => item.value)).toEqual(['contract', 'party'])
    expect(getBootstrapEntityOptions(registryEntries).map((item) => item.value)).toEqual([
      'party',
      'item',
      'contract',
      'binding',
    ])
    expect(getSyncEntityOptions(registryEntries).map((item) => item.value)).toEqual(['contract', 'party'])
    expect(getTokenEntityOptions(registryEntries).map((item) => item.value)).toEqual([
      'contract',
      'party',
      'item',
    ])
    expect(getTokenQualifierOptions(registryEntries, 'party').map((item) => item.value)).toEqual([
      'organization',
      'counterparty',
    ])
  })

  it('parses and builds tokens using registry token contract', () => {
    expect(buildMasterDataToken({
      token_entity_type: 'party',
      token_canonical_id: 'party-001',
      token_party_role: 'organization',
    }, registryEntries)).toBe('master_data.party.party-001.organization.ref')

    expect(buildMasterDataToken({
      token_entity_type: 'contract',
      token_canonical_id: 'contract-001',
      token_owner_counterparty_canonical_id: 'party-002',
    }, registryEntries)).toBe('master_data.contract.contract-001.party-002.ref')

    expect(parseMasterDataToken('master_data.party.party-001.organization.ref', registryEntries)).toEqual({
      entity_type: 'party',
      canonical_id: 'party-001',
      qualifier_kind: 'ib_catalog_kind',
      qualifier: 'organization',
    })

    expect(parseMasterDataToken('master_data.item.item-001.ref', registryEntries)).toEqual({
      entity_type: 'item',
      canonical_id: 'item-001',
      qualifier_kind: 'none',
    })
  })
})
