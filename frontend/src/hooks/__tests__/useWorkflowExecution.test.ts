import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mockCreateUiRuntimeId = vi.fn<(prefix: string) => string>()
const mockRecordUiWebSocketLifecycle = vi.fn()

vi.mock('../../api/baseUrl', () => ({
  getWsHost: () => 'localhost:15173',
}))

vi.mock('../../observability/uiActionJournal', () => ({
  createUiRuntimeId: (prefix: string) => mockCreateUiRuntimeId(prefix),
  recordUiWebSocketLifecycle: (input: unknown) => mockRecordUiWebSocketLifecycle(input),
}))

class MockWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 3
  static instances: MockWebSocket[] = []

  readonly url: string
  readyState = MockWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  readonly sent: string[] = []

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(payload: string) {
    this.sent.push(payload)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({
      code: 1000,
      reason: 'manual-close',
    } as CloseEvent)
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }
}

vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket)

const { useWorkflowExecution } = await import('../useWorkflowExecution')

describe('useWorkflowExecution websocket observability', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    mockCreateUiRuntimeId.mockReset()
    mockCreateUiRuntimeId.mockImplementation((prefix) => `${prefix}-1`)
    mockRecordUiWebSocketLifecycle.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('records close lifecycle when the default cleanup path unmounts the hook', () => {
    const { unmount } = renderHook(() => useWorkflowExecution('exec-1'))

    act(() => {
      vi.runOnlyPendingTimers()
    })

    const socket = MockWebSocket.instances[0]
    expect(socket).toBeDefined()
    expect(socket?.url).toContain('/ws/workflow/exec-1/')

    act(() => {
      socket?.open()
    })

    expect(mockRecordUiWebSocketLifecycle).toHaveBeenCalledWith(expect.objectContaining({
      owner: 'useWorkflowExecution',
      reuseKey: 'workflow-execution:exec-1',
      channelKind: 'dedicated',
      socketInstanceId: 'ws-1',
      outcome: 'connect',
    }))

    act(() => {
      unmount()
    })

    expect(mockRecordUiWebSocketLifecycle).toHaveBeenCalledWith(expect.objectContaining({
      owner: 'useWorkflowExecution',
      reuseKey: 'workflow-execution:exec-1',
      channelKind: 'dedicated',
      socketInstanceId: 'ws-1',
      outcome: 'close',
      closeCode: 1000,
      closeReason: 'manual-close',
    }))
  })
})
