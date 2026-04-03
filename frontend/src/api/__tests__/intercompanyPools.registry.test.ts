import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGetPoolsMasterDataRegistry = vi.fn()

vi.mock('../generated/v2/v2', () => ({
  getV2: () => ({
    getPoolsMasterDataRegistry: mockGetPoolsMasterDataRegistry,
  }),
}))

import { getPoolMasterDataRegistry } from '../intercompanyPools'

describe('intercompanyPools registry api wrapper', () => {
  beforeEach(() => {
    mockGetPoolsMasterDataRegistry.mockReset()
  })

  it('delegates registry reads to the generated v2 client without handwritten response remapping', async () => {
    const payload = {
      contract_version: 'pool_master_data_registry.v1',
      count: 1,
      entries: [
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
            qualifier_options: ['organization'],
          },
          bootstrap_contract: { enabled: true, dependency_order: 10 },
          runtime_consumers: ['bindings', 'token_catalog'],
        },
      ],
    }
    mockGetPoolsMasterDataRegistry.mockResolvedValue(payload)

    const result = await getPoolMasterDataRegistry()

    expect(mockGetPoolsMasterDataRegistry).toHaveBeenCalledWith({ skipGlobalError: true })
    expect(result).toEqual(payload)
  })
})
