import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  __TESTING__,
  captureUiRouteTransition,
  clearUiActionJournal,
  completeUiHttpRequest,
  exportUiActionJournalBundle,
  recordUiErrorBoundary,
  recordUiWebSocketLifecycle,
  setUiActionJournalEnabled,
  startUiHttpRequest,
  trackUiAction,
} from '../uiActionJournal'

describe('uiActionJournal', () => {
  beforeEach(() => {
    setUiActionJournalEnabled(true)
    clearUiActionJournal()
  })

  afterEach(() => {
    setUiActionJournalEnabled(false)
    clearUiActionJournal()
  })

  it('captures route, action, request failure, and boundary error in a redacted bundle', () => {
    captureUiRouteTransition({
      pathname: '/pools/runs',
      search: '?tab=create&token=super-secret',
      hash: '#workflow=wf-services-r4&token=super-secret',
    })

    trackUiAction({
      actionKind: 'modal.submit',
      actionName: 'Create pool run',
      context: {
        pool: 'pool-1',
        password: 'should-not-appear',
      },
    }, () => {
      const request = startUiHttpRequest({
        method: 'post',
        path: '/api/v2/pools/runs/',
        context: {
          pool: 'pool-1',
          token: 'should-not-appear',
        },
      })

      completeUiHttpRequest({
        requestId: request.requestId,
        uiActionId: request.uiActionId,
        method: 'POST',
        path: '/api/v2/pools/runs/',
        status: 400,
        problem: {
          code: 'POOL_RUN_INVALID',
          title: 'Pool Run Invalid',
          request_id: 'req-server-1',
          ui_action_id: request.uiActionId,
        },
      })

      recordUiErrorBoundary(new Error('render failed'), 'stack:line-1')
    })

    const bundle = exportUiActionJournalBundle()
    const failureEvent = bundle.events.find((event) => event.event_type === 'http.request.failure')
    const errorEvent = bundle.events.find((event) => event.event_type === 'ui.error.boundary')

    expect(bundle.session_id).toBeTruthy()
    expect(bundle.route.path).toBe('/pools/runs')
    expect(bundle.route.search).toBe('?tab=create')
    expect(bundle.route.hash).toBe('#workflow=wf-services-r4')
    expect(bundle.route.context).toEqual({
      tab: 'create',
      workflow: 'wf-services-r4',
    })
    expect(bundle.release.fingerprint).toBe(__TESTING__.buildReleaseFingerprint())
    expect(bundle.release.fingerprint).not.toBe(`${bundle.release.mode}:${bundle.release.origin}`)
    expect(bundle.events.map((event) => event.event_type)).toEqual(expect.arrayContaining([
      'route.transition',
      'ui.action',
      'http.request.failure',
      'ui.error.boundary',
    ]))
    expect(failureEvent).toMatchObject({
      request_id: 'req-server-1',
      error_code: 'POOL_RUN_INVALID',
      error_title: 'Pool Run Invalid',
    })
    expect(errorEvent).toMatchObject({
      error_message: 'render failed',
      error_source: 'ErrorBoundary',
    })
    expect(JSON.stringify(bundle)).not.toContain('super-secret')
    expect(JSON.stringify(bundle)).not.toContain('should-not-appear')
  })

  it('publishes machine-readable churn diagnostics for shared websocket leaks', () => {
    captureUiRouteTransition({
      pathname: '/service-mesh',
      search: '?service=orchestrator',
      hash: '',
    })

    recordUiWebSocketLifecycle({
      owner: 'serviceMeshManager',
      reuseKey: 'service-mesh:global',
      channelKind: 'shared',
      socketInstanceId: 'ws-1',
      outcome: 'connect',
    })
    recordUiWebSocketLifecycle({
      owner: 'serviceMeshManager',
      reuseKey: 'service-mesh:global',
      channelKind: 'shared',
      socketInstanceId: 'ws-2',
      outcome: 'connect',
    })

    const bundle = exportUiActionJournalBundle()
    const churnEvent = bundle.events.find((event) => event.event_type === 'websocket.churn_warning')

    expect(bundle.active_websockets_by_owner.serviceMeshManager).toMatchObject({
      active_connection_count: 2,
      reuse_keys: ['service-mesh:global'],
    })
    expect(bundle.active_websockets_by_reuse_key['service-mesh:global']).toMatchObject({
      active_connection_count: 2,
      owner: 'serviceMeshManager',
      channel_kind: 'shared',
    })
    expect(churnEvent).toMatchObject({
      owner: 'serviceMeshManager',
      reuse_key: 'service-mesh:global',
      active_connections_for_reuse_key: 2,
      outcome: 'churn_warning',
    })
  })
})
