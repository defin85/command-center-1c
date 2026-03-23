import { describe, expectTypeOf, it } from 'vitest'

import type {
  CreatePoolTopologyTemplatePayload,
  CreatePoolTopologyTemplateRevisionPayload,
  PoolTopologyTemplateMutationResponse,
} from '../intercompanyPools'
import type { TopologyTemplateCreateRequest } from '../generated/model/topologyTemplateCreateRequest'
import type { TopologyTemplateMutationResponse } from '../generated/model/topologyTemplateMutationResponse'
import type { TopologyTemplateRevisionCreateRequest } from '../generated/model/topologyTemplateRevisionCreateRequest'

describe('intercompanyPools topology template contract parity', () => {
  it('keeps create, revise, and mutation payloads aligned with generated API contracts', () => {
    expectTypeOf<CreatePoolTopologyTemplatePayload>().toMatchTypeOf<TopologyTemplateCreateRequest>()
    expectTypeOf<CreatePoolTopologyTemplateRevisionPayload>().toMatchTypeOf<TopologyTemplateRevisionCreateRequest>()
    expectTypeOf<PoolTopologyTemplateMutationResponse>().toMatchTypeOf<TopologyTemplateMutationResponse>()
  })
})
