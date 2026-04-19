import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render } from '@testing-library/react'
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
    vi.useRealTimers()
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

  it('invalidates expected query keys for operations scope after the bounded invalidation window', () => {
    vi.useFakeTimers()
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

    act(() => {
      ;(capturedListener as (event: { scope: string }) => void)({ scope: 'operations' })
    })

    expect(invalidateSpy).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1000)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.operations.all })
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: queryKeys.dashboard.stats })

    unmount()
    expect(unsubscribe).toHaveBeenCalledTimes(1)
    expect(stopSpy).toHaveBeenCalledTimes(1)
  })

  it('coalesces repeated invalidation events within the same window', () => {
    vi.useFakeTimers()
    const qc = new QueryClient()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    vi.spyOn(serviceMeshManager, 'start').mockImplementation(() => {})
    vi.spyOn(serviceMeshManager, 'stop').mockImplementation(() => {})

    let capturedListener: unknown = null
    vi.spyOn(serviceMeshManager, 'subscribeInvalidation').mockImplementation((cb) => {
      capturedListener = cb
      return () => {}
    })

    render(
      <QueryClientProvider client={qc}>
        <TestComponent enabled />
      </QueryClientProvider>
    )

    if (typeof capturedListener !== 'function') {
      throw new Error('Expected invalidation listener to be registered')
    }

    act(() => {
      const listener = capturedListener as (event: { scope: string }) => void
      listener({ scope: 'operations' })
      listener({ scope: 'operations' })
      listener({ scope: 'operations' })
      vi.advanceTimersByTime(1000)
    })

    expect(invalidateSpy.mock.calls).toEqual([
      [{ queryKey: queryKeys.operations.all }],
    ])
  })

  it('keeps dashboard polling isolated from realtime invalidation bursts', () => {
    vi.useFakeTimers()
    const qc = new QueryClient()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    vi.spyOn(serviceMeshManager, 'start').mockImplementation(() => {})
    vi.spyOn(serviceMeshManager, 'stop').mockImplementation(() => {})

    let capturedListener: unknown = null
    vi.spyOn(serviceMeshManager, 'subscribeInvalidation').mockImplementation((cb) => {
      capturedListener = cb
      return () => {}
    })

    render(
      <QueryClientProvider client={qc}>
        <TestComponent enabled />
      </QueryClientProvider>
    )

    if (typeof capturedListener !== 'function') {
      throw new Error('Expected invalidation listener to be registered')
    }

    act(() => {
      const listener = capturedListener as (event: { scope: string }) => void
      listener({ scope: 'operations' })
      listener({ scope: 'databases' })
      listener({ scope: 'clusters' })
      vi.advanceTimersByTime(1000)
    })

    expect(invalidateSpy.mock.calls).toEqual([
      [{ queryKey: queryKeys.operations.all }],
      [{ queryKey: queryKeys.databases.all }],
      [{ queryKey: queryKeys.clusters.all }],
    ])
  })
})
