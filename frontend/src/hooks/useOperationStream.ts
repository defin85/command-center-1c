import { useCallback, useEffect, useRef, useState } from 'react'
import { getStreamTicket } from '../api/operations'
import { buildStreamUrl, openSseStream } from '../api/sse'

export interface WorkflowEvent {
  version: string
  operation_id: string
  timestamp: string
  state: string
  microservice: string
  message: string
  metadata?: Record<string, unknown>
}

export interface UseOperationStreamResult {
  events: WorkflowEvent[]
  currentState: string
  error: string | null
  isConnected: boolean
}

const RECONNECT_INITIAL_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000

type StreamErrorPayload = {
  error?: string
}

const isWorkflowEvent = (data: unknown): data is WorkflowEvent => {
  if (typeof data !== 'object' || data === null) return false
  const record = data as Record<string, unknown>
  return typeof record.operation_id === 'string' && typeof record.state === 'string'
}

const getErrorMessage = (data: unknown): string | null => {
  if (typeof data !== 'object' || data === null) return null
  const record = data as StreamErrorPayload
  return typeof record.error === 'string' ? record.error : null
}

export const useOperationStream = (
  operationId: string | null
): UseOperationStreamResult => {
  const [events, setEvents] = useState<WorkflowEvent[]>([])
  const [currentState, setCurrentState] = useState<string>('PENDING')
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState<boolean>(false)

  const MAX_EVENTS = 1000
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

      const { stream_url } = await getStreamTicket(operationId)
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

            if (!isWorkflowEvent(data)) {
              return
            }

            setEvents((prev) => {
              const updated = [...prev, data]
              return updated.length > MAX_EVENTS
                ? updated.slice(-MAX_EVENTS)
                : updated
            })
            setCurrentState(data.state)
            setError(null)
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
            setError(`Stream busy. Retry in ~${Math.ceil(cooldownMs / 1000)}s`)
            if (streamCloseRef.current) {
              streamCloseRef.current()
              streamCloseRef.current = null
            }
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
          isConnectingRef.current = false
          scheduleReconnect()
        },
      })

      streamCloseRef.current = closeStream
    } catch (err) {
      const status = (err as { response?: { status?: number; headers?: Record<string, string> } })?.response?.status
      if (status === 429) {
        const retryAfterHeader = (err as { response?: { headers?: Record<string, string> } })?.response?.headers?.['retry-after']
        const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : NaN
        const cooldownMs = Number.isFinite(retryAfterSeconds) ? retryAfterSeconds * 1000 : 60_000
        cooldownUntilRef.current = Date.now() + cooldownMs
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

    // Reset state when operationId changes
    setEvents([])
    setCurrentState('PENDING')
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

    // Cleanup
    return () => {
      isActiveRef.current = false
      if (streamCloseRef.current) {
        streamCloseRef.current()
        streamCloseRef.current = null
      }
      lastEventIdRef.current = null
      cooldownUntilRef.current = 0
      isConnectingRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      setIsConnected(false)
    }
  }, [connect, operationId])

  return {
    events,
    currentState,
    error,
    isConnected,
  }
}
