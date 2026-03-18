import { buildDatabaseStreamUrl, getDatabaseStreamTicket } from '../../api/databasesStream'
import type { DatabaseStreamConflictResponse } from '../../api/generated'
import { openSseStream } from '../../api/sse'
import type {
  DatabaseRealtimeEvent,
  DatabaseStreamTransportEvent,
  DatabaseStreamTransportLike,
  DatabaseTransportState,
} from './databaseStreamTypes'

const CONNECT_TIMEOUT_MS = 10_000
const DEFAULT_COOLDOWN_SECONDS = 60

type DatabaseStreamConflictError = {
  response?: {
    status?: number
    headers?: Record<string, string>
    data?: unknown
  }
  status?: number
}

const isDatabaseStreamConflictResponse = (data: unknown): data is DatabaseStreamConflictResponse => {
  if (!data || typeof data !== 'object') {
    return false
  }
  const error = (data as { error?: unknown }).error
  if (!error || typeof error !== 'object') {
    return false
  }
  const details = (error as { details?: unknown }).details
  return Boolean(
    details &&
      typeof details === 'object' &&
      typeof (details as { retry_after?: unknown }).retry_after === 'number'
  )
}

type DatabaseStreamTransportOptions = {
  clientInstanceId: string
  clusterId?: string | null
  getToken?: () => string | null
}

export class DatabaseStreamTransport implements DatabaseStreamTransportLike {
  private state: DatabaseTransportState = {
    isConnected: false,
    isConnecting: false,
    error: null,
    cooldownSeconds: 0,
    sessionId: null,
    leaseId: null,
  }
  private listeners = new Set<(event: DatabaseStreamTransportEvent) => void>()
  private streamClose: (() => void) | null = null
  private cooldownUntil = 0
  private cooldownTimer: ReturnType<typeof setInterval> | null = null
  private lastEventId: string | null = null
  private readonly clientInstanceId: string
  private readonly clusterId: string | null
  private readonly getToken: () => string | null

  constructor(options: DatabaseStreamTransportOptions) {
    this.clientInstanceId = options.clientInstanceId
    this.clusterId = options.clusterId ?? null
    this.getToken = options.getToken ?? (() => localStorage.getItem('auth_token'))
  }

  subscribe(listener: (event: DatabaseStreamTransportEvent) => void) {
    this.listeners.add(listener)
    listener({ type: 'state', state: this.state })
    return () => {
      this.listeners.delete(listener)
    }
  }

  async connect(options?: { recovery?: boolean }) {
    if (this.state.isConnecting) {
      return
    }

    const token = this.getToken()
    if (!token) {
      this.updateState({
        isConnected: false,
        isConnecting: false,
        error: 'Authentication required',
      })
      return
    }

    this.closeStream()
    this.updateState({
      isConnected: false,
      isConnecting: true,
      error: null,
    })

    try {
      const ticket = await getDatabaseStreamTicket({
        clusterId: this.clusterId,
        clientInstanceId: this.clientInstanceId,
        sessionId: options?.recovery ? this.state.sessionId : undefined,
        recovery: Boolean(options?.recovery && this.state.sessionId),
      })

      this.updateState({
        sessionId: ticket.session_id,
        leaseId: ticket.lease_id,
      })

      this.streamClose = openSseStream(buildDatabaseStreamUrl(ticket.stream_url), {
        headers: {
          Authorization: `Bearer ${token}`,
          ...(this.lastEventId ? { 'Last-Event-ID': this.lastEventId } : {}),
        },
        connectTimeoutMs: CONNECT_TIMEOUT_MS,
        onOpen: () => {
          this.stopCooldownTimer()
          this.cooldownUntil = 0
          this.updateState({
            isConnected: true,
            isConnecting: false,
            error: null,
            cooldownSeconds: 0,
          })
        },
        onMessage: (message) => {
          if (message.id) {
            this.lastEventId = message.id
          }
          try {
            const event = JSON.parse(message.data) as DatabaseRealtimeEvent
            this.emit({ type: 'event', event })
          } catch {
            // ignore malformed events
          }
        },
        onError: (error) => {
          this.closeStream()
          this.handleTransportError(error)
        },
      })
    } catch (error) {
      this.handleTransportError(error)
    }
  }

  disconnect() {
    this.closeStream()
    this.stopCooldownTimer()
    this.cooldownUntil = 0
    this.updateState({
      isConnected: false,
      isConnecting: false,
      error: null,
      cooldownSeconds: 0,
    })
  }

  private handleTransportError(error: unknown) {
    const response = error as DatabaseStreamConflictError
    const status = response.response?.status ?? response.status
    if (status === 429) {
      const conflict = isDatabaseStreamConflictResponse(response.response?.data)
        ? response.response?.data
        : null
      const retryAfterHeader = Number(response.response?.headers?.['retry-after'])
      const retryAfterDetails = typeof conflict?.error.details.retry_after === 'number'
        ? conflict.error.details.retry_after
        : null
      const retryAfterSeconds: number = (
        Number.isFinite(retryAfterHeader) && retryAfterHeader > 0
          ? retryAfterHeader
          : retryAfterDetails !== null && retryAfterDetails > 0
            ? retryAfterDetails
            : DEFAULT_COOLDOWN_SECONDS
      )
      this.cooldownUntil = Date.now() + retryAfterSeconds * 1000
      this.startCooldownTimer()
      this.updateState({
        isConnected: false,
        isConnecting: false,
        error: conflict?.error.message ?? 'Database stream lease already active for this client session',
        cooldownSeconds: retryAfterSeconds,
      })
      return
    }

    this.updateState({
      isConnected: false,
      isConnecting: false,
      error: 'Connection lost. Reconnecting…',
    })
  }

  private startCooldownTimer() {
    if (this.cooldownTimer) return
    this.cooldownTimer = setInterval(() => {
      if (!this.cooldownUntil) {
        this.stopCooldownTimer()
        return
      }
      const seconds = Math.max(0, Math.ceil((this.cooldownUntil - Date.now()) / 1000))
      this.updateState({ cooldownSeconds: seconds })
      if (seconds <= 0) {
        this.cooldownUntil = 0
        this.stopCooldownTimer()
      }
    }, 1000)
  }

  private stopCooldownTimer() {
    if (this.cooldownTimer) {
      clearInterval(this.cooldownTimer)
      this.cooldownTimer = null
    }
  }

  private closeStream() {
    if (this.streamClose) {
      this.streamClose()
      this.streamClose = null
    }
  }

  private updateState(partial: Partial<DatabaseTransportState>) {
    this.state = {
      ...this.state,
      ...partial,
    }
    this.emit({ type: 'state', state: this.state })
  }

  private emit(event: DatabaseStreamTransportEvent) {
    for (const listener of this.listeners) {
      listener(event)
    }
  }
}
