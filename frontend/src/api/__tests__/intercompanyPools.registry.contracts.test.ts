import { describe, expectTypeOf, it } from 'vitest'

import type {
  PoolMasterDataRegistryBootstrapContract,
  PoolMasterDataRegistryCapabilities,
  PoolMasterDataRegistryEntry,
  PoolMasterDataRegistryKind,
  PoolMasterDataRegistryResponse,
  PoolMasterDataRegistryTokenContract,
  PoolMasterDataTokenQualifierKind,
} from '../intercompanyPools'
import type { PoolMasterDataRegistryBootstrapContract as GeneratedPoolMasterDataRegistryBootstrapContract } from '../generated/model/poolMasterDataRegistryBootstrapContract'
import type { PoolMasterDataRegistryCapabilities as GeneratedPoolMasterDataRegistryCapabilities } from '../generated/model/poolMasterDataRegistryCapabilities'
import type { PoolMasterDataRegistryEntry as GeneratedPoolMasterDataRegistryEntry } from '../generated/model/poolMasterDataRegistryEntry'
import type { PoolMasterDataRegistryInspectResponse as GeneratedPoolMasterDataRegistryResponse } from '../generated/model/poolMasterDataRegistryInspectResponse'
import type { PoolMasterDataRegistryTokenContract as GeneratedPoolMasterDataRegistryTokenContract } from '../generated/model/poolMasterDataRegistryTokenContract'

type GeneratedPoolMasterDataRegistryKind = GeneratedPoolMasterDataRegistryEntry['kind']
type GeneratedPoolMasterDataTokenQualifierKind = GeneratedPoolMasterDataRegistryTokenContract['qualifier_kind']

describe('intercompanyPools registry contract parity', () => {
  it('keeps registry types aligned with generated OpenAPI contracts', () => {
    expectTypeOf<PoolMasterDataRegistryKind>().toMatchTypeOf<GeneratedPoolMasterDataRegistryKind>()
    expectTypeOf<GeneratedPoolMasterDataRegistryKind>().toMatchTypeOf<PoolMasterDataRegistryKind>()
    expectTypeOf<PoolMasterDataTokenQualifierKind>().toMatchTypeOf<GeneratedPoolMasterDataTokenQualifierKind>()
    expectTypeOf<GeneratedPoolMasterDataTokenQualifierKind>().toMatchTypeOf<PoolMasterDataTokenQualifierKind>()
    expectTypeOf<PoolMasterDataRegistryCapabilities>().toMatchTypeOf<GeneratedPoolMasterDataRegistryCapabilities>()
    expectTypeOf<GeneratedPoolMasterDataRegistryCapabilities>().toMatchTypeOf<PoolMasterDataRegistryCapabilities>()
    expectTypeOf<PoolMasterDataRegistryTokenContract>().toMatchTypeOf<GeneratedPoolMasterDataRegistryTokenContract>()
    expectTypeOf<GeneratedPoolMasterDataRegistryTokenContract>().toMatchTypeOf<PoolMasterDataRegistryTokenContract>()
    expectTypeOf<PoolMasterDataRegistryBootstrapContract>().toMatchTypeOf<GeneratedPoolMasterDataRegistryBootstrapContract>()
    expectTypeOf<GeneratedPoolMasterDataRegistryBootstrapContract>().toMatchTypeOf<PoolMasterDataRegistryBootstrapContract>()
    expectTypeOf<PoolMasterDataRegistryEntry>().toMatchTypeOf<GeneratedPoolMasterDataRegistryEntry>()
    expectTypeOf<GeneratedPoolMasterDataRegistryEntry>().toMatchTypeOf<PoolMasterDataRegistryEntry>()
    expectTypeOf<PoolMasterDataRegistryResponse>().toMatchTypeOf<GeneratedPoolMasterDataRegistryResponse>()
    expectTypeOf<GeneratedPoolMasterDataRegistryResponse>().toMatchTypeOf<PoolMasterDataRegistryResponse>()
  })
})
