import { describe, expect, it } from 'vitest'

import { buildApiErrorNotificationKey, shouldDispatchGlobalApiError } from '../apiErrorPolicy'

describe('apiErrorPolicy', () => {
  it('builds a stable dedupe key for repeated background 429 errors', () => {
    const a = buildApiErrorNotificationKey({
      status: 429,
      code: 'RATE_LIMIT',
      method: 'get',
      path: '/api/v2/decisions/',
      errorPolicy: 'background',
    })
    const b = buildApiErrorNotificationKey({
      status: 429,
      code: 'RATE_LIMIT',
      method: 'get',
      path: '/api/v2/decisions/',
      errorPolicy: 'background',
    })

    expect(a).toBe(b)
    expect(a).not.toContain('Date.now')
  })

  it('suppresses global notifications for page-scoped failures', () => {
    expect(shouldDispatchGlobalApiError({ errorPolicy: 'page', skipGlobalError: false })).toBe(false)
    expect(shouldDispatchGlobalApiError({ errorPolicy: 'silent', skipGlobalError: false })).toBe(false)
  })

  it('keeps global notifications enabled for background and explicit global policies', () => {
    expect(shouldDispatchGlobalApiError({ errorPolicy: 'background', skipGlobalError: false })).toBe(true)
    expect(shouldDispatchGlobalApiError({ errorPolicy: 'global', skipGlobalError: false })).toBe(true)
  })
})
