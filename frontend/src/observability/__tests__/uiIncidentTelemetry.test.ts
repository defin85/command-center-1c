import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '../../api/queries/queryKeys'
import { queryClient, resetQueryClient } from '../../lib/queryClient'
import {
  captureUiRouteTransition,
  buildUiRouteParamDiff,
  clearUiActionJournal,
  completeUiHttpRequest,
  exportUiActionJournalBundle,
  queueUiRouteWrite,
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

function getFetchRequestInit(fetchMock: ReturnType<typeof vi.fn>, callIndex = 0): RequestInit {
  const call = fetchMock.mock.calls[callIndex]
  expect(call).toBeDefined()
  const request = call?.[1]
  expect(request).toBeDefined()
  return request as RequestInit
}

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
    const request = getFetchRequestInit(fetchMock)
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

  it('persists route.loop_warning in durable telemetry batches', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 202 }))
    vi.stubGlobal('fetch', fetchMock)

    captureUiRouteTransition({
      pathname: '/pools/master-data',
      search: '?tab=bindings&detail=1',
      hash: '',
    })

    const exportBundleRouteSearch = () => exportUiActionJournalBundle().route.search

    const switchZone = (toTab: 'bindings' | 'sync') => {
      const current = exportBundleRouteSearch()
      const next = `?tab=${toTab}&detail=1`
      trackUiAction({
        actionKind: 'route.change',
        actionName: `Open ${toTab} zone`,
        surfaceId: 'pool_master_data',
        controlId: `zone.${toTab}`,
        context: {
          from_tab: current.includes('tab=sync') ? 'sync' : 'bindings',
          to_tab: toTab,
          detail_before: true,
          detail_after: true,
        },
      }, ({ uiActionId }) => {
        queueUiRouteWrite({
          surfaceId: 'pool_master_data',
          routeWriterOwner: 'pool_master_data_page',
          writeReason: 'zone_switch',
          navigationMode: 'push',
          paramDiff: buildUiRouteParamDiff(current, next),
          causedByUiActionId: uiActionId,
        })
        captureUiRouteTransition({
          pathname: '/pools/master-data',
          search: next,
          hash: '',
        })
      })
    }

    switchZone('sync')
    switchZone('bindings')
    switchZone('sync')

    await vi.advanceTimersByTimeAsync(__TESTING__.FLUSH_INTERVAL_MS)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const request = getFetchRequestInit(fetchMock)
    const payload = JSON.parse(String(request?.body))

    expect(payload.events.some((event: { event_type: string }) => event.event_type === 'route.loop_warning')).toBe(true)
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
    const request = getFetchRequestInit(fetchMock, 2)
    const payload = JSON.parse(String(request?.body))

    expect(request?.keepalive).toBe(true)
    expect(payload.events.map((event: { event_type: string }) => event.event_type)).toEqual([
      'websocket.lifecycle',
    ])
  })

  it('drops 429 telemetry batches without retry storm', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 429 }))
    vi.stubGlobal('fetch', fetchMock)

    captureUiRouteTransition({
      pathname: '/pools/master-data',
      search: '?tab=sync',
      hash: '',
    })
    recordUiErrorBoundary(new Error('sync failed'), 'stack:line-2')

    await vi.advanceTimersByTimeAsync(__TESTING__.FLUSH_INTERVAL_MS)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(__TESTING__.RETRY_DELAY_MS)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('omits steady-state websocket lifecycle noise from durable telemetry while keeping incident signals', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 202 }))
    vi.stubGlobal('fetch', fetchMock)

    captureUiRouteTransition({
      pathname: '/service-mesh',
      search: '?service=orchestrator',
      hash: '',
    })
    recordUiWebSocketLifecycle({
      owner: 'serviceMeshManager',
      reuseKey: 'service-mesh:global',
      channelKind: 'shared',
      socketInstanceId: 'ws-10',
      outcome: 'connect',
    })
    recordUiWebSocketLifecycle({
      owner: 'serviceMeshManager',
      reuseKey: 'service-mesh:global',
      channelKind: 'shared',
      socketInstanceId: 'ws-10',
      outcome: 'close',
      closeCode: 1000,
    })
    recordUiWebSocketLifecycle({
      owner: 'serviceMeshManager',
      reuseKey: 'service-mesh:global',
      channelKind: 'shared',
      socketInstanceId: 'ws-10',
      outcome: 'reconnect',
    })

    await vi.advanceTimersByTimeAsync(__TESTING__.FLUSH_INTERVAL_MS)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const request = getFetchRequestInit(fetchMock)
    const payload = JSON.parse(String(request?.body))

    expect(payload.events.map((event: { event_type: string; outcome?: string }) => ({
      event_type: event.event_type,
      outcome: event.outcome,
    }))).toEqual([
      { event_type: 'route.transition', outcome: 'navigated' },
      { event_type: 'websocket.lifecycle', outcome: 'reconnect' },
    ])
    expect(payload.dropped_events_count).toBe(0)
  })
})
