import { describe, expectTypeOf, it } from 'vitest'

import type { UiIncidentSummaryPreview } from '../generated/model/uiIncidentSummaryPreview'

type Extends<T, U> = T extends U ? true : false

describe('ui incident telemetry generated contract parity', () => {
  it('keeps generated summary preview aligned with route intent observability fields', () => {
    expectTypeOf<Extends<UiIncidentSummaryPreview['surface_id'], string | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['control_id'], string | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['route_writer_owner'], string | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['write_reason'], string | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['navigation_mode'], string | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['caused_by_ui_action_id'], string | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['oscillating_keys'], string[] | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['writer_owners'], string[] | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['transition_count'], number | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['window_ms'], number | null | undefined>>().toEqualTypeOf<true>()
    expectTypeOf<Extends<UiIncidentSummaryPreview['param_diff'], Record<string, unknown> | undefined>>().toEqualTypeOf<true>()
  })
})
