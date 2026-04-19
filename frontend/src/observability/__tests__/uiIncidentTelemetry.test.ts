import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '../../api/queries/queryKeys'
import { queryClient, resetQueryClient } from '../../lib/queryClient'
import {
  captureUiRouteTransition,
  clearUiActionJournal,
  completeUiHttpRequest,
  recordUiErrorBoundary,
  recordUiWebSocketLifecycle,
  setUiActionJournalEnabled,
  startUiHttpRequest,
  trackUiAction,
} from '../uiActionJournal'
import {
  __TESTING__,
  setUiIncidentTelemetryEnabled,
} from '../uiIncidentTelemetry'

describe('uiIncidentTelemetry', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
    localStorage.setItem('auth_token', 'token-1')
    localStorage.setItem('active_tenant_id', 'tenant-1')
    queryClient.setQueryData(
      queryKeys.shell.bootstrap(),
      {
        me: {
          id: 7,
          username: 'operator-1',
          is_staff: false,
        },
        tenant_context: {
          active_tenant_id: 'tenant-1',
          tenants: [],
        },
        access: {},
        capabilities: {},
        i18n: {},
      },
    )
    setUiActionJournalEnabled(true)
    setUiIncidentTelemetryEnabled(true)
    clearUiActionJournal()
  })

  afterEach(() => {
    setUiIncidentTelemetryEnabled(false)
    setUiActionJournalEnabled(false)
    clearUiActionJournal()
    resetQueryClient()
    localStorage.clear()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('uploads durable semantic telemetry with machine-readable envelope', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 202 }))
    vi.stubGlobal('fetch', fetchMock)

    captureUiRouteTransition({
      pathname: '/pools/runs',
      search: '?tab=create',
      hash: '#workflow=wf-services-r4',
    })
    recordUiWebSocketLifecycle({
      owner: 'serviceMeshManager',
      reuseKey: 'service-mesh:global',
      channelKind: 'shared',
      socketInstanceId: 'ws-1',
      outcome: 'connect',
    })
    trackUiAction({
      actionKind: 'modal.submit',
      actionName: 'Create pool run',
    }, () => {
      const request = startUiHttpRequest({
        method: 'post',
        path: '/api/v2/pools/runs/',
      })
      completeUiHttpRequest({
        requestId: request.requestId,
        uiActionId: request.uiActionId,
        method: 'POST',
        path: '/api/v2/pools/runs/',
        status: 500,
        problem: {
          code: 'POOL_RUN_FAILED',
          title: 'Pool Run Failed',
          request_id: 'req-server-1',
          ui_action_id: request.uiActionId,
        },
      })
    })

    await vi.advanceTimersByTimeAsync(__TESTING__.FLUSH_INTERVAL_MS)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, request] = fetchMock.mock.calls[0] ?? []
    const payload = JSON.parse(String(request?.body))

    expect(request?.keepalive).toBe(false)
    expect(request?.headers).toMatchObject({
      Authorization: 'Bearer token-1',
      'X-CC1C-Tenant-ID': 'tenant-1',
    })
    expect(payload.tenant_id).toBe('tenant-1')
    expect(payload.actor).toEqual({
      user_id: 7,
      username: 'operator-1',
      is_staff: false,
    })
    expect(payload.route).toMatchObject({
      path: '/pools/runs',
      search: '?tab=create',
      hash: '#workflow=wf-services-r4',
    })
    expect(payload.events.map((event: { event_type: string }) => event.event_type)).toEqual([
      'route.transition',
      'ui.action',
      'http.request.failure',
    ])
  })

  it('retries failed batches and uses keepalive for pagehide flush', async () => {
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce(new Response('{}', { status: 202 }))
      .mockResolvedValueOnce(new Response('{}', { status: 202 }))
    vi.stubGlobal('fetch', fetchMock)

    captureUiRouteTransition({
      pathname: '/service-mesh',
      search: '?service=orchestrator',
      hash: '',
    })
    recordUiErrorBoundary(new Error('render failed'), 'stack:line-1')

    await vi.advanceTimersByTimeAsync(__TESTING__.FLUSH_INTERVAL_MS)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(__TESTING__.RETRY_DELAY_MS)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    recordUiWebSocketLifecycle({
      owner: 'serviceMeshManager',
      reuseKey: 'service-mesh:global',
      channelKind: 'shared',
      socketInstanceId: 'ws-2',
      outcome: 'reconnect',
    })

    window.dispatchEvent(new Event('pagehide'))
    await vi.runAllTimersAsync()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    const [, request] = fetchMock.mock.calls[2] ?? []
    const payload = JSON.parse(String(request?.body))

    expect(request?.keepalive).toBe(true)
    expect(payload.events.map((event: { event_type: string }) => event.event_type)).toEqual([
      'websocket.lifecycle',
    ])
  })
})
