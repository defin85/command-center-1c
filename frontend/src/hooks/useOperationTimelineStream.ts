import { useCallback, useEffect, useRef, useState } from 'react'
import { getStreamTicket } from '../api/operations'
import { buildStreamUrl, openSseStream } from '../api/sse'

export interface TimelineStreamEvent {
  operation_id: string
  timestamp: number
  event: string
  service: string
  metadata?: Record<string, unknown>
  trace_id?: string
  workflow_execution_id?: string
  node_id?: string
}

export interface UseOperationTimelineStreamResult {
  lastEvent: TimelineStreamEvent | null
  error: string | null
  isConnected: boolean
}

const RECONNECT_INITIAL_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000
const STREAM_ACTIVE_TTL_MS = 130_000

const getClientId = (): string => {
  const key = 'cc1c_stream_client_id'
  const existing = sessionStorage.getItem(key)
  if (existing) return existing
  const generated =
    (globalThis.crypto && 'randomUUID' in globalThis.crypto)
      ? globalThis.crypto.randomUUID()
      : `client-${Math.random().toString(36).slice(2)}`
  sessionStorage.setItem(key, generated)
  return generated
}

type StreamRegistryEntry = {
  client_id: string
  expires_at: number
}

const readStreamRegistry = (): Record<string, StreamRegistryEntry> => {
  const raw = localStorage.getItem('cc1c_stream_registry')
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw) as Record<string, StreamRegistryEntry>
    const now = Date.now()
    let changed = false
    for (const [key, value] of Object.entries(parsed)) {
      if (!value || typeof value.expires_at !== 'number' || value.expires_at <= now) {
        delete parsed[key]
        changed = true
      }
    }
    if (changed) {
      localStorage.setItem('cc1c_stream_registry', JSON.stringify(parsed))
    }
    return parsed
  } catch {
    return {}
  }
}

const writeStreamRegistry = (registry: Record<string, StreamRegistryEntry>) => {
  localStorage.setItem('cc1c_stream_registry', JSON.stringify(registry))
}

const markStreamActive = (operationId: string) => {
  const registry = readStreamRegistry()
  registry[operationId] = {
    client_id: getClientId(),
    expires_at: Date.now() + STREAM_ACTIVE_TTL_MS,
  }
  writeStreamRegistry(registry)
}

const refreshStreamActive = (operationId: string) => {
  const registry = readStreamRegistry()
  const entry = registry[operationId]
  if (!entry || entry.client_id !== getClientId()) return
  entry.expires_at = Date.now() + STREAM_ACTIVE_TTL_MS
  writeStreamRegistry(registry)
}

const clearStreamActive = (operationId: string) => {
  const registry = readStreamRegistry()
  const entry = registry[operationId]
  if (!entry || entry.client_id !== getClientId()) return
  delete registry[operationId]
  writeStreamRegistry(registry)
}

const isStreamActiveElsewhere = (operationId: string): boolean => {
  const registry = readStreamRegistry()
  const entry = registry[operationId]
  return Boolean(entry && entry.client_id !== getClientId() && entry.expires_at > Date.now())
}

let globalCooldownUntil = 0

const applyGlobalCooldown = (cooldownMs: number) => {
  if (cooldownMs <= 0) return
  const next = Date.now() + cooldownMs
  if (next > globalCooldownUntil) {
    globalCooldownUntil = next
  }
}

const getGlobalCooldownRemaining = () =>
  Math.max(0, globalCooldownUntil - Date.now())

type StreamErrorPayload = {
  error?: string
}

const isTimelineEvent = (data: unknown): data is TimelineStreamEvent => {
  if (typeof data !== 'object' || data === null) return false
  const record = data as Record<string, unknown>
  return (
    typeof record.operation_id === 'string' &&
    typeof record.event === 'string' &&
    typeof record.service === 'string'
  )
}

const getErrorMessage = (data: unknown): string | null => {
  if (typeof data !== 'object' || data === null) return null
  const record = data as StreamErrorPayload
  return typeof record.error === 'string' ? record.error : null
}

export const useOperationTimelineStream = (
  operationId: string | null
): UseOperationTimelineStreamResult => {
  const [lastEvent, setLastEvent] = useState<TimelineStreamEvent | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState<boolean>(false)

  const streamCloseRef = useRef<(() => void) | null>(null)
  const reconnectDelayRef = useRef(RECONNECT_INITIAL_DELAY)
  const lastEventIdRef = useRef<string | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cooldownUntilRef = useRef<number>(0)
  const isActiveRef = useRef(false)
  const isConnectingRef = useRef(false)
  const connectRef = useRef<() => void>(() => {})

  const scheduleReconnect = useCallback(() => {
    if (!isActiveRef.current || reconnectTimeoutRef.current) {
      return
    }

    const baseDelay = reconnectDelayRef.current
    const jitter = Math.floor(Math.random() * 250)
    const delay = Math.min(baseDelay + jitter, RECONNECT_MAX_DELAY)
    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectTimeoutRef.current = null
      reconnectDelayRef.current = Math.min(
        reconnectDelayRef.current * 2,
        RECONNECT_MAX_DELAY
      )
      connectRef.current()
    }, delay)
  }, [])

  const connect = useCallback(async () => {
    if (!operationId || !isActiveRef.current) {
      return
    }
    if (isConnectingRef.current) {
      return
    }
    const now = Date.now()
    const globalRemaining = getGlobalCooldownRemaining()
    if (globalRemaining > 0) {
      cooldownUntilRef.current = Math.max(
        cooldownUntilRef.current,
        now + globalRemaining
      )
    }
    if (now < cooldownUntilRef.current) {
      const remaining = cooldownUntilRef.current - now
      if (!reconnectTimeoutRef.current) {
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null
          connectRef.current()
        }, remaining)
      }
      return
    }
    isConnectingRef.current = true

    try {
      if (streamCloseRef.current) {
        streamCloseRef.current()
        streamCloseRef.current = null
      }

      const token = localStorage.getItem('auth_token')
      if (!token) {
        setIsConnected(false)
        setError('Authentication required')
        scheduleReconnect()
        return
      }

      if (isStreamActiveElsewhere(operationId)) {
        setIsConnected(false)
        setError('Stream already active in another tab')
        isConnectingRef.current = false
        return
      }

      const { stream_url } = await getStreamTicket(operationId, getClientId())
      const url = buildStreamUrl(stream_url)
      const lastEventId = lastEventIdRef.current
      const closeStream = openSseStream(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}),
        },
        connectTimeoutMs: 10000,
        onOpen: () => {
          setIsConnected(true)
          setError(null)
          reconnectDelayRef.current = RECONNECT_INITIAL_DELAY
          markStreamActive(operationId)
          isConnectingRef.current = false
        },
        onMessage: (message) => {
          try {
            if (message.id) {
              lastEventIdRef.current = message.id
            }
            const data: unknown = JSON.parse(message.data)

            const streamError = getErrorMessage(data)
            if (streamError) {
              setError(streamError)
              return
            }

            if (!isTimelineEvent(data)) {
              return
            }

            setLastEvent(data)
            setError(null)
            refreshStreamActive(operationId)
          } catch (err) {
            console.error('Failed to parse SSE event:', err)
            setError('Failed to parse event data')
          }
        },
        onError: (err) => {
          const errorStatus = (err as { status?: number } | undefined)?.status
          if (errorStatus === 429) {
            const cooldownMs = 60_000
            cooldownUntilRef.current = Date.now() + cooldownMs
            applyGlobalCooldown(cooldownMs)
            setError(`Stream busy. Retry in ~${Math.ceil(cooldownMs / 1000)}s`)
            if (streamCloseRef.current) {
              streamCloseRef.current()
              streamCloseRef.current = null
            }
            clearStreamActive(operationId)
            isConnectingRef.current = false
            scheduleReconnect()
            return
          }
          setIsConnected(false)
          setError('Connection lost. Reconnecting\u2026')
          if (streamCloseRef.current) {
            streamCloseRef.current()
            streamCloseRef.current = null
          }
          clearStreamActive(operationId)
          isConnectingRef.current = false
          scheduleReconnect()
        },
      })

      streamCloseRef.current = closeStream
    } catch (err) {
      const response = (err as { response?: { status?: number; headers?: Record<string, string>; data?: { error?: { code?: string; retry_after?: number } } } })?.response
      const status = response?.status
      if (status === 429) {
        const errorCode = response?.data?.error?.code
        const retryAfterHeader = response?.headers?.['retry-after']
        const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : NaN
        const retryAfterFromBody = response?.data?.error?.retry_after
        const retryAfterBodySeconds =
          typeof retryAfterFromBody === 'number' ? retryAfterFromBody : NaN
        const cooldownMs = Number.isFinite(retryAfterSeconds)
          ? retryAfterSeconds * 1000
          : Number.isFinite(retryAfterBodySeconds)
            ? retryAfterBodySeconds * 1000
            : 60_000
        cooldownUntilRef.current = Date.now() + cooldownMs
        applyGlobalCooldown(cooldownMs)
        if (errorCode === 'STREAM_ALREADY_ACTIVE') {
          setError('Stream already active in another tab')
          isConnectingRef.current = false
          return
        }
        setError(`Stream busy. Retry in ~${Math.ceil(cooldownMs / 1000)}s`)
        isConnectingRef.current = false
        scheduleReconnect()
        return
      }
      setIsConnected(false)
      setError('Failed to connect to operation stream')
      isConnectingRef.current = false
      scheduleReconnect()
    }
  }, [operationId, scheduleReconnect])

  useEffect(() => {
    connectRef.current = () => {
      void connect()
    }
  }, [connect])

  useEffect(() => {
    isActiveRef.current = true

    setLastEvent(null)
    setError(null)
    reconnectDelayRef.current = RECONNECT_INITIAL_DELAY
    lastEventIdRef.current = null
    cooldownUntilRef.current = 0

    if (!operationId) {
      setIsConnected(false)
      return () => {
        isActiveRef.current = false
      }
    }

    void connect()

    return () => {
      isActiveRef.current = false
      if (streamCloseRef.current) {
        streamCloseRef.current()
        streamCloseRef.current = null
      }
      if (operationId) {
        clearStreamActive(operationId)
      }
      lastEventIdRef.current = null
      cooldownUntilRef.current = 0
      isConnectingRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [connect, operationId])

  return { lastEvent, error, isConnected }
}
