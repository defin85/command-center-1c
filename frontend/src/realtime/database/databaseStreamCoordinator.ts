import type { QueryClient } from '@tanstack/react-query'

import {
  BrowserDatabaseCrossTabBus,
  BrowserDatabaseLeaderLeaseStore,
  getDatabaseStreamClientInstanceId,
  getDatabaseStreamTabId,
} from './databaseStreamBrowser'
import { createDatabaseEventProjector } from './databaseEventProjector'
import { DatabaseStreamTransport } from './databaseStreamTransport'
import type {
  DatabaseCoordinatorStateSnapshot,
  DatabaseCrossTabBus,
  DatabaseCrossTabMessage,
  DatabaseEventProjector,
  DatabaseLeaderLease,
  DatabaseLeaderLeaseStore,
  DatabaseRealtimeEvent,
  DatabaseStreamTransportEvent,
  DatabaseStreamTransportLike,
} from './databaseStreamTypes'

const DEFAULT_LEADERSHIP_TTL_MS = 8_000
const DEFAULT_HEARTBEAT_INTERVAL_MS = 3_000
const LEADERSHIP_RETRY_BUFFER_MS = 200

type DatabaseStreamCoordinatorOptions = {
  tabId?: string
  clientInstanceId?: string
  bus?: DatabaseCrossTabBus
  leaseStore?: DatabaseLeaderLeaseStore
  transport?: DatabaseStreamTransportLike
  projector?: DatabaseEventProjector
  leadershipTtlMs?: number
  heartbeatIntervalMs?: number
}

export class DatabaseStreamCoordinator {
  private readonly tabId: string
  private readonly clientInstanceId: string
  private readonly bus: DatabaseCrossTabBus
  private readonly leaseStore: DatabaseLeaderLeaseStore
  private readonly transport: DatabaseStreamTransportLike
  private readonly projector: DatabaseEventProjector
  private readonly leadershipTtlMs: number
  private readonly heartbeatIntervalMs: number
  private state: DatabaseCoordinatorStateSnapshot = {
    isConnected: false,
    isConnecting: false,
    error: null,
    cooldownSeconds: 0,
    sessionId: null,
    leaseId: null,
    mode: 'idle',
  }
  private listeners = new Set<(state: DatabaseCoordinatorStateSnapshot) => void>()
  private eventListeners = new Set<(event: DatabaseRealtimeEvent) => void>()
  private refCount = 0
  private queryClient: QueryClient | null = null
  private activeLeaderTabId: string | null = null
  private transportUnsubscribe: (() => void) | null = null
  private busUnsubscribe: (() => void) | null = null
  private leaseUnsubscribe: (() => void) | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private leadershipRetryTimer: ReturnType<typeof setTimeout> | null = null

  constructor(options: DatabaseStreamCoordinatorOptions = {}) {
    this.tabId = options.tabId ?? getDatabaseStreamTabId()
    this.clientInstanceId = options.clientInstanceId ?? getDatabaseStreamClientInstanceId()
    this.bus = options.bus ?? new BrowserDatabaseCrossTabBus()
    this.leaseStore = options.leaseStore ?? new BrowserDatabaseLeaderLeaseStore()
    this.transport = options.transport ?? new DatabaseStreamTransport({ clientInstanceId: this.clientInstanceId })
    this.projector = options.projector ?? createDatabaseEventProjector()
    this.leadershipTtlMs = options.leadershipTtlMs ?? DEFAULT_LEADERSHIP_TTL_MS
    this.heartbeatIntervalMs = options.heartbeatIntervalMs ?? DEFAULT_HEARTBEAT_INTERVAL_MS
  }

  getState() {
    return this.state
  }

  setQueryClient(queryClient: QueryClient | null) {
    this.queryClient = queryClient
  }

  subscribe(listener: (state: DatabaseCoordinatorStateSnapshot) => void) {
    this.listeners.add(listener)
    listener(this.state)
    return () => {
      this.listeners.delete(listener)
    }
  }

  subscribeEvent(listener: (event: DatabaseRealtimeEvent) => void) {
    this.eventListeners.add(listener)
    return () => {
      this.eventListeners.delete(listener)
    }
  }

  start() {
    this.refCount += 1
    if (this.refCount > 1) {
      return
    }
    this.ensureRuntimeSubscriptions()
    this.tryAcquireLeadership()
  }

  stop() {
    this.refCount = Math.max(0, this.refCount - 1)
    if (this.refCount > 0) {
      return
    }
    this.releaseLeadership()
    this.clearLeadershipRetry()
    this.teardownRuntimeSubscriptions()
    this.updateState({
      isConnected: false,
      isConnecting: false,
      error: null,
      cooldownSeconds: 0,
      mode: 'idle',
    })
  }

  reconnect() {
    if (this.state.mode === 'leader') {
      void this.transport.connect({ recovery: true })
      return
    }

    const lease = this.leaseStore.read()
    if (lease && lease.expiresAt > Date.now()) {
      this.bus.post({ type: 'reconnect-request', senderTabId: this.tabId })
      return
    }

    this.tryAcquireLeadership()
  }

  private ensureRuntimeSubscriptions() {
    if (!this.transportUnsubscribe) {
      this.transportUnsubscribe = this.transport.subscribe((event) => {
        this.handleTransportEvent(event)
      })
    }
    if (!this.busUnsubscribe) {
      this.busUnsubscribe = this.bus.subscribe((message) => {
        this.handleCrossTabMessage(message)
      })
    }
    if (!this.leaseUnsubscribe) {
      this.leaseUnsubscribe = this.leaseStore.subscribe((lease) => {
        this.handleLeaseChange(lease)
      })
    }
  }

  private teardownRuntimeSubscriptions() {
    if (this.transportUnsubscribe) {
      this.transportUnsubscribe()
      this.transportUnsubscribe = null
    }
    if (this.busUnsubscribe) {
      this.busUnsubscribe()
      this.busUnsubscribe = null
    }
    if (this.leaseUnsubscribe) {
      this.leaseUnsubscribe()
      this.leaseUnsubscribe = null
    }
  }

  private tryAcquireLeadership() {
    if (this.refCount === 0) return

    const now = Date.now()
    const lease = this.leaseStore.read()
    if (lease && lease.tabId !== this.tabId && lease.expiresAt > now) {
      this.followLeader(lease)
      return
    }

    const nextLease: DatabaseLeaderLease = {
      tabId: this.tabId,
      clientInstanceId: this.clientInstanceId,
      expiresAt: now + this.leadershipTtlMs,
    }
    this.leaseStore.write(nextLease)

    const confirmedLease = this.leaseStore.read()
    if (confirmedLease?.tabId === this.tabId) {
      this.becomeLeader()
      return
    }

    if (confirmedLease) {
      this.followLeader(confirmedLease)
    }
  }

  private becomeLeader() {
    this.clearLeadershipRetry()
    this.startHeartbeat()
    this.activeLeaderTabId = this.tabId
    this.updateState({
      mode: 'leader',
      error: null,
    })
    void this.transport.connect({ recovery: false })
  }

  private followLeader(lease: DatabaseLeaderLease) {
    if (this.state.mode === 'follower' && this.activeLeaderTabId === lease.tabId) {
      this.scheduleLeadershipRetry(lease.expiresAt)
      return
    }

    this.activeLeaderTabId = lease.tabId
    this.stopHeartbeat()
    this.transport.disconnect()
    this.updateState({
      ...this.state,
      mode: 'follower',
      isConnecting: false,
    })
    this.scheduleLeadershipRetry(lease.expiresAt)
    this.bus.post({ type: 'status-request', senderTabId: this.tabId })
  }

  private releaseLeadership() {
    const wasLeader = this.state.mode === 'leader'
    this.activeLeaderTabId = null
    this.stopHeartbeat()
    this.transport.disconnect()
    if (wasLeader) {
      this.leaseStore.clear(this.tabId)
      this.bus.post({ type: 'leader-released', senderTabId: this.tabId })
    }
  }

  private startHeartbeat() {
    if (this.heartbeatTimer) return
    this.heartbeatTimer = setInterval(() => {
      this.leaseStore.write({
        tabId: this.tabId,
        clientInstanceId: this.clientInstanceId,
        expiresAt: Date.now() + this.leadershipTtlMs,
      })
    }, this.heartbeatIntervalMs)
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleLeadershipRetry(expiresAt: number) {
    this.clearLeadershipRetry()
    const delay = Math.max(0, expiresAt - Date.now() + LEADERSHIP_RETRY_BUFFER_MS)
    this.leadershipRetryTimer = setTimeout(() => {
      this.leadershipRetryTimer = null
      this.tryAcquireLeadership()
    }, delay)
  }

  private clearLeadershipRetry() {
    if (this.leadershipRetryTimer) {
      clearTimeout(this.leadershipRetryTimer)
      this.leadershipRetryTimer = null
    }
  }

  private handleTransportEvent(event: DatabaseStreamTransportEvent) {
    if (this.state.mode !== 'leader') {
      return
    }

    if (event.type === 'state') {
      this.updateState({
        ...event.state,
        mode: 'leader',
      })
      this.broadcastState()
      return
    }

    void this.handleProjectedEvent(event.event, true)
  }

  private async handleProjectedEvent(event: DatabaseRealtimeEvent, broadcast: boolean) {
    if (this.queryClient) {
      await this.projector.project(this.queryClient, event)
    }
    for (const listener of this.eventListeners) {
      listener(event)
    }
    if (broadcast) {
      this.bus.post({
        type: 'event',
        senderTabId: this.tabId,
        event,
      })
    }
  }

  private handleCrossTabMessage(message: DatabaseCrossTabMessage) {
    if (message.senderTabId === this.tabId) {
      return
    }

    switch (message.type) {
      case 'state':
        if (this.state.mode === 'leader') return
        this.activeLeaderTabId = message.senderTabId
        this.updateState({
          ...message.state,
          mode: 'follower',
        })
        return
      case 'event':
        if (this.state.mode === 'leader') return
        void this.handleProjectedEvent(message.event, false)
        return
      case 'status-request':
        if (this.state.mode !== 'leader') return
        this.broadcastState()
        return
      case 'reconnect-request':
        if (this.state.mode !== 'leader') return
        void this.transport.connect({ recovery: true })
        return
      case 'leader-released':
        if (this.state.mode === 'leader') return
        this.activeLeaderTabId = null
        this.tryAcquireLeadership()
        return
    }
  }

  private handleLeaseChange(lease: DatabaseLeaderLease | null) {
    if (this.refCount === 0) {
      return
    }

    if (!lease) {
      if (this.state.mode !== 'leader') {
        this.tryAcquireLeadership()
      }
      return
    }

    if (lease.tabId === this.tabId) {
      this.activeLeaderTabId = this.tabId
      return
    }

    this.followLeader(lease)
  }

  private broadcastState() {
    this.bus.post({
      type: 'state',
      senderTabId: this.tabId,
      state: this.state,
    })
  }

  private updateState(nextState: Partial<DatabaseCoordinatorStateSnapshot>) {
    this.state = {
      ...this.state,
      ...nextState,
    }
    for (const listener of this.listeners) {
      listener(this.state)
    }
  }
}

export type {
  DatabaseCoordinatorStateSnapshot as DatabaseStreamState,
  DatabaseCrossTabBus,
  DatabaseCrossTabMessage,
  DatabaseLeaderLease,
  DatabaseLeaderLeaseStore,
  DatabaseRealtimeEvent,
  DatabaseStreamTransportEvent,
  DatabaseStreamTransportLike,
} from './databaseStreamTypes'
