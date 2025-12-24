import { buildDatabaseStreamUrl, getDatabaseStreamTicket } from '../api/databasesStream'
import { openSseStream } from '../api/sse'
import { queryKeys } from '../api/queries'
import type { QueryClient } from '@tanstack/react-query'

export interface DatabaseStreamState {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  cooldownSeconds: number
}

export interface DatabaseStreamEvent {
  version?: string
  type?: string
  action?: string
  database_id?: string
  cluster_id?: string | null
  timestamp?: string
}

type StateListener = (state: DatabaseStreamState) => void
type EventListener = (event: DatabaseStreamEvent) => void

const RECONNECT_INITIAL_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000
const INVALIDATION_DEBOUNCE_MS = 1000
const DISCONNECT_GRACE_MS = 250

class DatabaseStreamManager {
  private state: DatabaseStreamState = {
    isConnected: false,
    isConnecting: false,
    error: null,
    cooldownSeconds: 0,
  }
  private listeners = new Set<StateListener>()
  private eventListeners = new Set<EventListener>()
  private refCount = 0
  private stopTimer: ReturnType<typeof setTimeout> | null = null
  private streamClose: (() => void) | null = null
  private reconnectDelay = RECONNECT_INITIAL_DELAY
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private cooldownUntil = 0
  private cooldownTimer: ReturnType<typeof setInterval> | null = null
  private lastEventId: string | null = null
  private isStreaming = false
  private isConnecting = false
  private invalidateTimer: ReturnType<typeof setTimeout> | null = null
  private queryClient: QueryClient | null = null
  private forceAttempted = false

  start() {
    this.refCount += 1
    if (this.stopTimer) {
      clearTimeout(this.stopTimer)
      this.stopTimer = null
    }
    if (this.refCount === 1) {
      void this.connect()
    }
  }

  stop() {
    this.refCount = Math.max(0, this.refCount - 1)
    if (this.refCount === 0) {
      this.stopTimer = setTimeout(() => {
        if (this.refCount === 0) {
          this.disconnect()
        }
      }, DISCONNECT_GRACE_MS)
    }
  }

  setQueryClient(client: QueryClient | null) {
    this.queryClient = client
  }

  getState() {
    return this.state
  }

  subscribe(listener: StateListener) {
    this.listeners.add(listener)
    listener(this.state)
    return () => {
      this.listeners.delete(listener)
    }
  }

  subscribeEvent(listener: EventListener) {
    this.eventListeners.add(listener)
    return () => {
      this.eventListeners.delete(listener)
    }
  }

  reconnect() {
    if (this.cooldownUntil && Date.now() < this.cooldownUntil) {
      return
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.streamClose) {
      this.streamClose()
      this.streamClose = null
    }
    this.isStreaming = false
    this.isConnecting = false
    this.reconnectDelay = RECONNECT_INITIAL_DELAY
    this.cooldownUntil = 0
    this.updateCooldownSeconds(0)
    void this.connect()
  }

  private setState(partial: Partial<DatabaseStreamState>) {
    this.state = { ...this.state, ...partial }
    for (const listener of this.listeners) {
      listener(this.state)
    }
  }

  private scheduleInvalidation() {
    if (this.invalidateTimer || !this.queryClient) return
    this.invalidateTimer = setTimeout(() => {
      this.invalidateTimer = null
      this.queryClient?.invalidateQueries({ queryKey: queryKeys.databases.all })
    }, INVALIDATION_DEBOUNCE_MS)
  }

  private updateCooldownSeconds(seconds: number) {
    if (this.state.cooldownSeconds === seconds) return
    this.setState({ cooldownSeconds: seconds })
  }

  private startCooldownTimer() {
    if (this.cooldownTimer) return
    this.cooldownTimer = setInterval(() => {
      if (!this.cooldownUntil) {
        this.updateCooldownSeconds(0)
        this.stopCooldownTimer()
        return
      }
      const seconds = Math.max(0, Math.ceil((this.cooldownUntil - Date.now()) / 1000))
      this.updateCooldownSeconds(seconds)
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

  private scheduleReconnect() {
    if (this.reconnectTimer || this.refCount === 0) return
    const baseDelay = this.reconnectDelay
    const jitter = Math.floor(Math.random() * 250)
    const delay = Math.min(baseDelay + jitter, RECONNECT_MAX_DELAY)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_DELAY)
      void this.connect()
    }, delay)
  }

  private scheduleCooldownRetry() {
    if (!this.cooldownUntil) return
    const delay = Math.max(0, this.cooldownUntil - Date.now())
    if (delay <= 0) {
      void this.connect()
      return
    }
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      void this.connect()
    }, delay)
  }

  private handleStreamEvent(event: DatabaseStreamEvent) {
    for (const listener of this.eventListeners) {
      listener(event)
    }
    this.scheduleInvalidation()
  }

  private async connect() {
    if (this.refCount === 0) return
    if (this.isConnecting || this.isStreaming) return

    if (this.cooldownUntil && Date.now() < this.cooldownUntil) {
      this.startCooldownTimer()
      this.scheduleCooldownRetry()
      return
    }

    this.isConnecting = true
    this.setState({ isConnecting: true })

    try {
      if (this.streamClose) {
        this.streamClose()
        this.streamClose = null
      }

      const token = localStorage.getItem('auth_token')
      if (!token) {
        this.setState({ isConnected: false, error: 'Authentication required', isConnecting: false })
        this.isConnecting = false
        this.scheduleReconnect()
        return
      }

      const { stream_url } = await getDatabaseStreamTicket(null, true)
      this.forceAttempted = true
      const url = buildDatabaseStreamUrl(stream_url)
      const lastEventId = this.lastEventId
      this.isStreaming = true

      const closeStream = openSseStream(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}),
        },
        connectTimeoutMs: 10000,
        onOpen: () => {
          this.setState({ isConnected: true, error: null, isConnecting: false })
          this.isConnecting = false
          this.reconnectDelay = RECONNECT_INITIAL_DELAY
          this.scheduleInvalidation()
        },
        onMessage: (message) => {
          try {
            if (message.id) {
              this.lastEventId = message.id
            }
            const data = JSON.parse(message.data) as DatabaseStreamEvent
            this.handleStreamEvent(data)
          } catch {
            // ignore malformed events
          }
        },
        onError: (err) => {
          const status = (err as { status?: number } | undefined)?.status
          if (status === 429) {
            const cooldownMs = 60_000
            this.cooldownUntil = Date.now() + cooldownMs
            this.startCooldownTimer()
            this.setState({
              error: 'Database stream already active for this user',
              isConnected: false,
              isConnecting: false,
            })
            this.isConnecting = false
            this.isStreaming = false
            if (this.streamClose) {
              this.streamClose()
              this.streamClose = null
            }
            this.scheduleCooldownRetry()
            return
          }
          this.setState({ isConnected: false, error: 'Connection lost. Reconnecting...', isConnecting: false })
          this.isConnecting = false
          this.isStreaming = false
          if (this.streamClose) {
            this.streamClose()
            this.streamClose = null
          }
          this.scheduleReconnect()
        },
      })

      this.streamClose = closeStream
    } catch (err) {
      const status = (err as { response?: { status?: number; headers?: Record<string, string> } })?.response?.status
      if (status === 429) {
        if (!this.forceAttempted) {
          this.forceAttempted = true
          try {
            const { stream_url } = await getDatabaseStreamTicket(null, true)
            const url = buildDatabaseStreamUrl(stream_url)
            const lastEventId = this.lastEventId
            this.isStreaming = true
            const closeStream = openSseStream(url, {
              headers: {
                Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}`,
                ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}),
              },
              connectTimeoutMs: 10000,
              onOpen: () => {
                this.forceAttempted = false
                this.setState({ isConnected: true, error: null, isConnecting: false })
                this.isConnecting = false
                this.reconnectDelay = RECONNECT_INITIAL_DELAY
                this.scheduleInvalidation()
              },
              onMessage: (message) => {
                try {
                  if (message.id) {
                    this.lastEventId = message.id
                  }
                  const data = JSON.parse(message.data) as DatabaseStreamEvent
                  this.handleStreamEvent(data)
                } catch {
                  // ignore malformed events
                }
              },
              onError: (innerErr) => {
                this.forceAttempted = false
                const innerStatus = (innerErr as { status?: number } | undefined)?.status
                if (innerStatus === 429) {
                  const cooldownMs = 60_000
                  this.cooldownUntil = Date.now() + cooldownMs
                  this.startCooldownTimer()
                  this.setState({
                    error: 'Database stream already active for this user',
                    isConnected: false,
                    isConnecting: false,
                  })
                  this.isConnecting = false
                  this.isStreaming = false
                  if (this.streamClose) {
                    this.streamClose()
                    this.streamClose = null
                  }
                  this.scheduleCooldownRetry()
                  return
                }
                this.setState({ isConnected: false, error: 'Connection lost. Reconnecting...', isConnecting: false })
                this.isConnecting = false
                this.isStreaming = false
                if (this.streamClose) {
                  this.streamClose()
                  this.streamClose = null
                }
                this.scheduleReconnect()
              },
            })
            this.streamClose = closeStream
            return
          } catch {
            this.forceAttempted = false
          }
        }
        const retryAfterHeader = (err as { response?: { headers?: Record<string, string> } })?.response?.headers?.['retry-after']
        const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : NaN
        const cooldownMs = Number.isFinite(retryAfterSeconds) ? retryAfterSeconds * 1000 : 60_000
        this.cooldownUntil = Date.now() + cooldownMs
        this.startCooldownTimer()
        this.setState({
          error: 'Database stream already active for this user',
          isConnected: false,
          isConnecting: false,
        })
        this.isConnecting = false
        this.isStreaming = false
        this.scheduleCooldownRetry()
        return
      }
      this.setState({ isConnected: false, error: 'Failed to connect to database stream', isConnecting: false })
      this.isConnecting = false
      this.isStreaming = false
      this.scheduleReconnect()
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.streamClose) {
      this.streamClose()
      this.streamClose = null
    }
    this.isConnecting = false
    this.isStreaming = false
    this.lastEventId = null
    this.forceAttempted = false
    this.cooldownUntil = 0
    this.stopCooldownTimer()
    this.updateCooldownSeconds(0)
    this.setState({ isConnected: false, isConnecting: false })
  }
}

export const databaseStreamManager = new DatabaseStreamManager()
