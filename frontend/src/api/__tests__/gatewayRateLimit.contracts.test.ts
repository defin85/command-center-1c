import { describe, expectTypeOf, it } from 'vitest'

import type { ErrorResponse, GatewayRateLimitClass, TooManyRequestsResponse } from '../generated-gateway/model'

type Extends<T, U> = T extends U ? true : false

describe('api gateway rate-limit contract parity', () => {
  it('keeps generated gateway error envelopes aligned with class-aware 429 metadata', () => {
    expectTypeOf<Extends<ErrorResponse['request_id'], string | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<ErrorResponse['ui_action_id'], string | undefined>>().toEqualTypeOf<true>()

    expectTypeOf<Extends<TooManyRequestsResponse['rate_limit_class'], GatewayRateLimitClass>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<TooManyRequestsResponse['retry_after_seconds'], number>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<TooManyRequestsResponse['budget_scope'], string>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<TooManyRequestsResponse['request_id'], string>>().toEqualTypeOf<true>()
  })
})
