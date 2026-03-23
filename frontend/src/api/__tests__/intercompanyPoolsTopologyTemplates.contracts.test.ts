import { describe, expectTypeOf, it } from 'vitest'

import type {
  CreatePoolTopologyTemplatePayload,
  CreatePoolTopologyTemplateRevisionPayload,
  PoolTopologyTemplate,
  PoolTopologyTemplateListResponse,
  PoolTopologyTemplateRevision,
  PoolTopologyTemplateMutationResponse,
} from '../intercompanyPools'
import type { TopologyTemplateCreateRequest } from '../generated/model/topologyTemplateCreateRequest'
import type { TopologyTemplate as GeneratedTopologyTemplate } from '../generated/model/topologyTemplate'
import type { TopologyTemplateListResponse as GeneratedTopologyTemplateListResponse } from '../generated/model/topologyTemplateListResponse'
import type { TopologyTemplateMutationResponse } from '../generated/model/topologyTemplateMutationResponse'
import type { TopologyTemplateRevision as GeneratedTopologyTemplateRevision } from '../generated/model/topologyTemplateRevision'
import type { TopologyTemplateRevisionCreateRequest } from '../generated/model/topologyTemplateRevisionCreateRequest'

describe('intercompanyPools topology template contract parity', () => {
  it('keeps list, entity, revision, create, revise, and mutation payloads aligned with generated API contracts', () => {
    expectTypeOf<PoolTopologyTemplate>().toMatchTypeOf<GeneratedTopologyTemplate>()
    expectTypeOf<GeneratedTopologyTemplate>().toMatchTypeOf<PoolTopologyTemplate>()
    expectTypeOf<PoolTopologyTemplateRevision>().toMatchTypeOf<GeneratedTopologyTemplateRevision>()
    expectTypeOf<GeneratedTopologyTemplateRevision>().toMatchTypeOf<PoolTopologyTemplateRevision>()
    expectTypeOf<PoolTopologyTemplateListResponse>().toMatchTypeOf<GeneratedTopologyTemplateListResponse>()
    expectTypeOf<GeneratedTopologyTemplateListResponse>().toMatchTypeOf<PoolTopologyTemplateListResponse>()
    expectTypeOf<CreatePoolTopologyTemplatePayload>().toMatchTypeOf<TopologyTemplateCreateRequest>()
    expectTypeOf<CreatePoolTopologyTemplateRevisionPayload>().toMatchTypeOf<TopologyTemplateRevisionCreateRequest>()
    expectTypeOf<PoolTopologyTemplateMutationResponse>().toMatchTypeOf<TopologyTemplateMutationResponse>()
  })
})
