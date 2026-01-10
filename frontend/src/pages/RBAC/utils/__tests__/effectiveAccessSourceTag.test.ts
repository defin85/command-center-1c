import { describe, it, expect } from 'vitest'

import { getEffectiveAccessSourceTagColor } from '../effectiveAccessSourceTag'

describe('getEffectiveAccessSourceTagColor', () => {
  it('maps known sources to tag colors', () => {
    expect(getEffectiveAccessSourceTagColor('direct')).toBe('blue')
    expect(getEffectiveAccessSourceTagColor('group')).toBe('purple')
  })

  it('maps other sources to gold', () => {
    expect(getEffectiveAccessSourceTagColor('cluster')).toBe('gold')
    expect(getEffectiveAccessSourceTagColor('database')).toBe('gold')
    expect(getEffectiveAccessSourceTagColor('unknown')).toBe('gold')
  })
})

