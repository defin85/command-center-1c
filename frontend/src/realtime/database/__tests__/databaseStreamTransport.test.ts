import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { DatabaseStreamTicketResponse } from '../../../api/generated/model/databaseStreamTicketResponse'
import type { buildDatabaseStreamUrl, getDatabaseStreamTicket } from '../../../api/databasesStream'
import type { openSseStream, SSEOptions } from '../../../api/sse'

const mockGetDatabaseStreamTicket = vi.hoisted(() => vi.fn<typeof getDatabaseStreamTicket>())
const mockBuildDatabaseStreamUrl = vi.hoisted(() => vi.fn<typeof buildDatabaseStreamUrl>((url: string) => url))
const mockOpenSseStream = vi.hoisted(() => vi.fn<typeof openSseStream>())

vi.mock('../../../api/databasesStream', () => ({
  getDatabaseStreamTicket: mockGetDatabaseStreamTicket,
  buildDatabaseStreamUrl: mockBuildDatabaseStreamUrl,
}))

vi.mock('../../../api/sse', () => ({
  openSseStream: mockOpenSseStream,
}))

import { DatabaseStreamTransport } from '../databaseStreamTransport'

describe('DatabaseStreamTransport', () => {
  beforeEach(() => {
    mockGetDatabaseStreamTicket.mockReset()
    mockBuildDatabaseStreamUrl.mockClear()
    mockOpenSseStream.mockClear()
    mockOpenSseStream.mockImplementation((_url: string, options: SSEOptions) => {
      options.onOpen?.(new Response(null, { status: 200 }))
      return vi.fn()
    })
  })

  it('uses explicit session recovery for reconnects', async () => {
    mockGetDatabaseStreamTicket
      .mockResolvedValueOnce({
        ticket: 'ticket-1',
        expires_in: 30,
        stream_url: '/api/v2/databases/stream/?ticket=ticket-1',
        session_id: 'session-a',
        lease_id: 'lease-a',
        client_instance_id: 'browser-1',
        scope: '__all__',
        message: 'Database stream ticket issued',
      } satisfies DatabaseStreamTicketResponse)
      .mockResolvedValueOnce({
        ticket: 'ticket-2',
        expires_in: 30,
        stream_url: '/api/v2/databases/stream/?ticket=ticket-2',
        session_id: 'session-a',
        lease_id: 'lease-b',
        client_instance_id: 'browser-1',
        scope: '__all__',
        message: 'Database stream recovery ticket issued',
      } satisfies DatabaseStreamTicketResponse)

    const transport = new DatabaseStreamTransport({
      clientInstanceId: 'browser-1',
      getToken: () => 'test-token',
    })

    await transport.connect()
    await transport.connect({ recovery: true })

    expect(mockGetDatabaseStreamTicket).toHaveBeenNthCalledWith(1, {
      clusterId: null,
      clientInstanceId: 'browser-1',
      sessionId: undefined,
      recovery: false,
    })
    expect(mockGetDatabaseStreamTicket).toHaveBeenNthCalledWith(2, {
      clusterId: null,
      clientInstanceId: 'browser-1',
      sessionId: 'session-a',
      recovery: true,
    })
  })
})
