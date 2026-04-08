import { AxiosError, AxiosHeaders } from 'axios'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { apiClient } from '../client'
import {
  clearUiActionJournal,
  exportUiActionJournalBundle,
  setUiActionJournalEnabled,
  trackUiAction,
} from '../../observability/uiActionJournal'

const requestHandlers = (apiClient.interceptors.request as unknown as {
  handlers?: Array<{ fulfilled?: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }>
}).handlers ?? []

const responseHandlers = (apiClient.interceptors.response as unknown as {
  handlers?: Array<{
    fulfilled?: (response: AxiosResponse) => unknown
    rejected?: (error: AxiosError) => Promise<never>
  }>
}).handlers ?? []

const requestHandler = (() => {
  const handler = requestHandlers[0]?.fulfilled
  if (!handler) {
    throw new Error('Missing request observability interceptor')
  }
  return handler
})()

const responseHandler = (() => {
  const handler = responseHandlers[0]?.fulfilled
  if (!handler) {
    throw new Error('Missing response observability success interceptor')
  }
  return handler
})()

const errorHandler = (() => {
  const handler = responseHandlers[0]?.rejected
  if (!handler) {
    throw new Error('Missing response observability error interceptor')
  }
  return handler
})()

function createConfig(url: string, method: 'get' | 'post'): InternalAxiosRequestConfig {
  return {
    url,
    method,
    headers: new AxiosHeaders(),
  } as InternalAxiosRequestConfig
}

function createResponse(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown,
  headers: Record<string, string> = {},
): AxiosResponse {
  return {
    config,
    status,
    statusText: status >= 400 ? 'Error' : 'OK',
    data,
    headers,
  }
}

describe('apiClient observability interceptors', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('auth_token', 'token-1')
    localStorage.setItem('active_tenant_id', 'tenant-1')
    setUiActionJournalEnabled(true)
    clearUiActionJournal()
  })

  afterEach(() => {
    setUiActionJournalEnabled(false)
    clearUiActionJournal()
  })

  it('attaches stable request correlation headers and clears active requests on success', async () => {
    const config = requestHandler(createConfig('/api/v2/pools/runs', 'post'))

    expect(config.headers['X-Request-ID']).toMatch(/^req-/)
    expect(config.headers['X-UI-Action-ID']).toMatch(/^uia-/)
    expect(config.headers['X-CC1C-Tenant-ID']).toBe('tenant-1')

    const retriedConfig = requestHandler(config)

    expect(retriedConfig.headers['X-Request-ID']).toBe(config.headers['X-Request-ID'])
    expect(retriedConfig.headers['X-UI-Action-ID']).toBe(config.headers['X-UI-Action-ID'])

    responseHandler(createResponse(retriedConfig, 200, { ok: true }))

    expect(exportUiActionJournalBundle().active_http_requests).toHaveLength(0)
  })

  it('preserves the originating ui_action_id for detached async mutation-style requests', async () => {
    const deferredConfig = await new Promise<InternalAxiosRequestConfig>((resolve) => {
      trackUiAction({
        actionKind: 'operator.action',
        actionName: 'Create pool run',
      }, () => {
        queueMicrotask(() => {
          resolve(requestHandler(createConfig('/api/v2/pools/runs', 'post')))
        })
      })
    })

    const bundle = exportUiActionJournalBundle()
    const actionEvents = bundle.events.filter((event) => event.event_type === 'ui.action')
    const operatorAction = actionEvents[0]

    expect(actionEvents).toHaveLength(1)
    expect(operatorAction).toMatchObject({
      action_name: 'Create pool run',
      action_source: 'explicit',
    })
    expect(deferredConfig.headers['X-UI-Action-ID']).toBe(
      operatorAction && 'ui_action_id' in operatorAction ? operatorAction.ui_action_id : undefined,
    )

    responseHandler(createResponse(deferredConfig, 200, { ok: true }))
    expect(exportUiActionJournalBundle().active_http_requests).toHaveLength(0)
  })

  it('restores the parent ui_action_id after a nested action resolves before the deferred request starts', async () => {
    let releaseParentAction: (() => void) | undefined

    const deferredConfigPromise = trackUiAction({
      actionKind: 'operator.action',
      actionName: 'Create pool run',
    }, async () => {
      await new Promise<void>((resolve) => {
        releaseParentAction = resolve
      })
      return requestHandler(createConfig('/api/v2/pools/runs', 'post'))
    }) as Promise<InternalAxiosRequestConfig>

    trackUiAction({
      actionKind: 'modal.confirm',
      actionName: 'Inspect details',
    }, () => undefined)

    releaseParentAction?.()
    const deferredConfig = await deferredConfigPromise
    const bundle = exportUiActionJournalBundle()
    const actionEvents = bundle.events.filter((event) => event.event_type === 'ui.action')
    const parentAction = actionEvents.find((event) => event.action_name === 'Create pool run')
    const nestedAction = actionEvents.find((event) => event.action_name === 'Inspect details')

    expect(deferredConfig.headers['X-UI-Action-ID']).toBe(
      parentAction && 'ui_action_id' in parentAction ? parentAction.ui_action_id : undefined,
    )
    expect(deferredConfig.headers['X-UI-Action-ID']).not.toBe(
      nestedAction && 'ui_action_id' in nestedAction ? nestedAction.ui_action_id : undefined,
    )

    responseHandler(createResponse(deferredConfig, 200, { ok: true }))
    expect(exportUiActionJournalBundle().active_http_requests).toHaveLength(0)
  })

  it('correlates problem details and logs network failures without HTTP status', async () => {
    const failedConfig = requestHandler(createConfig('/api/v2/pools/runs/', 'post'))
    const failedResponse = createResponse(
      failedConfig,
      500,
      {
        title: 'Pool Run Failed',
        code: 'POOL_RUN_FAILED',
        detail: 'boom',
        request_id: 'req-backend-1',
        ui_action_id: 'uia-backend-1',
      },
      {
        'x-request-id': 'req-backend-1',
        'x-ui-action-id': 'uia-backend-1',
      },
    )

    await expect(
      errorHandler(new AxiosError('Request failed with status code 500', undefined, failedConfig, undefined, failedResponse)),
    ).rejects.toBeDefined()

    const networkConfig = requestHandler(createConfig('/api/v2/system/health/', 'get'))

    await expect(errorHandler(new AxiosError('socket hang up', undefined, networkConfig))).rejects.toBeDefined()

    const bundle = exportUiActionJournalBundle()
    const failureEvents = bundle.events.filter((event) => event.event_type === 'http.request.failure')

    expect(failureEvents).toEqual(expect.arrayContaining([
      expect.objectContaining({
        request_id: 'req-backend-1',
        ui_action_id: 'uia-backend-1',
        error_code: 'POOL_RUN_FAILED',
        status: 500,
      }),
      expect.objectContaining({
        method: 'GET',
        path: '/api/v2/system/health/',
      }),
    ]))
  })
})
