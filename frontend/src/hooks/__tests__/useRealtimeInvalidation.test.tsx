import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '../../api/queries/queryKeys'
import { serviceMeshManager } from '../../stores/serviceMeshManager'
import { useRealtimeInvalidation } from '../useRealtimeInvalidation'

function TestComponent({ enabled }: { enabled: boolean }) {
  useRealtimeInvalidation(enabled)
  return null
}

describe('useRealtimeInvalidation', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('subscribes to invalidation channel without state subscription', () => {
    const qc = new QueryClient()

    const subscribeSpy = vi.spyOn(serviceMeshManager, 'subscribe')
    const subscribeInvalidationSpy = vi.spyOn(serviceMeshManager, 'subscribeInvalidation').mockReturnValue(() => {})
    const startSpy = vi.spyOn(serviceMeshManager, 'start').mockImplementation(() => {})
    const stopSpy = vi.spyOn(serviceMeshManager, 'stop').mockImplementation(() => {})

    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <TestComponent enabled />
      </QueryClientProvider>
    )

    expect(subscribeSpy).not.toHaveBeenCalled()
    expect(subscribeInvalidationSpy).toHaveBeenCalledTimes(1)
    expect(startSpy).toHaveBeenCalledTimes(1)

    unmount()
    expect(stopSpy).toHaveBeenCalledTimes(1)
  })

  it('invalidates expected query keys for operations scope', () => {
    const qc = new QueryClient()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const startSpy = vi.spyOn(serviceMeshManager, 'start').mockImplementation(() => {})
    const stopSpy = vi.spyOn(serviceMeshManager, 'stop').mockImplementation(() => {})

    let capturedListener: unknown = null
    const unsubscribe = vi.fn()
    vi.spyOn(serviceMeshManager, 'subscribeInvalidation').mockImplementation((cb) => {
      capturedListener = cb
      return unsubscribe
    })

    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <TestComponent enabled />
      </QueryClientProvider>
    )

    expect(startSpy).toHaveBeenCalledTimes(1)

    if (typeof capturedListener !== 'function') {
      throw new Error('Expected invalidation listener to be registered')
    }

    ;(capturedListener as (event: { scope: string }) => void)({ scope: 'operations' })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.operations.all })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.dashboard.stats })

    unmount()
    expect(unsubscribe).toHaveBeenCalledTimes(1)
    expect(stopSpy).toHaveBeenCalledTimes(1)
  })
})
