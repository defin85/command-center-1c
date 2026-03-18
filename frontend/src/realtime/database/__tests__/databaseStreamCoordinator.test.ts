import { afterEach, describe, expect, it, vi } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'

import {
  DatabaseStreamCoordinator,
  type DatabaseCrossTabBus,
  type DatabaseCrossTabMessage,
  type DatabaseLeaderLease,
  type DatabaseLeaderLeaseStore,
  type DatabaseStreamTransportEvent,
  type DatabaseStreamTransportLike,
} from '../databaseStreamCoordinator'

const flushPromises = async (count = 8) => {
  for (let index = 0; index < count; index += 1) {
    await Promise.resolve()
  }
}

class InMemoryBus implements DatabaseCrossTabBus {
  private listeners = new Set<(message: DatabaseCrossTabMessage) => void>()

  post(message: DatabaseCrossTabMessage) {
    for (const listener of this.listeners) {
      listener(message)
    }
  }

  subscribe(listener: (message: DatabaseCrossTabMessage) => void) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  close() {}
}

class InMemoryLeaseStore implements DatabaseLeaderLeaseStore {
  private lease: DatabaseLeaderLease | null = null
  private listeners = new Set<(lease: DatabaseLeaderLease | null) => void>()

  read() {
    return this.lease
  }

  write(lease: DatabaseLeaderLease) {
    this.lease = lease
    for (const listener of this.listeners) {
      listener(this.lease)
    }
  }

  clear(ownerTabId?: string) {
    if (!ownerTabId || this.lease?.tabId === ownerTabId) {
      this.lease = null
      for (const listener of this.listeners) {
        listener(this.lease)
      }
    }
  }

  subscribe(listener: (lease: DatabaseLeaderLease | null) => void) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }
}

class FakeTransport implements DatabaseStreamTransportLike {
  private listeners = new Set<(event: DatabaseStreamTransportEvent) => void>()
  connectCalls: Array<{ recovery?: boolean }> = []

  subscribe(listener: (event: DatabaseStreamTransportEvent) => void) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  async connect(options?: { recovery?: boolean }) {
    this.connectCalls.push({ recovery: options?.recovery })
    this.emit({
      type: 'state',
      state: {
        isConnected: true,
        isConnecting: false,
        error: null,
        cooldownSeconds: 0,
        sessionId: 'session-a',
        leaseId: `lease-${this.connectCalls.length}`,
      },
    })
  }

  disconnect() {}

  emit(event: DatabaseStreamTransportEvent) {
    for (const listener of this.listeners) {
      listener(event)
    }
  }
}

describe('DatabaseStreamCoordinator', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('elects a single browser leader and keeps follower tabs off transport', async () => {
    vi.useFakeTimers()

    const bus = new InMemoryBus()
    const leaseStore = new InMemoryLeaseStore()
    const leaderTransport = new FakeTransport()
    const followerTransport = new FakeTransport()
    const leaderInvalidateQueries = vi.fn().mockResolvedValue(undefined)
    const followerInvalidateQueries = vi.fn().mockResolvedValue(undefined)

    const leader = new DatabaseStreamCoordinator({
      tabId: 'tab-a',
      clientInstanceId: 'browser-1',
      bus,
      leaseStore,
      transport: leaderTransport,
      leadershipTtlMs: 5_000,
      heartbeatIntervalMs: 1_000,
    })
    leader.setQueryClient({ invalidateQueries: leaderInvalidateQueries } as unknown as QueryClient)

    const follower = new DatabaseStreamCoordinator({
      tabId: 'tab-b',
      clientInstanceId: 'browser-1',
      bus,
      leaseStore,
      transport: followerTransport,
      leadershipTtlMs: 5_000,
      heartbeatIntervalMs: 1_000,
    })
    follower.setQueryClient({ invalidateQueries: followerInvalidateQueries } as unknown as QueryClient)

    leader.start()
    follower.start()
    await flushPromises()

    expect(leaderTransport.connectCalls).toEqual([{ recovery: false }])
    expect(followerTransport.connectCalls).toEqual([])
    expect(leader.getState().mode).toBe('leader')
    expect(follower.getState().mode).toBe('follower')

    leaderTransport.emit({
      type: 'event',
      event: {
        type: 'database_update',
        action: 'metadata_updated',
        database_id: 'db-42',
      },
    })
    await flushPromises()

    expect(followerInvalidateQueries).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['databases', 'detail', 'db-42'] }),
    )
    expect(followerTransport.connectCalls).toHaveLength(0)

    follower.reconnect()
    await flushPromises()

    expect(leaderTransport.connectCalls).toEqual([{ recovery: false }, { recovery: true }])

    leader.stop()
    follower.stop()
  })
})
