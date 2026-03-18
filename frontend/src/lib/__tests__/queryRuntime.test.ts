import { describe, expect, it } from 'vitest'

import { getQueryPolicy, shouldRetryQueryError } from '../queryRuntime'

function makeError(status?: number, code?: string) {
  return {
    response: status ? { status } : undefined,
    code,
    name: code === 'ERR_CANCELED' ? 'CanceledError' : 'AxiosError',
  }
}

describe('queryRuntime', () => {
  it('never retries deterministic 4xx and 429 errors', () => {
    expect(shouldRetryQueryError(0, makeError(400))).toBe(false)
    expect(shouldRetryQueryError(0, makeError(404))).toBe(false)
    expect(shouldRetryQueryError(0, makeError(429))).toBe(false)
  })

  it('retries transient network and 5xx errors only within budget', () => {
    expect(shouldRetryQueryError(0, makeError(undefined, 'ERR_NETWORK'))).toBe(true)
    expect(shouldRetryQueryError(0, makeError(503))).toBe(true)
    expect(shouldRetryQueryError(1, makeError(503))).toBe(false)
  })

  it('does not retry canceled requests', () => {
    expect(shouldRetryQueryError(0, makeError(undefined, 'ERR_CANCELED'))).toBe(false)
  })

  it('marks policy metadata and disables focus/reconnect refetch for realtime-backed workloads', () => {
    const policy = getQueryPolicy('realtime-backed')

    expect(policy.meta?.queryPolicy).toBe('realtime-backed')
    expect(policy.refetchOnWindowFocus).toBe(false)
    expect(policy.refetchOnReconnect).toBe(false)
    expect(policy.retry(0, makeError(503))).toBe(false)
  })
})
