import type { InvalidateQueryFilters, QueryClient } from '@tanstack/react-query'

export interface DatabaseRealtimeEvent {
  version?: string
  type?: string
  action?: string
  database_id?: string
  cluster_id?: string | null
  timestamp?: string
}

export interface DatabaseTransportState {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  cooldownSeconds: number
  sessionId: string | null
  leaseId: string | null
}

export type DatabaseStreamTransportEvent =
  | { type: 'state'; state: DatabaseTransportState }
  | { type: 'event'; event: DatabaseRealtimeEvent }

export interface DatabaseStreamTransportLike {
  subscribe: (listener: (event: DatabaseStreamTransportEvent) => void) => () => void
  connect: (options?: { recovery?: boolean }) => Promise<void>
  disconnect: () => void
}

export interface DatabaseLeaderLease {
  tabId: string
  clientInstanceId: string
  expiresAt: number
}

export interface DatabaseLeaderLeaseStore {
  read: () => DatabaseLeaderLease | null
  write: (lease: DatabaseLeaderLease) => void
  clear: (ownerTabId?: string) => void
  subscribe: (listener: (lease: DatabaseLeaderLease | null) => void) => () => void
}

export interface DatabaseCoordinatorStateSnapshot extends DatabaseTransportState {
  mode: 'idle' | 'leader' | 'follower'
}

export type DatabaseCrossTabMessage =
  | { type: 'state'; senderTabId: string; state: DatabaseCoordinatorStateSnapshot }
  | { type: 'event'; senderTabId: string; event: DatabaseRealtimeEvent }
  | { type: 'status-request'; senderTabId: string }
  | { type: 'reconnect-request'; senderTabId: string }
  | { type: 'leader-released'; senderTabId: string }

export interface DatabaseCrossTabBus {
  post: (message: DatabaseCrossTabMessage) => void
  subscribe: (listener: (message: DatabaseCrossTabMessage) => void) => () => void
  close: () => void
}

export interface DatabaseEventProjectionTarget {
  label: string
  filters: InvalidateQueryFilters
}

export interface DatabaseEventProjector {
  project: (queryClient: QueryClient, event: DatabaseRealtimeEvent) => Promise<void>
}
