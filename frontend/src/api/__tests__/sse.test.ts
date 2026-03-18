import { afterEach, describe, expect, it, vi } from 'vitest'

import { openSseStream } from '../sse'

describe('openSseStream', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('preserves machine-readable retry metadata from non-ok JSON responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      success: false,
      error: {
        code: 'STREAM_ALREADY_ACTIVE',
        message: 'Database stream lease already active for this client session',
        details: {
          retry_after: 17,
          client_instance_id: 'browser-1',
          active_session_id: 'session-a',
          active_lease_id: 'lease-a',
          recovery_supported: true,
        },
      },
    }), {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': '17',
      },
    }))

    const error = await new Promise<unknown>((resolve) => {
      openSseStream('/api/v2/databases/stream/?ticket=ticket-1', {
        onMessage: vi.fn(),
        onError: resolve,
      })
    })

    expect(error).toMatchObject({
      status: 429,
      response: {
        status: 429,
        headers: {
          'content-type': 'application/json',
          'retry-after': '17',
        },
        data: {
          error: {
            details: {
              retry_after: 17,
              active_session_id: 'session-a',
            },
          },
        },
      },
    })
  })
})
